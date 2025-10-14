"""Pre and post-deletion sanity checking."""
from pathlib import Path
from typing import Dict, Set, List
from OrphanHunter.scanner.file_scanner import FileScanner
from OrphanHunter.analyzer.dependency_graph import DependencyGraph

class SanityChecker:
    """Perform sanity checks before and after file operations."""
    
    def __init__(self, file_scanner: FileScanner, dependency_graph: DependencyGraph):
        self.file_scanner = file_scanner
        self.dependency_graph = dependency_graph
    
    def pre_deletion_check(self, files_to_delete: Set[str]) -> Dict:
        """Perform checks before deletion."""
        issues = {
            'critical': [],
            'warnings': [],
            'info': [],
            'safe_to_proceed': True
        }
        
        # Check for critical files
        for file_key in files_to_delete:
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            if not file_info:
                issues['critical'].append(f"File not found: {file_key}")
                issues['safe_to_proceed'] = False
                continue
            
            if file_info.is_critical:
                issues['critical'].append(f"Critical file marked for deletion: {file_key}")
                issues['safe_to_proceed'] = False
        
        # Check for broken dependencies
        impact = self.dependency_graph.get_deletion_impact(files_to_delete)
        
        if impact['critical_files_affected']:
            issues['critical'].append("Deletion would affect critical files")
            issues['safe_to_proceed'] = False
        
        if impact['affected_files']:
            issues['warnings'].append(
                f"{len(impact['affected_files'])} files reference the files marked for deletion"
            )
        
        if impact['broken_references']:
            issues['warnings'].append(
                f"{len(impact['broken_references'])} references will be broken"
            )
        
        if impact['affected_tables']:
            issues['info'].append(
                f"Deletion affects {len(impact['affected_tables'])} database tables"
            )
        
        # Check if files exist
        missing_files = []
        for file_key in files_to_delete:
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            if file_info and not file_info.path.exists():
                missing_files.append(file_key)
        
        if missing_files:
            issues['warnings'].append(f"{len(missing_files)} files already deleted or missing")
        
        return issues
    
    def post_deletion_check(self) -> Dict:
        """Perform checks after deletion."""
        issues = {
            'broken_includes': [],
            'broken_links': [],
            'syntax_errors': [],
            'all_ok': True
        }
        
        # Re-scan to get updated file list
        remaining_files = [
            f for f in self.file_scanner.files.values() 
            if f.path.exists()
        ]
        
        # Check for broken includes
        for file_info in remaining_files:
            if file_info.extension != '.php':
                continue
            
            # Check if any referenced files are missing
            for ref in file_info.references:
                ref_file = self.file_scanner.get_file_by_relative_path(ref)
                if not ref_file or not ref_file.path.exists():
                    issues['broken_includes'].append({
                        'file': file_info.relative_path_str,
                        'missing_reference': ref
                    })
                    issues['all_ok'] = False
        
        # Check navigation files
        for nav_file_key in self.file_scanner.navigation_files:
            nav_file = self.file_scanner.get_file_by_relative_path(nav_file_key)
            if not nav_file or not nav_file.path.exists():
                issues['broken_links'].append(f"Navigation file missing: {nav_file_key}")
                issues['all_ok'] = False
        
        return issues
    
    def validate_php_syntax(self, file_path: Path) -> Dict:
        """Validate PHP file syntax (basic check)."""
        result = {
            'valid': True,
            'errors': []
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Basic syntax checks
            # Check for unclosed PHP tags
            php_open_count = content.count('<?php')
            php_close_count = content.count('?>')
            
            # More opens than closes is actually OK (file can end without closing)
            # But we can flag unusual patterns
            
            # Check for unmatched brackets/braces (basic)
            open_braces = content.count('{')
            close_braces = content.count('}')
            open_parens = content.count('(')
            close_parens = content.count(')')
            open_brackets = content.count('[')
            close_brackets = content.count(']')
            
            if open_braces != close_braces:
                result['valid'] = False
                result['errors'].append(f"Unmatched braces: {open_braces} open, {close_braces} close")
            
            if open_parens != close_parens:
                result['valid'] = False
                result['errors'].append(f"Unmatched parentheses: {open_parens} open, {close_parens} close")
            
            if open_brackets != close_brackets:
                result['valid'] = False
                result['errors'].append(f"Unmatched brackets: {open_brackets} open, {close_brackets} close")
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(str(e))
        
        return result
    
    def validate_all_php_files(self) -> Dict:
        """Validate syntax of all PHP files."""
        results = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'errors': []
        }
        
        for file_info in self.file_scanner.get_all_php_files():
            if not file_info.path.exists():
                continue
            
            results['total'] += 1
            validation = self.validate_php_syntax(file_info.path)
            
            if validation['valid']:
                results['valid'] += 1
            else:
                results['invalid'] += 1
                results['errors'].append({
                    'file': file_info.relative_path_str,
                    'errors': validation['errors']
                })
        
        return results
    
    def check_system_health(self) -> Dict:
        """Comprehensive system health check."""
        health = {
            'status': 'healthy',
            'issues': [],
            'stats': {}
        }
        
        # Count files
        total_files = len(self.file_scanner.files)
        php_files = len(self.file_scanner.get_all_php_files())
        critical_files = len(self.file_scanner.critical_files)
        
        health['stats'] = {
            'total_files': total_files,
            'php_files': php_files,
            'critical_files': critical_files
        }
        
        # Check critical files exist
        for file_key in self.file_scanner.critical_files:
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            if not file_info or not file_info.path.exists():
                health['issues'].append(f"Critical file missing: {file_key}")
                health['status'] = 'critical'
        
        # Check navigation files exist
        for file_key in self.file_scanner.navigation_files:
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            if not file_info or not file_info.path.exists():
                health['issues'].append(f"Navigation file missing: {file_key}")
                if health['status'] == 'healthy':
                    health['status'] = 'warning'
        
        return health

    def _check_reference_chain(self, current_key: str, remaining_depth: int,
                               visited: Set[str], chain: List[str]) -> List[Dict]:
        """Recursively verify reference chains and collect missing targets."""
        issues: List[Dict] = []
        base_chain = chain + [current_key]
        file_info = self.file_scanner.get_file_by_relative_path(current_key)
        origin = base_chain[0]
        
        if not file_info:
            file_path = (self.file_scanner.root_dir / current_key)
            if not file_path.exists():
                issues.append({
                    'origin': origin,
                    'chain': base_chain,
                    'missing': current_key,
                    'reason': 'not-tracked'
                })
            return issues
        
        if not file_info.path.exists():
            issues.append({
                'origin': origin,
                'chain': base_chain,
                'missing': current_key,
                'reason': 'missing-on-disk'
            })
            return issues
        
        for ref in sorted(file_info.references):
            normalized = ref.replace('\\', '/')
            ref_path = (self.file_scanner.root_dir / normalized)
            ref_info = self.file_scanner.get_file_by_relative_path(normalized)
            issue_chain = base_chain + [normalized]
            
            if not ref_info and not ref_path.exists():
                issues.append({
                    'origin': origin,
                    'chain': issue_chain,
                    'missing': normalized,
                    'reason': 'reference-missing'
                })
                continue
            
            if remaining_depth > 1 and ref_info:
                if normalized in visited:
                    continue
                visited.add(normalized)
                issues.extend(
                    self._check_reference_chain(
                        normalized,
                        remaining_depth - 1,
                        visited,
                        base_chain
                    )
                )
                visited.remove(normalized)
        
        return issues
    
    def _collect_reference_issues(self, file_key: str, depth: int) -> List[Dict]:
        visited = {file_key}
        return self._check_reference_chain(file_key, depth, visited, [])
    
    def recursive_integrity_check(self, max_depth: int = 1) -> Dict:
        """Run multi-pass recursive integrity verification up to max_depth."""
        max_depth = max(1, max_depth)
        pass_reports: List[Dict] = []
        for depth in range(1, max_depth + 1):
            pass_issues: List[Dict] = []
            for file_key in sorted(self.file_scanner.files.keys()):
                pass_issues.extend(self._collect_reference_issues(file_key, depth))
            pass_reports.append({
                'depth': depth,
                'issues': pass_issues,
                'issue_count': len(pass_issues),
                'passed': len(pass_issues) == 0
            })
        return {
            'max_depth': max_depth,
            'passes': pass_reports,
            'overall_passed': all(report['passed'] for report in pass_reports)
        }
    
    def final_sanitation_check(self, passes: int = 2, ultra_mode: bool = False) -> Dict:
        """Execute comprehensive sanitation check with optional ultra mode."""
        passes = max(1, passes)
        if ultra_mode:
            passes = max(7, passes)
        integrity_report = self.recursive_integrity_check(passes)
        php_validation = self.validate_all_php_files()
        system_health = self.check_system_health()
        post_check = self.post_deletion_check()
        return {
            'passes_requested': passes,
            'integrity': integrity_report,
            'php_validation': php_validation,
            'system_health': system_health,
            'post_deletion': post_check
        }

