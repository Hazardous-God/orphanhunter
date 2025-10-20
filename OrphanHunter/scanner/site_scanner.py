"""Live website scanner with SEMRush-like capabilities."""
import re
import time
import threading
import requests
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple, Callable
import logging
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class PageData:
    """Data structure for scanned page information."""
    url: str
    title: str = ""
    description: str = ""
    keywords: List[str] = field(default_factory=list)
    h1_tags: List[str] = field(default_factory=list)
    h2_tags: List[str] = field(default_factory=list)
    internal_links: Set[str] = field(default_factory=set)
    external_links: Set[str] = field(default_factory=set)
    images: List[Dict] = field(default_factory=list)
    status_code: int = 0
    response_time: float = 0.0
    content_length: int = 0
    content_type: str = ""
    last_modified: Optional[str] = None
    canonical_url: Optional[str] = None
    meta_robots: str = ""
    schema_markup: List[Dict] = field(default_factory=list)
    social_tags: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    scan_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SiteMetrics:
    """Overall site metrics and SEO data."""
    total_pages: int = 0
    crawlable_pages: int = 0
    error_pages: int = 0
    redirect_pages: int = 0
    avg_response_time: float = 0.0
    total_internal_links: int = 0
    total_external_links: int = 0
    unique_domains: Set[str] = field(default_factory=set)
    page_depth_distribution: Dict[int, int] = field(default_factory=dict)
    content_types: Dict[str, int] = field(default_factory=dict)
    status_codes: Dict[int, int] = field(default_factory=dict)
    seo_issues: List[str] = field(default_factory=list)
    keywords_found: Dict[str, int] = field(default_factory=dict)


class SiteScanner:
    """Advanced website scanner with SEO analysis capabilities."""
    
    def __init__(self, base_url: str, max_pages: int = 1000, max_depth: int = 5):
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.max_pages = max_pages
        self.max_depth = max_depth
        
        # Scanning state
        self.pages_data: Dict[str, PageData] = {}
        self.urls_to_scan: List[Tuple[str, int]] = [(base_url, 0)]  # (url, depth)
        self.scanned_urls: Set[str] = set()
        self.scanning = False
        self.scan_thread = None
        
        # Configuration
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'OrphanHunter-SiteScanner/1.0 (SEO Analysis Bot)'
        })
        self.request_delay = 1.0  # seconds between requests
        self.timeout = 10
        
        # Callbacks and monitoring
        self.progress_callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
        
        # Robots.txt compliance
        self.robots_parser = None
        self._load_robots_txt()
        
        # SEO patterns
        self.seo_patterns = {
            'phone': re.compile(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'social_links': re.compile(r'(?:facebook|twitter|instagram|linkedin|youtube|tiktok)\.com/[^\s"\'<>]+'),
        }
    
    def _load_robots_txt(self):
        """Load and parse robots.txt for the domain."""
        try:
            robots_url = f"{self.base_url}/robots.txt"
            self.robots_parser = RobotFileParser()
            self.robots_parser.set_url(robots_url)
            self.robots_parser.read()
            self.logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            self.logger.warning(f"Could not load robots.txt: {e}")
    
    def can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        if not self.robots_parser:
            return True
        return self.robots_parser.can_fetch(self.session.headers['User-Agent'], url)
    
    def add_progress_callback(self, callback: Callable):
        """Add callback for progress updates."""
        self.progress_callbacks.append(callback)
    
    def _notify_progress(self, message: str, progress: float = 0.0):
        """Notify progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(message, progress)
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")
    
    def start_scan(self, threaded: bool = True) -> bool:
        """Start the website scan."""
        if self.scanning:
            return False
        
        self.scanning = True
        self.scanned_urls.clear()
        self.pages_data.clear()
        
        if threaded:
            self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
            self.scan_thread.start()
        else:
            self._scan_loop()
        
        return True
    
    def stop_scan(self):
        """Stop the website scan."""
        self.scanning = False
        if self.scan_thread and self.scan_thread.is_alive():
            self.scan_thread.join(timeout=5)
    
    def _scan_loop(self):
        """Main scanning loop."""
        self.logger.info(f"Starting scan of {self.base_url}")
        self._notify_progress(f"Starting scan of {self.base_url}", 0.0)
        
        while self.scanning and self.urls_to_scan and len(self.scanned_urls) < self.max_pages:
            url, depth = self.urls_to_scan.pop(0)
            
            if url in self.scanned_urls or depth > self.max_depth:
                continue
            
            if not self.can_fetch(url):
                self.logger.info(f"Skipping {url} (robots.txt)")
                continue
            
            try:
                page_data = self._scan_page(url, depth)
                if page_data:
                    self.pages_data[url] = page_data
                    self._extract_links(page_data, depth)
                
                self.scanned_urls.add(url)
                
                # Progress update
                progress = len(self.scanned_urls) / min(self.max_pages, len(self.urls_to_scan) + len(self.scanned_urls))
                self._notify_progress(f"Scanned {len(self.scanned_urls)} pages", progress)
                
                # Respect rate limiting
                time.sleep(self.request_delay)
                
            except Exception as e:
                self.logger.error(f"Error scanning {url}: {e}")
        
        self.scanning = False
        self._notify_progress(f"Scan complete: {len(self.scanned_urls)} pages", 1.0)
        self.logger.info(f"Scan complete: {len(self.scanned_urls)} pages")
    
    def _scan_page(self, url: str, depth: int) -> Optional[PageData]:
        """Scan a single page and extract data."""
        start_time = time.time()
        
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response_time = time.time() - start_time
            
            page_data = PageData(
                url=url,
                status_code=response.status_code,
                response_time=response_time,
                content_length=len(response.content),
                content_type=response.headers.get('content-type', ''),
                last_modified=response.headers.get('last-modified')
            )
            
            # Only process HTML content
            if 'text/html' not in page_data.content_type:
                return page_data
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract basic SEO data
            self._extract_seo_data(soup, page_data)
            
            # Extract links
            self._extract_page_links(soup, page_data, url)
            
            # Extract images
            self._extract_images(soup, page_data, url)
            
            # Extract structured data
            self._extract_structured_data(soup, page_data)
            
            # SEO analysis
            self._analyze_seo_issues(page_data, soup)
            
            return page_data
            
        except requests.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            return PageData(url=url, errors=[str(e)])
        except Exception as e:
            self.logger.error(f"Parsing error for {url}: {e}")
            return PageData(url=url, errors=[str(e)])
    
    def _extract_seo_data(self, soup: BeautifulSoup, page_data: PageData):
        """Extract basic SEO data from page."""
        # Title
        title_tag = soup.find('title')
        if title_tag:
            page_data.title = title_tag.get_text().strip()
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            page_data.description = meta_desc.get('content', '').strip()
        
        # Meta keywords
        meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
        if meta_keywords:
            keywords = meta_keywords.get('content', '')
            page_data.keywords = [k.strip() for k in keywords.split(',') if k.strip()]
        
        # Headings
        page_data.h1_tags = [h1.get_text().strip() for h1 in soup.find_all('h1')]
        page_data.h2_tags = [h2.get_text().strip() for h2 in soup.find_all('h2')]
        
        # Canonical URL
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            page_data.canonical_url = canonical.get('href')
        
        # Meta robots
        meta_robots = soup.find('meta', attrs={'name': 'robots'})
        if meta_robots:
            page_data.meta_robots = meta_robots.get('content', '')
        
        # Social media tags (Open Graph, Twitter Cards)
        for meta in soup.find_all('meta'):
            property_attr = meta.get('property', '')
            name_attr = meta.get('name', '')
            content = meta.get('content', '')
            
            if property_attr.startswith('og:'):
                page_data.social_tags[property_attr] = content
            elif name_attr.startswith('twitter:'):
                page_data.social_tags[name_attr] = content
    
    def _extract_page_links(self, soup: BeautifulSoup, page_data: PageData, base_url: str):
        """Extract internal and external links from page."""
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            if not href or href.startswith('#'):
                continue
            
            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)
            
            # Clean URL (remove fragments)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            # Categorize as internal or external
            if parsed.netloc == self.domain or not parsed.netloc:
                page_data.internal_links.add(clean_url)
            else:
                page_data.external_links.add(clean_url)
    
    def _extract_images(self, soup: BeautifulSoup, page_data: PageData, base_url: str):
        """Extract image information from page."""
        for img in soup.find_all('img'):
            src = img.get('src')
            if not src:
                continue
            
            full_url = urljoin(base_url, src)
            
            img_data = {
                'src': full_url,
                'alt': img.get('alt', ''),
                'title': img.get('title', ''),
                'width': img.get('width'),
                'height': img.get('height')
            }
            page_data.images.append(img_data)
    
    def _extract_structured_data(self, soup: BeautifulSoup, page_data: PageData):
        """Extract structured data (JSON-LD, microdata)."""
        # JSON-LD
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                page_data.schema_markup.append(data)
            except (json.JSONDecodeError, AttributeError):
                continue
    
    def _analyze_seo_issues(self, page_data: PageData, soup: BeautifulSoup):
        """Analyze page for SEO issues."""
        issues = []
        
        # Title issues
        if not page_data.title:
            issues.append("Missing title tag")
        elif len(page_data.title) > 60:
            issues.append("Title too long (>60 characters)")
        elif len(page_data.title) < 30:
            issues.append("Title too short (<30 characters)")
        
        # Description issues
        if not page_data.description:
            issues.append("Missing meta description")
        elif len(page_data.description) > 160:
            issues.append("Meta description too long (>160 characters)")
        
        # Heading issues
        if not page_data.h1_tags:
            issues.append("Missing H1 tag")
        elif len(page_data.h1_tags) > 1:
            issues.append("Multiple H1 tags found")
        
        # Image issues
        for img in page_data.images:
            if not img['alt']:
                issues.append("Images missing alt text")
                break
        
        page_data.errors.extend(issues)
    
    def _extract_links(self, page_data: PageData, current_depth: int):
        """Add internal links to scanning queue."""
        for link in page_data.internal_links:
            if link not in self.scanned_urls and current_depth < self.max_depth:
                # Avoid duplicate entries
                if (link, current_depth + 1) not in self.urls_to_scan:
                    self.urls_to_scan.append((link, current_depth + 1))
    
    def get_site_metrics(self) -> SiteMetrics:
        """Calculate comprehensive site metrics."""
        metrics = SiteMetrics()
        
        if not self.pages_data:
            return metrics
        
        metrics.total_pages = len(self.pages_data)
        
        response_times = []
        
        for page in self.pages_data.values():
            # Status code distribution
            metrics.status_codes[page.status_code] = metrics.status_codes.get(page.status_code, 0) + 1
            
            # Content type distribution
            content_type = page.content_type.split(';')[0]  # Remove charset
            metrics.content_types[content_type] = metrics.content_types.get(content_type, 0) + 1
            
            # Response times
            if page.response_time > 0:
                response_times.append(page.response_time)
            
            # Link counts
            metrics.total_internal_links += len(page.internal_links)
            metrics.total_external_links += len(page.external_links)
            
            # External domains
            for link in page.external_links:
                domain = urlparse(link).netloc
                if domain:
                    metrics.unique_domains.add(domain)
            
            # Keywords
            for keyword in page.keywords:
                metrics.keywords_found[keyword] = metrics.keywords_found.get(keyword, 0) + 1
            
            # SEO issues
            metrics.seo_issues.extend(page.errors)
        
        # Calculate averages
        if response_times:
            metrics.avg_response_time = sum(response_times) / len(response_times)
        
        # Count page types
        metrics.crawlable_pages = sum(1 for p in self.pages_data.values() if p.status_code == 200)
        metrics.error_pages = sum(1 for p in self.pages_data.values() if p.status_code >= 400)
        metrics.redirect_pages = sum(1 for p in self.pages_data.values() if 300 <= p.status_code < 400)
        
        return metrics
    
    def export_data(self, format: str = 'json') -> str:
        """Export scan data in specified format."""
        if format == 'json':
            data = {
                'scan_info': {
                    'base_url': self.base_url,
                    'scan_date': datetime.now().isoformat(),
                    'pages_scanned': len(self.pages_data)
                },
                'pages': {}
            }
            
            for url, page_data in self.pages_data.items():
                data['pages'][url] = {
                    'title': page_data.title,
                    'description': page_data.description,
                    'status_code': page_data.status_code,
                    'response_time': page_data.response_time,
                    'internal_links': list(page_data.internal_links),
                    'external_links': list(page_data.external_links),
                    'h1_tags': page_data.h1_tags,
                    'h2_tags': page_data.h2_tags,
                    'images_count': len(page_data.images),
                    'errors': page_data.errors,
                    'keywords': page_data.keywords
                }
            
            return json.dumps(data, indent=2)
        
        return ""
    
    def save_to_file(self, filepath: str, format: str = 'json'):
        """Save scan data to file."""
        data = self.export_data(format)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data)


class SiteScannerWithSQL:
    """Site scanner with SQL database integration."""
    
    def __init__(self, base_url: str, db_connector=None):
        self.scanner = SiteScanner(base_url)
        self.db_connector = db_connector
        self.logger = logging.getLogger(__name__)
    
    def create_tables(self):
        """Create database tables for storing scan data."""
        if not self.db_connector or not self.db_connector.connected:
            return False
        
        try:
            # Sites table
            self.db_connector.execute_query("""
                CREATE TABLE IF NOT EXISTS scanned_sites (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    domain VARCHAR(255) NOT NULL,
                    base_url VARCHAR(500) NOT NULL,
                    scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    pages_found INT DEFAULT 0,
                    status ENUM('scanning', 'completed', 'error') DEFAULT 'scanning',
                    UNIQUE KEY unique_domain (domain)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Pages table
            self.db_connector.execute_query("""
                CREATE TABLE IF NOT EXISTS scanned_pages (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    site_id INT,
                    url VARCHAR(1000) NOT NULL,
                    title VARCHAR(500),
                    description TEXT,
                    status_code INT,
                    response_time DECIMAL(8,3),
                    content_length INT,
                    h1_count INT DEFAULT 0,
                    h2_count INT DEFAULT 0,
                    internal_links_count INT DEFAULT 0,
                    external_links_count INT DEFAULT 0,
                    images_count INT DEFAULT 0,
                    seo_issues TEXT,
                    scan_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (site_id) REFERENCES scanned_sites(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_url_per_site (site_id, url(767))
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Keywords table
            self.db_connector.execute_query("""
                CREATE TABLE IF NOT EXISTS page_keywords (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    page_id INT,
                    keyword VARCHAR(255),
                    frequency INT DEFAULT 1,
                    FOREIGN KEY (page_id) REFERENCES scanned_pages(id) ON DELETE CASCADE,
                    KEY idx_keyword (keyword)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # Links table
            self.db_connector.execute_query("""
                CREATE TABLE IF NOT EXISTS page_links (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    page_id INT,
                    target_url VARCHAR(1000),
                    link_type ENUM('internal', 'external') NOT NULL,
                    anchor_text TEXT,
                    FOREIGN KEY (page_id) REFERENCES scanned_pages(id) ON DELETE CASCADE,
                    KEY idx_link_type (link_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            self.logger.info("Database tables created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            return False
    
    def save_scan_to_db(self) -> bool:
        """Save scan results to database."""
        if not self.db_connector or not self.db_connector.connected:
            return False
        
        try:
            # Insert or update site record
            domain = urlparse(self.scanner.base_url).netloc
            site_query = """
                INSERT INTO scanned_sites (domain, base_url, pages_found, status) 
                VALUES (%s, %s, %s, 'completed')
                ON DUPLICATE KEY UPDATE 
                base_url = VALUES(base_url),
                pages_found = VALUES(pages_found),
                status = VALUES(status),
                scan_date = CURRENT_TIMESTAMP
            """
            
            self.db_connector.cursor.execute(site_query, (
                domain, 
                self.scanner.base_url, 
                len(self.scanner.pages_data)
            ))
            
            # Get site ID
            self.db_connector.cursor.execute(
                "SELECT id FROM scanned_sites WHERE domain = %s", 
                (domain,)
            )
            site_id = self.db_connector.cursor.fetchone()[0]
            
            # Clear existing pages for this site
            self.db_connector.cursor.execute(
                "DELETE FROM scanned_pages WHERE site_id = %s", 
                (site_id,)
            )
            
            # Insert pages
            for url, page_data in self.scanner.pages_data.items():
                page_query = """
                    INSERT INTO scanned_pages (
                        site_id, url, title, description, status_code, response_time,
                        content_length, h1_count, h2_count, internal_links_count,
                        external_links_count, images_count, seo_issues
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                self.db_connector.cursor.execute(page_query, (
                    site_id, url, page_data.title, page_data.description,
                    page_data.status_code, page_data.response_time,
                    page_data.content_length, len(page_data.h1_tags),
                    len(page_data.h2_tags), len(page_data.internal_links),
                    len(page_data.external_links), len(page_data.images),
                    json.dumps(page_data.errors)
                ))
                
                page_id = self.db_connector.cursor.lastrowid
                
                # Insert keywords
                for keyword in page_data.keywords:
                    self.db_connector.cursor.execute(
                        "INSERT INTO page_keywords (page_id, keyword) VALUES (%s, %s)",
                        (page_id, keyword)
                    )
                
                # Insert links (sample - limit to avoid too much data)
                all_links = list(page_data.internal_links)[:50] + list(page_data.external_links)[:50]
                for link in all_links:
                    link_type = 'internal' if link in page_data.internal_links else 'external'
                    self.db_connector.cursor.execute(
                        "INSERT INTO page_links (page_id, target_url, link_type) VALUES (%s, %s, %s)",
                        (page_id, link, link_type)
                    )
            
            self.db_connector.connection.commit()
            self.logger.info(f"Saved {len(self.scanner.pages_data)} pages to database")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving to database: {e}")
            self.db_connector.connection.rollback()
            return False
    
    def get_scan_history(self, domain: str = None) -> List[Dict]:
        """Get scan history from database."""
        if not self.db_connector or not self.db_connector.connected:
            return []
        
        try:
            if domain:
                query = """
                    SELECT s.*, COUNT(p.id) as actual_pages 
                    FROM scanned_sites s 
                    LEFT JOIN scanned_pages p ON s.id = p.site_id 
                    WHERE s.domain = %s 
                    GROUP BY s.id 
                    ORDER BY s.scan_date DESC
                """
                results = self.db_connector.execute_query(query, (domain,))
            else:
                query = """
                    SELECT s.*, COUNT(p.id) as actual_pages 
                    FROM scanned_sites s 
                    LEFT JOIN scanned_pages p ON s.id = p.site_id 
                    GROUP BY s.id 
                    ORDER BY s.scan_date DESC 
                    LIMIT 100
                """
                results = self.db_connector.execute_query(query)
            
            history = []
            for row in results:
                history.append({
                    'id': row[0],
                    'domain': row[1],
                    'base_url': row[2],
                    'scan_date': row[3],
                    'pages_found': row[4],
                    'status': row[5],
                    'actual_pages': row[6]
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Error getting scan history: {e}")
            return []