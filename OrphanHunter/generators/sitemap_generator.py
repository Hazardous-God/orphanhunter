"""Generate sitemap.xml for the website."""
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from xml.dom import minidom
from OrphanHunter.scanner.file_scanner import FileScanner

class SitemapGenerator:
    """Generate sitemap.xml following the standard protocol."""
    
    def __init__(self, file_scanner: FileScanner, base_url: str):
        self.file_scanner = file_scanner
        self.base_url = base_url.rstrip('/')
    
    def calculate_priority(self, file_info) -> float:
        """Calculate priority based on file depth and reference count."""
        # Root files get higher priority
        depth = len(file_info.relative_path.parts)
        
        if depth == 1:
            priority = 1.0
        elif depth == 2:
            priority = 0.8
        else:
            priority = 0.6
        
        # Boost priority for files with many references
        if file_info.reference_count > 10:
            priority = min(1.0, priority + 0.1)
        elif file_info.reference_count > 5:
            priority = min(1.0, priority + 0.05)
        
        return round(priority, 1)
    
    def should_include_in_sitemap(self, file_info) -> bool:
        """Determine if a file should be included in sitemap."""
        # Only include PHP files
        if file_info.extension != '.php':
            return False
        
        # Exclude admin files
        if 'admin' in file_info.relative_path.parts:
            return False
        
        # Exclude API endpoints
        if 'api' in file_info.relative_path.parts:
            return False
        
        # Exclude files in certain directories
        exclude_dirs = ['includes', 'required', 'vendor', 'test']
        for exclude in exclude_dirs:
            if exclude in file_info.relative_path.parts:
                return False
        
        # Exclude certain file patterns
        exclude_patterns = ['test_', 'debug_', 'temp_', '_backup']
        for pattern in exclude_patterns:
            if pattern in file_info.name.lower():
                return False
        
        return True
    
    def get_url_from_file(self, file_info) -> str:
        """Convert file path to URL."""
        path = file_info.relative_path_str
        
        # Handle index.php specially
        if file_info.name == 'index.php':
            if path == 'index.php':
                return self.base_url + '/'
            else:
                # Directory index
                dir_path = file_info.relative_path.parent.as_posix()
                return f"{self.base_url}/{dir_path}/"
        
        return f"{self.base_url}/{path}"
    
    def generate_sitemap(self, output_path: Path = None) -> str:
        """Generate sitemap.xml content."""
        # Create XML structure
        urlset = Element('urlset')
        urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
        
        # Add URLs
        for file_info in self.file_scanner.files.values():
            if not self.should_include_in_sitemap(file_info):
                continue
            
            if not file_info.path.exists():
                continue
            
            url = SubElement(urlset, 'url')
            
            # Location
            loc = SubElement(url, 'loc')
            loc.text = self.get_url_from_file(file_info)
            
            # Last modified
            lastmod = SubElement(url, 'lastmod')
            mod_time = datetime.fromtimestamp(file_info.modified_time)
            lastmod.text = mod_time.strftime('%Y-%m-%d')
            
            # Priority
            priority = SubElement(url, 'priority')
            priority.text = str(self.calculate_priority(file_info))
        
        # Convert to pretty XML string
        xml_str = minidom.parseString(tostring(urlset)).toprettyxml(indent='  ')
        
        # Remove extra blank lines
        xml_lines = [line for line in xml_str.split('\n') if line.strip()]
        xml_str = '\n'.join(xml_lines)
        
        # Save to file if path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_str)
        
        return xml_str
    
    def get_sitemap_stats(self) -> Dict:
        """Get statistics about sitemap generation."""
        total_files = len(self.file_scanner.files)
        included = sum(1 for f in self.file_scanner.files.values() if self.should_include_in_sitemap(f))
        
        return {
            'total_files': total_files,
            'included_in_sitemap': included,
            'excluded': total_files - included
        }

