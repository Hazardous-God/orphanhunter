"""Live website scanner and crawler for SEO and content analysis."""
import re
import requests
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse
from bs4 import BeautifulSoup
import time
import threading
from datetime import datetime
from collections import deque


class PageInfo:
    """Information about a crawled page."""
    
    def __init__(self, url: str):
        self.url = url
        self.status_code: Optional[int] = None
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.keywords: Optional[str] = None
        self.h1_tags: List[str] = []
        self.h2_tags: List[str] = []
        self.links: Set[str] = set()
        self.images: Set[str] = set()
        self.scripts: Set[str] = set()
        self.stylesheets: Set[str] = set()
        self.content_length: int = 0
        self.load_time: float = 0
        self.last_modified: Optional[str] = None
        self.canonical_url: Optional[str] = None
        self.meta_robots: Optional[str] = None
        self.response_headers: Dict[str, str] = {}
        self.crawl_time: datetime = datetime.now()
        self.error: Optional[str] = None
        
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            'url': self.url,
            'status_code': self.status_code,
            'title': self.title,
            'description': self.description,
            'keywords': self.keywords,
            'h1_tags': '|'.join(self.h1_tags) if self.h1_tags else None,
            'h2_tags': '|'.join(self.h2_tags) if self.h2_tags else None,
            'links': '|'.join(self.links) if self.links else None,
            'images': '|'.join(self.images) if self.images else None,
            'scripts': '|'.join(self.scripts) if self.scripts else None,
            'stylesheets': '|'.join(self.stylesheets) if self.stylesheets else None,
            'content_length': self.content_length,
            'load_time': self.load_time,
            'last_modified': self.last_modified,
            'canonical_url': self.canonical_url,
            'meta_robots': self.meta_robots,
            'crawl_time': self.crawl_time.isoformat(),
            'error': self.error
        }


class SiteScanner:
    """Crawl and analyze websites similar to SEMRush."""
    
    def __init__(self, base_url: str, max_pages: int = 100):
        self.base_url = self._normalize_url(base_url)
        self.domain = urlparse(self.base_url).netloc
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.to_visit: deque = deque([self.base_url])
        self.pages: Dict[str, PageInfo] = {}
        self.crawling = False
        self.crawl_thread = None
        self.crawl_callback = None
        self.user_agent = 'OrphanHunter/1.2 (SEO Scanner; +https://github.com/Hazardous-God/orphanhunter)'
        self.delay_between_requests = 1.0  # Polite crawling delay in seconds
        self.timeout = 10  # Request timeout in seconds
        self.follow_external = False  # Whether to follow external links
        
    def _normalize_url(self, url: str) -> str:
        """Normalize URL to ensure consistency."""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        parsed = urlparse(url)
        # Remove fragment and ensure consistent format
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/') if parsed.path != '/' else '/',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and should be crawled."""
        if not url:
            return False
        
        parsed = urlparse(url)
        
        # Check if it's a valid HTTP(S) URL
        if parsed.scheme not in ('http', 'https'):
            return False
        
        # Check if it's the same domain (unless following external links)
        if not self.follow_external and parsed.netloc != self.domain:
            return False
        
        # Skip common non-HTML resources
        skip_extensions = {
            '.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.webp',
            '.pdf', '.zip', '.tar', '.gz', '.rar',
            '.mp3', '.mp4', '.avi', '.mov',
            '.css', '.js', '.xml', '.json',
            '.woff', '.woff2', '.ttf', '.eot'
        }
        
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            return False
        
        return True
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> Set[str]:
        """Extract all links from HTML content."""
        links = set()
        
        for tag in soup.find_all('a', href=True):
            href = tag['href']
            # Convert relative URLs to absolute
            absolute_url = urljoin(base_url, href)
            normalized = self._normalize_url(absolute_url)
            
            if self._is_valid_url(normalized):
                links.add(normalized)
        
        return links
    
    def _extract_page_info(self, url: str, response: requests.Response) -> PageInfo:
        """Extract information from a web page."""
        page = PageInfo(url)
        page.status_code = response.status_code
        page.content_length = len(response.content)
        page.response_headers = dict(response.headers)
        page.last_modified = response.headers.get('Last-Modified')
        
        if response.status_code != 200:
            page.error = f"HTTP {response.status_code}"
            return page
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            if title_tag:
                page.title = title_tag.get_text(strip=True)
            
            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                page.description = meta_desc['content']
            
            # Extract meta keywords
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords and meta_keywords.get('content'):
                page.keywords = meta_keywords['content']
            
            # Extract canonical URL
            canonical = soup.find('link', attrs={'rel': 'canonical'})
            if canonical and canonical.get('href'):
                page.canonical_url = canonical['href']
            
            # Extract meta robots
            meta_robots = soup.find('meta', attrs={'name': 'robots'})
            if meta_robots and meta_robots.get('content'):
                page.meta_robots = meta_robots['content']
            
            # Extract H1 tags
            page.h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
            
            # Extract H2 tags
            page.h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
            
            # Extract links
            page.links = self._extract_links(soup, url)
            
            # Extract images
            for img in soup.find_all('img', src=True):
                img_url = urljoin(url, img['src'])
                page.images.add(img_url)
            
            # Extract scripts
            for script in soup.find_all('script', src=True):
                script_url = urljoin(url, script['src'])
                page.scripts.add(script_url)
            
            # Extract stylesheets
            for link in soup.find_all('link', rel='stylesheet', href=True):
                css_url = urljoin(url, link['href'])
                page.stylesheets.add(css_url)
        
        except Exception as e:
            page.error = f"Parsing error: {str(e)}"
        
        return page
    
    def crawl_page(self, url: str) -> Optional[PageInfo]:
        """Crawl a single page."""
        if url in self.visited_urls:
            return None
        
        self.visited_urls.add(url)
        
        try:
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            start_time = time.time()
            response = requests.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
            end_time = time.time()
            
            page = self._extract_page_info(url, response)
            page.load_time = end_time - start_time
            
            self.pages[url] = page
            
            # Add new links to crawl queue
            if page.links:
                for link in page.links:
                    if link not in self.visited_urls and link not in self.to_visit:
                        self.to_visit.append(link)
            
            return page
        
        except requests.RequestException as e:
            page = PageInfo(url)
            page.error = f"Request error: {str(e)}"
            self.pages[url] = page
            return page
        
        except Exception as e:
            page = PageInfo(url)
            page.error = f"Unexpected error: {str(e)}"
            self.pages[url] = page
            return page
    
    def start_crawl(self, callback=None):
        """Start crawling in a background thread."""
        if self.crawling:
            return
        
        self.crawling = True
        self.crawl_callback = callback
        self.crawl_thread = threading.Thread(target=self._crawl_loop, daemon=True)
        self.crawl_thread.start()
    
    def stop_crawl(self):
        """Stop the crawling process."""
        self.crawling = False
        if self.crawl_thread:
            self.crawl_thread.join(timeout=10)
            self.crawl_thread = None
    
    def _crawl_loop(self):
        """Main crawling loop."""
        while self.crawling and self.to_visit and len(self.visited_urls) < self.max_pages:
            url = self.to_visit.popleft()
            
            if url in self.visited_urls:
                continue
            
            page = self.crawl_page(url)
            
            if self.crawl_callback:
                self.crawl_callback('page_crawled', page)
            
            # Polite delay between requests
            if self.crawling and self.to_visit:
                time.sleep(self.delay_between_requests)
        
        self.crawling = False
        if self.crawl_callback:
            self.crawl_callback('crawl_complete', {
                'total_pages': len(self.pages),
                'successful': sum(1 for p in self.pages.values() if p.status_code == 200),
                'errors': sum(1 for p in self.pages.values() if p.error is not None)
            })
    
    def get_statistics(self) -> Dict:
        """Get crawl statistics."""
        total_pages = len(self.pages)
        successful = sum(1 for p in self.pages.values() if p.status_code == 200)
        errors = sum(1 for p in self.pages.values() if p.error is not None)
        
        avg_load_time = 0
        if successful > 0:
            avg_load_time = sum(p.load_time for p in self.pages.values() if p.status_code == 200) / successful
        
        return {
            'total_pages': total_pages,
            'successful': successful,
            'errors': errors,
            'pending': len(self.to_visit),
            'avg_load_time': avg_load_time,
            'crawling': self.crawling
        }
    
    def get_pages_with_issues(self) -> List[PageInfo]:
        """Get pages with errors or issues."""
        issues = []
        
        for page in self.pages.values():
            if page.error or page.status_code != 200:
                issues.append(page)
            elif not page.title:
                issues.append(page)
            elif not page.description:
                issues.append(page)
        
        return issues
    
    def get_all_pages(self) -> List[PageInfo]:
        """Get all crawled pages."""
        return list(self.pages.values())


class SiteScannerDB:
    """Store site scanner results in database."""
    
    def __init__(self, db_connector):
        """Initialize with a database connector instance.
        
        Args:
            db_connector: LiveDatabaseConnector instance
        """
        self.db = db_connector
        self.table_name = 'site_scanner_pages'
    
    def ensure_table_exists(self) -> Tuple[bool, str]:
        """Create the scanner table if it doesn't exist."""
        if not self.db.connected:
            return False, "Database not connected"
        
        try:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.table_name}` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `url` VARCHAR(2048) NOT NULL,
                `domain` VARCHAR(255) NOT NULL,
                `status_code` INT,
                `title` VARCHAR(512),
                `description` TEXT,
                `keywords` TEXT,
                `h1_tags` TEXT,
                `h2_tags` TEXT,
                `links` LONGTEXT,
                `images` LONGTEXT,
                `scripts` LONGTEXT,
                `stylesheets` LONGTEXT,
                `content_length` INT,
                `load_time` FLOAT,
                `last_modified` VARCHAR(255),
                `canonical_url` VARCHAR(2048),
                `meta_robots` VARCHAR(255),
                `crawl_time` DATETIME,
                `error` TEXT,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX `idx_url` (`url`(255)),
                INDEX `idx_domain` (`domain`),
                INDEX `idx_status` (`status_code`),
                INDEX `idx_crawl_time` (`crawl_time`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            
            self.db.cursor.execute(create_table_sql)
            self.db.connection.commit()
            return True, f"Table '{self.table_name}' ready"
        
        except Exception as e:
            return False, f"Error creating table: {str(e)}"
    
    def save_page(self, page: PageInfo) -> Tuple[bool, str]:
        """Save or update a page in the database."""
        if not self.db.connected:
            return False, "Database not connected"
        
        try:
            domain = urlparse(page.url).netloc
            page_data = page.to_dict()
            
            # Use INSERT ... ON DUPLICATE KEY UPDATE to handle both insert and update
            insert_sql = f"""
            INSERT INTO `{self.table_name}` (
                url, domain, status_code, title, description, keywords,
                h1_tags, h2_tags, links, images, scripts, stylesheets,
                content_length, load_time, last_modified, canonical_url,
                meta_robots, crawl_time, error
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) ON DUPLICATE KEY UPDATE
                status_code = VALUES(status_code),
                title = VALUES(title),
                description = VALUES(description),
                keywords = VALUES(keywords),
                h1_tags = VALUES(h1_tags),
                h2_tags = VALUES(h2_tags),
                links = VALUES(links),
                images = VALUES(images),
                scripts = VALUES(scripts),
                stylesheets = VALUES(stylesheets),
                content_length = VALUES(content_length),
                load_time = VALUES(load_time),
                last_modified = VALUES(last_modified),
                canonical_url = VALUES(canonical_url),
                meta_robots = VALUES(meta_robots),
                crawl_time = VALUES(crawl_time),
                error = VALUES(error),
                updated_at = CURRENT_TIMESTAMP
            """
            
            self.db.cursor.execute(insert_sql, (
                page.url,
                domain,
                page.status_code,
                page.title,
                page.description,
                page.keywords,
                page_data['h1_tags'],
                page_data['h2_tags'],
                page_data['links'],
                page_data['images'],
                page_data['scripts'],
                page_data['stylesheets'],
                page.content_length,
                page.load_time,
                page.last_modified,
                page.canonical_url,
                page.meta_robots,
                page.crawl_time,
                page.error
            ))
            
            self.db.connection.commit()
            return True, f"Saved page: {page.url}"
        
        except Exception as e:
            self.db.connection.rollback()
            return False, f"Error saving page: {str(e)}"
    
    def get_pages_by_domain(self, domain: str) -> List[Dict]:
        """Retrieve all pages for a domain."""
        if not self.db.connected:
            return []
        
        try:
            query = f"""
            SELECT * FROM `{self.table_name}`
            WHERE domain = %s
            ORDER BY crawl_time DESC
            """
            
            self.db.cursor.execute(query, (domain,))
            
            columns = [desc[0] for desc in self.db.cursor.description]
            results = []
            
            for row in self.db.cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
        
        except Exception as e:
            print(f"Error retrieving pages: {e}")
            return []
    
    def get_page_count(self, domain: Optional[str] = None) -> int:
        """Get total count of crawled pages."""
        if not self.db.connected:
            return 0
        
        try:
            if domain:
                query = f"SELECT COUNT(*) FROM `{self.table_name}` WHERE domain = %s"
                self.db.cursor.execute(query, (domain,))
            else:
                query = f"SELECT COUNT(*) FROM `{self.table_name}`"
                self.db.cursor.execute(query)
            
            result = self.db.cursor.fetchone()
            return result[0] if result else 0
        
        except Exception as e:
            print(f"Error counting pages: {e}")
            return 0
