"""Reference tracker for detailed line-by-line reference analysis."""
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
import chardet

class FileReference:
    """Represents a single reference to a file."""
    
    def __init__(self, source_file: str, target_file: str, line_number: int, 
                 line_content: str, reference_type: str):
        self.source_file = source_file
        self.target_file = target_file
        self.line_number = line_number
        self.line_content = line_content.strip()
        self.reference_type = reference_type  # 'include', 'href', 'import', 'src', etc.
    
    def get_snippet(self, max_length: int = 120) -> str:
        """Get code snippet, truncated to max_length."""
        if len(self.line_content) <= max_length:
            return self.line_content
        return self.line_content[:max_length] + "..."
    
    def __repr__(self):
        return f"Reference({self.source_file}:{self.line_number} -> {self.target_file})"


class ReferenceTracker:
    """Track detailed file references with line numbers and code snippets."""
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.references: Dict[str, List[FileReference]] = {}  # target_file -> list of references
        
        # Extended patterns for multiple file types
        self.patterns = {
            # PHP patterns
            'php_include': re.compile(r'(?:include|require|include_once|require_once)\s*[\(\s]+[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'php_href': re.compile(r'href\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'php_src': re.compile(r'src\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'php_action': re.compile(r'action\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            
            # JavaScript/TypeScript patterns
            'js_import': re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'js_require': re.compile(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'js_fetch': re.compile(r'fetch\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'js_ajax': re.compile(r'(?:url|endpoint|href):\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            
            # HTML patterns
            'html_script': re.compile(r'<script[^>]+src\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'html_link': re.compile(r'<link[^>]+href\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'html_a': re.compile(r'<a[^>]+href\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'html_img': re.compile(r'<img[^>]+src\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'html_form': re.compile(r'<form[^>]+action\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            
            # JSON patterns (paths in config files)
            'json_path': re.compile(r'[\'"]path[\'"]:\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'json_url': re.compile(r'[\'"]url[\'"]:\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            
            # JavaScript navigation handlers (buttons, click events)
            'js_location_assign': re.compile(
                r'(?:window\.|document\.)?location(?:\.href)?\s*=\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            ),
            'js_location_call': re.compile(
                r'(?:window\.|document\.)?location\.(?:assign|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            ),
            'js_window_open': re.compile(
                r'window\.open\s*\(\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            )
        }
    
    def read_file_safe(self, file_path: Path) -> List[str]:
        """Safely read file and return lines."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.readlines()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return []
    
    def normalize_path(self, path: str, current_file: Path) -> str:
        """Normalize a file path reference."""
        path = path.strip()
        
        # Remove query strings and anchors
        path = re.split(r'[?#]', path)[0]
        
        # Skip external URLs
        if path.startswith(('http://', 'https://', '//', 'mailto:', 'tel:')):
            return ""
        
        # Handle absolute paths from root
        if path.startswith('/'):
            path = path.lstrip('/')
        else:
            # Handle relative paths
            current_dir = current_file.parent
            try:
                resolved = (current_dir / path).resolve()
                path = str(resolved.relative_to(self.root_dir))
            except (ValueError, OSError):
                # Path is outside root directory or doesn't resolve
                return ""
        
        return path.replace('\\', '/')
    
    def analyze_file(self, file_path: Path, relative_path: str):
        """Analyze a file for references to other files."""
        lines = self.read_file_safe(file_path)
        if not lines:
            return
        
        for line_num, line_content in enumerate(lines, start=1):
            # Try each pattern
            for ref_type, pattern in self.patterns.items():
                for match in pattern.finditer(line_content):
                    referenced_path = match.group(1)
                    normalized = self.normalize_path(referenced_path, file_path)
                    
                    if normalized:
                        ref = FileReference(
                            source_file=relative_path,
                            target_file=normalized,
                            line_number=line_num,
                            line_content=line_content,
                            reference_type=ref_type
                        )
                        
                        if normalized not in self.references:
                            self.references[normalized] = []
                        self.references[normalized].append(ref)
    
    def get_references_to(self, file_key: str) -> List[FileReference]:
        """Get all references to a specific file."""
        return self.references.get(file_key, [])
    
    def get_reference_summary(self, file_key: str) -> Dict:
        """Get summary of references to a file."""
        refs = self.get_references_to(file_key)
        
        summary = {
            'total_references': len(refs),
            'unique_sources': len(set(r.source_file for r in refs)),
            'reference_types': {},
            'references': refs
        }
        
        for ref in refs:
            ref_type = ref.reference_type
            if ref_type not in summary['reference_types']:
                summary['reference_types'][ref_type] = 0
            summary['reference_types'][ref_type] += 1
        
        return summary


class SQLURLAnalyzer:
    """Analyze SQL database for URL references."""
    
    def __init__(self):
        # Patterns to find URLs in SQL
        self.url_patterns = [
            re.compile(r'https?://[^\s\'"]+', re.IGNORECASE),
            re.compile(r'/[a-zA-Z0-9_\-/]+\.(?:php|html|htm|js|css)', re.IGNORECASE),
            re.compile(r'[\'"]([a-zA-Z0-9_\-/]+\.(?:php|html|htm))[\'"]', re.IGNORECASE),
        ]
        
        self.found_urls: Set[str] = set()
        self.url_references: Dict[str, List[Tuple[int, str]]] = {}  # url -> [(line, context)]
    
    def read_sql_file(self, file_path: Path) -> List[str]:
        """Read SQL file safely."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.readlines()
        except Exception as e:
            print(f"Error reading SQL file {file_path}: {e}")
            return []
    
    def analyze_sql(self, file_path: Path):
        """Analyze SQL dump for URL references."""
        lines = self.read_sql_file(file_path)
        
        for line_num, line in enumerate(lines, start=1):
            for pattern in self.url_patterns:
                for match in pattern.finditer(line):
                    url = match.group(1) if pattern.groups > 0 else match.group(0)
                    url = url.strip('/')
                    
                    # Clean up URL
                    url = re.split(r'[?#]', url)[0]
                    
                    # Skip if it's a full external URL
                    if url.startswith(('http://', 'https://')):
                        # Extract path part
                        url_parts = url.split('/', 3)
                        if len(url_parts) > 3:
                            url = url_parts[3]
                        else:
                            continue
                    
                    if url and not url.startswith(('http://', 'https://', '//')):
                        self.found_urls.add(url)
                        
                        if url not in self.url_references:
                            self.url_references[url] = []
                        
                        # Store line number and snippet
                        snippet = line.strip()[:200]
                        self.url_references[url].append((line_num, snippet))
    
    def get_url_summary(self, url: str) -> Dict:
        """Get summary for a specific URL found in SQL."""
        refs = self.url_references.get(url, [])
        return {
            'url': url,
            'found_in_sql': len(refs) > 0,
            'occurrences': len(refs),
            'references': refs
        }
    
    def get_all_urls(self) -> Set[str]:
        """Get all URLs found in SQL."""
        return self.found_urls
    
    def cross_reference_files(self, known_files: Set[str]) -> Dict:
        """Cross-reference SQL URLs with known files."""
        results = {
            'matched': [],
            'unmatched_sql': [],
            'unmatched_files': []
        }
        
        for url in self.found_urls:
            # Normalize for comparison
            normalized = url.replace('\\', '/')
            
            # Try exact match
            if normalized in known_files:
                results['matched'].append({
                    'url': url,
                    'file': normalized,
                    'sql_refs': len(self.url_references.get(url, []))
                })
            else:
                # Try partial matches
                found = False
                for file in known_files:
                    if file.endswith(normalized) or normalized.endswith(file):
                        results['matched'].append({
                            'url': url,
                            'file': file,
                            'sql_refs': len(self.url_references.get(url, []))
                        })
                        found = True
                        break
                
                if not found:
                    results['unmatched_sql'].append(url)
        
        # Find files not referenced in SQL
        for file in known_files:
            matched = False
            for url in self.found_urls:
                if file.endswith(url) or url.endswith(file):
                    matched = True
                    break
            if not matched:
                results['unmatched_files'].append(file)
        
        return results

