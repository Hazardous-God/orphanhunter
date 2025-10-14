"""URL detection and analysis for migration."""
import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
import chardet
from urllib.parse import urlparse


@dataclass
class URLInstance:
    """Represents a single URL found in code."""
    url: str
    file_path: Path
    line_number: int
    line_content: str
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    is_internal: bool = False
    is_whitelisted: bool = False
    domain: str = ""
    path: str = ""
    query_string: str = ""
    fragment: str = ""
    replacement: str = ""
    
    def __hash__(self):
        return hash((str(self.file_path), self.line_number, self.url))


@dataclass
class HelperFunction:
    """Represents a detected URL helper function."""
    name: str
    pattern: str
    file_found: str
    example: str


class URLAnalyzer:
    """Analyzes files to detect and classify URLs."""
    
    def __init__(self, internal_domains: List[str], external_whitelist: List[str] = None):
        self.internal_domains = [self._normalize_domain(d) for d in internal_domains]
        self.external_whitelist = external_whitelist or []
        self.url_instances: List[URLInstance] = []
        self.helper_functions: List[HelperFunction] = []
        
        # Comprehensive URL pattern - matches http:// and https://
        self.url_pattern = re.compile(
            r'(?:https?://)'  # Protocol
            r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'  # Subdomains
            r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'  # Domain
            r'(?:\.[a-zA-Z]{2,})'  # TLD
            r'(?::[0-9]{1,5})?'  # Optional port
            r'(?:[/?#][^\s\'"<>]*)?',  # Path, query, fragment
            re.IGNORECASE
        )
        
        # Patterns to detect URL helper functions in config.php/header.php
        self.helper_patterns = [
            (r"define\s*\(\s*['\"]BASE_URL['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", "BASE_URL"),
            (r"define\s*\(\s*['\"]SITE_URL['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", "SITE_URL"),
            (r"\$base_url\s*=\s*['\"]([^'\"]+)['\"]", "$base_url"),
            (r"\$site_url\s*=\s*['\"]([^'\"]+)['\"]", "$site_url"),
            (r"function\s+safe_url\s*\(", "safe_url()"),
            (r"function\s+asset_url\s*\(", "asset_url()"),
            (r"function\s+api_url\s*\(", "api_url()"),
            (r"function\s+url\s*\(", "url()"),
            (r"function\s+base_url\s*\(", "base_url()"),
        ]
    
    def scan_file(self, file_path: Path, root_dir: Path) -> List[URLInstance]:
        """Scan a single file for URLs."""
        try:
            content = self._read_file_safe(file_path)
            if not content:
                return []
            
            instances = []
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, start=1):
                # Find all URLs in this line
                for match in self.url_pattern.finditer(line):
                    url = match.group(0)
                    
                    # Skip if whitelisted
                    if self._is_whitelisted(url):
                        continue
                    
                    # Parse URL
                    parsed = urlparse(url)
                    domain = self._normalize_domain(f"{parsed.netloc}")
                    is_internal = domain in self.internal_domains
                    
                    # Get context lines
                    context_before = lines[max(0, line_num-4):line_num-1]
                    context_after = lines[line_num:min(len(lines), line_num+3)]
                    
                    instance = URLInstance(
                        url=url,
                        file_path=file_path.relative_to(root_dir),
                        line_number=line_num,
                        line_content=line.strip(),
                        context_before=context_before,
                        context_after=context_after,
                        is_internal=is_internal,
                        is_whitelisted=False,
                        domain=domain,
                        path=parsed.path,
                        query_string=parsed.query,
                        fragment=parsed.fragment
                    )
                    instances.append(instance)
            
            return instances
            
        except Exception as e:
            print(f"Error scanning {file_path}: {e}")
            return []
    
    def scan_directory(self, root_dir: Path, file_types: List[str], 
                      ignore_patterns: List[str] = None) -> List[URLInstance]:
        """Scan entire directory structure for URLs."""
        ignore_patterns = ignore_patterns or []
        self.url_instances.clear()
        
        for file_path in root_dir.rglob('*'):
            if not file_path.is_file():
                continue
            
            # Check if file type is enabled
            if file_types and file_path.suffix not in file_types:
                continue
            
            # Check ignore patterns
            if self._should_ignore(file_path, ignore_patterns):
                continue
            
            instances = self.scan_file(file_path, root_dir)
            self.url_instances.extend(instances)
        
        return self.url_instances
    
    def detect_helper_functions(self, config_files: List[Path]) -> List[HelperFunction]:
        """Detect URL helper functions in config/header files."""
        self.helper_functions.clear()
        
        for config_file in config_files:
            if not config_file.exists():
                continue
            
            try:
                content = self._read_file_safe(config_file)
                if not content:
                    continue
                
                for pattern, name in self.helper_patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        # Extract example line
                        line_start = content.rfind('\n', 0, match.start()) + 1
                        line_end = content.find('\n', match.end())
                        if line_end == -1:
                            line_end = len(content)
                        example = content[line_start:line_end].strip()
                        
                        helper = HelperFunction(
                            name=name,
                            pattern=pattern,
                            file_found=str(config_file),
                            example=example
                        )
                        
                        # Avoid duplicates
                        if not any(h.name == helper.name for h in self.helper_functions):
                            self.helper_functions.append(helper)
                
            except Exception as e:
                print(f"Error detecting helpers in {config_file}: {e}")
        
        return self.helper_functions
    
    def extract_domain_from_config(self, config_file: Path) -> List[str]:
        """Extract domain definitions from config.php."""
        domains = []
        
        if not config_file.exists():
            return domains
        
        try:
            content = self._read_file_safe(config_file)
            if not content:
                return domains
            
            # Look for common domain definition patterns
            patterns = [
                r"define\s*\(\s*['\"]BASE_URL['\"]\s*,\s*['\"]https?://([^'\"]+)['\"]",
                r"define\s*\(\s*['\"]SITE_URL['\"]\s*,\s*['\"]https?://([^'\"]+)['\"]",
                r"\$base_url\s*=\s*['\"]https?://([^'\"]+)['\"]",
                r"\$site_url\s*=\s*['\"]https?://([^'\"]+)['\"]",
                r"['\"]domain['\"]\s*=>\s*['\"]([^'\"]+)['\"]",
                r"['\"]url['\"]\s*=>\s*['\"]https?://([^'\"]+)['\"]",
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    domain = self._normalize_domain(match.group(1))
                    if domain and domain not in domains:
                        domains.append(domain)
        
        except Exception as e:
            print(f"Error extracting domain from {config_file}: {e}")
        
        return domains
    
    def verify_classification(self) -> Dict[str, any]:
        """Second-pass verification of URL classifications."""
        stats = {
            "total_urls": len(self.url_instances),
            "internal_urls": 0,
            "external_urls": 0,
            "whitelisted_urls": 0,
            "potential_issues": []
        }
        
        for instance in self.url_instances:
            if instance.is_whitelisted:
                stats["whitelisted_urls"] += 1
            elif instance.is_internal:
                stats["internal_urls"] += 1
            else:
                stats["external_urls"] += 1
            
            # Check for potential issues
            if instance.is_internal and not instance.path:
                stats["potential_issues"].append(
                    f"Internal URL with no path: {instance.url} in {instance.file_path}:{instance.line_number}"
                )
        
        return stats
    
    def get_internal_urls(self) -> List[URLInstance]:
        """Get all internal URLs to be migrated."""
        return [u for u in self.url_instances if u.is_internal and not u.is_whitelisted]
    
    def get_external_urls(self) -> List[URLInstance]:
        """Get all external URLs (will not be modified)."""
        return [u for u in self.url_instances if not u.is_internal]
    
    def get_urls_by_file(self) -> Dict[Path, List[URLInstance]]:
        """Group URLs by file."""
        by_file = {}
        for instance in self.url_instances:
            if instance.file_path not in by_file:
                by_file[instance.file_path] = []
            by_file[instance.file_path].append(instance)
        return by_file
    
    def _read_file_safe(self, file_path: Path) -> str:
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
    
    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing protocol and trailing slashes."""
        domain = domain.strip()
        domain = domain.replace('https://', '').replace('http://', '')
        domain = domain.rstrip('/')
        # Remove port if present for comparison
        domain = domain.split(':')[0]
        return domain
    
    def _is_whitelisted(self, url: str) -> bool:
        """Check if URL is in whitelist."""
        for whitelisted in self.external_whitelist:
            if url.startswith(whitelisted):
                return True
        return False
    
    def _should_ignore(self, file_path: Path, ignore_patterns: List[str]) -> bool:
        """Check if file should be ignored."""
        file_str = str(file_path)
        for pattern in ignore_patterns:
            if pattern in file_str or file_path.name.startswith('.'):
                return True
        return False

