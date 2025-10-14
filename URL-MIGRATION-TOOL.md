# URL Migration Tool Documentation

**Version:** 1.0  
**Date:** 2025-10-14  
**Status:** Production Ready

## Overview

The URL Migration Tool is a comprehensive system for converting hardcoded URLs in your PHP/web projects to dynamic base URL references. This ensures your application is 100% migratable between domains without manual URL updates.

## Key Features

- **Intelligent URL Detection**: Scans PHP, HTML, JS, CSS, and SQL files for hardcoded URLs
- **Domain Classification**: Automatically identifies internal vs external URLs
- **Helper Function Detection**: Auto-detects existing URL patterns (BASE_URL, safe_url(), etc.)
- **2-Pass Verification**: Double-checks all classifications before making changes
- **Full Backup System**: Creates complete system backups before any modifications
- **Selective Rollback**: Restore entire system or specific files only
- **Change Preview**: Review every proposed change before approval
- **Progress Tracking**: Real-time progress indicators during operations

## Workflow (7 Steps)

### Step 1: Configure & Scan
- Add internal domains (or auto-detect from config.php)
- Add legacy domains to convert
- Choose replacement format (auto, BASE_URL, safe_url(), etc.)
- Select file types to scan
- Run initial scan

### Step 2: Verify Results
- Review scan statistics
- Check detected helper functions
- View sample URLs found
- Identify potential issues

### Step 3: Review Changes
- See every proposed URL replacement
- Filter changes by file, URL, or path
- Select/deselect individual changes
- View context for each change

### Step 4: Create Backup
- Generate full system backup
- Verify backup integrity
- View backup location and size

### Step 5: Final Approval
- Review migration summary
- Confirm changes
- Proceed to migration

### Step 6: Apply Changes
- Apply selected URL replacements
- Real-time progress tracking
- Post-migration verification
- Generate detailed report

### Step 7: Rollback Options
- **Full Rollback**: Restore entire backup
- **Selective Rollback**: Revert specific files only

## Installation

The URL Migration Tool is integrated into OrphanHunter. All dependencies are automatically installed when running `system-mapper.py`.

### Required Files
```
analyzer/url_analyzer.py        - URL detection and analysis
operations/url_migrator.py      - URL replacement engine
utils/url_config.py             - Configuration management
gui/url_migration_window.py     - User interface
```

## Usage

### Quick Start

1. **Launch System Mapper**
   ```bash
   python system-mapper.py
   ```

2. **Configure Root Directory**
   - Go to "Configuration" tab
   - Set your project root directory
   - Set config.php path (optional but recommended)

3. **Open URL Migration Tool**
   - Go to "Generate Docs" tab
   - Click "Open URL Migration Tool"

4. **Configure Domains**
   - Click "Auto-Detect from config.php" (recommended)
   - Or manually add internal domains
   - Add any legacy domains to convert

5. **Run Scan**
   - Select file types to scan
   - Choose replacement format
   - Click "Start Scan"

6. **Review and Approve**
   - Review verification results
   - Check proposed changes
   - Create backup
   - Approve and apply changes

### Configuration Options

#### Internal Domains
Domains that belong to your application. URLs from these domains will be converted to dynamic references.

**Example:**
- `example.com`
- `www.example.com`
- `subdomain.example.com`

#### Legacy Domains
Old domains from previous migrations or rebrands that should also be converted.

**Example:**
- `old-site.com`
- `dev.foggyroom.com`

#### Replacement Formats

**Auto-detect** (Recommended)
- Analyzes config.php and header.php
- Uses detected patterns (BASE_URL, safe_url(), etc.)
- Falls back to BASE_URL if nothing found

**BASE_URL**
```php
// Before: "https://example.com/page.php"
// After:  BASE_URL . '/page.php'
```

**safe_url()**
```php
// Before: "https://example.com/page.php"
// After:  safe_url('/page.php')
```

**asset_url()**
```php
// Before: "https://example.com/assets/style.css"
// After:  asset_url('/assets/style.css')
```

**Custom**
```php
// Define your own pattern with {path} placeholder
// Example: "$config['base_url'] . '{path}'"
```

#### File Types

Enable/disable scanning for specific file types:
- `.php` - PHP files
- `.html` - HTML files
- `.js` - JavaScript files
- `.css` - CSS files (URLs in stylesheets)
- `.sql` - SQL dump files

## Safety Features

### URL Protection
- **External URLs Preserved**: Never modifies URLs to other websites (Google, CDNs, APIs, etc.)
- **Whitelisting**: Add specific URLs to never modify
- **Query Strings Preserved**: Maintains ?param=value in URLs
- **Fragments Preserved**: Keeps #anchors intact

### Verification System
1. **First Pass**: Initial scan with pattern detection
2. **Second Pass**: Verify all classifications are correct
3. **Post-Migration**: Confirm changes were applied correctly

### Backup System
- Full system backup before changes
- Backup integrity verification
- Timestamped backups with manifests
- Multiple backup retention

### Rollback Capabilities

**Full Rollback**
- Restores entire system from backup
- Use when major issues occur

**Selective Rollback**
- Choose specific files to revert
- Re-apply good changes to other files
- Use for fine-tuning after migration

## Configuration Files

### url-migration-config.json
Stores URL migration settings:
```json
{
  "internal_domains": ["example.com"],
  "legacy_domains": ["old-site.com"],
  "replacement_format": "auto",
  "custom_format": "",
  "enabled_file_types": [".php", ".html", ".js", ".css", ".sql"],
  "external_whitelist": [],
  "deep_scan_mode": true,
  "last_migration_date": "2025-10-14T10:30:00",
  "last_migration_backup": "backups/backup_20251014_103000.zip"
}
```

### system-mapper-config.json
Updated to include URL migration settings in main config.

## Reports and Logs

### Migration Report
Generated after each migration:
- Location: `system-mapper-backups/url_migration_report_YYYYMMDD_HHMMSS.txt`
- Contains: All changes made, file paths, line numbers, old/new values
- Used for: Audit trail, troubleshooting, documentation

### Backup Manifest
Generated with each backup:
- Location: `system-mapper-backups/manifest_YYYYMMDD_HHMMSS.json`
- Contains: File list, checksums, sizes, timestamps
- Used for: Backup verification, selective restore

## Common Use Cases

### 1. Domain Migration
**Scenario**: Moving from dev.oldsite.com to newsite.com

**Steps:**
1. Add `dev.oldsite.com` to legacy domains
2. Add `newsite.com` to internal domains
3. Run scan
4. Review and apply changes

### 2. Multi-Domain Consolidation
**Scenario**: Multiple subdomains now using single domain

**Steps:**
1. Add all old subdomains to legacy domains
2. Add new domain to internal domains
3. Choose BASE_URL format
4. Apply changes

### 3. Protocol Migration
**Scenario**: Moving from http:// to https://

**Steps:**
1. Add domain to internal domains (both http and https versions)
2. Scan and convert
3. URLs become protocol-independent with BASE_URL

## Troubleshooting

### Issue: No URLs Found
**Solution:**
- Check that internal domains are configured
- Verify file types are enabled
- Ensure root directory is correct

### Issue: External URLs Being Migrated
**Solution:**
- Add to external whitelist
- Check domain classification
- Re-run verification

### Issue: Backup Failed
**Solution:**
- Check disk space
- Verify write permissions to backup directory
- Check for file locks

### Issue: Changes Not Applied
**Solution:**
- Check file permissions
- Review error log in results panel
- Verify files weren't modified during migration

## Best Practices

1. **Always Run on Dev First**: Test the migration on development environment
2. **Review Every Change**: Use the review panel to check all replacements
3. **Keep Backups**: Don't delete backups immediately after migration
4. **Test After Migration**: Thoroughly test your application
5. **Use Auto-Detect**: Let the tool find your existing URL patterns
6. **Configure Whitelist**: Add known external domains before scanning
7. **Document Custom Formats**: If using custom format, document it

## Technical Details

### URL Detection Pattern
```regex
(?:https?://)                                      # Protocol
(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*  # Subdomains
[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?    # Domain
(?:\.[a-zA-Z]{2,})                                # TLD
(?::[0-9]{1,5})?                                  # Optional port
(?:[/?#][^\s'"<>]*)?                              # Path, query, fragment
```

### Helper Function Detection
Automatically detects:
- `define('BASE_URL', ...)` constants
- `$base_url = ...` variables
- `function safe_url()` declarations
- `function asset_url()` declarations
- `function api_url()` declarations

### File Encoding
- Auto-detects file encoding using chardet
- Preserves original encoding when writing
- Handles UTF-8, ISO-8859-1, Windows-1252, etc.

## Testing

Run the test suite to verify installation:
```bash
python test_url_migration.py
```

Expected output:
```
✓ ALL TESTS PASSED
```

## Version History

### v1.0 (2025-10-14)
- Initial release
- Complete 7-step workflow
- Full backup and rollback support
- Multi-format support
- 2-pass verification
- Comprehensive GUI

## Support

For issues or questions:
1. Check this documentation
2. Review troubleshooting section
3. Check migration report for details
4. Restore from backup if needed

## License

Part of OrphanHunter - System Mapper project.


