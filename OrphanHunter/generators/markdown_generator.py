"""Generate markdown documentation for system structure."""
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
from OrphanHunter.scanner.file_scanner import FileScanner
from OrphanHunter.analyzer.dependency_graph import DependencyGraph

class MarkdownGenerator:
    """Generate markdown documentation files."""
    
    def __init__(self, file_scanner: FileScanner, dependency_graph: DependencyGraph):
        self.file_scanner = file_scanner
        self.dependency_graph = dependency_graph
    
    def get_status_indicator(self, file_info) -> str:
        """Get status indicator emoji/symbol for a file."""
        if file_info.is_critical:
            return "🔴"
        elif file_info.is_navigation:
            return "🔵"
        elif file_info.reference_count == 0:
            return "⚪"
        elif file_info.reference_count > 10:
            return "🟢"
        elif file_info.reference_count > 5:
            return "🟡"
        else:
            return "🟠"
    
    def generate_tree_map(self, output_path: Path = None, verbose: bool = True) -> str:
        """Generate complete file/folder hierarchy with status indicators."""
        lines = [
            "# System Tree Map",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Legend",
            "",
            "- 🔴 Critical File (index.php, config.php, etc.)",
            "- 🔵 Navigation File (header.php, footer.php, etc.)",
            "- 🟢 Highly Referenced (10+ references)",
            "- 🟡 Moderately Referenced (5-10 references)",
            "- 🟠 Low References (1-4 references)",
            "- ⚪ No References (potential orphan)",
            "- 💾 Referenced in SQL Database",
            "",
            "## File Structure",
            ""
        ]
        
        # Build directory tree
        def add_directory_tree(tree: Dict, prefix: str = "", is_last: bool = True):
            items = sorted(tree.items())
            
            for idx, (name, content) in enumerate(items):
                is_last_item = (idx == len(items) - 1)
                connector = "└── " if is_last_item else "├── "
                
                if isinstance(content, dict):
                    # It's a directory
                    lines.append(f"{prefix}{connector}{name}/")
                    extension = "    " if is_last_item else "│   "
                    add_directory_tree(content, prefix + extension, is_last_item)
                else:
                    # It's a file (FileInfo object)
                    file_info = content
                    status = self.get_status_indicator(file_info)
                    refs = f" ({file_info.reference_count} refs)" if file_info.reference_count > 0 else ""
                    lines.append(f"{prefix}{connector}{status} {name}{refs}")
        
        tree = self.file_scanner.get_directory_tree()
        add_directory_tree(tree)
        
        # Add statistics
        lines.extend([
            "",
            "## Statistics",
            "",
            f"- Total Files: {len(self.file_scanner.files)}",
            f"- Critical Files: {len(self.file_scanner.critical_files)}",
            f"- Navigation Files: {len(self.file_scanner.navigation_files)}",
            f"- PHP Files: {len(self.file_scanner.get_all_php_files())}",
            ""
        ])
        
        # Add asset analysis stats if available
        if hasattr(self.dependency_graph, 'asset_analyzer'):
            asset_summary = self.dependency_graph.asset_analyzer.get_asset_summary()
            if asset_summary and asset_summary['orphaned_assets'] > 0:
                lines.extend([
                    "### Orphaned Assets",
                    "",
                    f"- Total Orphaned Assets: {asset_summary['orphaned_assets']}",
                ])
                for ext, count in sorted(asset_summary['by_type'].items()):
                    lines.append(f"  - {ext} files: {count}")
                lines.append("")
        
        # Add verbose reference section if enabled
        if verbose and hasattr(self.dependency_graph, 'reference_tracker'):
            lines.extend(self._generate_verbose_references())
        
        content = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content
    
    def _generate_verbose_references(self) -> List[str]:
        """Generate verbose reference section with line numbers and code snippets."""
        lines = [
            "",
            "---",
            "",
            "# Verbose Reference Map",
            "",
            "Detailed listing of all file references with line numbers and code snippets.",
            ""
        ]
        
        # Sort files by number of references (most referenced first)
        files_by_refs = sorted(
            self.file_scanner.files.items(),
            key=lambda x: x[1].reference_count,
            reverse=True
        )
        
        for file_key, file_info in files_by_refs:
            if file_info.reference_count == 0:
                continue  # Skip unreferenced files in verbose section
            
            references = self.dependency_graph.reference_tracker.get_references_to(file_key)
            sql_refs = []
            
            # Check for SQL references
            if '__SQL_DATABASE__' in file_info.referenced_by:
                sql_summary = self.dependency_graph.sql_url_analyzer.get_url_summary(file_key)
                if sql_summary.get('found_in_sql'):
                    sql_refs = sql_summary.get('references', [])
            
            lines.extend([
                f"## `{file_key}`",
                "",
                f"**Total References:** {file_info.reference_count}",
                f"**Reference Types:** Code ({len(references)}), SQL ({len(sql_refs)})",
                ""
            ])
            
            if references:
                lines.append("### Code References")
                lines.append("")
                
                # Group by source file
                by_source = {}
                for ref in references:
                    if ref.source_file not in by_source:
                        by_source[ref.source_file] = []
                    by_source[ref.source_file].append(ref)
                
                for source_file in sorted(by_source.keys()):
                    refs = by_source[source_file]
                    lines.append(f"#### From: `{source_file}`")
                    lines.append("")
                    
                    for ref in refs:
                        snippet = ref.get_snippet(120)
                        lines.extend([
                            f"**Line {ref.line_number}** ({ref.reference_type}):",
                            "```",
                            snippet,
                            "```",
                            ""
                        ])
            
            if sql_refs:
                lines.append("### SQL Database References")
                lines.append("")
                lines.append("Found in SQL dump:")
                lines.append("")
                
                for line_num, snippet in sql_refs[:5]:  # Limit to first 5
                    lines.extend([
                        f"**SQL Line {line_num}**:",
                        "```sql",
                        snippet[:120] + ("..." if len(snippet) > 120 else ""),
                        "```",
                        ""
                    ])
                
                if len(sql_refs) > 5:
                    lines.append(f"*... and {len(sql_refs) - 5} more SQL references*")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return lines
    
    def generate_navigation_map(self, output_path: Path = None) -> str:
        """Generate navigation structure documentation."""
        lines = [
            "# Navigation Map",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Public Navigation",
            ""
        ]
        
        # Analyze navigation files
        for nav_key in self.file_scanner.navigation_files:
            file_info = self.file_scanner.get_file_by_relative_path(nav_key)
            if not file_info:
                continue
            
            lines.extend([
                f"### {file_info.name}",
                "",
                f"**Location:** `{file_info.relative_path}`",
                f"**Referenced by:** {len(file_info.referenced_by)} files",
                ""
            ])
            
            # List pages linked from this navigation file
            references = file_info.references
            if references:
                lines.append("**Links to:**")
                lines.append("")
                for ref in sorted(references):
                    ref_file = self.file_scanner.get_file_by_relative_path(ref)
                    if ref_file:
                        display_ref = ref_file.relative_path_str
                        lines.append(f"- `{display_ref}` ({ref_file.reference_count} refs)")
                lines.append("")
        
        # Admin navigation
        admin_files = [
            f for f in self.file_scanner.files.values()
            if 'admin' in f.relative_path.parts and f.is_navigation
        ]
        
        if admin_files:
            lines.extend([
                "## Admin Navigation",
                ""
            ])
            
            for file_info in admin_files:
                lines.extend([
                    f"### {file_info.name}",
                    "",
                    f"**Location:** `{file_info.relative_path}`",
                    f"**Referenced by:** {len(file_info.referenced_by)} files",
                    ""
                ])
                
                references = file_info.references
                if references:
                    lines.append("**Links to:**")
                    lines.append("")
                    for ref in sorted(references):
                        ref_file = self.file_scanner.get_file_by_relative_path(ref)
                        if ref_file:
                            display_ref = ref_file.relative_path_str
                            lines.append(f"- `{display_ref}` ({ref_file.reference_count} refs)")
                    lines.append("")
        
        # Page inventory
        lines.extend([
            "## Complete Page Inventory",
            "",
            "### Public Pages",
            ""
        ])
        
        public_pages = [
            f for f in self.file_scanner.files.values()
            if f.extension == '.php' and 'admin' not in f.relative_path.parts
        ]
        
        for file_info in sorted(public_pages, key=lambda x: x.relative_path_str):
            status = "✓ Active" if file_info.reference_count > 0 else "⚠ Orphaned"
            lines.append(f"- `{file_info.relative_path_str}` - {status} ({file_info.reference_count} refs)")
        
        lines.extend([
            "",
            "### Admin Pages",
            ""
        ])
        
        admin_pages = [
            f for f in self.file_scanner.files.values()
            if f.extension == '.php' and 'admin' in f.relative_path.parts
        ]
        
        for file_info in sorted(admin_pages, key=lambda x: x.relative_path_str):
            status = "✓ Active" if file_info.reference_count > 0 else "⚠ Orphaned"
            lines.append(f"- `{file_info.relative_path_str}` - {status} ({file_info.reference_count} refs)")
        
        # SQL Table Usage
        table_summary = self.dependency_graph.get_table_usage_summary()
        if table_summary:
            lines.extend([
                "",
                "## Database Table Usage",
                ""
            ])
            
            for table, info in sorted(table_summary.items()):
                lines.extend([
                    f"### Table: `{table}`",
                    "",
                    f"- Used in {info['file_count']} files",
                    f"- Total references: {info['total_references']}",
                    "",
                    "**Files:**",
                    ""
                ])
                
                for file_key in sorted(info['files']):
                    refs = self.dependency_graph.table_usage.get(file_key, {}).get(table, 0)
                    display_key = file_key
                    lines.append(f"- `{display_key}` ({refs} refs)")
                
                lines.append("")
        
        content = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content
    
    def generate_orphan_report(self, orphaned_files: Set[str], output_path: Path = None) -> str:
        """Generate report of orphaned files."""
        lines = [
            "# Orphaned Files Report",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Found {len(orphaned_files)} potentially orphaned files.",
            "",
            "## Orphaned Files",
            ""
        ]
        
        for file_key in sorted(orphaned_files):
            file_info = self.file_scanner.get_file_by_relative_path(file_key)
            if file_info:
                size_kb = round(file_info.size / 1024, 2)
                lines.append(f"- `{file_key}` ({size_kb} KB)")
        
        content = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content

