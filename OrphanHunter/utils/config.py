"""Configuration management for System Mapper."""
import json
from pathlib import Path
from typing import Dict, Any, List

class Config:
    """Manages application configuration."""
    
    def __init__(self):
        self.config_file = Path("system-mapper-config.json")
        self.config: Dict[str, Any] = self._load_default_config()
        self.load()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "root_directory": "",
            "admin_directory": "admin",
            "sql_dump_path": "",
            "config_php_path": "",  # Path to config.php for live database connection
            "use_live_database": False,  # Use live DB connection instead of SQL dump
            "backup_directory": "system-mapper-backups",
            "ignore_patterns": [".git", "node_modules", "__pycache__", "*.pyc", ".vscode", ".idea"],
            "ignore_dot_directories": True,  # Ignore all directories starting with .
            "blacklist_directories": [],  # User-defined directories to completely ignore
            "critical_files": ["index.php", "config.php", "db_connect.php"],
            "navigation_files": ["header.php", "footer.php", "navigation.php"],
            "orphan_criteria": {
                "not_in_navigation": True,
                "not_included_anywhere": True,
                "not_referenced": True,
                "min_reference_count": 0,
                "exclude_patterns": []
            },
            "scan_extensions": [".php", ".html", ".htm", ".js", ".ts", ".json", ".css"],
            "sql_extensions": [".sql"],
            "enable_verbose_references": True,  # Show detailed references with line numbers and snippets
            "enable_asset_analysis": True,  # Analyze orphaned JS, TS, JSON, CSS files
            "enable_css_analysis": True,  # Analyze CSS conflicts and overlaps
            "last_scan_date": None,
            "last_backup_path": None,
            "url_migration": {
                "internal_domains": [],  # Auto-populated + user-added
                "legacy_domains": [],  # Additional old domains to convert
                "replacement_format": "auto",  # auto|base_url|safe_url|asset_url|custom
                "custom_format": "",  # e.g., "$config['base_url']"
                "enabled_file_types": [".php", ".html", ".js", ".css", ".sql"],
                "external_whitelist": [],  # External URLs to never touch
                "deep_scan_mode": True,  # Scan all text files
                "last_migration_date": None,
                "last_migration_backup": None
            }
        }
    
    def load(self):
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"Error loading config: {e}")
    
    def save(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value
    
    def get_ignore_patterns(self) -> List[str]:
        """Get list of patterns to ignore during scanning."""
        return self.config.get("ignore_patterns", [])
    
    def get_critical_files(self) -> List[str]:
        """Get list of critical files that should never be deleted."""
        return self.config.get("critical_files", [])
    
    def get_blacklist_directories(self) -> List[str]:
        """Get list of blacklisted directories to ignore."""
        return self.config.get("blacklist_directories", [])
    
    def should_ignore_dot_directories(self) -> bool:
        """Check if dot directories should be ignored."""
        return self.config.get("ignore_dot_directories", True)

