"""Backup and archive management."""
import zipfile
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

class BackupManager:
    """Manages backup archives and restoration."""
    
    def __init__(self, root_dir: Path, backup_dir: str = "system-mapper-backups"):
        self.root_dir = Path(root_dir).resolve()
        self.backup_dir = Path(backup_dir).resolve()
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.current_backup: Optional[Path] = None
        self.manifest: Dict = {}
    
    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            print(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    def create_backup(self, ignore_patterns: List[str] = None) -> Path:
        """Create a ZIP backup of the entire root directory."""
        ignore_patterns = ignore_patterns or []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}.zip"
        backup_path = self.backup_dir / backup_name
        
        manifest = {
            'timestamp': timestamp,
            'root_directory': str(self.root_dir),
            'files': {}
        }
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.root_dir.rglob('*'):
                if file_path.is_file():
                    # Check if should be ignored
                    should_ignore = False
                    for pattern in ignore_patterns:
                        if pattern in file_path.parts or file_path.name.startswith('.'):
                            should_ignore = True
                            break
                    
                    # Don't backup the backup directory itself
                    if str(self.backup_dir) in str(file_path):
                        should_ignore = True
                    
                    if not should_ignore:
                        relative_path = file_path.relative_to(self.root_dir)
                        zipf.write(file_path, relative_path)
                        
                        # Add to manifest with checksum
                        checksum = self.calculate_checksum(file_path)
                        manifest['files'][str(relative_path)] = {
                            'checksum': checksum,
                            'size': file_path.stat().st_size,
                            'modified': file_path.stat().st_mtime
                        }
        
        # Save manifest
        manifest_path = self.backup_dir / f"manifest_{timestamp}.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        self.current_backup = backup_path
        self.manifest = manifest
        
        return backup_path
    
    def restore_backup(self, backup_path: Path) -> bool:
        """Restore from a backup archive."""
        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return False
        
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                zipf.extractall(self.root_dir)
            return True
        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False
    
    def restore_current_backup(self) -> bool:
        """Restore from the most recent backup."""
        if not self.current_backup or not self.current_backup.exists():
            print("No current backup available")
            return False
        
        return self.restore_backup(self.current_backup)
    
    def verify_backup(self, backup_path: Path) -> Dict:
        """Verify integrity of a backup."""
        result = {
            'valid': True,
            'errors': [],
            'file_count': 0
        }
        
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                # Test ZIP integrity
                bad_file = zipf.testzip()
                if bad_file:
                    result['valid'] = False
                    result['errors'].append(f"Corrupted file in archive: {bad_file}")
                
                result['file_count'] = len(zipf.namelist())
        except Exception as e:
            result['valid'] = False
            result['errors'].append(str(e))
        
        return result
    
    def list_backups(self) -> List[Dict]:
        """List all available backups."""
        backups = []
        
        for backup_file in self.backup_dir.glob("backup_*.zip"):
            size = backup_file.stat().st_size
            modified = datetime.fromtimestamp(backup_file.stat().st_mtime)
            
            backups.append({
                'path': backup_file,
                'name': backup_file.name,
                'size': size,
                'size_mb': round(size / (1024 * 1024), 2),
                'date': modified,
                'date_str': modified.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        # Sort by date descending
        backups.sort(key=lambda x: x['date'], reverse=True)
        
        return backups
    
    def delete_old_backups(self, keep_count: int = 5):
        """Delete old backups, keeping only the most recent N."""
        backups = self.list_backups()
        
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                try:
                    backup['path'].unlink()
                    # Also delete associated manifest
                    manifest_name = backup['name'].replace('backup_', 'manifest_').replace('.zip', '.json')
                    manifest_path = self.backup_dir / manifest_name
                    if manifest_path.exists():
                        manifest_path.unlink()
                except Exception as e:
                    print(f"Error deleting backup {backup['name']}: {e}")

