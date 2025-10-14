"""SQL dump parser for extracting table information."""
import re
from pathlib import Path
from typing import Set, Dict, List
import chardet

class SQLParser:
    """Parse SQL dump files to extract table information."""
    
    def __init__(self):
        # Patterns for extracting table names
        self.create_table_pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(\w+)`?',
            re.IGNORECASE
        )
        self.insert_into_pattern = re.compile(
            r'INSERT\s+INTO\s+`?(\w+)`?',
            re.IGNORECASE
        )
        self.drop_table_pattern = re.compile(
            r'DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?',
            re.IGNORECASE
        )
        
        # Column extraction
        self.column_pattern = re.compile(
            r'`(\w+)`\s+(?:INT|VARCHAR|TEXT|DATETIME|TIMESTAMP|DECIMAL|FLOAT|DOUBLE|BOOLEAN|ENUM|SET)',
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
            print(f"Error reading SQL file {file_path}: {e}")
            return ""
    
    def extract_tables(self, content: str) -> Set[str]:
        """Extract all table names from SQL content."""
        tables = set()
        
        for match in self.create_table_pattern.finditer(content):
            tables.add(match.group(1))
        
        for match in self.insert_into_pattern.finditer(content):
            tables.add(match.group(1))
        
        return tables
    
    def extract_table_columns(self, content: str, table_name: str) -> List[str]:
        """Extract column names for a specific table."""
        columns = []
        
        # Find the CREATE TABLE statement for this table
        pattern = re.compile(
            rf'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?{table_name}`?\s*\((.*?)\)(?:\s+ENGINE|\s+DEFAULT|\s*;)',
            re.IGNORECASE | re.DOTALL
        )
        
        match = pattern.search(content)
        if match:
            table_def = match.group(1)
            for col_match in self.column_pattern.finditer(table_def):
                columns.append(col_match.group(1))
        
        return columns
    
    def parse_sql_file(self, file_path: Path) -> Dict[str, List[str]]:
        """Parse SQL file and return table->columns mapping."""
        content = self.read_file_safe(file_path)
        
        if not content:
            return {}
        
        tables = self.extract_tables(content)
        table_info = {}
        
        for table in tables:
            columns = self.extract_table_columns(content, table)
            table_info[table] = columns
        
        return table_info


class SQLReferenceAnalyzer:
    """Analyze PHP files for SQL table references."""
    
    def __init__(self):
        # Patterns for finding table references in PHP
        self.query_patterns = [
            re.compile(r'FROM\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'JOIN\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'INTO\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'UPDATE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'TABLE\s+`?(\w+)`?', re.IGNORECASE),
            re.compile(r'DELETE\s+FROM\s+`?(\w+)`?', re.IGNORECASE),
        ]
        
        # Pattern for quoted table names in queries
        self.quoted_table_pattern = re.compile(r'[\'"](\w+)[\'"]')
    
    def find_table_references(self, content: str, known_tables: Set[str]) -> Dict[str, int]:
        """Find references to known tables in PHP content."""
        table_refs = {}
        
        for table in known_tables:
            count = 0
            
            # Direct table name matches in queries
            for pattern in self.query_patterns:
                count += len([m for m in pattern.finditer(content) if m.group(1) == table])
            
            # Table name in string literals
            # Look for table name surrounded by word boundaries
            word_pattern = re.compile(rf'\b{re.escape(table)}\b', re.IGNORECASE)
            count += len(word_pattern.findall(content))
            
            if count > 0:
                table_refs[table] = count
        
        return table_refs
    
    def analyze_file_for_tables(self, file_path: Path, known_tables: Set[str]) -> Dict[str, int]:
        """Analyze a single PHP file for table references."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
                return self.find_table_references(content, known_tables)
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return {}

