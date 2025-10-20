#!/usr/bin/env python3
"""
SQL to PHP Mapper System
Analyzes SQL tables and their usage throughout PHP codebase
Generates comprehensive reports showing table connections and usage patterns
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, Counter
from datetime import datetime
import chardet

# Import existing analyzers from OrphanHunter
from OrphanHunter.analyzer.sql_parser import SQLParser, SQLReferenceAnalyzer
from OrphanHunter.analyzer.php_parser import PHPParser


class EnhancedSQLAnalyzer:
    """Enhanced SQL analyzer that extracts detailed table information and relationships."""
    
    def __init__(self):
        self.sql_parser = SQLParser()
        self.table_info = {}
        self.table_relationships = defaultdict(set)
        self.foreign_keys = defaultdict(list)
        
        # Enhanced patterns for table analysis
        self.foreign_key_pattern = re.compile(
            r'FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+`?(\w+)`?\s*\([^)]+\)',
            re.IGNORECASE
        )
        self.index_pattern = re.compile(
            r'(?:KEY|INDEX)\s+`?(\w+)`?\s*\([^)]+\)',
            re.IGNORECASE
        )
        self.primary_key_pattern = re.compile(
            r'PRIMARY\s+KEY\s*\([^)]+\)',
            re.IGNORECASE
        )
        
    def analyze_table_structure(self, content: str, table_name: str) -> Dict:
        """Analyze detailed table structure including relationships."""
        table_info = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': [],
            'engine': 'InnoDB',
            'charset': 'utf8mb4',
            'relationships': set()
        }
        
        # Find the CREATE TABLE statement
        pattern = re.compile(
            rf'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?{table_name}`?\s*\((.*?)\)(?:\s+ENGINE\s*=\s*(\w+))?(?:\s+(?:DEFAULT\s+)?CHARSET\s*=\s*(\w+))?',
            re.IGNORECASE | re.DOTALL
        )
        
        match = pattern.search(content)
        if not match:
            return table_info
            
        table_def = match.group(1)
        engine = match.group(2) or 'InnoDB'
        charset = match.group(3) or 'utf8mb4'
        
        table_info['engine'] = engine
        table_info['charset'] = charset
        
        # Extract columns with detailed information
        column_pattern = re.compile(
            r'`(\w+)`\s+((?:INT|VARCHAR|TEXT|DATETIME|TIMESTAMP|DECIMAL|FLOAT|DOUBLE|BOOLEAN|ENUM|SET|TINYINT|SMALLINT|MEDIUMINT|BIGINT|CHAR|BINARY|VARBINARY|BLOB|MEDIUMBLOB|LONGBLOB|MEDIUMTEXT|LONGTEXT|DATE|TIME|YEAR|JSON)(?:\([^)]+\))?(?:\s+UNSIGNED)?(?:\s+ZEROFILL)?)\s*([^,\n]*)',
            re.IGNORECASE
        )
        
        for col_match in column_pattern.finditer(table_def):
            column_name = col_match.group(1)
            column_type = col_match.group(2)
            column_attributes = col_match.group(3).strip()
            
            table_info['columns'].append({
                'name': column_name,
                'type': column_type,
                'attributes': column_attributes,
                'nullable': 'NOT NULL' not in column_attributes.upper(),
                'auto_increment': 'AUTO_INCREMENT' in column_attributes.upper(),
                'default': self._extract_default_value(column_attributes)
            })
        
        # Extract foreign keys
        for fk_match in self.foreign_key_pattern.finditer(table_def):
            referenced_table = fk_match.group(1)
            table_info['foreign_keys'].append(referenced_table)
            table_info['relationships'].add(referenced_table)
            self.table_relationships[table_name].add(referenced_table)
        
        # Extract indexes
        for idx_match in self.index_pattern.finditer(table_def):
            table_info['indexes'].append(idx_match.group(1))
        
        # Extract primary key
        pk_match = self.primary_key_pattern.search(table_def)
        if pk_match:
            pk_content = pk_match.group(0)
            pk_columns = re.findall(r'`(\w+)`', pk_content)
            table_info['primary_keys'] = pk_columns
        
        return table_info
    
    def _extract_default_value(self, attributes: str) -> Optional[str]:
        """Extract default value from column attributes."""
        default_match = re.search(r'DEFAULT\s+([^,\s]+)', attributes, re.IGNORECASE)
        if default_match:
            return default_match.group(1).strip("'\"")
        return None
    
    def analyze_sql_files(self, directory: Path) -> Dict[str, Dict]:
        """Analyze all SQL files in directory and extract comprehensive table information."""
        sql_files = list(directory.rglob('*.sql'))
        
        for sql_file in sql_files:
            print(f"Analyzing SQL file: {sql_file}")
            content = self.sql_parser.read_file_safe(sql_file)
            
            if not content:
                continue
                
            # Extract tables from this file
            tables = self.sql_parser.extract_tables(content)
            
            for table in tables:
                table_structure = self.analyze_table_structure(content, table)
                
                if table not in self.table_info:
                    self.table_info[table] = table_structure
                else:
                    # Merge information if table appears in multiple files
                    self.table_info[table]['columns'].extend(table_structure['columns'])
                    self.table_info[table]['foreign_keys'].extend(table_structure['foreign_keys'])
                    self.table_info[table]['relationships'].update(table_structure['relationships'])
        
        return self.table_info


class PHPTableMapper:
    """Maps PHP files to SQL table usage with detailed analysis."""
    
    def __init__(self):
        self.php_parser = PHPParser()
        self.sql_ref_analyzer = SQLReferenceAnalyzer()
        self.table_usage = defaultdict(lambda: defaultdict(list))
        self.file_table_map = defaultdict(set)
        self.query_patterns = self._build_enhanced_patterns()
        
    def _build_enhanced_patterns(self) -> List[re.Pattern]:
        """Build comprehensive patterns for detecting SQL table references."""
        patterns = [
            # Standard SQL operations
            re.compile(r'SELECT\s+.*?\s+FROM\s+`?(\w+)`?', re.IGNORECASE | re.DOTALL),
            re.compile(r'INSERT\s+INTO\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'UPDATE\s+`?(\w+)`?\s+SET', re.IGNORECASE),
            re.compile(r'DELETE\s+FROM\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'REPLACE\s+INTO\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'TRUNCATE\s+TABLE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?', re.IGNORECASE),
            re.compile(r'ALTER\s+TABLE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?', re.IGNORECASE),
            
            # JOIN operations
            re.compile(r'(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN\s+`?(\w+)`?', re.IGNORECASE),
            
            # Table references in strings
            re.compile(r'[\'"](\w+)[\'"](?=\s*(?:WHERE|ORDER|GROUP|LIMIT|;))', re.IGNORECASE),
            
            # ORM-style references
            re.compile(r'\$this->db->(?:get|insert|update|delete|query)\([\'"](\w+)[\'"]', re.IGNORECASE),
            re.compile(r'->table\([\'"](\w+)[\'"]', re.IGNORECASE),
            re.compile(r'->from\([\'"](\w+)[\'"]', re.IGNORECASE),
            
            # WordPress-style table references
            re.compile(r'\$wpdb->(\w+)', re.IGNORECASE),
            re.compile(r'wp_(\w+)', re.IGNORECASE),
            
            # Laravel/Eloquent patterns
            re.compile(r'DB::table\([\'"](\w+)[\'"]', re.IGNORECASE),
            re.compile(r'Model::table\([\'"](\w+)[\'"]', re.IGNORECASE),
        ]
        
        return patterns
    
    def analyze_php_file(self, file_path: Path, known_tables: Set[str]) -> Dict[str, List[Dict]]:
        """Analyze a PHP file for table references with context."""
        try:
            content = self.php_parser.read_file_safe(file_path)
            if not content:
                return {}
            
            file_table_usage = defaultdict(list)
            
            # Find all table references with context
            for table in known_tables:
                references = self._find_table_references_with_context(content, table, str(file_path))
                if references:
                    file_table_usage[table] = references
                    self.file_table_map[str(file_path)].add(table)
            
            return dict(file_table_usage)
            
        except Exception as e:
            print(f"Error analyzing PHP file {file_path}: {e}")
            return {}
    
    def _find_table_references_with_context(self, content: str, table: str, file_path: str) -> List[Dict]:
        """Find table references with surrounding context and operation type."""
        references = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            line_num = i + 1
            
            # Check each pattern
            for pattern in self.query_patterns:
                matches = pattern.finditer(line)
                for match in matches:
                    if match.group(1).lower() == table.lower():
                        # Determine operation type
                        operation = self._determine_operation_type(line)
                        
                        # Get context (surrounding lines)
                        context_start = max(0, i - 2)
                        context_end = min(len(lines), i + 3)
                        context = '\n'.join(lines[context_start:context_end])
                        
                        references.append({
                            'line_number': line_num,
                            'line_content': line.strip(),
                            'operation': operation,
                            'context': context,
                            'match_text': match.group(0)
                        })
            
            # Also check for table name as string literal
            if table.lower() in line.lower():
                # Make sure it's not a false positive
                if self._is_likely_table_reference(line, table):
                    operation = self._determine_operation_type(line)
                    context_start = max(0, i - 2)
                    context_end = min(len(lines), i + 3)
                    context = '\n'.join(lines[context_start:context_end])
                    
                    references.append({
                        'line_number': line_num,
                        'line_content': line.strip(),
                        'operation': operation or 'reference',
                        'context': context,
                        'match_text': table
                    })
        
        return references
    
    def _determine_operation_type(self, line: str) -> str:
        """Determine the type of SQL operation from the line."""
        line_upper = line.upper()
        
        if 'SELECT' in line_upper and 'FROM' in line_upper:
            return 'SELECT'
        elif 'INSERT' in line_upper:
            return 'INSERT'
        elif 'UPDATE' in line_upper:
            return 'UPDATE'
        elif 'DELETE' in line_upper:
            return 'DELETE'
        elif 'JOIN' in line_upper:
            return 'JOIN'
        elif 'CREATE' in line_upper:
            return 'CREATE'
        elif 'DROP' in line_upper:
            return 'DROP'
        elif 'ALTER' in line_upper:
            return 'ALTER'
        elif 'TRUNCATE' in line_upper:
            return 'TRUNCATE'
        else:
            return 'reference'
    
    def _is_likely_table_reference(self, line: str, table: str) -> bool:
        """Check if a line likely contains a table reference."""
        # Skip comments
        if line.strip().startswith('//') or line.strip().startswith('#'):
            return False
        
        # Check for SQL keywords nearby
        sql_keywords = ['SELECT', 'FROM', 'INSERT', 'UPDATE', 'DELETE', 'JOIN', 'TABLE']
        line_upper = line.upper()
        
        for keyword in sql_keywords:
            if keyword in line_upper:
                return True
        
        # Check for database-related function calls
        db_functions = ['query', 'execute', 'prepare', 'get', 'insert', 'update', 'delete']
        for func in db_functions:
            if func in line.lower():
                return True
        
        return False
    
    def analyze_directory(self, directory: Path, known_tables: Set[str]) -> Dict:
        """Analyze all PHP files in directory for table usage."""
        php_files = list(directory.rglob('*.php'))
        
        print(f"Analyzing {len(php_files)} PHP files for table usage...")
        
        for php_file in php_files:
            file_usage = self.analyze_php_file(php_file, known_tables)
            
            for table, references in file_usage.items():
                self.table_usage[table][str(php_file)] = references
        
        return dict(self.table_usage)


class SQLPHPReportGenerator:
    """Generates comprehensive reports showing SQL table usage and connections."""
    
    def __init__(self, table_info: Dict, table_usage: Dict, file_table_map: Dict):
        self.table_info = table_info
        self.table_usage = table_usage
        self.file_table_map = file_table_map
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_table_map_report(self) -> str:
        """Generate comprehensive table-map.md report."""
        report = []
        
        # Header
        report.append("# SQL Table Map Report")
        report.append(f"Generated: {self.timestamp}")
        report.append("")
        report.append("## Overview")
        report.append(f"- **Total Tables**: {len(self.table_info)}")
        report.append(f"- **Tables with PHP Usage**: {len([t for t in self.table_info.keys() if t in self.table_usage])}")
        report.append(f"- **Unused Tables**: {len([t for t in self.table_info.keys() if t not in self.table_usage])}")
        report.append("")
        
        # Table of Contents
        report.append("## Table of Contents")
        report.append("1. [Table Summary](#table-summary)")
        report.append("2. [Table Details](#table-details)")
        report.append("3. [Table Relationships](#table-relationships)")
        report.append("4. [Usage Statistics](#usage-statistics)")
        report.append("")
        
        # Table Summary
        report.append("## Table Summary")
        report.append("")
        report.append("| Table Name | Columns | Primary Key | Foreign Keys | PHP Usage | Status |")
        report.append("|------------|---------|-------------|--------------|-----------|--------|")
        
        for table_name, info in sorted(self.table_info.items()):
            columns_count = len(info.get('columns', []))
            primary_keys = ', '.join(info.get('primary_keys', []))
            foreign_keys = ', '.join(info.get('foreign_keys', []))
            php_usage = "✅ Used" if table_name in self.table_usage else "❌ Unused"
            usage_count = len(self.table_usage.get(table_name, {}))
            status = f"{usage_count} files" if usage_count > 0 else "No usage"
            
            report.append(f"| `{table_name}` | {columns_count} | {primary_keys or 'None'} | {foreign_keys or 'None'} | {php_usage} | {status} |")
        
        report.append("")
        
        # Table Details
        report.append("## Table Details")
        report.append("")
        
        for table_name, info in sorted(self.table_info.items()):
            report.append(f"### `{table_name}`")
            report.append("")
            
            # Basic info
            report.append(f"- **Engine**: {info.get('engine', 'Unknown')}")
            report.append(f"- **Charset**: {info.get('charset', 'Unknown')}")
            report.append(f"- **Columns**: {len(info.get('columns', []))}")
            report.append("")
            
            # Columns
            if info.get('columns'):
                report.append("#### Columns")
                report.append("")
                report.append("| Column | Type | Nullable | Default | Attributes |")
                report.append("|--------|------|----------|---------|------------|")
                
                for col in info['columns']:
                    nullable = "Yes" if col.get('nullable', True) else "No"
                    default = col.get('default', 'NULL')
                    attributes = col.get('attributes', '').strip()
                    
                    report.append(f"| `{col['name']}` | {col['type']} | {nullable} | {default} | {attributes} |")
                
                report.append("")
            
            # Relationships
            if info.get('foreign_keys'):
                report.append("#### Foreign Key Relationships")
                report.append("")
                for fk in info['foreign_keys']:
                    report.append(f"- References: `{fk}`")
                report.append("")
            
            # PHP Usage
            if table_name in self.table_usage:
                usage_files = self.table_usage[table_name]
                report.append(f"#### PHP Usage ({len(usage_files)} files)")
                report.append("")
                
                for file_path, references in usage_files.items():
                    file_name = Path(file_path).name
                    report.append(f"**{file_name}** ({len(references)} references)")
                    
                    # Group by operation type
                    ops = defaultdict(int)
                    for ref in references:
                        ops[ref['operation']] += 1
                    
                    op_summary = ', '.join([f"{op}: {count}" for op, count in ops.items()])
                    report.append(f"- Operations: {op_summary}")
                    report.append("")
            else:
                report.append("#### PHP Usage")
                report.append("❌ **No PHP usage detected**")
                report.append("")
            
            report.append("---")
            report.append("")
        
        # Table Relationships
        report.append("## Table Relationships")
        report.append("")
        
        relationships_found = False
        for table_name, info in self.table_info.items():
            if info.get('foreign_keys'):
                relationships_found = True
                report.append(f"### `{table_name}` Relationships")
                for fk in info['foreign_keys']:
                    report.append(f"- `{table_name}` → `{fk}`")
                report.append("")
        
        if not relationships_found:
            report.append("No foreign key relationships detected in the analyzed tables.")
            report.append("")
        
        # Usage Statistics
        report.append("## Usage Statistics")
        report.append("")
        
        used_tables = [t for t in self.table_info.keys() if t in self.table_usage]
        unused_tables = [t for t in self.table_info.keys() if t not in self.table_usage]
        
        report.append(f"### Used Tables ({len(used_tables)})")
        if used_tables:
            for table in sorted(used_tables):
                file_count = len(self.table_usage[table])
                total_refs = sum(len(refs) for refs in self.table_usage[table].values())
                report.append(f"- `{table}`: {file_count} files, {total_refs} references")
        else:
            report.append("No tables are being used in PHP code.")
        
        report.append("")
        report.append(f"### Unused Tables ({len(unused_tables)})")
        if unused_tables:
            report.append("⚠️ **These tables are not referenced in any PHP files:**")
            report.append("")
            for table in sorted(unused_tables):
                report.append(f"- `{table}`")
        else:
            report.append("✅ All tables are being used in PHP code.")
        
        report.append("")
        
        return '\n'.join(report)
    
    def generate_usage_report(self) -> str:
        """Generate detailed usage report showing connections breakdown."""
        report = []
        
        # Header
        report.append("# SQL to PHP Usage Report")
        report.append(f"Generated: {self.timestamp}")
        report.append("")
        
        # Summary
        total_files = len(set().union(*[files.keys() for files in self.table_usage.values()]))
        total_references = sum(
            sum(len(refs) for refs in table_files.values())
            for table_files in self.table_usage.values()
        )
        
        report.append("## Summary")
        report.append(f"- **Total PHP Files with SQL**: {total_files}")
        report.append(f"- **Total Table References**: {total_references}")
        report.append(f"- **Tables in Use**: {len(self.table_usage)}")
        report.append("")
        
        # File-by-File Breakdown
        report.append("## File-by-File Breakdown")
        report.append("")
        
        # Group by file
        file_usage = defaultdict(dict)
        for table, files in self.table_usage.items():
            for file_path, references in files.items():
                file_usage[file_path][table] = references
        
        for file_path in sorted(file_usage.keys()):
            file_name = Path(file_path).name
            tables_used = file_usage[file_path]
            
            report.append(f"### `{file_name}`")
            report.append(f"**Path**: `{file_path}`")
            report.append(f"**Tables Used**: {len(tables_used)}")
            report.append("")
            
            for table, references in tables_used.items():
                report.append(f"#### Table: `{table}` ({len(references)} references)")
                
                # Group references by operation
                ops = defaultdict(list)
                for ref in references:
                    ops[ref['operation']].append(ref)
                
                for operation, refs in ops.items():
                    report.append(f"**{operation.upper()}** ({len(refs)} occurrences):")
                    for ref in refs[:3]:  # Show first 3 references
                        report.append(f"- Line {ref['line_number']}: `{ref['line_content'][:80]}{'...' if len(ref['line_content']) > 80 else ''}`")
                    if len(refs) > 3:
                        report.append(f"- ... and {len(refs) - 3} more")
                    report.append("")
            
            report.append("---")
            report.append("")
        
        # Table-by-Table Breakdown
        report.append("## Table-by-Table Breakdown")
        report.append("")
        
        for table in sorted(self.table_usage.keys()):
            files = self.table_usage[table]
            total_refs = sum(len(refs) for refs in files.values())
            
            report.append(f"### `{table}` ({len(files)} files, {total_refs} references)")
            report.append("")
            
            for file_path, references in files.items():
                file_name = Path(file_path).name
                
                # Operation summary
                ops = Counter(ref['operation'] for ref in references)
                op_summary = ', '.join([f"{op}: {count}" for op, count in ops.most_common()])
                
                report.append(f"- **{file_name}**: {len(references)} refs ({op_summary})")
            
            report.append("")
        
        return '\n'.join(report)


def main():
    """Main function to run the SQL to PHP mapper system."""
    print("🔍 SQL to PHP Mapper System")
    print("=" * 50)
    
    # Get project directory
    project_dir = Path(input("Enter project directory path (or press Enter for current): ").strip() or ".")
    
    if not project_dir.exists():
        print(f"❌ Directory {project_dir} does not exist!")
        return
    
    print(f"📂 Analyzing project: {project_dir.absolute()}")
    
    # Initialize analyzers
    sql_analyzer = EnhancedSQLAnalyzer()
    php_mapper = PHPTableMapper()
    
    # Step 1: Analyze SQL files
    print("\n🗄️  Step 1: Analyzing SQL files...")
    table_info = sql_analyzer.analyze_sql_files(project_dir)
    
    if not table_info:
        print("❌ No SQL tables found! Make sure your project contains .sql files.")
        return
    
    print(f"✅ Found {len(table_info)} tables")
    
    # Step 2: Analyze PHP files for table usage
    print("\n🐘 Step 2: Analyzing PHP files for table usage...")
    known_tables = set(table_info.keys())
    table_usage = php_mapper.analyze_directory(project_dir, known_tables)
    
    print(f"✅ Analyzed PHP files, found usage for {len(table_usage)} tables")
    
    # Step 3: Generate reports
    print("\n📊 Step 3: Generating reports...")
    report_generator = SQLPHPReportGenerator(table_info, table_usage, php_mapper.file_table_map)
    
    # Generate table-map.md
    table_map_content = report_generator.generate_table_map_report()
    table_map_path = project_dir / "table-map.md"
    
    with open(table_map_path, 'w', encoding='utf-8') as f:
        f.write(table_map_content)
    
    print(f"✅ Generated: {table_map_path}")
    
    # Generate usage report
    usage_report_content = report_generator.generate_usage_report()
    usage_report_path = project_dir / f"sql-php-usage-report-{datetime.now().strftime('%Y%m%d')}.md"
    
    with open(usage_report_path, 'w', encoding='utf-8') as f:
        f.write(usage_report_content)
    
    print(f"✅ Generated: {usage_report_path}")
    
    # Summary
    print("\n📈 Summary:")
    print(f"- Total tables: {len(table_info)}")
    print(f"- Tables with PHP usage: {len(table_usage)}")
    print(f"- Unused tables: {len(table_info) - len(table_usage)}")
    
    unused_tables = [t for t in table_info.keys() if t not in table_usage]
    if unused_tables:
        print(f"\n⚠️  Unused tables: {', '.join(unused_tables)}")
    
    print(f"\n✅ Reports generated successfully!")
    print(f"📄 Table Map: {table_map_path}")
    print(f"📄 Usage Report: {usage_report_path}")


if __name__ == "__main__":
    main()