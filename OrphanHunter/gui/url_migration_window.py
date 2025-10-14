"""URL Migration Window - comprehensive URL replacement tool."""
import sys
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar,
    QTableWidget, QTableWidgetItem, QTextEdit, QGroupBox, QComboBox,
    QCheckBox, QLineEdit, QSplitter, QMessageBox, QHeaderView, QFileDialog,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup, QTabWidget,
    QFormLayout, QSpinBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont

from OrphanHunter.utils.config import Config
from OrphanHunter.utils.url_config import URLConfig
from OrphanHunter.analyzer.url_analyzer import URLAnalyzer, URLInstance
from OrphanHunter.operations.url_migrator import URLMigrator, ChangeRecord
from OrphanHunter.operations.backup_manager import BackupManager


class URLScanWorker(QThread):
    """Worker thread for URL scanning operations."""
    
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, root_dir, url_config, config):
        super().__init__()
        self.root_dir = Path(root_dir)
        self.url_config = url_config
        self.config = config
    
    def run(self):
        """Run the URL scan operation."""
        try:
            result = {}
            
            # Get all internal domains
            internal_domains = self.url_config.get_all_internal_domains()
            external_whitelist = self.url_config.get("external_whitelist", [])
            
            self.progress.emit(f"Scanning for URLs (domains: {', '.join(internal_domains) or 'none configured'})...")
            
            # Create analyzer
            analyzer = URLAnalyzer(internal_domains, external_whitelist)
            
            # Detect helper functions from config files
            config_files = []
            if self.config.get("config_php_path"):
                config_files.append(Path(self.config.get("config_php_path")))
            
            # Look for header.php
            header_paths = list(self.root_dir.rglob("header.php"))
            config_files.extend(header_paths[:3])  # Check first 3 matches
            
            self.progress.emit("Detecting URL helper functions...")
            helpers = analyzer.detect_helper_functions(config_files)
            result['helpers'] = helpers
            
            # Extract domains from config if not already set
            if not internal_domains and self.config.get("config_php_path"):
                self.progress.emit("Extracting domains from config.php...")
                extracted_domains = analyzer.extract_domain_from_config(
                    Path(self.config.get("config_php_path"))
                )
                result['extracted_domains'] = extracted_domains
            
            # Scan all files
            file_types = self.url_config.get_enabled_file_types()
            ignore_patterns = self.config.get_ignore_patterns()
            
            self.progress.emit(f"Scanning files ({', '.join(file_types)})...")
            url_instances = analyzer.scan_directory(self.root_dir, file_types, ignore_patterns)
            result['url_instances'] = url_instances
            
            # Verify classifications (second pass)
            self.progress.emit("Verifying URL classifications...")
            verification = analyzer.verify_classification()
            result['verification'] = verification
            
            result['analyzer'] = analyzer
            
            self.progress.emit("Scan complete!")
            self.finished.emit(result)
            
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class URLMigrationWindow(QDialog):
    """Main window for URL migration workflow."""
    
    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self.url_config = URLConfig()
        self.root_dir = Path(self.config.get('root_directory', ''))
        
        self.analyzer = None
        self.migrator = None
        self.backup_manager = None
        self.scan_results = None
        self.change_records = []
        self.selected_records = []
        self.backup_path = None
        
        self.current_step = 0
        self.steps = [
            "Configure & Scan",
            "Verify Results",
            "Review Changes",
            "Create Backup",
            "Final Approval",
            "Apply Changes",
            "Rollback Options"
        ]
        
        self.init_ui()
        self.setWindowTitle("URL Migration Tool")
        self.resize(1200, 800)
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()
        
        # Step indicator
        self.step_label = QLabel()
        self.step_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.step_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.step_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Tab widget for different steps
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Step 1: Configure & Scan
        self.step1_widget = self.create_step1_configure()
        self.tab_widget.addTab(self.step1_widget, "1. Configure & Scan")
        
        # Step 2: Verify Results
        self.step2_widget = self.create_step2_verify()
        self.tab_widget.addTab(self.step2_widget, "2. Verify Results")
        
        # Step 3: Review Changes
        self.step3_widget = self.create_step3_review()
        self.tab_widget.addTab(self.step3_widget, "3. Review Changes")
        
        # Step 4: Backup
        self.step4_widget = self.create_step4_backup()
        self.tab_widget.addTab(self.step4_widget, "4. Create Backup")
        
        # Step 5: Final Approval
        self.step5_widget = self.create_step5_approval()
        self.tab_widget.addTab(self.step5_widget, "5. Final Approval")
        
        # Step 6: Apply Changes
        self.step6_widget = self.create_step6_apply()
        self.tab_widget.addTab(self.step6_widget, "6. Apply Changes")
        
        # Step 7: Rollback
        self.step7_widget = self.create_step7_rollback()
        self.tab_widget.addTab(self.step7_widget, "7. Rollback Options")
        
        # Disable tabs initially
        for i in range(1, 7):
            self.tab_widget.setTabEnabled(i, False)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_step)
        self.prev_button.setEnabled(False)
        button_layout.addWidget(self.prev_button)
        
        button_layout.addStretch()
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_step)
        button_layout.addWidget(self.next_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        self.update_step_display()
    
    def create_step1_configure(self):
        """Step 1: Configuration and initial scan."""
        widget = QGroupBox("Configuration")
        layout = QVBoxLayout()
        
        # Domain configuration
        domain_group = QGroupBox("Internal Domains")
        domain_layout = QVBoxLayout()
        
        domain_layout.addWidget(QLabel("Internal domains that should be converted to dynamic URLs:"))
        
        self.domain_list = QListWidget()
        domain_layout.addWidget(self.domain_list)
        
        domain_btn_layout = QHBoxLayout()
        self.add_domain_btn = QPushButton("Add Domain")
        self.add_domain_btn.clicked.connect(self.add_internal_domain)
        domain_btn_layout.addWidget(self.add_domain_btn)
        
        self.remove_domain_btn = QPushButton("Remove Domain")
        self.remove_domain_btn.clicked.connect(self.remove_internal_domain)
        domain_btn_layout.addWidget(self.remove_domain_btn)
        
        self.auto_detect_btn = QPushButton("Auto-Detect from config.php")
        self.auto_detect_btn.clicked.connect(self.auto_detect_domains)
        domain_btn_layout.addWidget(self.auto_detect_btn)
        
        domain_layout.addLayout(domain_btn_layout)
        domain_group.setLayout(domain_layout)
        layout.addWidget(domain_group)
        
        # Legacy domains
        legacy_group = QGroupBox("Legacy Domains")
        legacy_layout = QVBoxLayout()
        legacy_layout.addWidget(QLabel("Additional old domains to convert:"))
        
        self.legacy_list = QListWidget()
        legacy_layout.addWidget(self.legacy_list)
        
        legacy_btn_layout = QHBoxLayout()
        self.add_legacy_btn = QPushButton("Add Legacy Domain")
        self.add_legacy_btn.clicked.connect(self.add_legacy_domain)
        legacy_btn_layout.addWidget(self.add_legacy_btn)
        
        self.remove_legacy_btn = QPushButton("Remove Legacy Domain")
        self.remove_legacy_btn.clicked.connect(self.remove_legacy_domain)
        legacy_btn_layout.addWidget(self.remove_legacy_btn)
        
        legacy_layout.addLayout(legacy_btn_layout)
        legacy_group.setLayout(legacy_layout)
        layout.addWidget(legacy_group)
        
        # Replacement format
        format_group = QGroupBox("Replacement Format")
        format_layout = QFormLayout()
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Auto-detect", "BASE_URL", "safe_url()", "asset_url()", "Custom"])
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        format_layout.addRow("Format:", self.format_combo)
        
        self.custom_format_input = QLineEdit()
        self.custom_format_input.setPlaceholderText("e.g., $config['base_url'] . '{path}'")
        self.custom_format_input.setEnabled(False)
        format_layout.addRow("Custom Format:", self.custom_format_input)
        
        format_group.setLayout(format_layout)
        layout.addWidget(format_group)
        
        # File types
        filetype_group = QGroupBox("File Types to Scan")
        filetype_layout = QVBoxLayout()
        
        self.php_check = QCheckBox(".php")
        self.php_check.setChecked(True)
        self.html_check = QCheckBox(".html")
        self.html_check.setChecked(True)
        self.js_check = QCheckBox(".js")
        self.js_check.setChecked(True)
        self.css_check = QCheckBox(".css")
        self.css_check.setChecked(True)
        self.sql_check = QCheckBox(".sql")
        self.sql_check.setChecked(True)
        
        ft_layout = QHBoxLayout()
        ft_layout.addWidget(self.php_check)
        ft_layout.addWidget(self.html_check)
        ft_layout.addWidget(self.js_check)
        ft_layout.addWidget(self.css_check)
        ft_layout.addWidget(self.sql_check)
        filetype_layout.addLayout(ft_layout)
        
        filetype_group.setLayout(filetype_layout)
        layout.addWidget(filetype_group)
        
        # Scan button
        self.scan_button = QPushButton("Start Scan")
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        layout.addWidget(self.scan_button)
        
        layout.addStretch()
        widget.setLayout(layout)
        
        self.load_config_to_ui()
        return widget
    
    def create_step2_verify(self):
        """Step 2: Sanity check and verification results."""
        widget = QGroupBox("Verification Results")
        layout = QVBoxLayout()
        
        # Statistics
        stats_layout = QFormLayout()
        self.total_urls_label = QLabel("0")
        self.internal_urls_label = QLabel("0")
        self.external_urls_label = QLabel("0")
        self.helpers_found_label = QLabel("None")
        
        stats_layout.addRow("Total URLs Found:", self.total_urls_label)
        stats_layout.addRow("Internal URLs (to migrate):", self.internal_urls_label)
        stats_layout.addRow("External URLs (ignored):", self.external_urls_label)
        stats_layout.addRow("Helper Functions Detected:", self.helpers_found_label)
        
        layout.addLayout(stats_layout)
        
        # Issues/warnings
        layout.addWidget(QLabel("Potential Issues:"))
        self.issues_text = QTextEdit()
        self.issues_text.setReadOnly(True)
        self.issues_text.setMaximumHeight(150)
        layout.addWidget(self.issues_text)
        
        # Sample URLs
        layout.addWidget(QLabel("Sample URLs Found:"))
        self.sample_table = QTableWidget()
        self.sample_table.setColumnCount(4)
        self.sample_table.setHorizontalHeaderLabels(["Type", "Domain", "URL", "File"])
        self.sample_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.sample_table)
        
        widget.setLayout(layout)
        return widget
    
    def create_step3_review(self):
        """Step 3: Review all proposed changes."""
        widget = QGroupBox("Review Proposed Changes")
        layout = QVBoxLayout()
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter by file, URL, or path...")
        self.filter_input.textChanged.connect(self.filter_changes)
        filter_layout.addWidget(self.filter_input)
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_changes)
        filter_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all_changes)
        filter_layout.addWidget(self.deselect_all_btn)
        
        layout.addLayout(filter_layout)
        
        # Changes table
        self.changes_table = QTableWidget()
        self.changes_table.setColumnCount(6)
        self.changes_table.setHorizontalHeaderLabels([
            "Include", "File", "Line", "Old URL", "New Format", "Context"
        ])
        self.changes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.changes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.changes_table.itemSelectionChanged.connect(self.on_change_selected)
        layout.addWidget(self.changes_table)
        
        # Context viewer
        layout.addWidget(QLabel("Context:"))
        self.context_viewer = QTextEdit()
        self.context_viewer.setReadOnly(True)
        self.context_viewer.setMaximumHeight(150)
        layout.addWidget(self.context_viewer)
        
        # Summary
        self.changes_summary_label = QLabel()
        layout.addWidget(self.changes_summary_label)
        
        widget.setLayout(layout)
        return widget
    
    def create_step4_backup(self):
        """Step 4: Backup creation."""
        widget = QGroupBox("Create Backup")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("A full backup will be created before making any changes."))
        layout.addWidget(QLabel("This backup can be used to restore your system if needed."))
        
        # Backup info
        info_layout = QFormLayout()
        self.backup_dir_label = QLabel()
        self.backup_size_label = QLabel()
        
        info_layout.addRow("Backup Directory:", self.backup_dir_label)
        info_layout.addRow("Estimated Size:", self.backup_size_label)
        
        layout.addLayout(info_layout)
        
        # Create backup button
        self.create_backup_btn = QPushButton("Create Backup Now")
        self.create_backup_btn.clicked.connect(self.create_backup)
        self.create_backup_btn.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        layout.addWidget(self.create_backup_btn)
        
        # Backup result
        self.backup_result_text = QTextEdit()
        self.backup_result_text.setReadOnly(True)
        self.backup_result_text.setMaximumHeight(200)
        layout.addWidget(self.backup_result_text)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def create_step5_approval(self):
        """Step 5: Final approval before migration."""
        widget = QGroupBox("Final Approval")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Please review the summary before proceeding:"))
        
        self.approval_summary = QTextEdit()
        self.approval_summary.setReadOnly(True)
        layout.addWidget(self.approval_summary)
        
        # Warning
        warning_label = QLabel("WARNING: This will modify your files. Make sure the backup was created successfully!")
        warning_label.setStyleSheet("QLabel { color: red; font-weight: bold; }")
        layout.addWidget(warning_label)
        
        # Confirmation checkbox
        self.confirm_check = QCheckBox("I have reviewed the changes and want to proceed")
        layout.addWidget(self.confirm_check)
        
        widget.setLayout(layout)
        return widget
    
    def create_step6_apply(self):
        """Step 6: Apply changes with progress tracking."""
        widget = QGroupBox("Applying Changes")
        layout = QVBoxLayout()
        
        self.apply_progress = QProgressBar()
        layout.addWidget(self.apply_progress)
        
        self.apply_status_label = QLabel()
        self.apply_status_label.setWordWrap(True)
        layout.addWidget(self.apply_status_label)
        
        # Results
        self.apply_results_text = QTextEdit()
        self.apply_results_text.setReadOnly(True)
        layout.addWidget(self.apply_results_text)
        
        # Apply button
        self.apply_button = QPushButton("Apply Changes Now")
        self.apply_button.clicked.connect(self.apply_changes)
        self.apply_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; }")
        layout.addWidget(self.apply_button)
        
        widget.setLayout(layout)
        return widget
    
    def create_step7_rollback(self):
        """Step 7: Rollback options."""
        widget = QGroupBox("Rollback Options")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("If something went wrong, you can rollback the changes:"))
        
        # Rollback type selection
        self.rollback_group = QButtonGroup()
        
        self.full_rollback_radio = QRadioButton("Full Rollback - Restore entire backup")
        self.full_rollback_radio.setChecked(True)
        self.rollback_group.addButton(self.full_rollback_radio)
        layout.addWidget(self.full_rollback_radio)
        
        self.selective_rollback_radio = QRadioButton("Selective Rollback - Choose files to revert")
        self.rollback_group.addButton(self.selective_rollback_radio)
        layout.addWidget(self.selective_rollback_radio)
        
        # File selection for selective rollback
        layout.addWidget(QLabel("Files to rollback (for selective rollback):"))
        self.rollback_file_list = QListWidget()
        self.rollback_file_list.setSelectionMode(QListWidget.MultiSelection)
        layout.addWidget(self.rollback_file_list)
        
        # Rollback buttons
        btn_layout = QHBoxLayout()
        
        self.rollback_button = QPushButton("Perform Rollback")
        self.rollback_button.clicked.connect(self.perform_rollback)
        self.rollback_button.setStyleSheet("QPushButton { font-size: 14px; padding: 10px; background-color: #ff6b6b; }")
        btn_layout.addWidget(self.rollback_button)
        
        layout.addLayout(btn_layout)
        
        # Rollback result
        self.rollback_result_text = QTextEdit()
        self.rollback_result_text.setReadOnly(True)
        layout.addWidget(self.rollback_result_text)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
    
    def update_step_display(self):
        """Update the step display label."""
        self.step_label.setText(f"Step {self.current_step + 1}: {self.steps[self.current_step]}")
        self.tab_widget.setCurrentIndex(self.current_step)
        
        # Update button states
        self.prev_button.setEnabled(self.current_step > 0)
        
        # Disable next on certain steps until conditions are met
        if self.current_step == 0:
            self.next_button.setEnabled(self.scan_results is not None)
        elif self.current_step == 3:
            self.next_button.setEnabled(self.backup_path is not None)
        elif self.current_step == 4:
            self.next_button.setEnabled(self.confirm_check.isChecked())
        else:
            self.next_button.setEnabled(True)
    
    def next_step(self):
        """Move to next step."""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
            self.tab_widget.setTabEnabled(self.current_step, True)
            self.update_step_display()
            
            # Prepare the step
            if self.current_step == 2:
                self.prepare_step3()
            elif self.current_step == 3:
                self.prepare_step4()
            elif self.current_step == 4:
                self.prepare_step5()
            elif self.current_step == 6:
                self.prepare_step7()
    
    def previous_step(self):
        """Move to previous step."""
        if self.current_step > 0:
            self.current_step -= 1
            self.update_step_display()
    
    def load_config_to_ui(self):
        """Load configuration into UI elements."""
        # Load domains
        self.domain_list.clear()
        for domain in self.url_config.get("internal_domains", []):
            self.domain_list.addItem(domain)
        
        self.legacy_list.clear()
        for domain in self.url_config.get("legacy_domains", []):
            self.legacy_list.addItem(domain)
        
        # Load format
        format_map = {
            "auto": 0,
            "base_url": 1,
            "safe_url": 2,
            "asset_url": 3,
            "custom": 4
        }
        format_type = self.url_config.get("replacement_format", "auto")
        self.format_combo.setCurrentIndex(format_map.get(format_type, 0))
        
        if format_type == "custom":
            self.custom_format_input.setText(self.url_config.get("custom_format", ""))
    
    def save_config_from_ui(self):
        """Save configuration from UI elements."""
        # Save domains
        domains = [self.domain_list.item(i).text() for i in range(self.domain_list.count())]
        self.url_config.set("internal_domains", domains)
        
        legacy = [self.legacy_list.item(i).text() for i in range(self.legacy_list.count())]
        self.url_config.set("legacy_domains", legacy)
        
        # Save format
        format_map = {
            0: "auto",
            1: "base_url",
            2: "safe_url",
            3: "asset_url",
            4: "custom"
        }
        format_type = format_map[self.format_combo.currentIndex()]
        self.url_config.set_replacement_format(format_type, self.custom_format_input.text())
        
        # Save file types
        file_types = []
        if self.php_check.isChecked():
            file_types.append(".php")
        if self.html_check.isChecked():
            file_types.append(".html")
        if self.js_check.isChecked():
            file_types.append(".js")
        if self.css_check.isChecked():
            file_types.append(".css")
        if self.sql_check.isChecked():
            file_types.append(".sql")
        
        self.url_config.set_enabled_file_types(file_types)
        self.url_config.save()
    
    def add_internal_domain(self):
        """Add internal domain."""
        from PyQt5.QtWidgets import QInputDialog
        domain, ok = QInputDialog.getText(self, "Add Internal Domain", "Enter domain (e.g., example.com):")
        if ok and domain:
            self.url_config.add_internal_domain(domain)
            self.domain_list.addItem(self.url_config._normalize_domain(domain))
    
    def remove_internal_domain(self):
        """Remove selected internal domain."""
        current = self.domain_list.currentItem()
        if current:
            domain = current.text()
            self.url_config.remove_internal_domain(domain)
            self.domain_list.takeItem(self.domain_list.row(current))
    
    def add_legacy_domain(self):
        """Add legacy domain."""
        from PyQt5.QtWidgets import QInputDialog
        domain, ok = QInputDialog.getText(self, "Add Legacy Domain", "Enter legacy domain (e.g., old-site.com):")
        if ok and domain:
            self.url_config.add_legacy_domain(domain)
            self.legacy_list.addItem(self.url_config._normalize_domain(domain))
    
    def remove_legacy_domain(self):
        """Remove selected legacy domain."""
        current = self.legacy_list.currentItem()
        if current:
            domain = current.text()
            self.url_config.remove_legacy_domain(domain)
            self.legacy_list.takeItem(self.legacy_list.row(current))
    
    def auto_detect_domains(self):
        """Auto-detect domains from config.php."""
        config_php_path = self.config.get("config_php_path")
        if not config_php_path:
            QMessageBox.warning(self, "No config.php", "Please set config.php path in main settings first.")
            return
        
        config_php = Path(config_php_path)
        if not config_php.exists():
            QMessageBox.warning(self, "File Not Found", f"config.php not found at {config_php_path}")
            return
        
        analyzer = URLAnalyzer([], [])
        domains = analyzer.extract_domain_from_config(config_php)
        
        if domains:
            for domain in domains:
                self.url_config.add_internal_domain(domain)
                self.domain_list.addItem(domain)
            QMessageBox.information(self, "Success", f"Found {len(domains)} domain(s): {', '.join(domains)}")
        else:
            QMessageBox.information(self, "No Domains", "No domains found in config.php")
    
    def on_format_changed(self, text):
        """Handle format selection change."""
        self.custom_format_input.setEnabled(text == "Custom")
    
    def start_scan(self):
        """Start the URL scanning process."""
        # Save configuration first
        self.save_config_from_ui()
        
        # Validate configuration
        if not self.url_config.get_all_internal_domains():
            reply = QMessageBox.question(
                self,
                "No Internal Domains",
                "No internal domains configured. This means no URLs will be migrated.\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        if not self.root_dir or not self.root_dir.exists():
            QMessageBox.warning(self, "Invalid Directory", "Please set root directory in main settings first.")
            return
        
        # Start scan worker
        self.scan_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_label.setText("Scanning...")
        
        self.scan_worker = URLScanWorker(self.root_dir, self.url_config, self.config)
        self.scan_worker.progress.connect(self.on_scan_progress)
        self.scan_worker.finished.connect(self.on_scan_finished)
        self.scan_worker.error.connect(self.on_scan_error)
        self.scan_worker.start()
    
    @pyqtSlot(str)
    def on_scan_progress(self, message):
        """Handle scan progress updates."""
        self.status_label.setText(message)
    
    @pyqtSlot(dict)
    def on_scan_finished(self, results):
        """Handle scan completion."""
        self.scan_results = results
        self.analyzer = results.get('analyzer')
        
        self.progress_bar.setVisible(False)
        self.scan_button.setEnabled(True)
        self.status_label.setText("Scan complete! Click Next to review results.")
        
        # Auto-add extracted domains
        if 'extracted_domains' in results and results['extracted_domains']:
            for domain in results['extracted_domains']:
                self.url_config.add_internal_domain(domain)
                self.domain_list.addItem(domain)
        
        # Populate step 2
        self.populate_step2()
        
        # Enable next button
        self.update_step_display()
        
        QMessageBox.information(self, "Scan Complete", 
                              f"Found {len(results['url_instances'])} URLs\n"
                              f"Internal: {results['verification']['internal_urls']}\n"
                              f"External: {results['verification']['external_urls']}")
    
    @pyqtSlot(str)
    def on_scan_error(self, error_msg):
        """Handle scan error."""
        self.progress_bar.setVisible(False)
        self.scan_button.setEnabled(True)
        self.status_label.setText("Scan failed!")
        QMessageBox.critical(self, "Scan Error", f"An error occurred during scanning:\n\n{error_msg}")
    
    def populate_step2(self):
        """Populate step 2 verification results."""
        if not self.scan_results:
            return
        
        verification = self.scan_results['verification']
        helpers = self.scan_results.get('helpers', [])
        
        # Update statistics
        self.total_urls_label.setText(str(verification['total_urls']))
        self.internal_urls_label.setText(str(verification['internal_urls']))
        self.external_urls_label.setText(str(verification['external_urls']))
        
        if helpers:
            helper_names = [h.name for h in helpers]
            self.helpers_found_label.setText(", ".join(helper_names))
        else:
            self.helpers_found_label.setText("None - using BASE_URL constant")
        
        # Show issues
        issues = verification.get('potential_issues', [])
        if issues:
            self.issues_text.setPlainText("\n".join(issues))
        else:
            self.issues_text.setPlainText("No issues detected.")
        
        # Sample URLs
        url_instances = self.scan_results['url_instances']
        internal = [u for u in url_instances if u.is_internal][:20]
        external = [u for u in url_instances if not u.is_internal][:10]
        
        self.sample_table.setRowCount(0)
        
        for url in internal:
            row = self.sample_table.rowCount()
            self.sample_table.insertRow(row)
            self.sample_table.setItem(row, 0, QTableWidgetItem("Internal"))
            self.sample_table.setItem(row, 1, QTableWidgetItem(url.domain))
            self.sample_table.setItem(row, 2, QTableWidgetItem(url.url[:50]))
            self.sample_table.setItem(row, 3, QTableWidgetItem(str(url.file_path)))
        
        for url in external:
            row = self.sample_table.rowCount()
            self.sample_table.insertRow(row)
            self.sample_table.setItem(row, 0, QTableWidgetItem("External"))
            item = QTableWidgetItem(url.domain)
            item.setBackground(QColor(255, 255, 200))
            self.sample_table.setItem(row, 1, item)
            self.sample_table.setItem(row, 2, QTableWidgetItem(url.url[:50]))
            self.sample_table.setItem(row, 3, QTableWidgetItem(str(url.file_path)))
    
    def prepare_step3(self):
        """Prepare step 3 - generate and display change records."""
        if not self.analyzer:
            return
        
        # Create migrator
        format_map = {
            0: "auto",
            1: "base_url",
            2: "safe_url",
            3: "asset_url",
            4: "custom"
        }
        format_type = format_map[self.format_combo.currentIndex()]
        custom_format = self.custom_format_input.text() if format_type == "custom" else ""
        
        self.migrator = URLMigrator(self.root_dir, format_type, custom_format)
        
        # Plan replacements
        internal_urls = self.analyzer.get_internal_urls()
        helpers = self.scan_results.get('helpers', [])
        self.change_records = self.migrator.plan_replacements(internal_urls, helpers)
        
        # Populate changes table
        self.changes_table.setRowCount(0)
        
        for record in self.change_records:
            row = self.changes_table.rowCount()
            self.changes_table.insertRow(row)
            
            # Checkbox
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            self.changes_table.setCellWidget(row, 0, checkbox)
            
            # File
            self.changes_table.setItem(row, 1, QTableWidgetItem(str(record.file_path)))
            
            # Line
            self.changes_table.setItem(row, 2, QTableWidgetItem(str(record.line_number)))
            
            # Old URL
            self.changes_table.setItem(row, 3, QTableWidgetItem(record.old_url[:40]))
            
            # New format
            self.changes_table.setItem(row, 4, QTableWidgetItem(record.new_url[:40]))
            
            # Context (first part of line)
            context = record.old_line[:30] + "..." if len(record.old_line) > 30 else record.old_line
            self.changes_table.setItem(row, 5, QTableWidgetItem(context))
        
        self.changes_summary_label.setText(
            f"Total changes: {len(self.change_records)} in {len(self.migrator.get_changes_by_file())} files"
        )
    
    def prepare_step4(self):
        """Prepare step 4 - backup information."""
        backup_dir = self.config.get("backup_directory", "system-mapper-backups")
        self.backup_dir_label.setText(str(Path(backup_dir).resolve()))
        
        # Estimate size
        total_size = sum(f.stat().st_size for f in self.root_dir.rglob('*') if f.is_file())
        size_mb = total_size / (1024 * 1024)
        self.backup_size_label.setText(f"{size_mb:.2f} MB")
    
    def prepare_step5(self):
        """Prepare step 5 - final approval summary."""
        summary_lines = [
            "MIGRATION SUMMARY",
            "=" * 60,
            f"Root Directory: {self.root_dir}",
            f"Replacement Format: {self.format_combo.currentText()}",
            "",
            f"Total Changes: {len(self.get_selected_records())}",
            f"Files to Modify: {len(set(r.file_path for r in self.get_selected_records()))}",
            f"Backup Location: {self.backup_path}",
            "",
            "=" * 60,
            "Files that will be modified:",
            ""
        ]
        
        files_by_count = {}
        for record in self.get_selected_records():
            files_by_count[record.file_path] = files_by_count.get(record.file_path, 0) + 1
        
        for file_path, count in sorted(files_by_count.items()):
            summary_lines.append(f"  {file_path}: {count} changes")
        
        self.approval_summary.setPlainText("\n".join(summary_lines))
    
    def prepare_step7(self):
        """Prepare step 7 - rollback options."""
        if not self.migrator:
            return
        
        # Populate file list for selective rollback
        self.rollback_file_list.clear()
        files = sorted(self.migrator.files_modified)
        for file_path in files:
            item = QListWidgetItem(str(file_path))
            self.rollback_file_list.addItem(item)
    
    def get_selected_records(self):
        """Get list of selected change records from table."""
        selected = []
        for row in range(self.changes_table.rowCount()):
            checkbox = self.changes_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                if row < len(self.change_records):
                    selected.append(self.change_records[row])
        return selected
    
    def filter_changes(self, text):
        """Filter the changes table."""
        for row in range(self.changes_table.rowCount()):
            show = True
            if text:
                file_item = self.changes_table.item(row, 1)
                url_item = self.changes_table.item(row, 3)
                new_item = self.changes_table.item(row, 4)
                
                if file_item and url_item and new_item:
                    file_text = file_item.text().lower()
                    url_text = url_item.text().lower()
                    new_text = new_item.text().lower()
                    filter_text = text.lower()
                    
                    show = filter_text in file_text or filter_text in url_text or filter_text in new_text
            
            self.changes_table.setRowHidden(row, not show)
    
    def select_all_changes(self):
        """Select all visible changes."""
        for row in range(self.changes_table.rowCount()):
            if not self.changes_table.isRowHidden(row):
                checkbox = self.changes_table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(True)
    
    def deselect_all_changes(self):
        """Deselect all changes."""
        for row in range(self.changes_table.rowCount()):
            checkbox = self.changes_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
    
    def on_change_selected(self):
        """Handle change selection in table."""
        current_row = self.changes_table.currentRow()
        if current_row >= 0 and current_row < len(self.change_records):
            record = self.change_records[current_row]
            
            # Show context
            context_lines = [
                f"File: {record.file_path}",
                f"Line: {record.line_number}",
                "",
                "OLD:",
                record.old_line,
                "",
                "NEW:",
                record.new_line,
            ]
            self.context_viewer.setPlainText("\n".join(context_lines))
    
    def create_backup(self):
        """Create full system backup."""
        if not self.root_dir:
            QMessageBox.warning(self, "Error", "Root directory not set.")
            return
        
        self.create_backup_btn.setEnabled(False)
        self.backup_result_text.setPlainText("Creating backup...")
        
        try:
            backup_dir = self.config.get("backup_directory", "system-mapper-backups")
            self.backup_manager = BackupManager(self.root_dir, backup_dir)
            
            ignore_patterns = self.config.get_ignore_patterns()
            self.backup_path = self.backup_manager.create_backup(ignore_patterns)
            
            # Verify backup
            verification = self.backup_manager.verify_backup(self.backup_path)
            
            result_text = [
                "Backup created successfully!",
                "",
                f"Location: {self.backup_path}",
                f"Files backed up: {verification['file_count']}",
                f"Size: {self.backup_path.stat().st_size / (1024*1024):.2f} MB",
                "",
                "You can now proceed to the next step."
            ]
            
            if not verification['valid']:
                result_text.append("")
                result_text.append("WARNING: Backup verification found issues:")
                result_text.extend(verification['errors'])
            
            self.backup_result_text.setPlainText("\n".join(result_text))
            self.update_step_display()
            
        except Exception as e:
            self.backup_result_text.setPlainText(f"ERROR: Failed to create backup:\n{str(e)}")
            QMessageBox.critical(self, "Backup Error", f"Failed to create backup:\n{str(e)}")
        finally:
            self.create_backup_btn.setEnabled(True)
    
    def apply_changes(self):
        """Apply the URL migrations."""
        if not self.migrator:
            QMessageBox.warning(self, "Error", "No migration planned.")
            return
        
        selected_records = self.get_selected_records()
        if not selected_records:
            QMessageBox.warning(self, "No Changes", "No changes selected to apply.")
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Changes",
            f"Apply {len(selected_records)} changes to {len(set(r.file_path for r in selected_records))} files?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        self.apply_button.setEnabled(False)
        self.apply_progress.setRange(0, 100)
        self.apply_status_label.setText("Applying changes...")
        
        def progress_callback(current, total):
            progress = int((current / total) * 100)
            self.apply_progress.setValue(progress)
            self.apply_status_label.setText(f"Processing file {current} of {total}...")
        
        try:
            results = self.migrator.apply_changes(selected_records, progress_callback)
            
            # Verify changes
            verification = self.migrator.verify_changes(self.root_dir)
            
            result_lines = [
                "MIGRATION COMPLETE",
                "=" * 60,
                f"Files Modified: {results['files_modified']}",
                f"Changes Applied: {results['changes_applied']}",
                "",
                "VERIFICATION:",
                f"Verified: {verification['verified']}",
                f"Applied: {verification['applied_count']}",
                f"Failed: {verification['failed_count']}",
            ]
            
            if results['errors']:
                result_lines.append("")
                result_lines.append("ERRORS:")
                result_lines.extend(results['errors'])
            
            if verification['failures']:
                result_lines.append("")
                result_lines.append("VERIFICATION FAILURES:")
                for failure in verification['failures']:
                    result_lines.append(f"  {failure['file']}:{failure['line']} - {failure['reason']}")
            
            self.apply_results_text.setPlainText("\n".join(result_lines))
            self.apply_progress.setValue(100)
            
            # Save report
            report_path = Path(self.config.get("backup_directory", "system-mapper-backups")) / \
                         f"url_migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            self.migrator.save_report(report_path)
            
            # Update config
            self.url_config.record_migration(str(self.backup_path), results['changes_applied'], results['files_modified'])
            self.url_config.save()
            
            QMessageBox.information(self, "Complete", 
                                  f"Migration complete!\n\n"
                                  f"Files modified: {results['files_modified']}\n"
                                  f"Changes applied: {results['changes_applied']}\n\n"
                                  f"Report saved to: {report_path}")
            
        except Exception as e:
            self.apply_results_text.setPlainText(f"ERROR: {str(e)}")
            QMessageBox.critical(self, "Migration Error", f"Failed to apply changes:\n{str(e)}")
        finally:
            self.apply_button.setEnabled(True)
    
    def perform_rollback(self):
        """Perform rollback operation."""
        if not self.backup_manager or not self.backup_path:
            QMessageBox.warning(self, "No Backup", "No backup available for rollback.")
            return
        
        if self.full_rollback_radio.isChecked():
            reply = QMessageBox.question(
                self,
                "Confirm Full Rollback",
                "This will restore ALL files from the backup.\n\nAre you sure?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    success = self.backup_manager.restore_backup(self.backup_path)
                    if success:
                        self.rollback_result_text.setPlainText(
                            "Full rollback complete!\n\n"
                            "All files have been restored from backup."
                        )
                        QMessageBox.information(self, "Success", "Full rollback complete!")
                    else:
                        self.rollback_result_text.setPlainText("Rollback failed!")
                        QMessageBox.critical(self, "Error", "Rollback failed!")
                except Exception as e:
                    self.rollback_result_text.setPlainText(f"ERROR: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Rollback error:\n{str(e)}")
        
        elif self.selective_rollback_radio.isChecked():
            selected_items = self.rollback_file_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "No Files", "Please select files to rollback.")
                return
            
            files_to_rollback = [item.text() for item in selected_items]
            
            reply = QMessageBox.question(
                self,
                "Confirm Selective Rollback",
                f"Rollback {len(files_to_rollback)} selected file(s)?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                try:
                    import zipfile
                    
                    restored_count = 0
                    errors = []
                    
                    with zipfile.ZipFile(self.backup_path, 'r') as zipf:
                        for file_rel in files_to_rollback:
                            try:
                                # Extract specific file
                                zipf.extract(file_rel, self.root_dir)
                                restored_count += 1
                            except Exception as e:
                                errors.append(f"{file_rel}: {str(e)}")
                    
                    result_lines = [
                        "Selective rollback complete!",
                        "",
                        f"Files restored: {restored_count}",
                        f"Errors: {len(errors)}"
                    ]
                    
                    if errors:
                        result_lines.append("")
                        result_lines.append("ERRORS:")
                        result_lines.extend(errors)
                    
                    self.rollback_result_text.setPlainText("\n".join(result_lines))
                    QMessageBox.information(self, "Complete", 
                                          f"Restored {restored_count} file(s).")
                    
                except Exception as e:
                    self.rollback_result_text.setPlainText(f"ERROR: {str(e)}")
                    QMessageBox.critical(self, "Error", f"Selective rollback error:\n{str(e)}")

