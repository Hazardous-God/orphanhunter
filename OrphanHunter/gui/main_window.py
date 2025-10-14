"""Main window for System Mapper application."""
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QLabel, QLineEdit, QFileDialog, QMessageBox,
    QGroupBox, QFormLayout, QCheckBox, QSpinBox, QTextEdit,
    QSplitter, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

from OrphanHunter.utils.config import Config
from OrphanHunter.utils.logger import Logger
from OrphanHunter.scanner.file_scanner import FileScanner
from OrphanHunter.analyzer.php_parser import PHPParser
from OrphanHunter.analyzer.sql_parser import SQLParser, SQLReferenceAnalyzer
from OrphanHunter.analyzer.dependency_graph import DependencyGraph
from OrphanHunter.operations.backup_manager import BackupManager
from OrphanHunter.operations.deletion_manager import DeletionManager
from OrphanHunter.operations.sanity_checker import SanityChecker
from OrphanHunter.generators.sitemap_generator import SitemapGenerator
from OrphanHunter.generators.markdown_generator import MarkdownGenerator
from OrphanHunter.gui.widgets import FileTreeWidget, LogConsole, StatusPanel, StatsWidget
from OrphanHunter.gui.url_migration_window import URLMigrationWindow


class ScanWorker(QThread):
    """Worker thread for scanning operations."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, root_dir, config):
        super().__init__()
        self.root_dir = root_dir
        self.config = config
    
    def run(self):
        """Run the scan operation."""
        try:
            result = {}
            
            # Scan files
            self.progress.emit("Scanning files...")
            scanner = FileScanner(
                self.root_dir,
                self.config.get_ignore_patterns(),
                self.config.should_ignore_dot_directories(),
                self.config.get_blacklist_directories()
            )
            scanner.scan(self.config.get('scan_extensions'))
            scanner.mark_critical_files(self.config.get_critical_files())
            scanner.mark_navigation_files(self.config.get('navigation_files'))
            result['scanner'] = scanner
            
            # Parse SQL or connect to live database
            sql_tables = set()
            use_live_db = self.config.get('use_live_database', False)
            
            if use_live_db:
                # Use live database connection
                config_php = self.config.get('config_php_path')
                if config_php and Path(config_php).exists():
                    self.progress.emit("Connecting to live database...")
                    try:
                        from OrphanHunter.analyzer.live_db_connector import DatabaseAnalyzer
                        
                        db_analyzer = DatabaseAnalyzer()
                        success, message = db_analyzer.load_from_config(Path(config_php))
                        
                        if success:
                            known_files = set()  # Will be populated after scan
                            success, message, db_result = db_analyzer.connect_and_analyze(known_files)
                            
                            if success:
                                sql_tables = db_result['tables']
                                result['sql_tables'] = sql_tables
                                result['live_db_data'] = db_result
                                result['live_db_url_data'] = db_result['url_data']
                                self.progress.emit(f"Live DB: {message}")
                            else:
                                self.progress.emit(f"Live DB error: {message}")
                            
                            db_analyzer.disconnect()
                        else:
                            self.progress.emit(f"Config error: {message}")
                    
                    except ImportError:
                        self.progress.emit("Installing mysql-connector-python...")
                        import subprocess
                        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mysql-connector-python'])
                        self.progress.emit("Package installed. Please restart scan.")
                    except Exception as e:
                        self.progress.emit(f"Live DB error: {e}")
            else:
                # Use SQL dump file
                sql_dump = self.config.get('sql_dump_path')
                if sql_dump and Path(sql_dump).exists():
                    self.progress.emit("Parsing SQL dump...")
                    sql_parser = SQLParser()
                    table_info = sql_parser.parse_sql_file(Path(sql_dump))
                    sql_tables = set(table_info.keys())
                    result['sql_tables'] = sql_tables
                    result['table_info'] = table_info
            
            # Build dependency graph
            self.progress.emit("Building dependency graph...")
            dep_graph = DependencyGraph(scanner, Path(self.root_dir))
            sql_dump_path = Path(sql_dump) if sql_dump else None
            dep_graph.build_graph(sql_tables, sql_dump_path)
            result['dependency_graph'] = dep_graph
            
            # Find orphaned files
            self.progress.emit("Identifying orphaned files...")
            orphaned = dep_graph.get_orphaned_files(
                self.config.get('orphan_criteria')
            )
            result['orphaned_files'] = orphaned
            
            # Analyze assets (JS, TS, JSON, CSS orphans)
            if self.config.get('enable_asset_analysis', True):
                self.progress.emit("Analyzing assets (JS, TS, JSON, CSS)...")
                dep_graph.asset_analyzer.analyze()
                result['asset_summary'] = dep_graph.asset_analyzer.get_asset_summary()
            
            # Analyze CSS conflicts and overlaps
            if self.config.get('enable_css_analysis', True):
                self.progress.emit("Analyzing CSS conflicts...")
                css_files = {
                    k: v.path for k, v in scanner.files.items()
                    if v.extension == '.css'
                }
                if css_files:
                    dep_graph.css_analyzer.analyze_css_files(css_files)
                    dep_graph.css_analyzer.find_conflicts()
                    
                    # Analyze page CSS usage
                    for file_key, file_info in scanner.files.items():
                        if file_info.extension in ['.php', '.html', '.htm']:
                            dep_graph.css_analyzer.scan_page_css_usage(file_info.path, file_key)
                    
                    result['css_stats'] = dep_graph.css_analyzer.get_statistics()
            
            self.progress.emit("Scan complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.config = Config()
        self.logger = Logger()
        self.scanner = None
        self.dependency_graph = None
        self.backup_manager = None
        self.deletion_manager = None
        self.sanity_checker = None
        self.orphaned_files = set()
        self.sql_tables = set()
        
        self.init_ui()
        self.connect_signals()
        self.load_config()
    
    def init_ui(self):
        """Initialize user interface."""
        self.setWindowTitle("System Mapper - PHP Project Analyzer")
        self.setGeometry(100, 100, 1400, 900)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Status panel
        self.status_panel = StatusPanel()
        main_layout.addWidget(self.status_panel)
        
        # Tab widget
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self.create_config_tab()
        self.create_scan_tab()
        self.create_delete_tab()
        self.create_generate_tab()
        self.create_log_tab()
        
        # Log console at bottom
        self.log_console = LogConsole()
        main_layout.addWidget(self.log_console)
    
    def create_config_tab(self):
        """Create configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Directory configuration
        dir_group = QGroupBox("Directory Configuration")
        dir_layout = QFormLayout()
        
        # Root directory
        root_layout = QHBoxLayout()
        self.root_dir_input = QLineEdit()
        root_layout.addWidget(self.root_dir_input)
        root_browse = QPushButton("Browse...")
        root_browse.clicked.connect(self.browse_root_directory)
        root_layout.addWidget(root_browse)
        dir_layout.addRow("Root Directory:", root_layout)
        
        # Admin directory
        self.admin_dir_input = QLineEdit()
        dir_layout.addRow("Admin Directory:", self.admin_dir_input)
        
        # SQL dump path
        sql_layout = QHBoxLayout()
        self.sql_dump_input = QLineEdit()
        sql_layout.addWidget(self.sql_dump_input)
        sql_browse = QPushButton("Browse...")
        sql_browse.clicked.connect(self.browse_sql_dump)
        sql_layout.addWidget(sql_browse)
        dir_layout.addRow("SQL Dump File:", sql_layout)
        
        # Config.php path for live database
        config_php_layout = QHBoxLayout()
        self.config_php_input = QLineEdit()
        config_php_layout.addWidget(self.config_php_input)
        config_php_browse = QPushButton("Browse...")
        config_php_browse.clicked.connect(self.browse_config_php)
        config_php_layout.addWidget(config_php_browse)
        dir_layout.addRow("Config.php (Live DB):", config_php_layout)
        
        # Use live database checkbox
        self.use_live_db = QCheckBox("Use live database connection (instead of SQL dump)")
        self.use_live_db.setToolTip("Connect to live MySQL database using config.php credentials")
        dir_layout.addRow("", self.use_live_db)
        
        dir_group.setLayout(dir_layout)
        layout.addWidget(dir_group)
        
        # Ignore options
        ignore_group = QGroupBox("Directory Ignore Options")
        ignore_layout = QVBoxLayout()
        
        self.ignore_dot_dirs = QCheckBox("Ignore all directories starting with . (dot directories)")
        self.ignore_dot_dirs.setChecked(True)
        self.ignore_dot_dirs.setToolTip("Ignores directories like .git, .vscode, .idea that typically aren't uploaded to FTP")
        ignore_layout.addWidget(self.ignore_dot_dirs)
        
        # Blacklist directories
        blacklist_label = QLabel("Blacklist Directories (comma-separated):")
        blacklist_label.setToolTip("Enter directory names or paths to completely ignore during scanning")
        ignore_layout.addWidget(blacklist_label)
        
        self.blacklist_dirs_input = QTextEdit()
        self.blacklist_dirs_input.setMaximumHeight(80)
        self.blacklist_dirs_input.setPlaceholderText("e.g., temp, backup, old_files, test_data")
        self.blacklist_dirs_input.setToolTip("One per line or comma-separated. These directories will be completely ignored.")
        ignore_layout.addWidget(self.blacklist_dirs_input)
        
        ignore_group.setLayout(ignore_layout)
        layout.addWidget(ignore_group)
        
        # Orphan criteria
        orphan_group = QGroupBox("Orphan Detection Criteria")
        orphan_layout = QVBoxLayout()
        
        self.criteria_not_in_nav = QCheckBox("Not linked in navigation files")
        self.criteria_not_in_nav.setChecked(True)
        orphan_layout.addWidget(self.criteria_not_in_nav)
        
        self.criteria_not_included = QCheckBox("Not included/required anywhere")
        self.criteria_not_included.setChecked(True)
        orphan_layout.addWidget(self.criteria_not_included)
        
        ref_layout = QHBoxLayout()
        ref_layout.addWidget(QLabel("Minimum reference count:"))
        self.min_ref_count = QSpinBox()
        self.min_ref_count.setMinimum(0)
        self.min_ref_count.setMaximum(100)
        ref_layout.addWidget(self.min_ref_count)
        ref_layout.addStretch()
        orphan_layout.addLayout(ref_layout)
        
        orphan_group.setLayout(orphan_layout)
        layout.addWidget(orphan_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Configuration")
    
    def create_scan_tab(self):
        """Create scan results tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Scan Project")
        self.scan_btn.clicked.connect(self.start_scan)
        button_layout.addWidget(self.scan_btn)
        
        self.backup_btn = QPushButton("Create Backup")
        self.backup_btn.clicked.connect(self.create_backup)
        self.backup_btn.setEnabled(False)
        button_layout.addWidget(self.backup_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Splitter for tree and details
        splitter = QSplitter(Qt.Horizontal)
        
        # File tree
        self.file_tree = FileTreeWidget()
        splitter.addWidget(self.file_tree)
        
        # Details panel
        details_widget = QWidget()
        details_layout = QVBoxLayout()
        
        self.stats_widget = StatsWidget()
        details_layout.addWidget(self.stats_widget)
        
        self.file_detail_text = QTextEdit()
        self.file_detail_text.setReadOnly(True)
        details_layout.addWidget(self.file_detail_text)
        
        details_widget.setLayout(details_layout)
        splitter.addWidget(details_widget)
        
        splitter.setSizes([800, 600])
        layout.addWidget(splitter)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Scan Results")
    
    def create_delete_tab(self):
        """Create deletion management tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Info label
        info = QLabel("Select files from the Scan Results tab, then manage deletion here.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Selection info
        self.deletion_info_label = QLabel("No files selected")
        layout.addWidget(self.deletion_info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.select_orphaned_btn = QPushButton("Select All Orphaned")
        self.select_orphaned_btn.clicked.connect(self.select_orphaned_files)
        button_layout.addWidget(self.select_orphaned_btn)
        
        self.clear_selection_btn = QPushButton("Clear Selection")
        self.clear_selection_btn.clicked.connect(self.clear_file_selection)
        button_layout.addWidget(self.clear_selection_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Deletion mode
        mode_group = QGroupBox("Deletion Mode")
        mode_layout = QVBoxLayout()
        
        self.batch_mode_btn = QPushButton("Batch Delete (with confirmation)")
        self.batch_mode_btn.clicked.connect(self.batch_delete)
        mode_layout.addWidget(self.batch_mode_btn)
        
        self.individual_mode_btn = QPushButton("Individual Delete (one by one)")
        self.individual_mode_btn.clicked.connect(self.individual_delete)
        mode_layout.addWidget(self.individual_mode_btn)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Rollback section
        rollback_group = QGroupBox("Backup & Rollback")
        rollback_layout = QVBoxLayout()
        
        self.backup_list_label = QLabel("No backups available")
        rollback_layout.addWidget(self.backup_list_label)
        
        rollback_btn_layout = QHBoxLayout()
        self.restore_btn = QPushButton("Restore Latest Backup")
        self.restore_btn.clicked.connect(self.restore_backup)
        rollback_btn_layout.addWidget(self.restore_btn)
        
        self.list_backups_btn = QPushButton("List All Backups")
        self.list_backups_btn.clicked.connect(self.list_backups)
        rollback_btn_layout.addWidget(self.list_backups_btn)
        
        rollback_layout.addLayout(rollback_btn_layout)
        rollback_group.setLayout(rollback_layout)
        layout.addWidget(rollback_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Delete Management")
    
    def create_generate_tab(self):
        """Create documentation generation tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Sitemap generation
        sitemap_group = QGroupBox("Generate sitemap.xml")
        sitemap_layout = QVBoxLayout()
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Base URL:"))
        self.base_url_input = QLineEdit("https://example.com")
        url_layout.addWidget(self.base_url_input)
        sitemap_layout.addLayout(url_layout)
        
        self.generate_sitemap_btn = QPushButton("Generate Sitemap")
        self.generate_sitemap_btn.clicked.connect(self.generate_sitemap)
        sitemap_layout.addWidget(self.generate_sitemap_btn)
        
        sitemap_group.setLayout(sitemap_layout)
        layout.addWidget(sitemap_group)
        
        # Markdown documentation
        markdown_group = QGroupBox("Generate Documentation")
        markdown_layout = QVBoxLayout()
        
        self.generate_tree_btn = QPushButton("Generate System Tree Map")
        self.generate_tree_btn.clicked.connect(self.generate_tree_map)
        markdown_layout.addWidget(self.generate_tree_btn)
        
        self.generate_nav_btn = QPushButton("Generate Navigation Map")
        self.generate_nav_btn.clicked.connect(self.generate_navigation_map)
        markdown_layout.addWidget(self.generate_nav_btn)
        
        self.generate_all_btn = QPushButton("Generate All Documentation")
        self.generate_all_btn.clicked.connect(self.generate_all_docs)
        markdown_layout.addWidget(self.generate_all_btn)
        
        markdown_group.setLayout(markdown_layout)
        layout.addWidget(markdown_group)
        
        # Style error report
        style_group = QGroupBox("Style Analysis Report")
        style_layout = QVBoxLayout()
        
        self.generate_style_report_btn = QPushButton("Generate Style Error Report")
        self.generate_style_report_btn.clicked.connect(self.generate_style_report)
        style_layout.addWidget(self.generate_style_report_btn)
        
        style_group.setLayout(style_layout)
        layout.addWidget(style_group)
        
        # URL Migration Tool
        url_migration_group = QGroupBox("URL Migration Tool")
        url_migration_layout = QVBoxLayout()
        url_migration_layout.addWidget(QLabel("Convert hardcoded URLs to dynamic base URLs"))
        
        self.url_migration_btn = QPushButton("Open URL Migration Tool")
        self.url_migration_btn.clicked.connect(self.open_url_migration)
        url_migration_layout.addWidget(self.url_migration_btn)
        
        url_migration_group.setLayout(url_migration_layout)
        layout.addWidget(url_migration_group)
        
        layout.addStretch()
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Generate Docs")
    
    def create_log_tab(self):
        """Create log viewer tab."""
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        layout.addWidget(self.log_viewer)
        
        button_layout = QHBoxLayout()
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.log_viewer.clear)
        button_layout.addWidget(clear_log_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Logs")
    
    def connect_signals(self):
        """Connect signals and slots."""
        self.logger.signals.log_message.connect(self.on_log_message)
        self.file_tree.file_selected.connect(self.on_file_selected)
        self.file_tree.files_checked.connect(self.on_files_checked)
    
    def on_log_message(self, message: str, level: str):
        """Handle log messages."""
        self.log_console.append_log(message, level)
        self.log_viewer.append(f"[{level}] {message}")
    
    def on_file_selected(self, file_key: str):
        """Handle file selection in tree."""
        if not self.scanner:
            return
        
        file_info = self.scanner.get_file_by_relative_path(file_key)
        if not file_info:
            return
        
        details = []
        details.append(f"<h3>{file_info.name}</h3>")
        details.append(f"<b>Path:</b> {file_info.relative_path}<br>")
        details.append(f"<b>Size:</b> {round(file_info.size/1024, 2)} KB<br>")
        details.append(f"<b>References:</b> {file_info.reference_count}<br>")
        details.append(f"<b>Critical:</b> {'Yes' if file_info.is_critical else 'No'}<br>")
        details.append(f"<b>Navigation:</b> {'Yes' if file_info.is_navigation else 'No'}<br>")
        
        if file_info.referenced_by:
            details.append("<br><b>Referenced by:</b><ul>")
            for ref in list(file_info.referenced_by)[:10]:
                details.append(f"<li>{ref}</li>")
            if len(file_info.referenced_by) > 10:
                details.append(f"<li>... and {len(file_info.referenced_by) - 10} more</li>")
            details.append("</ul>")
        
        if file_info.references:
            details.append("<br><b>References:</b><ul>")
            for ref in list(file_info.references)[:10]:
                details.append(f"<li>{ref}</li>")
            if len(file_info.references) > 10:
                details.append(f"<li>... and {len(file_info.references) - 10} more</li>")
            details.append("</ul>")
        
        self.file_detail_text.setHtml("".join(details))
    
    def on_files_checked(self, file_keys: set):
        """Handle file checkbox changes."""
        count = len(file_keys)
        self.deletion_info_label.setText(f"{count} file(s) selected for deletion")
    
    def load_config(self):
        """Load configuration into UI."""
        self.root_dir_input.setText(self.config.get('root_directory', ''))
        self.admin_dir_input.setText(self.config.get('admin_directory', 'admin'))
        self.sql_dump_input.setText(self.config.get('sql_dump_path', ''))
        self.config_php_input.setText(self.config.get('config_php_path', ''))
        self.use_live_db.setChecked(self.config.get('use_live_database', False))
        
        # Ignore options
        self.ignore_dot_dirs.setChecked(self.config.get('ignore_dot_directories', True))
        blacklist = self.config.get('blacklist_directories', [])
        self.blacklist_dirs_input.setPlainText(', '.join(blacklist))
        
        criteria = self.config.get('orphan_criteria', {})
        self.criteria_not_in_nav.setChecked(criteria.get('not_in_navigation', True))
        self.criteria_not_included.setChecked(criteria.get('not_included_anywhere', True))
        self.min_ref_count.setValue(criteria.get('min_reference_count', 0))
    
    def save_config(self):
        """Save configuration from UI."""
        self.config.set('root_directory', self.root_dir_input.text())
        self.config.set('admin_directory', self.admin_dir_input.text())
        self.config.set('sql_dump_path', self.sql_dump_input.text())
        self.config.set('config_php_path', self.config_php_input.text())
        self.config.set('use_live_database', self.use_live_db.isChecked())
        
        # Save ignore options
        self.config.set('ignore_dot_directories', self.ignore_dot_dirs.isChecked())
        
        # Parse blacklist directories
        blacklist_text = self.blacklist_dirs_input.toPlainText()
        blacklist = []
        if blacklist_text.strip():
            # Split by comma or newline
            for item in blacklist_text.replace('\n', ',').split(','):
                item = item.strip()
                if item:
                    blacklist.append(item)
        self.config.set('blacklist_directories', blacklist)
        
        criteria = {
            'not_in_navigation': self.criteria_not_in_nav.isChecked(),
            'not_included_anywhere': self.criteria_not_included.isChecked(),
            'min_reference_count': self.min_ref_count.value()
        }
        self.config.set('orphan_criteria', criteria)
        
        self.config.save()
        self.logger.info("Configuration saved")
        QMessageBox.information(self, "Success", "Configuration saved successfully!")
    
    def browse_root_directory(self):
        """Browse for root directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Root Directory")
        if directory:
            self.root_dir_input.setText(directory)
    
    def browse_sql_dump(self):
        """Browse for SQL dump file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select SQL Dump File", "", "SQL Files (*.sql);;All Files (*)"
        )
        if file_path:
            self.sql_dump_input.setText(file_path)
    
    def browse_config_php(self):
        """Browse for config.php file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select config.php File", "", "PHP Files (*.php);;All Files (*)"
        )
        if file_path:
            self.config_php_input.setText(file_path)
    
    def start_scan(self):
        """Start scanning operation."""
        root_dir = self.root_dir_input.text()
        if not root_dir or not Path(root_dir).exists():
            QMessageBox.warning(self, "Error", "Please select a valid root directory")
            return
        
        self.save_config()
        
        self.status_panel.set_status("Scanning...", "Please wait")
        self.status_panel.show_progress(True)
        self.scan_btn.setEnabled(False)
        
        self.scan_worker = ScanWorker(root_dir, self.config)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.finished.connect(self.on_scan_complete)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.start()
    
    def on_scan_progress(self, message: str):
        """Handle scan progress updates."""
        self.logger.info(message)
        self.status_panel.set_status("Scanning...", message)
    
    def on_scan_complete(self, result: dict):
        """Handle scan completion."""
        self.scanner = result['scanner']
        self.dependency_graph = result['dependency_graph']
        self.orphaned_files = result['orphaned_files']
        self.sql_tables = result.get('sql_tables', set())
        
        # Initialize managers
        root_dir = Path(self.root_dir_input.text())
        self.backup_manager = BackupManager(root_dir)
        self.deletion_manager = DeletionManager(self.scanner, root_dir)
        self.sanity_checker = SanityChecker(self.scanner, self.dependency_graph)
        
        # Update UI
        self.file_tree.populate_tree(self.scanner.files)
        self.file_tree.highlight_orphaned()
        
        # Count files by extension
        file_counts = {}
        for file_info in self.scanner.files.values():
            ext = file_info.extension
            file_counts[ext] = file_counts.get(ext, 0) + 1
        
        stats = {
            'Total Files': len(self.scanner.files),
            'PHP Files': file_counts.get('.php', 0),
            'HTML Files': file_counts.get('.html', 0) + file_counts.get('.htm', 0),
            'JavaScript Files': file_counts.get('.js', 0),
            'TypeScript Files': file_counts.get('.ts', 0),
            'JSON Files': file_counts.get('.json', 0),
            'CSS Files': file_counts.get('.css', 0),
            'Critical Files': len(self.scanner.critical_files),
            'Navigation Files': len(self.scanner.navigation_files),
            'Orphaned Files': len(self.orphaned_files),
            'SQL Tables': len(self.sql_tables),
            'SQL URLs Found': len(self.dependency_graph.sql_urls) if hasattr(self.dependency_graph, 'sql_urls') else 0
        }
        
        # Add asset analysis stats if available
        if hasattr(self.dependency_graph, 'asset_analyzer'):
            asset_summary = self.dependency_graph.asset_analyzer.get_asset_summary()
            if asset_summary:
                stats['Orphaned Assets'] = asset_summary['orphaned_assets']
                if asset_summary['by_type']:
                    stats['Orphaned CSS'] = asset_summary['by_type'].get('.css', 0)
                    stats['Orphaned JS'] = asset_summary['by_type'].get('.js', 0)
        
        # Add CSS analysis stats if available
        if hasattr(self.dependency_graph, 'css_analyzer'):
            css_stats = self.dependency_graph.css_analyzer.get_statistics()
            if css_stats:
                stats['CSS Conflicts'] = css_stats.get('property_conflicts', 0)
                stats['Duplicate Selectors'] = css_stats.get('duplicate_selectors', 0)
        self.stats_widget.update_stats(stats)
        
        self.status_panel.set_status("Scan Complete", f"Found {len(self.scanner.files)} files")
        self.status_panel.show_progress(False)
        self.scan_btn.setEnabled(True)
        self.backup_btn.setEnabled(True)
        
        self.logger.info(f"Scan complete: {len(self.scanner.files)} files analyzed")
        QMessageBox.information(
            self, "Scan Complete",
            f"Analysis complete!\n\nTotal Files: {len(self.scanner.files)}\nOrphaned: {len(self.orphaned_files)}"
        )
    
    def on_scan_error(self, error: str):
        """Handle scan error."""
        self.status_panel.set_status("Error", error)
        self.status_panel.show_progress(False)
        self.scan_btn.setEnabled(True)
        self.logger.error(f"Scan error: {error}")
        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n\n{error}")
    
    def create_backup(self):
        """Create backup archive."""
        if not self.backup_manager:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        reply = QMessageBox.question(
            self, "Create Backup",
            "Create a full backup of the project?\nThis may take a few moments.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.status_panel.set_status("Creating backup...", "Please wait")
            self.logger.info("Creating backup...")
            
            try:
                backup_path = self.backup_manager.create_backup(
                    self.config.get_ignore_patterns()
                )
                self.config.set('last_backup_path', str(backup_path))
                self.config.save()
                
                size_mb = round(backup_path.stat().st_size / (1024 * 1024), 2)
                self.status_panel.set_status("Backup Created", str(backup_path))
                self.logger.info(f"Backup created: {backup_path} ({size_mb} MB)")
                QMessageBox.information(
                    self, "Backup Created",
                    f"Backup created successfully!\n\nLocation: {backup_path}\nSize: {size_mb} MB"
                )
            except Exception as e:
                self.logger.error(f"Backup error: {e}")
                QMessageBox.critical(self, "Backup Error", f"Error creating backup:\n\n{str(e)}")
    
    def select_orphaned_files(self):
        """Select all orphaned files in tree."""
        if self.orphaned_files:
            self.file_tree.set_checked_files(self.orphaned_files)
            self.logger.info(f"Selected {len(self.orphaned_files)} orphaned files")
    
    def clear_file_selection(self):
        """Clear file selection."""
        self.file_tree.set_checked_files(set())
        self.logger.info("Cleared file selection")
    
    def batch_delete(self):
        """Perform batch deletion."""
        checked = self.file_tree.get_checked_files()
        if not checked:
            QMessageBox.warning(self, "No Selection", "No files selected for deletion")
            return
        
        if not self.deletion_manager or not self.sanity_checker:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        # Pre-deletion check
        self.logger.info("Running pre-deletion sanity check...")
        check = self.sanity_checker.pre_deletion_check(checked)
        
        if not check['safe_to_proceed']:
            msg = "WARNING: Pre-deletion check failed!\n\n"
            msg += "Critical Issues:\n" + "\n".join(check['critical'])
            QMessageBox.critical(self, "Cannot Delete", msg)
            return
        
        # Show confirmation with warnings
        msg = f"Delete {len(checked)} files?\n\n"
        if check['warnings']:
            msg += "Warnings:\n" + "\n".join(check['warnings'][:5])
            if len(check['warnings']) > 5:
                msg += f"\n... and {len(check['warnings']) - 5} more warnings"
        
        reply = QMessageBox.question(self, "Confirm Deletion", msg, QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Create backup first
            self.logger.info("Creating pre-deletion backup...")
            backup_path = self.backup_manager.create_backup(self.config.get_ignore_patterns())
            
            # Perform deletion
            self.logger.info(f"Deleting {len(checked)} files...")
            self.deletion_manager.deletion_queue = checked
            result = self.deletion_manager.execute_deletions()
            
            self.logger.info(f"Deletion complete: {result['successful']} successful, {result['failed']} failed")
            
            # Post-deletion check
            post_check = self.sanity_checker.post_deletion_check()
            
            if not post_check['all_ok']:
                msg = f"Deleted {result['successful']} files, but issues detected:\n\n"
                msg += f"Broken includes: {len(post_check['broken_includes'])}\n"
                msg += f"Broken links: {len(post_check['broken_links'])}\n\n"
                msg += "Restore from backup?"
                
                reply = QMessageBox.question(self, "Issues Detected", msg, QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.restore_backup()
            else:
                QMessageBox.information(
                    self, "Success",
                    f"Successfully deleted {result['successful']} files!\n\nNo issues detected."
                )
                # Rescan
                self.start_scan()
    
    def individual_delete(self):
        """Perform individual deletion with confirmations."""
        checked = list(self.file_tree.get_checked_files())
        if not checked:
            QMessageBox.warning(self, "No Selection", "No files selected for deletion")
            return
        
        QMessageBox.information(
            self, "Individual Delete",
            f"Will process {len(checked)} files one by one.\n\nClick OK to start."
        )
        
        deleted_count = 0
        for file_key in checked:
            file_info = self.scanner.get_file_by_relative_path(file_key)
            if not file_info:
                continue
            
            msg = f"Delete this file?\n\n{file_key}\n\nSize: {round(file_info.size/1024, 2)} KB"
            reply = QMessageBox.question(
                self, "Delete File",
                msg,
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                break
            elif reply == QMessageBox.Yes:
                if self.deletion_manager.delete_file(file_key):
                    deleted_count += 1
                    self.logger.info(f"Deleted: {file_key}")
        
        if deleted_count > 0:
            QMessageBox.information(
                self, "Complete",
                f"Deleted {deleted_count} file(s)"
            )
            self.start_scan()
    
    def restore_backup(self):
        """Restore from backup."""
        if not self.backup_manager:
            QMessageBox.warning(self, "Error", "Backup manager not initialized")
            return
        
        backups = self.backup_manager.list_backups()
        if not backups:
            QMessageBox.warning(self, "No Backups", "No backup archives found")
            return
        
        latest = backups[0]
        msg = f"Restore from latest backup?\n\n{latest['name']}\nDate: {latest['date_str']}\nSize: {latest['size_mb']} MB"
        
        reply = QMessageBox.question(self, "Restore Backup", msg, QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.logger.info(f"Restoring backup: {latest['name']}")
            if self.backup_manager.restore_backup(latest['path']):
                self.logger.info("Backup restored successfully")
                QMessageBox.information(self, "Success", "Backup restored successfully!")
                self.start_scan()
            else:
                self.logger.error("Backup restoration failed")
                QMessageBox.critical(self, "Error", "Failed to restore backup")
    
    def list_backups(self):
        """List all available backups."""
        if not self.backup_manager:
            QMessageBox.warning(self, "Error", "Backup manager not initialized")
            return
        
        backups = self.backup_manager.list_backups()
        if not backups:
            QMessageBox.information(self, "No Backups", "No backup archives found")
            return
        
        msg = "Available Backups:\n\n"
        for backup in backups[:10]:
            msg += f"{backup['name']}\n  Date: {backup['date_str']}, Size: {backup['size_mb']} MB\n\n"
        
        if len(backups) > 10:
            msg += f"... and {len(backups) - 10} more"
        
        QMessageBox.information(self, "Backups", msg)
    
    def generate_sitemap(self):
        """Generate sitemap.xml."""
        if not self.scanner:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        base_url = self.base_url_input.text()
        if not base_url:
            QMessageBox.warning(self, "Error", "Please enter a base URL")
            return
        
        root_dir = Path(self.root_dir_input.text())
        output_path = root_dir / "sitemap.xml"
        
        generator = SitemapGenerator(self.scanner, base_url)
        generator.generate_sitemap(output_path)
        
        stats = generator.get_sitemap_stats()
        self.logger.info(f"Sitemap generated: {output_path}")
        QMessageBox.information(
            self, "Success",
            f"Sitemap generated!\n\nLocation: {output_path}\nURLs included: {stats['included_in_sitemap']}"
        )
    
    def generate_tree_map(self):
        """Generate system tree map."""
        if not self.scanner or not self.dependency_graph:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        root_dir = Path(self.root_dir_input.text())
        output_path = root_dir / "system-tree-map.md"
        
        generator = MarkdownGenerator(self.scanner, self.dependency_graph)
        generator.generate_tree_map(output_path)
        
        self.logger.info(f"Tree map generated: {output_path}")
        QMessageBox.information(self, "Success", f"System tree map generated!\n\nLocation: {output_path}")
    
    def generate_navigation_map(self):
        """Generate navigation map."""
        if not self.scanner or not self.dependency_graph:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        root_dir = Path(self.root_dir_input.text())
        output_path = root_dir / "navigation-map.md"
        
        generator = MarkdownGenerator(self.scanner, self.dependency_graph)
        generator.generate_navigation_map(output_path)
        
        self.logger.info(f"Navigation map generated: {output_path}")
        QMessageBox.information(self, "Success", f"Navigation map generated!\n\nLocation: {output_path}")
    
    def generate_all_docs(self):
        """Generate all documentation."""
        self.generate_sitemap()
        self.generate_tree_map()
        self.generate_navigation_map()
        self.generate_style_report()
    
    def generate_style_report(self):
        """Generate style error report."""
        if not self.scanner or not self.dependency_graph:
            QMessageBox.warning(self, "Error", "Please run a scan first")
            return
        
        root_dir = Path(self.root_dir_input.text())
        output_path = root_dir / "style-error-report.md"
        
        try:
            from OrphanHunter.analyzer.css_analyzer import StyleErrorReportGenerator
            
            generator = StyleErrorReportGenerator(
                self.dependency_graph.css_analyzer,
                self.dependency_graph.asset_analyzer
            )
            generator.generate_report(output_path)
            
            self.logger.info(f"Style error report generated: {output_path}")
            QMessageBox.information(
                self, "Success",
                f"Style error report generated!\n\nLocation: {output_path}"
            )
        except Exception as e:
            self.logger.error(f"Error generating style report: {e}")
            QMessageBox.critical(self, "Error", f"Failed to generate style report:\n\n{str(e)}")
    
    def open_url_migration(self):
        """Open URL Migration Tool window."""
        # Ensure root directory is set
        root_dir = self.root_dir_input.text().strip()
        if not root_dir or not Path(root_dir).exists():
            QMessageBox.warning(
                self, 
                "Root Directory Required", 
                "Please set a valid root directory in the Configuration tab first."
            )
            return
        
        # Create and show URL migration window
        migration_window = URLMigrationWindow(self.config, self)
        migration_window.exec_()

