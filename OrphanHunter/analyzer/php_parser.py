"""PHP file parser for detecting references and dependencies."""
import re
from pathlib import Path
from typing import Set, Dict, List, Tuple
import chardet

class PHPParser:
    """Parse PHP files to extract references and dependencies."""
    
    def __init__(self):
        # Level A - Basic patterns
        self.include_pattern = re.compile(
            r'(?:include|require|include_once|require_once)\s*[\(\s]+[\'"]([^\'"]+)[\'"]',
            re.IGNORECASE
        )
        self.href_pattern = re.compile(
            r'href\s*=\s*[\'"]([^\'"]+\.php[^\'"]*)[\'"]',
            re.IGNORECASE
        )
        self.action_pattern = re.compile(
            r'action\s*=\s*[\'"]([^\'"]+\.php[^\'"]*)[\'"]',
            re.IGNORECASE
        )
        self.redirect_pattern = re.compile(
            r'(?:header|Location:)\s*[\'"](?:Location:\s*)?([^\'"]+\.php[^\'"]*)[\'"]',
            re.IGNORECASE
        )
        
        # Level B - Advanced patterns
        self.route_patterns = [
            re.compile(r'\$routes?\[[\'"](.*?)[\'"]\]', re.IGNORECASE),
            re.compile(r'Router::(?:get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            re.compile(r'case\s+[\'"]([^\'"]+\.php[^\'"]*)[\'"]:', re.IGNORECASE),
        ]
        
        self.function_def_pattern = re.compile(
            r'function\s+(\w+)\s*\(',
            re.IGNORECASE
        )
        self.function_call_pattern = re.compile(
            r'(\w+)\s*\(',
            re.IGNORECASE
        )
        self.class_def_pattern = re.compile(
            r'class\s+(\w+)',
            re.IGNORECASE
        )
        
        # AJAX/API patterns
        self.ajax_pattern = re.compile(
            r'(?:url|endpoint):\s*[\'"]([^\'"]+\.php[^\'"]*)[\'"]',
            re.IGNORECASE
        )
        self.fetch_pattern = re.compile(
            r'fetch\s*\(\s*[\'"]([^\'"]+\.php[^\'"]*)[\'"]',
            re.IGNORECASE
        )
        self.js_navigation_patterns = [
            re.compile(
                r'(?:window\.|document\.)?location(?:\.href)?\s*=\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            ),
            re.compile(
                r'(?:window\.|document\.)?location\.(?:assign|replace)\s*\(\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            ),
            re.compile(
                r'window\.open\s*\(\s*[\'"]([^\'"]+)[\'"]',
                re.IGNORECASE
            )
        ]
    
    def read_file_safe(self, file_path: Path) -> str:
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
    
    def normalize_path(self, path: str, current_file: Path, root_dir: Path) -> str:
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
            resolved = (current_dir / path).resolve()
            try:
                path = str(resolved.relative_to(root_dir))
            except ValueError:
                # Path is outside root directory
                return ""
        
        return path.replace('\\', '/')
    
    def extract_includes(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract include/require statements."""
        includes = set()
        for match in self.include_pattern.finditer(content):
            path = self.normalize_path(match.group(1), current_file, root_dir)
            if path:
                includes.add(path)
        return includes
    
    def extract_hrefs(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract href links to PHP files."""
        hrefs = set()
        for match in self.href_pattern.finditer(content):
            path = self.normalize_path(match.group(1), current_file, root_dir)
            if path:
                hrefs.add(path)
        return hrefs
    
    def extract_actions(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract form action attributes."""
        actions = set()
        for match in self.action_pattern.finditer(content):
            path = self.normalize_path(match.group(1), current_file, root_dir)
            if path:
                actions.add(path)
        return actions
    
    def extract_redirects(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract redirect locations."""
        redirects = set()
        for match in self.redirect_pattern.finditer(content):
            path = self.normalize_path(match.group(1), current_file, root_dir)
            if path:
                redirects.add(path)
        return redirects
    
    def extract_routes(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract route definitions."""
        routes = set()
        for pattern in self.route_patterns:
            for match in pattern.finditer(content):
                path = self.normalize_path(match.group(1), current_file, root_dir)
                if path:
                    routes.add(path)
        return routes
    
    def extract_ajax_endpoints(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract AJAX/fetch endpoints."""
        endpoints = set()
        for pattern in [self.ajax_pattern, self.fetch_pattern]:
            for match in pattern.finditer(content):
                path = self.normalize_path(match.group(1), current_file, root_dir)
                if path:
                    endpoints.add(path)
        return endpoints
    
    def extract_functions(self, content: str) -> Tuple[Set[str], Set[str]]:
        """Extract function definitions and calls."""
        definitions = set()
        calls = set()
        
        for match in self.function_def_pattern.finditer(content):
            definitions.add(match.group(1))
        
        for match in self.function_call_pattern.finditer(content):
            func_name = match.group(1)
            # Filter out language constructs and common keywords
            if func_name not in ['if', 'for', 'while', 'switch', 'echo', 'print', 'return', 'array']:
                calls.add(func_name)
        
        return definitions, calls
    
    def extract_classes(self, content: str) -> Set[str]:
        """Extract class definitions."""
        classes = set()
        for match in self.class_def_pattern.finditer(content):
            classes.add(match.group(1))
        return classes
    
    def extract_js_navigation(self, content: str, current_file: Path, root_dir: Path) -> Set[str]:
        """Extract navigation targets from JavaScript handlers."""
        targets = set()
        for pattern in self.js_navigation_patterns:
            for match in pattern.finditer(content):
                path = self.normalize_path(match.group(1), current_file, root_dir)
                if path:
                    targets.add(path)
        return targets
    
    def parse_file(self, file_path: Path, root_dir: Path) -> Dict:
        """Parse a PHP file and extract all references."""
        content = self.read_file_safe(file_path)
        
        if not content:
            return {
                'includes': set(),
                'hrefs': set(),
                'actions': set(),
                'redirects': set(),
                'routes': set(),
                'ajax_endpoints': set(),
                'function_definitions': set(),
                'function_calls': set(),
                'class_definitions': set(),
                'all_references': set()
            }
        
        includes = self.extract_includes(content, file_path, root_dir)
        hrefs = self.extract_hrefs(content, file_path, root_dir)
        actions = self.extract_actions(content, file_path, root_dir)
        redirects = self.extract_redirects(content, file_path, root_dir)
        routes = self.extract_routes(content, file_path, root_dir)
        ajax_endpoints = self.extract_ajax_endpoints(content, file_path, root_dir)
        js_navigation = self.extract_js_navigation(content, file_path, root_dir)
        func_defs, func_calls = self.extract_functions(content)
        class_defs = self.extract_classes(content)
        all_refs = includes | hrefs | actions | redirects | routes | ajax_endpoints | js_navigation
        
        return {
            'includes': includes,
            'hrefs': hrefs,
            'actions': actions,
            'redirects': redirects,
            'routes': routes,
            'ajax_endpoints': ajax_endpoints,
            'js_navigation': js_navigation,
            'function_definitions': func_defs,
            'function_calls': func_calls,
            'class_definitions': class_defs,
            'all_references': all_refs
        }

