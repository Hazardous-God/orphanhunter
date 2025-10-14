"""Analyzer for orphaned assets (JS, TS, JSON, CSS files)."""
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple
from OrphanHunter.scanner.file_scanner import FileScanner
import chardet


class AssetAnalyzer:
    """Detect orphaned JavaScript, TypeScript, JSON, and CSS files."""
    
    def __init__(self, file_scanner: FileScanner, root_dir: Path):
        self.file_scanner = file_scanner
        self.root_dir = root_dir
        
        # Asset types to track
        self.asset_extensions = {'.js', '.ts', '.json', '.css'}
        self.page_extensions = {'.php', '.html', '.htm'}
        
        # Patterns for finding asset references
        self.patterns = {
            'script_src': re.compile(r'<script[^>]+src\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'link_href': re.compile(r'<link[^>]+href\s*=\s*[\'"]([^\'"]+\.(?:css|js))[\'"]', re.IGNORECASE),
            'import_js': re.compile(r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'require_js': re.compile(r'require\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            'json_ref': re.compile(r'[\'"]([^\'"]+\.json)[\'"]', re.IGNORECASE),
            'style_import': re.compile(r'@import\s+[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
        }
        
        self.asset_references: Dict[str, Set[str]] = {}  # asset -> pages that reference it
        self.orphaned_assets: Dict[str, Set[str]] = {}  # extension -> orphaned files
    
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
            return ""
    
    def normalize_asset_path(self, path: str, current_file: Path) -> str:
        """Normalize an asset path reference."""
        path = path.strip()
        
        # Remove query strings and anchors
        path = re.split(r'[?#]', path)[0]
        
        # Skip external URLs
        if path.startswith(('http://', 'https://', '//', 'data:')):
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
                return ""
        
        return path.replace('\\', '/')
    
    def scan_page_for_assets(self, page_path: Path, page_key: str):
        """Scan a page file for asset references."""
        content = self.read_file_safe(page_path)
        if not content:
            return
        
        found_assets = set()
        
        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            for match in pattern.finditer(content):
                asset_path = match.group(1)
                normalized = self.normalize_asset_path(asset_path, page_path)
                
                if normalized:
                    # Check if it's an asset file
                    asset_ext = Path(normalized).suffix.lower()
                    if asset_ext in self.asset_extensions:
                        found_assets.add(normalized)
                        
                        if normalized not in self.asset_references:
                            self.asset_references[normalized] = set()
                        self.asset_references[normalized].add(page_key)
    
    def analyze(self):
        """Analyze all pages for asset references and identify orphaned assets."""
        # Reset
        self.asset_references.clear()
        self.orphaned_assets.clear()
        
        # Scan all page files for asset references
        for file_key, file_info in self.file_scanner.files.items():
            if file_info.extension in self.page_extensions:
                self.scan_page_for_assets(file_info.path, file_key)
        
        # Also check CSS files for @import references to other CSS
        for file_key, file_info in self.file_scanner.files.items():
            if file_info.extension == '.css':
                content = self.read_file_safe(file_info.path)
                for match in self.patterns['style_import'].finditer(content):
                    css_path = match.group(1)
                    normalized = self.normalize_asset_path(css_path, file_info.path)
                    if normalized:
                        if normalized not in self.asset_references:
                            self.asset_references[normalized] = set()
                        self.asset_references[normalized].add(file_key)
        
        # Identify orphaned assets
        for file_key, file_info in self.file_scanner.files.items():
            if file_info.extension in self.asset_extensions:
                if file_key not in self.asset_references:
                    ext = file_info.extension
                    if ext not in self.orphaned_assets:
                        self.orphaned_assets[ext] = set()
                    self.orphaned_assets[ext].add(file_key)
        
        return self.orphaned_assets
    
    def get_asset_summary(self) -> Dict:
        """Get summary of asset analysis."""
        total_assets = sum(
            1 for f in self.file_scanner.files.values()
            if f.extension in self.asset_extensions
        )
        
        total_orphaned = sum(len(files) for files in self.orphaned_assets.values())
        
        referenced_assets = len(self.asset_references)
        
        return {
            'total_assets': total_assets,
            'referenced_assets': referenced_assets,
            'orphaned_assets': total_orphaned,
            'by_type': {
                ext: len(files) 
                for ext, files in self.orphaned_assets.items()
            },
            'orphaned_files': self.orphaned_assets
        }
    
    def get_asset_references(self, asset_key: str) -> Set[str]:
        """Get pages that reference a specific asset."""
        return self.asset_references.get(asset_key, set())

