"""SQL Table Mapper - Maps SQL tables to PHP file usage."""
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import chardet


class SQLTableMapper:
    """Comprehensive SQL table to PHP file mapper."""
    
    def __init__(self):
        # SQL table discovery patterns
        self.create_table_pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?',
            re.IGNORECASE
        )
        self.insert_into_pattern = re.compile(
            r'INSERT\s+INTO\s+`?(\w+)`?',
            re.IGNORECASE
        )
        self.alter_table_pattern = re.compile(
            r'ALTER\s+TABLE\s+`?(\w+)`?',
            re.IGNORECASE
        )
        
        # PHP SQL query patterns - comprehensive detection
        self.php_table_patterns = [
            re.compile(r'FROM\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'JOIN\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'INTO\s+`?(\w+)`?(?:\s+\(|;)', re.IGNORECASE),
            re.compile(r'UPDATE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'DELETE\s+FROM\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'TABLE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'TRUNCATE\s+(?:TABLE\s+)?`?(\w+)`?', re.IGNORECASE),
            re.compile(r'DESCRIBE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'SHOW\s+CREATE\s+TABLE\s+`?(\w+)`?', re.IGNORECASE),
        ]
        
        # Table name in string patterns
        self.string_table_pattern = re.compile(
            r'["\'](\w+)["\']',
            re.IGNORECASE
        )
        
        # Column extraction for table schema
        self.column_pattern = re.compile(
            r'`(\w+)`\s+(INT|VARCHAR|TEXT|DATETIME|TIMESTAMP|DECIMAL|FLOAT|DOUBLE|BOOLEAN|ENUM|SET|BIGINT|SMALLINT|TINYINT|MEDIUMINT|CHAR|BLOB|LONGTEXT|MEDIUMTEXT|TINYTEXT|DATE|TIME|YEAR|BINARY|VARBINARY|BIT|JSON)',
            re.IGNORECASE
        )
        
        # Primary key detection
        self.primary_key_pattern = re.compile(
            r'PRIMARY\s+KEY\s*\(\s*`?(\w+)`?\s*\)',
            re.IGNORECASE
        )
        
        # Foreign key detection
        self.foreign_key_pattern = re.compile(
            r'FOREIGN\s+KEY\s*\(\s*`?(\w+)`?\s*\)\s+REFERENCES\s+`?(\w+)`?\s*\(\s*`?(\w+)`?\s*\)',
            re.IGNORECASE
        )
        
        # Index detection
        self.index_pattern = re.compile(
            r'(?:KEY|INDEX)\s+`?(\w+)`?\s*\(',
            re.IGNORECASE
        )
        
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
    
    def discover_tables_from_sql(self, sql_content: str) -> Set[str]:
        """Discover all table names from SQL content."""
        tables = set()
        
        for match in self.create_table_pattern.finditer(sql_content):
            tables.add(match.group(1))
        
        for match in self.insert_into_pattern.finditer(sql_content):
            tables.add(match.group(1))
            
        for match in self.alter_table_pattern.finditer(sql_content):
            tables.add(match.group(1))
        
        return tables
    
    def extract_table_schema(self, sql_content: str, table_name: str) -> Dict:
        """Extract detailed schema information for a table."""
        schema = {
            'columns': [],
            'primary_keys': [],
            'foreign_keys': [],
            'indexes': [],
            'engine': None,
            'charset': None,
        }
        
        # Find the CREATE TABLE statement
        pattern = re.compile(
            rf'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?{re.escape(table_name)}`?\s*\((.*?)\)(?:\s+ENGINE\s*=\s*(\w+))?(?:\s+(?:DEFAULT\s+)?CHARSET\s*=\s*(\w+))?',
            re.IGNORECASE | re.DOTALL
        )
        
        match = pattern.search(sql_content)
        if match:
            table_def = match.group(1)
            schema['engine'] = match.group(2)
            schema['charset'] = match.group(3)
            
            # Extract columns with types
            for col_match in self.column_pattern.finditer(table_def):
                col_name = col_match.group(1)
                col_type = col_match.group(2)
                schema['columns'].append({'name': col_name, 'type': col_type})
            
            # Extract primary keys
            for pk_match in self.primary_key_pattern.finditer(table_def):
                schema['primary_keys'].append(pk_match.group(1))
            
            # Extract foreign keys
            for fk_match in self.foreign_key_pattern.finditer(table_def):
                schema['foreign_keys'].append({
                    'column': fk_match.group(1),
                    'references_table': fk_match.group(2),
                    'references_column': fk_match.group(3)
                })
            
            # Extract indexes
            for idx_match in self.index_pattern.finditer(table_def):
                schema['indexes'].append(idx_match.group(1))
        
        return schema
    
    def scan_sql_files(self, root_dir: Path) -> Dict[str, Dict]:
        """Scan all SQL files in directory and extract table information."""
        tables_info = {}
        
        # Find all .sql files
        sql_files = list(root_dir.rglob('*.sql'))
        
        for sql_file in sql_files:
            content = self.read_file_safe(sql_file)
            if not content:
                continue
            
            # Discover tables
            tables = self.discover_tables_from_sql(content)
            
            # Extract schema for each table
            for table in tables:
                if table not in tables_info:
                    schema = self.extract_table_schema(content, table)
                    tables_info[table] = {
                        'schema': schema,
                        'found_in': str(sql_file.relative_to(root_dir)),
                        'used_in_php': []
                    }
        
        return tables_info
    
    def find_table_usage_in_php(self, php_content: str, table_name: str) -> List[Dict]:
        """Find all usages of a table in PHP content with context."""
        usages = []
        lines = php_content.split('\n')
        
        # Search for table references
        for pattern in self.php_table_patterns:
            for match in pattern.finditer(php_content):
                if match.group(1).lower() == table_name.lower():
                    # Find line number
                    position = match.start()
                    line_num = php_content[:position].count('\n') + 1
                    
                    # Get context (line containing the match)
                    if line_num <= len(lines):
                        context = lines[line_num - 1].strip()
                        usages.append({
                            'line': line_num,
                            'context': context,
                            'pattern': pattern.pattern
                        })
        
        # Also search for table name in string literals (more lenient)
        table_pattern = re.compile(rf'\b{re.escape(table_name)}\b', re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if table_pattern.search(line):
                # Avoid duplicates
                if not any(u['line'] == i for u in usages):
                    usages.append({
                        'line': i,
                        'context': line.strip(),
                        'pattern': 'string_literal'
                    })
        
        return usages
    
    def scan_php_files(self, root_dir: Path, tables_info: Dict[str, Dict]) -> Dict[str, Dict]:
        """Scan PHP files and map table usage."""
        # Find all PHP files
        php_files = list(root_dir.rglob('*.php'))
        
        # Track usage
        for php_file in php_files:
            content = self.read_file_safe(php_file)
            if not content:
                continue
            
            relative_path = str(php_file.relative_to(root_dir))
            
            # Check each table
            for table_name, table_info in tables_info.items():
                usages = self.find_table_usage_in_php(content, table_name)
                
                if usages:
                    table_info['used_in_php'].append({
                        'file': relative_path,
                        'usages': usages,
                        'count': len(usages)
                    })
        
        return tables_info
    
    def analyze(self, root_dir: Path) -> Dict:
        """Complete analysis of SQL tables and PHP usage."""
        print(f"Scanning SQL files in {root_dir}...")
        tables_info = self.scan_sql_files(root_dir)
        
        print(f"Found {len(tables_info)} SQL tables")
        print(f"Scanning PHP files for table usage...")
        
        tables_info = self.scan_php_files(root_dir, tables_info)
        
        # Categorize tables
        used_tables = {name: info for name, info in tables_info.items() if info['used_in_php']}
        unused_tables = {name: info for name, info in tables_info.items() if not info['used_in_php']}
        
        # Calculate statistics
        total_php_files = len(list(root_dir.rglob('*.php')))
        total_sql_files = len(list(root_dir.rglob('*.sql')))
        
        return {
            'all_tables': tables_info,
            'used_tables': used_tables,
            'unused_tables': unused_tables,
            'statistics': {
                'total_tables': len(tables_info),
                'used_tables': len(used_tables),
                'unused_tables': len(unused_tables),
                'total_php_files': total_php_files,
                'total_sql_files': total_sql_files,
            }
        }
