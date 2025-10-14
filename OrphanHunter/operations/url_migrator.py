"""URL migration and replacement operations."""
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import chardet
import shutil


@dataclass
class ChangeRecord:
    """Record of a single URL replacement."""
    file_path: Path
    line_number: int
    old_url: str
    new_url: str
    old_line: str
    new_line: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    applied: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "old_url": self.old_url,
            "new_url": self.new_url,
            "old_line": self.old_line,
            "new_line": self.new_line,
            "timestamp": self.timestamp,
            "applied": self.applied
        }


class URLMigrator:
    """Handles URL replacement operations with tracking."""
    
    def __init__(self, root_dir: Path, replacement_format: str = "auto", 
                 custom_format: str = ""):
        self.root_dir = Path(root_dir).resolve()
        self.replacement_format = replacement_format
        self.custom_format = custom_format
        self.change_records: List[ChangeRecord] = []
        self.files_modified: Set[Path] = set()
        
        # Format templates
        self.format_templates = {
            "base_url": "BASE_URL . '{path}'",
            "safe_url": "safe_url('{path}')",
            "asset_url": "asset_url('{path}')",
            "api_url": "api_url('{path}')",
            "site_url": "SITE_URL . '{path}'",
        }
    
    def generate_replacement(self, url: str, url_path: str, query: str = "", 
                           fragment: str = "", detected_format: str = None) -> str:
        """Generate the replacement string for a URL."""
        # Reconstruct the full path with query and fragment
        full_path = url_path
        if query:
            full_path += f"?{query}"
        if fragment:
            full_path += f"#{fragment}"
        
        # Determine which format to use
        format_to_use = self.replacement_format
        
        if format_to_use == "auto" and detected_format:
            format_to_use = detected_format
        elif format_to_use == "auto":
            # Default to BASE_URL if auto and nothing detected
            format_to_use = "base_url"
        
        # Handle custom format
        if format_to_use == "custom" and self.custom_format:
            template = self.custom_format
        else:
            template = self.format_templates.get(format_to_use, self.format_templates["base_url"])
        
        # Replace the path placeholder
        replacement = template.replace("{path}", full_path)
        
        return replacement
    
    def plan_replacements(self, url_instances: list, detected_helpers: list = None) -> List[ChangeRecord]:
        """Plan all replacements without applying them."""
        self.change_records.clear()
        
        # Detect which format to use if auto
        auto_format = None
        if self.replacement_format == "auto" and detected_helpers:
            # Prioritize function helpers over constants
            for helper in detected_helpers:
                if "safe_url" in helper.name:
                    auto_format = "safe_url"
                    break
                elif "asset_url" in helper.name:
                    auto_format = "asset_url"
                    break
                elif "BASE_URL" in helper.name:
                    auto_format = "base_url"
                    break
        
        for instance in url_instances:
            if not instance.is_internal or instance.is_whitelisted:
                continue
            
            # Generate replacement
            replacement = self.generate_replacement(
                instance.url,
                instance.path,
                instance.query_string,
                instance.fragment,
                auto_format
            )
            
            # Create new line with replacement
            new_line = instance.line_content.replace(instance.url, replacement)
            
            record = ChangeRecord(
                file_path=instance.file_path,
                line_number=instance.line_number,
                old_url=instance.url,
                new_url=replacement,
                old_line=instance.line_content,
                new_line=new_line,
                applied=False
            )
            
            self.change_records.append(record)
        
        return self.change_records
    
    def apply_changes(self, selected_records: List[ChangeRecord] = None, 
                     progress_callback=None) -> Dict[str, any]:
        """Apply URL replacements to files."""
        records_to_apply = selected_records if selected_records else self.change_records
        
        # Group by file
        changes_by_file = {}
        for record in records_to_apply:
            file_path = self.root_dir / record.file_path
            if file_path not in changes_by_file:
                changes_by_file[file_path] = []
            changes_by_file[file_path].append(record)
        
        results = {
            "success": True,
            "files_modified": 0,
            "changes_applied": 0,
            "errors": []
        }
        
        total_files = len(changes_by_file)
        processed = 0
        
        for file_path, records in changes_by_file.items():
            try:
                # Read file
                content = self._read_file_safe(file_path)
                if not content:
                    results["errors"].append(f"Could not read {file_path}")
                    continue
                
                lines = content.split('\n')
                
                # Sort records by line number (descending) to avoid line number shifts
                records.sort(key=lambda r: r.line_number, reverse=True)
                
                # Apply changes
                for record in records:
                    line_idx = record.line_number - 1
                    if 0 <= line_idx < len(lines):
                        # Verify the line still matches
                        if record.old_url in lines[line_idx]:
                            lines[line_idx] = lines[line_idx].replace(record.old_url, record.new_url)
                            record.applied = True
                            results["changes_applied"] += 1
                        else:
                            results["errors"].append(
                                f"Line mismatch in {file_path}:{record.line_number} - file may have changed"
                            )
                
                # Write file back
                new_content = '\n'.join(lines)
                self._write_file_safe(file_path, new_content)
                
                self.files_modified.add(file_path)
                results["files_modified"] += 1
                
            except Exception as e:
                results["success"] = False
                results["errors"].append(f"Error processing {file_path}: {e}")
            
            # Progress callback
            processed += 1
            if progress_callback:
                progress_callback(processed, total_files)
        
        return results
    
    def verify_changes(self, root_dir: Path) -> Dict[str, any]:
        """Verify that changes were applied correctly."""
        verification = {
            "verified": True,
            "total_records": len(self.change_records),
            "applied_count": 0,
            "failed_count": 0,
            "failures": []
        }
        
        for record in self.change_records:
            if record.applied:
                verification["applied_count"] += 1
                
                # Check if the new URL is actually in the file
                file_path = root_dir / record.file_path
                try:
                    content = self._read_file_safe(file_path)
                    lines = content.split('\n')
                    
                    if record.line_number <= len(lines):
                        line = lines[record.line_number - 1]
                        if record.new_url not in line:
                            verification["verified"] = False
                            verification["failed_count"] += 1
                            verification["failures"].append({
                                "file": str(record.file_path),
                                "line": record.line_number,
                                "expected": record.new_url,
                                "reason": "Replacement not found in file"
                            })
                except Exception as e:
                    verification["verified"] = False
                    verification["failed_count"] += 1
                    verification["failures"].append({
                        "file": str(record.file_path),
                        "line": record.line_number,
                        "reason": f"Error reading file: {e}"
                    })
        
        return verification
    
    def get_changes_by_file(self) -> Dict[Path, List[ChangeRecord]]:
        """Group change records by file."""
        by_file = {}
        for record in self.change_records:
            if record.file_path not in by_file:
                by_file[record.file_path] = []
            by_file[record.file_path].append(record)
        return by_file
    
    def get_changes_for_files(self, file_paths: List[Path]) -> List[ChangeRecord]:
        """Get change records for specific files."""
        return [r for r in self.change_records if r.file_path in file_paths]
    
    def generate_report(self) -> str:
        """Generate a detailed migration report."""
        report_lines = [
            "=" * 80,
            "URL MIGRATION REPORT",
            "=" * 80,
            f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Root Directory: {self.root_dir}",
            f"Replacement Format: {self.replacement_format}",
            "",
            f"Total Changes: {len(self.change_records)}",
            f"Applied Changes: {sum(1 for r in self.change_records if r.applied)}",
            f"Files Modified: {len(self.files_modified)}",
            "",
            "=" * 80,
            "CHANGES BY FILE",
            "=" * 80,
        ]
        
        changes_by_file = self.get_changes_by_file()
        for file_path, records in sorted(changes_by_file.items()):
            report_lines.append(f"\n{file_path}")
            report_lines.append("-" * 80)
            for record in sorted(records, key=lambda r: r.line_number):
                status = "APPLIED" if record.applied else "PENDING"
                report_lines.append(f"  Line {record.line_number} [{status}]")
                report_lines.append(f"    OLD: {record.old_url}")
                report_lines.append(f"    NEW: {record.new_url}")
        
        return "\n".join(report_lines)
    
    def save_report(self, output_path: Path):
        """Save migration report to file."""
        report = self.generate_report()
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
        except Exception as e:
            print(f"Error saving report: {e}")
    
    def _read_file_safe(self, file_path: Path) -> str:
        """Safely read file with encoding detection."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return ""
    
    def _write_file_safe(self, file_path: Path, content: str):
        """Safely write file preserving original encoding when possible."""
        try:
            # Detect original encoding
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            # Write with detected encoding
            with open(file_path, 'w', encoding=encoding, errors='ignore') as f:
                f.write(content)
        except Exception as e:
            # Fallback to UTF-8
            try:
                with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(content)
            except Exception as e2:
                print(f"Error writing {file_path}: {e2}")
                raise

