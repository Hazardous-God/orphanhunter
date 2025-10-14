#!/usr/bin/env python3
"""
Cleanup script for OrphanHunter repository.
Removes development files, caches, and temporary data.
Run this before committing or distributing.
"""
import os
import shutil
from pathlib import Path


def clean_pycache():
    """Remove all __pycache__ directories."""
    count = 0
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            cache_path = Path(root) / '__pycache__'
            shutil.rmtree(cache_path)
            count += 1
            print(f"Removed: {cache_path}")
    return count


def clean_pyc_files():
    """Remove all .pyc files."""
    count = 0
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith(('.pyc', '.pyo')):
                file_path = Path(root) / file
                file_path.unlink()
                count += 1
    return count


def clean_config_files():
    """Remove generated config files."""
    configs = [
        'system-mapper-config.json',
        'url-migration-config.json'
    ]
    count = 0
    for config in configs:
        config_path = Path(config)
        if config_path.exists():
            config_path.unlink()
            print(f"Removed: {config}")
            count += 1
    return count


def clean_backup_dirs():
    """Remove backup directories."""
    backup_dir = Path('system-mapper-backups')
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
        print(f"Removed: {backup_dir}")
        return 1
    return 0


def clean_temp_files():
    """Remove temporary files."""
    patterns = ['*.tmp', '*.bak', '*.log', '*~']
    count = 0
    for pattern in patterns:
        for file_path in Path('.').rglob(pattern):
            if file_path.is_file():
                file_path.unlink()
                count += 1
    return count


def main():
    """Run all cleanup operations."""
    print("=" * 60)
    print("OrphanHunter Repository Cleanup")
    print("=" * 60)
    print()
    
    # Change to script directory
    os.chdir(Path(__file__).parent)
    
    print("Cleaning Python cache files...")
    pycache_count = clean_pycache()
    pyc_count = clean_pyc_files()
    print(f"  Removed {pycache_count} __pycache__ directories")
    print(f"  Removed {pyc_count} .pyc/.pyo files")
    print()
    
    print("Cleaning configuration files...")
    config_count = clean_config_files()
    print(f"  Removed {config_count} config files")
    print()
    
    print("Cleaning backup directories...")
    backup_count = clean_backup_dirs()
    print(f"  Removed {backup_count} backup directories")
    print()
    
    print("Cleaning temporary files...")
    temp_count = clean_temp_files()
    print(f"  Removed {temp_count} temporary files")
    print()
    
    print("=" * 60)
    print("Cleanup Complete!")
    print("=" * 60)
    print()
    print("Repository is now clean and ready for distribution.")
    print()
    print("Files kept:")
    print("  + Source code (*.py)")
    print("  + Documentation (README.md, URL-MIGRATION-TOOL.md)")
    print("  + Configuration (.gitignore)")
    print()
    print("Files removed:")
    print("  - Python cache (__pycache__, *.pyc)")
    print("  - User configs (*.json)")
    print("  - Backups (system-mapper-backups/)")
    print("  - Temporary files (*.tmp, *.bak, *.log)")
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nCleanup cancelled.")
    except Exception as e:
        print(f"\nError during cleanup: {e}")
        import traceback
        traceback.print_exc()

