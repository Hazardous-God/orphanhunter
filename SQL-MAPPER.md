# 🗄️ SQL to PHP Mapper - Documentation

**Comprehensive SQL Table Analysis Tool**

## Overview

The SQL to PHP Mapper is a powerful analysis tool that maps your SQL database tables to their usage across your PHP codebase. It generates detailed markdown reports showing where tables are used, which tables are unused, and provides comprehensive schema breakdowns.

---

## 🚀 Quick Start

```bash
# Analyze current directory
python sql-mapper.py

# Analyze specific project
python sql-mapper.py /path/to/your/project

# Custom output directory
python sql-mapper.py /path/to/project --output ./custom-reports

# View all options
python sql-mapper.py --help
```

---

## 📊 Reports Generated

The SQL Mapper generates **2 comprehensive markdown reports**:

### 1. `table-map.md`
Complete breakdown of all SQL tables in your database.

**Contains:**
- **Statistics**: Total tables, used vs unused counts
- **All Tables**: Alphabetical listing with:
  - Usage status (✅ IN USE or ⚠️ UNUSED)
  - Source SQL file
  - Complete column list with types
  - Primary keys
  - Foreign key relationships
  - Indexes
  - Engine and charset information

**Example:**
```markdown
### `users`
**Status:** ✅ IN USE (47 references in 12 files)
**Defined in:** `database/schema.sql`
**Engine:** InnoDB | **Charset:** utf8mb4

**Columns (8):**
| Column Name | Type |
|-------------|------|
| `id` | INT |
| `username` | VARCHAR |
| `email` | VARCHAR |
| `password` | VARCHAR |
...

**Primary Keys:** `id`
**Foreign Keys:**
- `role_id` → `roles`.`id`
```

### 2. `YYYY-MM-DD-sql-php-connections.md`
Dated connection analysis showing SQL-PHP relationships.

**Contains:**
- **Executive Summary**: Usage statistics and percentages
- **Tables in Use**: 
  - Reference counts per table
  - Files using each table
  - Line numbers with code context
  - Examples of actual usage
- **Unused Tables**: Warning list with recommendations
- **Table Relationships**: Foreign key relationship map
- **Recommendations**: Actionable insights for your database

**Example:**
```markdown
### `users`
**Usage:** 47 references across 12 PHP file(s)
**Defined in:** `database/schema.sql`
**Columns:** 8

**Used in:**

#### `auth/login.php` (8 references)
- Line 23: `$query = "SELECT * FROM users WHERE username = ?";`
- Line 45: `UPDATE users SET last_login = NOW() WHERE id = ?`
...
```

---

## 🔍 What It Analyzes

### SQL Files (`.sql`)
- ✅ `CREATE TABLE` statements
- ✅ `INSERT INTO` statements
- ✅ `ALTER TABLE` statements
- ✅ Column definitions and data types
- ✅ Primary key constraints
- ✅ Foreign key relationships
- ✅ Index definitions
- ✅ Engine and charset specifications

### PHP Files (`.php`)
- ✅ `SELECT ... FROM table`
- ✅ `JOIN table`
- ✅ `INSERT INTO table`
- ✅ `UPDATE table`
- ✅ `DELETE FROM table`
- ✅ `TRUNCATE table`
- ✅ `DESCRIBE table`
- ✅ Table names in string literals
- ✅ Dynamic table references

---

## ✨ Features

### Comprehensive Detection
- **Multi-pattern matching**: Detects tables referenced in various SQL syntax forms
- **Context awareness**: Shows exact line numbers and code snippets
- **String literal scanning**: Finds tables even in dynamic queries
- **False positive reduction**: Intelligent filtering to avoid noise

### Detailed Schema Extraction
- **Column analysis**: Name, type, and modifiers
- **Relationship mapping**: Primary and foreign keys
- **Index tracking**: All indexes per table
- **Metadata**: Engine, charset, and other properties

### Smart Reporting
- **Visual indicators**: ✅ for used tables, ⚠️ for unused
- **Sortable data**: Alphabetical ordering for easy navigation
- **Usage metrics**: Reference counts and file distributions
- **Code context**: See exactly how tables are used

### Performance
- **Fast scanning**: Processes thousands of files quickly
- **Safe encoding**: Handles various file encodings automatically
- **Low memory**: Streaming processing for large codebases
- **Progress feedback**: Real-time status updates

---

## 💡 Use Cases

### 1. Database Cleanup
**Problem**: Legacy databases with unknown tables
**Solution**: Identify unused tables safe for removal

```bash
python sql-mapper.py /path/to/project
# Review unused tables in the connection report
# Safely remove orphaned tables
```

### 2. Code Auditing
**Problem**: Need to know where specific tables are used
**Solution**: Complete usage map with file locations

**Example Output:**
```
users table used in:
- auth/login.php (8 refs)
- admin/users.php (15 refs)
- api/user-profile.php (12 refs)
```

### 3. Migration Planning
**Problem**: Moving to new database structure
**Solution**: Understand all table dependencies

- See which tables have foreign keys
- Map table relationships
- Identify critical vs optional tables

### 4. Documentation
**Problem**: No database documentation exists
**Solution**: Auto-generated comprehensive docs

- Complete schema reference
- Usage examples from real code
- Relationship diagrams
- Timestamp for version tracking

### 5. Legacy Analysis
**Problem**: Inherited codebase, unknown database
**Solution**: Fast comprehensive understanding

**Time savings:**
- Manual analysis: 4-8 hours
- SQL Mapper: 2 minutes

---

## 📁 Directory Structure

```
your-project/
├── *.php files (analyzed for table usage)
├── *.sql files (analyzed for table definitions)
└── sql-reports/ (generated)
    ├── table-map.md
    └── 2025-10-20-sql-php-connections.md
```

---

## ⚙️ Command Line Options

```bash
python sql-mapper.py [project_dir] [options]

Arguments:
  project_dir          Directory to scan (default: current directory)

Options:
  -o, --output DIR     Output directory for reports
                       (default: project_dir/sql-reports)
  
  --quiet             Suppress progress messages
  
  --help              Show help message
```

---

## 📋 Example Workflow

### Step 1: Run Analysis
```bash
cd /path/to/your/php/project
python /path/to/OrphanHunter/sql-mapper.py
```

### Step 2: Review Output
```
======================================================================
  SQL TO PHP MAPPER - Comprehensive Table Analysis
======================================================================

Project Directory: /path/to/your/php/project
Output Directory:  /path/to/your/php/project/sql-reports

----------------------------------------------------------------------

Phase 1: Discovering SQL tables...
Scanning SQL files in /path/to/your/php/project...
Found 42 SQL tables
Scanning PHP files for table usage...

✓ Analysis Complete!

  Tables Found:     42
  Tables Used:      35
  Tables Unused:    7
  PHP Files:        156
  SQL Files:        3

----------------------------------------------------------------------

Phase 2: Generating reports...

✓ Reports Generated!

  Table Map:        /path/to/your/php/project/sql-reports/table-map.md
  Connection Report: /path/to/your/php/project/sql-reports/2025-10-20-sql-php-connections.md

======================================================================

⚠️  Warning: 7 unused table(s) detected
   Review the connection report for details.

✓ Complete! Open the reports in: /path/to/your/php/project/sql-reports
```

### Step 3: Review Reports
Open the generated `.md` files in any markdown viewer or text editor.

### Step 4: Take Action
- Remove unused tables (after verification)
- Document table usage
- Plan refactoring
- Update team documentation

---

## 🎯 Understanding the Results

### Used Tables (✅)
**Meaning**: Table is actively referenced in PHP code
**Action**: Keep these tables, they're critical

### Unused Tables (⚠️)
**Possible reasons:**
1. **Legacy/deprecated** - Safe to remove
2. **External usage** - Used by other systems
3. **Migrations pending** - Will be used soon
4. **Dynamic references** - Variable table names in code

**Recommendation**: Review each unused table before deletion

### Reference Counts
- **High counts (50+)**: Core tables, heavily used
- **Medium counts (10-49)**: Regular usage
- **Low counts (1-9)**: Occasional usage
- **Zero counts**: Unused, investigate further

---

## 🔧 Troubleshooting

### No tables found
**Cause**: No `.sql` files in project
**Solution**: Ensure SQL schema files are present

### Tables not detected in PHP
**Cause**: Dynamic table names or unusual syntax
**Solution**: Manual review of flagged unused tables

### Encoding errors
**Cause**: Non-UTF-8 files
**Solution**: Tool handles this automatically with chardet

---

## 🤝 Integration with OrphanHunter

The SQL Mapper is part of the OrphanHunter suite:

- **Standalone**: Can run independently
- **Complementary**: Works alongside other OrphanHunter tools
- **Consistent**: Uses same architecture and patterns

---

## 📝 Report Examples

See sample reports in the `/examples/` directory (if available):
- `example-table-map.md`
- `example-connections.md`

---

## ⚡ Performance Notes

**Typical Performance:**
- 100 PHP files: ~2 seconds
- 500 PHP files: ~8 seconds
- 1000 PHP files: ~15 seconds

**Scales well with:**
- Large codebases (1000+ files)
- Many tables (100+)
- Complex relationships

---

## 🎓 Best Practices

1. **Run regularly**: Track database evolution over time
2. **Date your reports**: Keep historical records
3. **Review before deletion**: Verify unused tables
4. **Document decisions**: Note why tables were kept/removed
5. **Team collaboration**: Share reports with your team

---

## 🔒 Safety

- **Read-only**: Never modifies your code or database
- **Non-destructive**: Only generates reports
- **Safe scanning**: Handles encoding issues gracefully
- **No database connection**: Analyzes files only

---

## 📚 Related Tools

- **OrphanHunter**: Main GUI application
- **URL Migration Tool**: Domain migration system
- **System Mapper**: Comprehensive project analysis

---

**Version**: 1.0  
**Part of**: OrphanHunter v1.3  
**Release Date**: October 20, 2025  
**License**: MIT
