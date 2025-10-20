"""SQL Report Generator - Creates markdown reports for SQL table analysis."""
from datetime import datetime
from pathlib import Path
from typing import Dict


class SQLReportGenerator:
    """Generate comprehensive SQL analysis reports."""
    
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.date = datetime.now().strftime("%Y-%m-%d")
    
    def generate_table_map(self, analysis: Dict, output_path: Path) -> str:
        """Generate table-map.md with comprehensive table breakdown."""
        
        all_tables = analysis['all_tables']
        stats = analysis['statistics']
        
        content = []
        content.append(f"# SQL Table Map")
        content.append(f"\n**Generated:** {self.timestamp}")
        content.append(f"\n---\n")
        
        # Statistics
        content.append("## Statistics\n")
        content.append(f"- **Total Tables:** {stats['total_tables']}")
        content.append(f"- **Tables in Use:** {stats['used_tables']}")
        content.append(f"- **Unused Tables:** {stats['unused_tables']}")
        content.append(f"- **PHP Files Scanned:** {stats['total_php_files']}")
        content.append(f"- **SQL Files Scanned:** {stats['total_sql_files']}")
        content.append(f"\n---\n")
        
        # All Tables Overview
        content.append("## All Tables\n")
        
        for table_name in sorted(all_tables.keys()):
            table_info = all_tables[table_name]
            schema = table_info['schema']
            usage_count = len(table_info['used_in_php'])
            total_references = sum(usage['count'] for usage in table_info['used_in_php'])
            
            content.append(f"### `{table_name}`\n")
            
            # Status badge
            if usage_count > 0:
                content.append(f"**Status:** ✅ IN USE ({total_references} references in {usage_count} files)\n")
            else:
                content.append(f"**Status:** ⚠️ UNUSED\n")
            
            # Source
            content.append(f"**Defined in:** `{table_info['found_in']}`\n")
            
            # Schema details
            if schema['engine']:
                content.append(f"**Engine:** {schema['engine']}")
            if schema['charset']:
                content.append(f" | **Charset:** {schema['charset']}")
            content.append("\n")
            
            # Columns
            if schema['columns']:
                content.append(f"\n**Columns ({len(schema['columns'])}):**\n")
                content.append("| Column Name | Type |")
                content.append("\n|-------------|------|")
                for col in schema['columns']:
                    content.append(f"\n| `{col['name']}` | {col['type']} |")
                content.append("\n")
            
            # Primary Keys
            if schema['primary_keys']:
                content.append(f"\n**Primary Keys:** {', '.join(f'`{pk}`' for pk in schema['primary_keys'])}\n")
            
            # Foreign Keys
            if schema['foreign_keys']:
                content.append(f"\n**Foreign Keys:**\n")
                for fk in schema['foreign_keys']:
                    content.append(f"- `{fk['column']}` → `{fk['references_table']}`.`{fk['references_column']}`\n")
            
            # Indexes
            if schema['indexes']:
                content.append(f"\n**Indexes:** {', '.join(f'`{idx}`' for idx in schema['indexes'])}\n")
            
            content.append("\n---\n")
        
        report = ''.join(content)
        
        # Write to file
        output_path.write_text(report, encoding='utf-8')
        return str(output_path)
    
    def generate_connection_report(self, analysis: Dict, output_path: Path) -> str:
        """Generate comprehensive SQL-PHP connection report."""
        
        used_tables = analysis['used_tables']
        unused_tables = analysis['unused_tables']
        stats = analysis['statistics']
        
        content = []
        content.append(f"# SQL to PHP Connection Report")
        content.append(f"\n**Generated:** {self.timestamp}")
        content.append(f"\n---\n")
        
        # Executive Summary
        content.append("## Executive Summary\n")
        content.append(f"- **Total SQL Tables:** {stats['total_tables']}")
        content.append(f"- **Tables Used in PHP:** {stats['used_tables']} ({stats['used_tables']/max(stats['total_tables'], 1)*100:.1f}%)")
        content.append(f"- **Tables NOT Used in PHP:** {stats['unused_tables']} ({stats['unused_tables']/max(stats['total_tables'], 1)*100:.1f}%)")
        content.append(f"- **PHP Files Analyzed:** {stats['total_php_files']}")
        content.append(f"\n---\n")
        
        # Tables in Use
        content.append("## Tables in Use\n")
        content.append("\nThese tables are actively referenced in your PHP codebase:\n")
        
        if used_tables:
            for table_name in sorted(used_tables.keys()):
                table_info = used_tables[table_name]
                total_refs = sum(usage['count'] for usage in table_info['used_in_php'])
                file_count = len(table_info['used_in_php'])
                
                content.append(f"\n### `{table_name}`\n")
                content.append(f"**Usage:** {total_refs} references across {file_count} PHP file(s)\n")
                content.append(f"**Defined in:** `{table_info['found_in']}`\n")
                
                # Column count
                if table_info['schema']['columns']:
                    content.append(f"**Columns:** {len(table_info['schema']['columns'])}\n")
                
                # List files using this table
                content.append(f"\n**Used in:**\n")
                for usage in sorted(table_info['used_in_php'], key=lambda x: x['file']):
                    content.append(f"\n#### `{usage['file']}` ({usage['count']} references)\n")
                    
                    # Show first few usages with context
                    shown = 0
                    for ref in usage['usages'][:5]:  # Show max 5 examples per file
                        content.append(f"- Line {ref['line']}: `{ref['context'][:100]}`\n")
                        shown += 1
                    
                    if len(usage['usages']) > 5:
                        content.append(f"- *(+{len(usage['usages']) - 5} more references)*\n")
                
                content.append("\n---\n")
        else:
            content.append("\n*No tables are currently in use.*\n")
        
        # Unused Tables
        content.append("\n## Unused Tables ⚠️\n")
        content.append("\nThese tables are defined in your SQL files but NOT referenced in any PHP files:\n")
        
        if unused_tables:
            content.append("\n| Table Name | Defined In | Columns | Notes |")
            content.append("\n|------------|------------|---------|-------|")
            
            for table_name in sorted(unused_tables.keys()):
                table_info = unused_tables[table_name]
                col_count = len(table_info['schema']['columns'])
                source = table_info['found_in']
                
                # Check for foreign keys as a hint
                has_fk = len(table_info['schema']['foreign_keys']) > 0
                note = "Has foreign keys" if has_fk else "-"
                
                content.append(f"\n| `{table_name}` | `{source}` | {col_count} | {note} |")
            
            content.append("\n\n**⚠️ Warning:** These tables may be:")
            content.append("\n- Legacy/deprecated tables that can be removed")
            content.append("\n- Used by external systems or direct SQL queries")
            content.append("\n- Part of migrations not yet applied")
            content.append("\n- Referenced dynamically (variable table names)")
            content.append("\n\n**Recommendation:** Review each unused table before deletion.\n")
        else:
            content.append("\n*All tables are in use! Excellent code hygiene.*\n")
        
        content.append("\n---\n")
        
        # Table Relationship Map
        content.append("## Table Relationships\n")
        content.append("\nForeign key relationships between tables:\n")
        
        has_relationships = False
        for table_name in sorted(analysis['all_tables'].keys()):
            table_info = analysis['all_tables'][table_name]
            if table_info['schema']['foreign_keys']:
                has_relationships = True
                content.append(f"\n### `{table_name}`\n")
                for fk in table_info['schema']['foreign_keys']:
                    content.append(f"- `{fk['column']}` → `{fk['references_table']}`.`{fk['references_column']}`\n")
        
        if not has_relationships:
            content.append("\n*No foreign key relationships detected.*\n")
        
        content.append("\n---\n")
        
        # Recommendations
        content.append("## Recommendations\n")
        
        if stats['unused_tables'] > 0:
            content.append(f"\n### 1. Review Unused Tables ({stats['unused_tables']})\n")
            content.append("Consider removing unused tables to:\n")
            content.append("- Reduce database size\n")
            content.append("- Simplify schema maintenance\n")
            content.append("- Improve backup/restore times\n")
        
        if stats['used_tables'] > 0:
            content.append(f"\n### 2. Document Table Usage\n")
            content.append("Your tables are actively used. Consider:\n")
            content.append("- Adding inline documentation for complex queries\n")
            content.append("- Creating database documentation\n")
            content.append("- Setting up query performance monitoring\n")
        
        content.append(f"\n### 3. Regular Audits\n")
        content.append("Run this analysis periodically to:\n")
        content.append("- Track schema evolution\n")
        content.append("- Identify orphaned tables\n")
        content.append("- Maintain clean codebase\n")
        
        content.append("\n---\n")
        content.append(f"\n*Report generated by OrphanHunter SQL Mapper*\n")
        
        report = ''.join(content)
        
        # Write to file
        output_path.write_text(report, encoding='utf-8')
        return str(output_path)
    
    def generate_both_reports(self, analysis: Dict, output_dir: Path) -> Dict[str, str]:
        """Generate both reports and return their paths."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate table-map.md
        table_map_path = output_dir / "table-map.md"
        table_map = self.generate_table_map(analysis, table_map_path)
        
        # Generate connection report with date
        connection_report_path = output_dir / f"{self.date}-sql-php-connections.md"
        connection_report = self.generate_connection_report(analysis, connection_report_path)
        
        return {
            'table_map': table_map,
            'connection_report': connection_report
        }
