#!/usr/bin/env python3
"""
System Mapper - PHP Project Analyzer (v1.5)
A comprehensive tool for analyzing PHP projects, identifying orphaned files,
managing deletions safely, and generating documentation.

PORTABLE MODE: This tool is fully self-contained and portable.
- Auto-detects and installs missing dependencies
- Creates necessary directory structure automatically
- Can be run from any location
"""
import sys
import os
import subprocess
from pathlib import Path

# --- BOOTSTRAP SECTION ---
# This section runs before any imports to ensure dependencies are available

def check_python_version():
    """Check if Python version is adequate."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("=" * 60)
        print("ERROR: Python 3.7 or higher is required")
        print(f"Current version: {version.major}.{version.minor}.{version.micro}")
        print("=" * 60)
        print("\nPlease install Python 3.7+ from https://www.python.org/downloads/")
        input("Press Enter to exit...")
        sys.exit(1)
    return True

def check_dependency(module_name, package_name=None):
    """Check if a module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False

def install_dependencies():
    """Install missing dependencies."""
    print("\n" + "=" * 60)
    print("SYSTEM MAPPER - FIRST RUN SETUP")
    print("=" * 60)
    print("\nChecking dependencies...")
    
    required = [
        ('PyQt5', 'PyQt5'),
        ('lxml', 'lxml'),
        ('chardet', 'chardet')
    ]
    
    missing = []
    for module, package in required:
        if not check_dependency(module):
            missing.append(package)
            print(f"  MISSING - {package}")
        else:
            print(f"  OK - {package}")
    
    if not missing:
        print("\nOK - All dependencies are installed!")
        return True
    
    print(f"\nWARNING - Missing {len(missing)} package(s): {', '.join(missing)}")
    print("\nWould you like to install them now? (Recommended)")
    print("This will run: pip install " + " ".join(missing))
    
    response = input("\nInstall now? [Y/n]: ").strip().lower()
    
    if response in ['', 'y', 'yes']:
        print("\nInstalling dependencies...")
        print("-" * 60)
        
        try:
            # Try to upgrade pip first
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip'], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass  # Continue even if pip upgrade fails
        
        for package in missing:
            print(f"\nInstalling {package}...")
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"  OK - {package} installed successfully")
            except subprocess.CalledProcessError:
                print(f"  ERROR - Failed to install {package}")
                print(f"\nPlease install manually: pip install {package}")
                input("Press Enter to exit...")
                sys.exit(1)
        
        print("\n" + "=" * 60)
        print("OK - All dependencies installed successfully!")
        print("=" * 60)
        print("\nRestarting System Mapper...")
        print()
        
        # Restart the script to load new dependencies
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        print("\nInstallation cancelled.")
        print("\nTo install manually, run:")
        print(f"  pip install {' '.join(missing)}")
        input("\nPress Enter to exit...")
        sys.exit(0)

def create_directory_structure():
    """Create necessary directory structure if not present."""
    script_dir = Path(__file__).parent
    
    directories = [
        'utils',
        'scanner',
        'analyzer',
        'operations',
        'generators',
        'gui'
    ]
    
    created = []
    for directory in directories:
        dir_path = script_dir / directory
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(directory)
            
            # Create __init__.py if it doesn't exist
            init_file = dir_path / '__init__.py'
            if not init_file.exists():
                init_file.write_text(f"# {directory.capitalize()} package\n")
    
    if created:
        print(f"\nOK - Created missing directories: {', '.join(created)}")
    
    return True

def check_module_files():
    """Check if all required module files exist."""
    script_dir = Path(__file__).parent
    
    required_files = [
        'utils/config.py',
        'utils/logger.py',
        'scanner/file_scanner.py',
        'analyzer/php_parser.py',
        'analyzer/sql_parser.py',
        'analyzer/dependency_graph.py',
        'operations/backup_manager.py',
        'operations/deletion_manager.py',
        'operations/sanity_checker.py',
        'generators/sitemap_generator.py',
        'generators/markdown_generator.py',
        'gui/widgets.py',
        'gui/main_window.py'
    ]
    
    missing = []
    for file_path in required_files:
        if not (script_dir / file_path).exists():
            missing.append(file_path)
    
    if missing:
        print("\n" + "=" * 60)
        print("ERROR: Missing Required Files")
        print("=" * 60)
        print("\nThe following files are missing:")
        for file in missing:
            print(f"  ERROR - Missing file: {file}")
        print("\nPlease ensure all System Mapper files are in the same directory.")
        print("You can download the complete package from the source.")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    return True

def bootstrap():
    """Bootstrap the application - check and setup everything."""
    print("System Mapper - Portable PHP Project Analyzer")
    print("Starting up...\n")
    
    # 1. Check Python version
    check_python_version()
    
    # 2. Create directory structure if needed
    create_directory_structure()
    
    # 3. Check dependencies and install if needed
    install_dependencies()
    
    # 4. Verify all module files exist
    check_module_files()
    
    print("OK - Bootstrap complete - Loading application...\n")
    return True

# --- END BOOTSTRAP SECTION ---

# Run bootstrap before importing application modules
if bootstrap():
    # Now safe to import application modules
    try:
        from PyQt5.QtWidgets import QApplication
        from gui.main_window import MainWindow
    except ImportError as e:
        print(f"\nERROR: Failed to import required modules: {e}")
        print("\nTry restarting the application or reinstalling dependencies.")
        input("Press Enter to exit...")
        sys.exit(1)

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("System Mapper")
    app.setOrganizationName("PropertyXRP")
    
    # Set application style
    app.setStyle('Fusion')
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec_())

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nShutdown requested... exiting")
        sys.exit(0)
    except Exception as e:
        print("\n" + "=" * 60)
        print("FATAL ERROR")
        print("=" * 60)
        print(f"\n{type(e).__name__}: {e}")
        print("\nPlease report this error with the details above.")
        input("\nPress Enter to exit...")
        sys.exit(1)

