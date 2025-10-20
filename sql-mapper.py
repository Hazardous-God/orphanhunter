#!/usr/bin/env python3
"""
SQL to PHP Mapper - Comprehensive SQL Table Analysis Tool
Analyzes SQL tables and their usage across PHP files, generating detailed reports.

Usage:
    python sql-mapper.py [project_directory] [--output output_dir]
    
If no directory is specified, scans the current directory.
"""

import sys
import os
from pathlib import Path
import argparse


def check_dependencies():
    """Check if required dependencies are available."""
    try:
        import chardet
        return True
    except ImportError:
        print("=" * 60)
        print("Missing Dependency: chardet")
        print("=" * 60)
        print("\nInstalling required dependency...")
        
        import subprocess
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'chardet'])
            print("\n✓ chardet installed successfully!")
            print("Please run the script again.\n")
        except subprocess.CalledProcessError:
            print("\n✗ Failed to install chardet")
            print("\nPlease install manually: pip install chardet\n")
            return False
        
        sys.exit(0)


def main():
    """Main entry point for SQL Mapper."""
    
    # Check dependencies first
    if not check_dependencies():
        sys.exit(1)
    
    # Now safe to import our modules
    sys.path.insert(0, str(Path(__file__).parent))
    
    from OrphanHunter.analyzer.sql_table_mapper import SQLTableMapper
    from OrphanHunter.generators.sql_report_generator import SQLReportGenerator
    
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='SQL to PHP Mapper - Analyze SQL table usage in PHP codebase',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python sql-mapper.py                              # Scan current directory
    python sql-mapper.py /path/to/project             # Scan specific project
    python sql-mapper.py /path/to/project --output ./reports  # Custom output
    
Reports Generated:
    - table-map.md                        # Comprehensive table breakdown
    - YYYY-MM-DD-sql-php-connections.md  # Connection analysis
        """
    )
    
    parser.add_argument(
        'project_dir',
        nargs='?',
        default='.',
        help='Project directory to scan (default: current directory)'
    )
    
    parser.add_argument(
        '-o', '--output',
        default=None,
        help='Output directory for reports (default: project_dir/sql-reports)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress messages'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    project_dir = Path(args.project_dir).resolve()
    
    if not project_dir.exists():
        print(f"✗ Error: Directory not found: {project_dir}")
        sys.exit(1)
    
    if not project_dir.is_dir():
        print(f"✗ Error: Not a directory: {project_dir}")
        sys.exit(1)
    
    # Determine output directory
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = project_dir / 'sql-reports'
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Print header
    if not args.quiet:
        print()
        print("=" * 70)
        print("  SQL TO PHP MAPPER - Comprehensive Table Analysis")
        print("=" * 70)
        print()
        print(f"Project Directory: {project_dir}")
        print(f"Output Directory:  {output_dir}")
        print()
        print("-" * 70)
        print()
    
    try:
        # Initialize mapper and analyzer
        mapper = SQLTableMapper()
        reporter = SQLReportGenerator()
        
        # Run analysis
        if not args.quiet:
            print("Phase 1: Discovering SQL tables...")
        
        analysis = mapper.analyze(project_dir)
        
        if not args.quiet:
            print()
            print("✓ Analysis Complete!")
            print()
            print(f"  Tables Found:     {analysis['statistics']['total_tables']}")
            print(f"  Tables Used:      {analysis['statistics']['used_tables']}")
            print(f"  Tables Unused:    {analysis['statistics']['unused_tables']}")
            print(f"  PHP Files:        {analysis['statistics']['total_php_files']}")
            print(f"  SQL Files:        {analysis['statistics']['total_sql_files']}")
            print()
            print("-" * 70)
            print()
            print("Phase 2: Generating reports...")
        
        # Generate reports
        reports = reporter.generate_both_reports(analysis, output_dir)
        
        if not args.quiet:
            print()
            print("✓ Reports Generated!")
            print()
            print(f"  Table Map:        {reports['table_map']}")
            print(f"  Connection Report: {reports['connection_report']}")
            print()
            print("=" * 70)
            print()
        
        # Summary statistics
        stats = analysis['statistics']
        
        if stats['unused_tables'] > 0:
            print(f"⚠️  Warning: {stats['unused_tables']} unused table(s) detected")
            print(f"   Review the connection report for details.")
            print()
        else:
            print("✓ All tables are in use!")
            print()
        
        if stats['total_tables'] == 0:
            print("⚠️  No SQL tables found in the project.")
            print("   Make sure .sql files are present in the project directory.")
            print()
        
        print(f"✓ Complete! Open the reports in: {output_dir}")
        print()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n✗ Analysis cancelled by user")
        sys.exit(1)
        
    except Exception as e:
        print()
        print("=" * 70)
        print("  ERROR")
        print("=" * 70)
        print()
        print(f"An error occurred during analysis:")
        print(f"  {type(e).__name__}: {e}")
        print()
        
        if '--debug' in sys.argv:
            import traceback
            traceback.print_exc()
        
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
