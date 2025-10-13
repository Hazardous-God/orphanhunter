#!/usr/bin/env python3
"""
Test script to verify System Mapper installation.
Run this before launching the main application.
"""
import sys

def test_python_version():
    """Test Python version."""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ ERROR: Python 3.7 or higher required")
        return False
    
    print("✓ Python version OK")
    return True

def test_import(module_name, package_name=None):
    """Test if a module can be imported."""
    try:
        __import__(module_name)
        print(f"✓ {package_name or module_name} installed")
        return True
    except ImportError:
        print(f"❌ {package_name or module_name} NOT installed")
        return False

def main():
    """Run installation tests."""
    print("=" * 50)
    print("System Mapper - Installation Test")
    print("=" * 50)
    print()
    
    all_ok = True
    
    # Test Python version
    print("Checking Python version...")
    if not test_python_version():
        all_ok = False
    print()
    
    # Test required packages
    print("Checking required packages...")
    
    required = [
        ("PyQt5", "PyQt5"),
        ("PyQt5.QtWidgets", None),
        ("PyQt5.QtCore", None),
        ("PyQt5.QtGui", None),
        ("lxml", "lxml"),
        ("chardet", "chardet")
    ]
    
    for module, package in required:
        if not test_import(module, package):
            all_ok = False
    
    print()
    
    # Test internal modules
    print("Checking internal modules...")
    
    internal = [
        "utils.config",
        "utils.logger",
        "scanner.file_scanner",
        "analyzer.php_parser",
        "analyzer.sql_parser",
        "analyzer.dependency_graph",
        "operations.backup_manager",
        "operations.deletion_manager",
        "operations.sanity_checker",
        "generators.sitemap_generator",
        "generators.markdown_generator",
        "gui.widgets",
        "gui.main_window"
    ]
    
    for module in internal:
        if not test_import(module):
            all_ok = False
    
    print()
    print("=" * 50)
    
    if all_ok:
        print("✓ All tests passed!")
        print()
        print("You can now run System Mapper:")
        print("  python system-mapper.py")
    else:
        print("❌ Some tests failed!")
        print()
        print("To install missing packages, run:")
        print("  pip install -r requirements.txt")
    
    print("=" * 50)
    
    return 0 if all_ok else 1

if __name__ == '__main__':
    sys.exit(main())

