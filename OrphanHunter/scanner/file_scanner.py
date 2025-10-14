"""File scanner for discovering project structure."""
import os
from pathlib import Path
from typing import List, Dict, Set, Optional
import fnmatch

class FileInfo:
    """Information about a scanned file."""
    
    def __init__(self, path: Path, root_dir: Path):
        self.path = path
        self.root_dir = root_dir
        self.relative_path = path.relative_to(root_dir)
        self.relative_path_str = self.relative_path.as_posix()
        self.name = path.name
        self.extension = path.suffix
        self.size = path.stat().st_size if path.exists() else 0
        self.modified_time = path.stat().st_mtime if path.exists() else 0
        self.is_critical = False
        self.is_navigation = False
        self.reference_count = 0
        self.referenced_by: Set[str] = set()
        self.references: Set[str] = set()
        
    def __repr__(self):
        return f"FileInfo({self.relative_path_str})"

class FileScanner:
    """Scans directory structure and identifies files."""
    
    def __init__(self, root_dir: str, ignore_patterns: List[str] = None, 
                 ignore_dot_dirs: bool = True, blacklist_dirs: List[str] = None):
        self.root_dir = Path(root_dir).resolve()
        self.ignore_patterns = ignore_patterns or []
        self.ignore_dot_dirs = ignore_dot_dirs
        self.blacklist_dirs = [d.strip('/\\') for d in (blacklist_dirs or [])]
        self.files: Dict[str, FileInfo] = {}
        self.directories: Set[Path] = set()
        self.critical_files: Set[str] = set()
        self.navigation_files: Set[str] = set()
        
    def should_ignore(self, path: Path) -> bool:
        """Check if path should be ignored based on patterns."""
        # NEVER ignore the root directory itself
        if path.resolve() == self.root_dir:
            return False
        
        path_str = str(path)
        try:
            relative = path.relative_to(self.root_dir).as_posix()
        except ValueError:
            return False
        
        # Don't ignore if this is the root (empty relative path or '.')
        if relative in ['', '.']:
            return False
        
        # Check if directory is blacklisted
        if path.is_dir():
            dir_name = path.name
            relative_path = str(path.relative_to(self.root_dir)).replace('\\', '/')
            
            # Check blacklist (exact match or subdirectory)
            for blacklisted in self.blacklist_dirs:
                blacklisted_normalized = blacklisted.replace('\\', '/')
                if dir_name == blacklisted_normalized or relative_path == blacklisted_normalized:
                    return True
                # Check if it's a subdirectory of a blacklisted directory
                if relative_path.startswith(blacklisted_normalized + '/'):
                    return True
            
            # Check if it's a dot directory (but NOT the root even if it starts with .)
            if self.ignore_dot_dirs and dir_name.startswith('.') and dir_name not in ['.', '..']:
                return True
        
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            # Check if it's a directory name match
            if pattern in path.parts:
                return True
            # Check if it matches the pattern
            if fnmatch.fnmatch(path.name, pattern):
                return True
            if fnmatch.fnmatch(relative, pattern):
                return True
        return False
    
    def scan(self, extensions: List[str] = None) -> Dict[str, FileInfo]:
        """Scan directory and return file information."""
        extensions = extensions or ['.php', '.html', '.htm']
        
        if not self.root_dir.exists():
            raise ValueError(f"Root directory does not exist: {self.root_dir}")
        
        self.files.clear()
        self.directories.clear()
        
        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)
            
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if not self.should_ignore(root_path / d)]
            
            self.directories.add(root_path)
            
            for file in files:
                file_path = root_path / file
                
                if self.should_ignore(file_path):
                    continue
                
                # Check if file has one of the target extensions
                if extensions and file_path.suffix not in extensions:
                    continue
                
                file_info = FileInfo(file_path, self.root_dir)
                file_key = file_info.relative_path_str
                self.files[file_key] = file_info
        
        return self.files
    
    def mark_critical_files(self, critical_file_names: List[str]):
        """Mark files as critical based on filenames."""
        self.critical_files.clear()
        for file_key, file_info in self.files.items():
            if file_info.name in critical_file_names:
                file_info.is_critical = True
                self.critical_files.add(file_key)
    
    def mark_navigation_files(self, navigation_file_names: List[str]):
        """Mark files as navigation files."""
        self.navigation_files.clear()
        for file_key, file_info in self.files.items():
            if file_info.name in navigation_file_names:
                file_info.is_navigation = True
                self.navigation_files.add(file_key)
    
    def find_file_by_name(self, filename: str) -> List[FileInfo]:
        """Find all files matching the given filename."""
        results = []
        for file_info in self.files.values():
            if file_info.name == filename:
                results.append(file_info)
        return results
    
    def get_file_by_relative_path(self, relative_path: str) -> Optional[FileInfo]:
        """Get file info by relative path."""
        return self.files.get(relative_path)
    
    def get_all_php_files(self) -> List[FileInfo]:
        """Get all PHP files."""
        return [f for f in self.files.values() if f.extension == '.php']
    
    def get_directory_tree(self) -> Dict:
        """Get directory tree structure."""
        tree = {}
        for file_key in sorted(self.files.keys()):
            parts = Path(file_key).parts
            current = tree
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[parts[-1]] = self.files[file_key]
        return tree

