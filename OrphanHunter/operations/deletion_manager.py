"""File and directory deletion management."""
import shutil
from pathlib import Path
from typing import Set, List, Dict, Optional
from OrphanHunter.scanner.file_scanner import FileScanner

class DeletionManager:
    """Manages safe file and directory deletion."""
    
    def __init__(self, file_scanner: FileScanner, root_dir: Path):
        self.file_scanner = file_scanner
        self.root_dir = Path(root_dir).resolve()
        self.deletion_queue: Set[str] = set()
        self.deleted_files: List[str] = []
        self.deletion_log: List[Dict] = []
    
    def add_to_queue(self, file_key: str):
        """Add a file to the deletion queue."""
        if file_key in self.file_scanner.files:
            self.deletion_queue.add(file_key)
    
    def remove_from_queue(self, file_key: str):
        """Remove a file from the deletion queue."""
        self.deletion_queue.discard(file_key)
    
    def clear_queue(self):
        """Clear the deletion queue."""
        self.deletion_queue.clear()
    
    def get_queue_size(self) -> int:
        """Get the number of files in the deletion queue."""
        return len(self.deletion_queue)
    
    def validate_deletion_queue(self) -> Dict:
        """Validate files in deletion queue."""
        issues = {
            'critical_files': [],
            'missing_files': [],
            'protected_files': [],
            'valid': True
        }
        
        for file_key in self.deletion_queue:
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            
            if not file_info:
                issues['missing_files'].append(file_key)
                issues['valid'] = False
                continue
            
            # Check if critical
            if file_info.is_critical:
                issues['critical_files'].append(file_key)
                issues['valid'] = False
            
            # Check if file still exists
            if not file_info.path.exists():
                issues['missing_files'].append(file_key)
                issues['valid'] = False
        
        return issues
    
    def delete_file(self, file_key: str, dry_run: bool = False) -> bool:
        """Delete a single file."""
        file_info = self.file_scanner.get_file_by_relative_path(file_key)
        
        if not file_info:
            print(f"File not found: {file_key}")
            return False
        
        if not file_info.path.exists():
            print(f"File does not exist: {file_info.path}")
            return False
        
        if dry_run:
            print(f"[DRY RUN] Would delete: {file_info.path}")
            return True
        
        try:
            file_info.path.unlink()
            self.deleted_files.append(file_key)
            self.deletion_log.append({
                'file': file_key,
                'path': str(file_info.path),
                'success': True,
                'error': None
            })
            return True
        except Exception as e:
            print(f"Error deleting {file_info.path}: {e}")
            self.deletion_log.append({
                'file': file_key,
                'path': str(file_info.path),
                'success': False,
                'error': str(e)
            })
            return False
    
    def delete_directory(self, dir_path: Path, dry_run: bool = False) -> bool:
        """Delete an entire directory."""
        if not dir_path.exists():
            print(f"Directory does not exist: {dir_path}")
            return False
        
        if not dir_path.is_dir():
            print(f"Not a directory: {dir_path}")
            return False
        
        if dry_run:
            print(f"[DRY RUN] Would delete directory: {dir_path}")
            return True
        
        try:
            shutil.rmtree(dir_path)
            self.deletion_log.append({
                'directory': str(dir_path),
                'success': True,
                'error': None
            })
            return True
        except Exception as e:
            print(f"Error deleting directory {dir_path}: {e}")
            self.deletion_log.append({
                'directory': str(dir_path),
                'success': False,
                'error': str(e)
            })
            return False
    
    def execute_deletions(self, dry_run: bool = False) -> Dict:
        """Execute all deletions in the queue."""
        result = {
            'attempted': len(self.deletion_queue),
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        for file_key in list(self.deletion_queue):
            if self.delete_file(file_key, dry_run):
                result['successful'] += 1
            else:
                result['failed'] += 1
                result['errors'].append(file_key)
        
        if not dry_run:
            self.deletion_queue.clear()
        
        return result
    
    def cleanup_empty_directories(self, dry_run: bool = False) -> int:
        """Remove empty directories after deletion."""
        removed_count = 0
        
        # Walk from bottom up to catch nested empty directories
        for dir_path in sorted(self.root_dir.rglob('*'), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                if dry_run:
                    print(f"[DRY RUN] Would remove empty directory: {dir_path}")
                else:
                    try:
                        dir_path.rmdir()
                        removed_count += 1
                    except Exception as e:
                        print(f"Error removing directory {dir_path}: {e}")
        
        return removed_count
    
    def get_deletion_summary(self) -> Dict:
        """Get summary of deletion operations."""
        return {
            'total_deleted': len(self.deleted_files),
            'in_queue': len(self.deletion_queue),
            'log_entries': len(self.deletion_log),
            'deleted_files': self.deleted_files.copy(),
            'recent_log': self.deletion_log[-10:] if self.deletion_log else []
        }

