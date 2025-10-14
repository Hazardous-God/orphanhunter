"""URL Migration Configuration Management."""
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class URLConfig:
    """Manages URL migration configuration and metadata."""
    
    def __init__(self, config_file: str = "url-migration-config.json"):
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = self._load_default_config()
        self.load()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Return default URL migration configuration."""
        return {
            "internal_domains": [],  # Auto-populated + user-added
            "legacy_domains": [],  # Additional old domains to convert
            "replacement_format": "auto",  # auto|base_url|safe_url|asset_url|custom
            "custom_format": "",  # e.g., "$config['base_url']"
            "enabled_file_types": [".php", ".html", ".js", ".css", ".sql"],
            "external_whitelist": [],  # External URLs to never touch
            "deep_scan_mode": True,  # Scan all text files
            "last_migration_date": None,
            "last_migration_backup": None,
            "migration_history": []  # List of past migrations
        }
    
    def load(self):
        """Load configuration from file."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"Error loading URL config: {e}")
    
    def save(self):
        """Save configuration to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving URL config: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value."""
        self.config[key] = value
    
    def add_internal_domain(self, domain: str):
        """Add a domain to internal domains list."""
        domain = self._normalize_domain(domain)
        if domain and domain not in self.config["internal_domains"]:
            self.config["internal_domains"].append(domain)
    
    def add_legacy_domain(self, domain: str):
        """Add a domain to legacy domains list."""
        domain = self._normalize_domain(domain)
        if domain and domain not in self.config["legacy_domains"]:
            self.config["legacy_domains"].append(domain)
    
    def remove_internal_domain(self, domain: str):
        """Remove a domain from internal domains list."""
        domain = self._normalize_domain(domain)
        if domain in self.config["internal_domains"]:
            self.config["internal_domains"].remove(domain)
    
    def remove_legacy_domain(self, domain: str):
        """Remove a domain from legacy domains list."""
        domain = self._normalize_domain(domain)
        if domain in self.config["legacy_domains"]:
            self.config["legacy_domains"].remove(domain)
    
    def get_all_internal_domains(self) -> List[str]:
        """Get all internal domains (internal + legacy)."""
        return self.config["internal_domains"] + self.config["legacy_domains"]
    
    def is_internal_domain(self, domain: str) -> bool:
        """Check if domain is internal."""
        domain = self._normalize_domain(domain)
        return domain in self.get_all_internal_domains()
    
    def add_external_whitelist(self, url: str):
        """Add URL to external whitelist."""
        if url and url not in self.config["external_whitelist"]:
            self.config["external_whitelist"].append(url)
    
    def is_whitelisted(self, url: str) -> bool:
        """Check if URL is whitelisted (should not be modified)."""
        for whitelisted in self.config["external_whitelist"]:
            if url.startswith(whitelisted):
                return True
        return False
    
    def set_replacement_format(self, format_type: str, custom_format: str = ""):
        """Set the replacement format to use."""
        valid_formats = ["auto", "base_url", "safe_url", "asset_url", "custom"]
        if format_type in valid_formats:
            self.config["replacement_format"] = format_type
            if format_type == "custom":
                self.config["custom_format"] = custom_format
    
    def get_replacement_format(self) -> tuple[str, str]:
        """Get replacement format and custom format if applicable."""
        return (
            self.config.get("replacement_format", "auto"),
            self.config.get("custom_format", "")
        )
    
    def set_enabled_file_types(self, file_types: List[str]):
        """Set enabled file types for scanning."""
        self.config["enabled_file_types"] = [
            ft if ft.startswith('.') else f'.{ft}' 
            for ft in file_types
        ]
    
    def get_enabled_file_types(self) -> List[str]:
        """Get enabled file types."""
        return self.config.get("enabled_file_types", [".php", ".html", ".js", ".css", ".sql"])
    
    def is_file_type_enabled(self, extension: str) -> bool:
        """Check if file type is enabled for scanning."""
        if not extension.startswith('.'):
            extension = f'.{extension}'
        return extension in self.get_enabled_file_types()
    
    def record_migration(self, backup_path: str, changes_count: int, files_affected: int):
        """Record a completed migration."""
        migration_record = {
            "date": datetime.now().isoformat(),
            "backup_path": backup_path,
            "changes_count": changes_count,
            "files_affected": files_affected
        }
        self.config["migration_history"].append(migration_record)
        self.config["last_migration_date"] = migration_record["date"]
        self.config["last_migration_backup"] = backup_path
    
    def get_migration_history(self) -> List[Dict]:
        """Get migration history."""
        return self.config.get("migration_history", [])
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing protocol and trailing slashes."""
        domain = domain.strip()
        # Remove protocol
        domain = domain.replace('https://', '').replace('http://', '')
        # Remove trailing slash
        domain = domain.rstrip('/')
        return domain
    
    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        self.config = self._load_default_config()

