"""Live database connection using config.php credentials."""
import re
from pathlib import Path
from typing import Dict, Set, Optional, List, Tuple
import chardet
import time
import threading

class ConfigParser:
    """Parse config.php to extract database credentials."""
    
    def __init__(self):
        self.credentials = {
            'host': None,
            'user': None,
            'password': None,
            'database': None,
            'port': 3306
        }
        
        # Common patterns for database configuration in PHP
        self.patterns = {
            'host': [
                re.compile(r'DB_HOST[\'"]?\s*[,=]\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$db_host\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$host\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'[\'"]host[\'"]\s*=>\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            ],
            'user': [
                re.compile(r'DB_USER[\'"]?\s*[,=]\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$db_user\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$username\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'[\'"]user[\'"]\s*=>\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            ],
            'password': [
                re.compile(r'DB_PASS(?:WORD)?[\'"]?\s*[,=]\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE),
                re.compile(r'\$db_pass(?:word)?\s*=\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE),
                re.compile(r'\$password\s*=\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE),
                re.compile(r'[\'"]pass(?:word)?[\'"]\s*=>\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE),
            ],
            'database': [
                re.compile(r'DB_NAME[\'"]?\s*[,=]\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$db_name\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'\$database\s*=\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'[\'"]database[\'"]\s*=>\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
                re.compile(r'[\'"]dbname[\'"]\s*=>\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE),
            ],
            'port': [
                re.compile(r'DB_PORT[\'"]?\s*[,=]\s*[\'"]?(\d+)[\'"]?', re.IGNORECASE),
                re.compile(r'\$db_port\s*=\s*[\'"]?(\d+)[\'"]?', re.IGNORECASE),
                re.compile(r'[\'"]port[\'"]\s*=>\s*[\'"]?(\d+)[\'"]?', re.IGNORECASE),
            ]
        }
    
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
            print(f"Error reading config file {file_path}: {e}")
            return ""
    
    def parse_config(self, config_path: Path) -> Dict[str, Optional[str]]:
        """Parse config.php and extract database credentials."""
        content = self.read_file_safe(config_path)
        if not content:
            return self.credentials
        
        # Try each pattern for each credential type
        for cred_type, patterns in self.patterns.items():
            for pattern in patterns:
                match = pattern.search(content)
                if match:
                    value = match.group(1)
                    if cred_type == 'port':
                        self.credentials[cred_type] = int(value)
                    else:
                        self.credentials[cred_type] = value
                    break  # Found a match, move to next credential type
        
        return self.credentials
    
    def validate_credentials(self) -> Tuple[bool, str]:
        """Validate that we have minimum required credentials."""
        if not self.credentials['host']:
            return False, "Database host not found in config"
        if not self.credentials['user']:
            return False, "Database user not found in config"
        if not self.credentials['database']:
            return False, "Database name not found in config"
        
        return True, "Credentials validated"


class LiveDatabaseConnector:
    """Connect to live MySQL/MariaDB database and analyze."""
    
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.connected = False
        self.tables: Set[str] = set()
        self.table_structure: Dict[str, List[str]] = {}
        self.url_data: Dict[str, List[Tuple[str, int, str]]] = {}  # url -> [(table, row_id, column)]
        self.credentials: Dict[str, Optional[str]] = {}
        self.monitoring = False
        self.monitor_thread = None
        self.monitor_callback = None
        self.last_check_time = 0
        
    def connect(self, credentials: Dict[str, Optional[str]]) -> Tuple[bool, str]:
        """Connect to database using credentials with proper charset handling."""
        try:
            import mysql.connector
        except ImportError:
            return False, "mysql-connector-python not installed. Run: pip install mysql-connector-python"
        
        try:
            self.connection = mysql.connector.connect(
                host=credentials['host'],
                user=credentials['user'],
                password=credentials['password'] or '',
                database=credentials['database'],
                port=credentials.get('port', 3306),
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                use_unicode=True,
                autocommit=False
            )
            self.cursor = self.connection.cursor(buffered=True)
            self.connected = True
            self.credentials = credentials.copy()
            return True, f"Connected to {credentials['database']} on {credentials['host']}"
        
        except mysql.connector.Error as e:
            return False, f"Database connection error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
    
    def disconnect(self):
        """Close database connection."""
        self.stop_monitoring()
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.connected = False
    
    def get_tables(self) -> Set[str]:
        """Get list of all tables in database."""
        if not self.connected:
            return set()
        
        try:
            self.cursor.execute("SHOW TABLES")
            tables = set()
            for (table_name,) in self.cursor:
                tables.add(table_name)
            self.tables = tables
            return tables
        except Exception as e:
            print(f"Error getting tables: {e}")
            return set()
    
    def get_table_columns(self, table_name: str) -> List[str]:
        """Get column names for a table."""
        if not self.connected:
            return []
        
        try:
            self.cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
            columns = []
            for (column_name, *_) in self.cursor:
                columns.append(column_name)
            return columns
        except Exception as e:
            print(f"Error getting columns for {table_name}: {e}")
            return []
    
    def scan_for_urls(self, file_extensions: Set[str] = None) -> Dict[str, List[Tuple[str, int, str]]]:
        """Scan all tables for URL/file references."""
        if not self.connected:
            return {}
        
        file_extensions = file_extensions or {'.php', '.html', '.htm', '.js', '.ts'}
        url_pattern = re.compile(
            r'(?:https?://[^\s\'"]+|/[a-zA-Z0-9_\-/]+\.[a-zA-Z]+|[a-zA-Z0-9_\-/]+\.(?:php|html|htm|js|ts|css))',
            re.IGNORECASE
        )
        
        self.url_data.clear()
        tables = self.get_tables()
        
        for table in tables:
            try:
                # Get all text/varchar columns
                columns = self.get_table_columns(table)
                text_columns = []
                
                for col in columns:
                    # Get column type - use parameterized query to prevent SQL injection
                    query = "SHOW COLUMNS FROM `{}` WHERE Field = %s".format(table)
                    self.cursor.execute(query, (col,))
                    result = self.cursor.fetchone()
                    if result:
                        col_type = result[1].lower()
                        if any(t in col_type for t in ['char', 'text', 'varchar']):
                            text_columns.append(col)
                
                if not text_columns:
                    continue
                
                # Build query to scan text columns
                column_list = ', '.join([f"`{col}`" for col in text_columns])
                id_col = 'id' if 'id' in columns else columns[0]  # Use 'id' or first column
                
                query = f"SELECT `{id_col}`, {column_list} FROM `{table}`"
                self.cursor.execute(query)
                
                for row in self.cursor:
                    row_id = row[0]
                    for i, value in enumerate(row[1:], 1):
                        if value and isinstance(value, str):
                            # Search for URLs/file paths
                            matches = url_pattern.findall(value)
                            for match in matches:
                                # Clean up URL
                                url = match.strip('/')
                                # Remove query strings
                                url = re.split(r'[?#]', url)[0]
                                
                                # Skip external full URLs
                                if url.startswith(('http://', 'https://')):
                                    # Extract path
                                    parts = url.split('/', 3)
                                    if len(parts) > 3:
                                        url = parts[3]
                                    else:
                                        continue
                                
                                if url and any(url.endswith(ext) for ext in file_extensions):
                                    if url not in self.url_data:
                                        self.url_data[url] = []
                                    self.url_data[url].append((table, row_id, text_columns[i-1]))
            
            except Exception as e:
                print(f"Error scanning table {table}: {e}")
                continue
        
        return self.url_data
    
    def get_url_references(self, url: str) -> List[Tuple[str, int, str]]:
        """Get all database references for a specific URL."""
        return self.url_data.get(url, [])
    
    def cross_reference_files(self, known_files: Set[str]) -> Dict:
        """Cross-reference found URLs with known files."""
        results = {
            'matched': [],
            'unmatched_db': [],
            'unmatched_files': []
        }
        
        for url in self.url_data.keys():
            normalized = url.replace('\\', '/')
            
            # Try exact match
            if normalized in known_files:
                results['matched'].append({
                    'url': url,
                    'file': normalized,
                    'db_refs': len(self.url_data[url])
                })
            else:
                # Try partial matches
                found = False
                for file in known_files:
                    if file.endswith(normalized) or normalized.endswith(file):
                        results['matched'].append({
                            'url': url,
                            'file': file,
                            'db_refs': len(self.url_data[url])
                        })
                        found = True
                        break
                
                if not found:
                    results['unmatched_db'].append(url)
        
        # Find files not in database
        for file in known_files:
            matched = False
            for url in self.url_data.keys():
                if file.endswith(url) or url.endswith(file):
                    matched = True
                    break
            if not matched:
                results['unmatched_files'].append(file)
        
        return results
    
    def get_statistics(self) -> Dict:
        """Get database statistics."""
        if not self.connected:
            return {}
        
        return {
            'connected': self.connected,
            'total_tables': len(self.tables),
            'urls_found': len(self.url_data),
            'total_url_references': sum(len(refs) for refs in self.url_data.values()),
            'monitoring': self.monitoring
        }
    
    def check_connection(self) -> bool:
        """Check if database connection is alive."""
        if not self.connection:
            return False
        
        try:
            self.connection.ping(reconnect=False, attempts=1, delay=0)
            return True
        except Exception:
            return False
    
    def reconnect(self) -> Tuple[bool, str]:
        """Attempt to reconnect to the database."""
        if not self.credentials:
            return False, "No credentials stored for reconnection"
        
        # Close existing connection
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
        
        self.connected = False
        
        # Reconnect
        return self.connect(self.credentials)
    
    def ensure_connection(self) -> Tuple[bool, str]:
        """Ensure connection is alive, reconnect if necessary."""
        if self.check_connection():
            return True, "Connection is active"
        
        return self.reconnect()
    
    def start_monitoring(self, interval: int = 30, callback=None):
        """Start live monitoring of database connection.
        
        Args:
            interval: Check interval in seconds
            callback: Function to call when connection status changes
        """
        if self.monitoring:
            return
        
        self.monitoring = True
        self.monitor_callback = callback
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop live monitoring."""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
            self.monitor_thread = None
    
    def _monitor_loop(self, interval: int):
        """Internal monitoring loop."""
        while self.monitoring:
            current_time = time.time()
            
            # Check connection health
            was_connected = self.connected
            is_alive = self.check_connection()
            
            if not is_alive and was_connected:
                # Connection lost, attempt reconnect
                success, message = self.reconnect()
                if self.monitor_callback:
                    self.monitor_callback('reconnect', success, message)
            elif is_alive and not was_connected:
                # Connection restored
                self.connected = True
                if self.monitor_callback:
                    self.monitor_callback('connected', True, 'Connection restored')
            
            self.last_check_time = current_time
            
            # Sleep in small intervals to allow quick shutdown
            for _ in range(interval * 10):
                if not self.monitoring:
                    break
                time.sleep(0.1)


class DatabaseAnalyzer:
    """High-level database analyzer combining config parsing and live connection."""
    
    def __init__(self):
        self.config_parser = ConfigParser()
        self.connector = LiveDatabaseConnector()
        self.credentials = {}
    
    def load_from_config(self, config_path: Path) -> Tuple[bool, str]:
        """Load credentials from config.php."""
        if not config_path.exists():
            return False, f"Config file not found: {config_path}"
        
        self.credentials = self.config_parser.parse_config(config_path)
        valid, message = self.config_parser.validate_credentials()
        
        if not valid:
            return False, message
        
        return True, f"Credentials loaded from {config_path.name}"
    
    def connect_and_analyze(self, known_files: Set[str]) -> Tuple[bool, str, Dict]:
        """Connect to database and perform analysis."""
        # Connect
        success, message = self.connector.connect(self.credentials)
        if not success:
            return False, message, {}
        
        # Get tables
        tables = self.connector.get_tables()
        
        # Scan for URLs
        url_data = self.connector.scan_for_urls()
        
        # Cross-reference with files
        cross_ref = self.connector.cross_reference_files(known_files)
        
        # Get statistics
        stats = self.connector.get_statistics()
        
        result = {
            'tables': tables,
            'url_data': url_data,
            'cross_reference': cross_ref,
            'statistics': stats
        }
        
        return True, f"Analysis complete: {len(url_data)} URLs found in database", result
    
    def disconnect(self):
        """Disconnect from database."""
        self.connector.disconnect()

