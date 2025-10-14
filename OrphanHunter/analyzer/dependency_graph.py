"""Build and manage dependency graph between files."""
from typing import Dict, Set, List, Optional
from pathlib import Path
from OrphanHunter.scanner.file_scanner import FileInfo, FileScanner
from OrphanHunter.analyzer.php_parser import PHPParser
from OrphanHunter.analyzer.sql_parser import SQLReferenceAnalyzer
from OrphanHunter.analyzer.reference_tracker import ReferenceTracker, SQLURLAnalyzer
from OrphanHunter.analyzer.asset_analyzer import AssetAnalyzer
from OrphanHunter.analyzer.css_analyzer import CSSAnalyzer

class DependencyGraph:
    """Manages file dependencies and reference tracking."""
    
    def __init__(self, file_scanner: FileScanner, root_dir: Path):
        self.file_scanner = file_scanner
        self.root_dir = root_dir
        self.php_parser = PHPParser()
        self.sql_analyzer = SQLReferenceAnalyzer()
        self.reference_tracker = ReferenceTracker(root_dir)
        self.sql_url_analyzer = SQLURLAnalyzer()
        self.asset_analyzer = AssetAnalyzer(file_scanner, root_dir)
        self.css_analyzer = CSSAnalyzer(root_dir)
        
        # Dependency mappings
        self.file_dependencies: Dict[str, Set[str]] = {}  # file -> files it references
        self.file_dependents: Dict[str, Set[str]] = {}    # file -> files that reference it
        self.function_definitions: Dict[str, Set[str]] = {}  # function -> files defining it
        self.function_usage: Dict[str, Set[str]] = {}        # function -> files using it
        self.table_usage: Dict[str, Dict[str, int]] = {}    # file -> {table: count}
        self.table_files: Dict[str, Set[str]] = {}          # table -> files using it
        self.sql_urls: Set[str] = set()  # URLs found in SQL
        
    def build_graph(self, sql_tables: Optional[Set[str]] = None, sql_dump_path: Optional[Path] = None):
        """Build complete dependency graph."""
        sql_tables = sql_tables or set()
        
        # Initialize dictionaries
        for file_key in self.file_scanner.files:
            self.file_dependencies[file_key] = set()
            self.file_dependents[file_key] = set()
        
        # Parse each file (PHP, HTML, JS, TS, JSON)
        for file_key, file_info in self.file_scanner.files.items():
            # Use reference tracker for detailed tracking
            self.reference_tracker.analyze_file(file_info.path, file_key)
            
            # Also use PHP parser for compatibility
            if file_info.extension in ['.php', '.html', '.htm']:
                parse_result = self.php_parser.parse_file(file_info.path, self.root_dir)
                
                # Store file dependencies
                self.file_dependencies[file_key] = parse_result['all_references']
                
                # Update dependents
                for ref in parse_result['all_references']:
                    if ref in self.file_scanner.files:
                        if ref not in self.file_dependents:
                            self.file_dependents[ref] = set()
                        self.file_dependents[ref].add(file_key)
                
                # Track functions
                for func in parse_result['function_definitions']:
                    if func not in self.function_definitions:
                        self.function_definitions[func] = set()
                    self.function_definitions[func].add(file_key)
                
                for func in parse_result['function_calls']:
                    if func not in self.function_usage:
                        self.function_usage[func] = set()
                    self.function_usage[func].add(file_key)
                
                # Analyze SQL table usage
                if sql_tables:
                    table_refs = self.sql_analyzer.analyze_file_for_tables(file_info.path, sql_tables)
                    if table_refs:
                        self.table_usage[file_key] = table_refs
                        for table, count in table_refs.items():
                            if table not in self.table_files:
                                self.table_files[table] = set()
                            self.table_files[table].add(file_key)
        
        # Analyze SQL dump for URL references
        if sql_dump_path and sql_dump_path.exists():
            self.sql_url_analyzer.analyze_sql(sql_dump_path)
            self.sql_urls = self.sql_url_analyzer.get_all_urls()
            
            # Cross-reference SQL URLs with actual files
            known_files = set(self.file_scanner.files.keys())
            cross_ref = self.sql_url_analyzer.cross_reference_files(known_files)
            
            # Update dependents for files referenced in SQL
            for match in cross_ref['matched']:
                file_key = match['file']
                if file_key in self.file_scanner.files:
                    # Add SQL as a "virtual" referrer
                    if file_key not in self.file_dependents:
                        self.file_dependents[file_key] = set()
                    self.file_dependents[file_key].add('__SQL_DATABASE__')
        
        # Update reference counts in file_info objects
        for file_key, file_info in self.file_scanner.files.items():
            dependents = self.file_dependents.get(file_key, set())
            file_info.reference_count = len(dependents)
            file_info.referenced_by = dependents
            file_info.references = self.file_dependencies.get(file_key, set())
    
    def get_file_references(self, file_key: str) -> Set[str]:
        """Get all files referenced by the given file."""
        return self.file_dependencies.get(file_key, set())
    
    def get_file_dependents(self, file_key: str) -> Set[str]:
        """Get all files that reference the given file."""
        return self.file_dependents.get(file_key, set())
    
    def get_orphaned_files(self, criteria: Dict) -> Set[str]:
        """Identify orphaned files based on criteria."""
        orphaned = set()
        navigation_files_set = set(self.file_scanner.navigation_files)
        exclude_patterns = set(criteria.get('exclude_patterns', []))
        
        for file_key, file_info in self.file_scanner.files.items():
            # Skip critical files
            if file_info.is_critical:
                continue
            
            # Skip navigation files themselves
            if file_info.is_navigation:
                continue
            
            # Apply exclusion patterns (suffix match)
            if exclude_patterns and any(file_key.endswith(pattern) for pattern in exclude_patterns):
                continue

            is_orphaned = True
            
            # Check criteria
            if criteria.get('not_in_navigation', True) and is_orphaned:
                # Check if referenced by any navigation file
                if file_info.referenced_by & navigation_files_set:
                    is_orphaned = False
            
            if criteria.get('not_included_anywhere', True) and is_orphaned:
                # Check if referenced by any file at all
                if file_info.referenced_by:
                    is_orphaned = False
            
            if criteria.get('not_referenced', True) and is_orphaned:
                if file_info.reference_count > 0:
                    is_orphaned = False
            
            # Check minimum reference count
            min_refs = criteria.get('min_reference_count', 0)
            if min_refs > 0 and file_info.reference_count >= min_refs:
                is_orphaned = False
            
            if is_orphaned:
                orphaned.add(file_key)
        
        return orphaned
    
    def get_deletion_impact(self, file_keys: Set[str]) -> Dict:
        """Analyze the impact of deleting given files."""
        impact = {
            'files_to_delete': file_keys,
            'affected_files': set(),
            'broken_references': [],
            'affected_tables': set(),
            'critical_files_affected': False
        }
        
        for file_key in file_keys:
            # Find files that depend on this file
            dependents = self.get_file_dependents(file_key)
            impact['affected_files'].update(dependents)
            
            # Check if any critical files are affected
            for dep in dependents:
                if dep in self.file_scanner.critical_files:
                    impact['critical_files_affected'] = True
                impact['broken_references'].append({
                    'from': dep,
                    'to': file_key
                })
            
            # Check SQL tables
            if file_key in self.table_usage:
                impact['affected_tables'].update(self.table_usage[file_key].keys())
        
        return impact
    
    def find_unused_tables(self, all_tables: Set[str]) -> Set[str]:
        """Find SQL tables that are not referenced in any PHP file."""
        used_tables = set(self.table_files.keys())
        return all_tables - used_tables
    
    def get_table_usage_summary(self) -> Dict[str, Dict]:
        """Get summary of table usage across files."""
        summary = {}
        for table, files in self.table_files.items():
            total_refs = sum(
                self.table_usage.get(f, {}).get(table, 0) 
                for f in files
            )
            summary[table] = {
                'files': list(files),
                'file_count': len(files),
                'total_references': total_refs
            }
        return summary

