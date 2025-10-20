# OrphanHunter

A Python toolkit for auditing and cleaning legacy PHP/web projects. It detects orphaned files, analyzes CSS conflicts, maps SQL tables to their usage in PHP, and provides a guided URL Migration Tool to convert hardcoded URLs into dynamic base references.

## Features
- URL Migration Tool: classify internal vs external URLs, preview changes, backup, and rollback
- Orphaned file detection and safe deletion workflow with backups
- CSS analysis for duplicates and unused selectors
- SQL→PHP mapper: builds table maps and usage reports
- Sitemap and documentation generators

## Requirements
- Python 3.7+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

## Quick start
- Launch GUI:
  ```bash
  python system-mapper.py
  ```
- SQL→PHP Mapper (CLI):
  ```bash
  # scan current directory
  python sql-mapper.py

  # scan a specific project and write reports to ./sql-reports
  python sql-mapper.py /path/to/project

  # custom output directory
  python sql-mapper.py /path/to/project -o ./reports
  ```

## Documentation
- URL Migration Tool: see `URL-MIGRATION-TOOL.md`
- SQL→PHP Mapper: see `SQL-MAPPER.md`

## Housekeeping
- Clean caches and temp artifacts before distributing:
  ```bash
  python cleanup.py
  ```

## Repository layout
```
OrphanHunter/            # core modules (analyzers, generators, gui, operations, utils)
sql-mapper.py            # SQL→PHP mapper CLI
system-mapper.py         # GUI entry point
cleanup.py               # repository cleanup helper
migrations/              # example migrations (dated)
README.md                # this file
URL-MIGRATION-TOOL.md    # URL migration documentation
SQL-MAPPER.md            # SQL mapper documentation
```

## License
MIT License. See `LICENSE`.
