"""Site Scanner GUI Window."""
import sys
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QProgressBar, QSpinBox,
    QGroupBox, QFormLayout, QCheckBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QSplitter, QMessageBox, QFileDialog, QComboBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from OrphanHunter.scanner.site_scanner import SiteScanner, SiteScannerWithSQL


class SiteScanWorker(QThread):
    """Worker thread for site scanning."""
    
    progress = pyqtSignal(str, float)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, scanner):
        super().__init__()
        self.scanner = scanner
    
    def run(self):
        """Run the site scan."""
        try:
            self.scanner.add_progress_callback(self.progress.emit)
            self.scanner.start_scan(threaded=False)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))


class SiteScannerWindow(QMainWindow):
    """Main window for site scanning functionality."""
    
    def __init__(self, parent=None, db_connector=None):
        super().__init__(parent)
        self.db_connector = db_connector
        self.scanner = None
        self.scan_worker = None
        self.scanner_with_sql = None
        
        self.setWindowTitle("OrphanHunter - Live Site Scanner")
        self.setGeometry(100, 100, 1200, 800)
        
        self.init_ui()
        
        # Auto-refresh timer for monitoring
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.update_monitoring_display)
        
    def init_ui(self):
        """Initialize the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tabs
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Scanner tab
        self.scanner_tab = self.create_scanner_tab()
        self.tab_widget.addTab(self.scanner_tab, "Website Scanner")
        
        # Results tab
        self.results_tab = self.create_results_tab()
        self.tab_widget.addTab(self.results_tab, "Scan Results")
        
        # Monitoring tab
        self.monitoring_tab = self.create_monitoring_tab()
        self.tab_widget.addTab(self.monitoring_tab, "Live Monitoring")
        
        # History tab
        self.history_tab = self.create_history_tab()
        self.tab_widget.addTab(self.history_tab, "Scan History")
        
        # Status bar
        self.statusBar().showMessage("Ready to scan websites")
    
    def create_scanner_tab(self):
        """Create the main scanner configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Configuration group
        config_group = QGroupBox("Scan Configuration")
        config_layout = QFormLayout(config_group)
        
        # URL input
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        config_layout.addRow("Website URL:", self.url_input)
        
        # Max pages
        self.max_pages_input = QSpinBox()
        self.max_pages_input.setRange(1, 10000)
        self.max_pages_input.setValue(1000)
        config_layout.addRow("Max Pages:", self.max_pages_input)
        
        # Max depth
        self.max_depth_input = QSpinBox()
        self.max_depth_input.setRange(1, 10)
        self.max_depth_input.setValue(5)
        config_layout.addRow("Max Depth:", self.max_depth_input)
        
        # Request delay
        self.delay_input = QSpinBox()
        self.delay_input.setRange(0, 10)
        self.delay_input.setValue(1)
        self.delay_input.setSuffix(" seconds")
        config_layout.addRow("Request Delay:", self.delay_input)
        
        # Save to database
        self.save_to_db_checkbox = QCheckBox("Save results to database")
        self.save_to_db_checkbox.setChecked(True)
        config_layout.addRow("", self.save_to_db_checkbox)
        
        layout.addWidget(config_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_scan_btn = QPushButton("Start Scan")
        self.start_scan_btn.clicked.connect(self.start_scan)
        button_layout.addWidget(self.start_scan_btn)
        
        self.stop_scan_btn = QPushButton("Stop Scan")
        self.stop_scan_btn.clicked.connect(self.stop_scan)
        self.stop_scan_btn.setEnabled(False)
        button_layout.addWidget(self.stop_scan_btn)
        
        self.export_btn = QPushButton("Export Results")
        self.export_btn.clicked.connect(self.export_results)
        self.export_btn.setEnabled(False)
        button_layout.addWidget(self.export_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Log output
        log_group = QGroupBox("Scan Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_output = QTextEdit()
        self.log_output.setMaximumHeight(200)
        self.log_output.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_output)
        
        layout.addWidget(log_group)
        
        return widget
    
    def create_results_tab(self):
        """Create the results display tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Summary stats
        stats_group = QGroupBox("Scan Summary")
        stats_layout = QFormLayout(stats_group)
        
        self.stats_labels = {
            'total_pages': QLabel("0"),
            'crawlable_pages': QLabel("0"),
            'error_pages': QLabel("0"),
            'avg_response_time': QLabel("0.0s"),
            'total_links': QLabel("0"),
            'unique_domains': QLabel("0")
        }
        
        stats_layout.addRow("Total Pages:", self.stats_labels['total_pages'])
        stats_layout.addRow("Crawlable Pages:", self.stats_labels['crawlable_pages'])
        stats_layout.addRow("Error Pages:", self.stats_labels['error_pages'])
        stats_layout.addRow("Avg Response Time:", self.stats_labels['avg_response_time'])
        stats_layout.addRow("Total Links:", self.stats_labels['total_links'])
        stats_layout.addRow("Unique Domains:", self.stats_labels['unique_domains'])
        
        layout.addWidget(stats_group)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(8)
        self.results_table.setHorizontalHeaderLabels([
            "URL", "Title", "Status", "Response Time", "Links", "Images", "SEO Issues", "H1 Count"
        ])
        layout.addWidget(self.results_table)
        
        return widget
    
    def create_monitoring_tab(self):
        """Create the live monitoring tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Monitoring controls
        controls_layout = QHBoxLayout()
        
        self.start_monitoring_btn = QPushButton("Start Live Monitoring")
        self.start_monitoring_btn.clicked.connect(self.start_monitoring)
        controls_layout.addWidget(self.start_monitoring_btn)
        
        self.stop_monitoring_btn = QPushButton("Stop Monitoring")
        self.stop_monitoring_btn.clicked.connect(self.stop_monitoring)
        self.stop_monitoring_btn.setEnabled(False)
        controls_layout.addWidget(self.stop_monitoring_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Database connection status
        db_group = QGroupBox("Database Connection Status")
        db_layout = QFormLayout(db_group)
        
        self.db_status_labels = {
            'connected': QLabel("Disconnected"),
            'uptime': QLabel("0s"),
            'query_count': QLabel("0"),
            'error_count': QLabel("0"),
            'tables': QLabel("0")
        }
        
        db_layout.addRow("Status:", self.db_status_labels['connected'])
        db_layout.addRow("Uptime:", self.db_status_labels['uptime'])
        db_layout.addRow("Queries:", self.db_status_labels['query_count'])
        db_layout.addRow("Errors:", self.db_status_labels['error_count'])
        db_layout.addRow("Tables:", self.db_status_labels['tables'])
        
        layout.addWidget(db_group)
        
        # Live stats
        live_group = QGroupBox("Live Statistics")
        live_layout = QVBoxLayout(live_group)
        
        self.live_stats_text = QTextEdit()
        self.live_stats_text.setMaximumHeight(300)
        self.live_stats_text.setFont(QFont("Consolas", 9))
        live_layout.addWidget(self.live_stats_text)
        
        layout.addWidget(live_group)
        
        return widget
    
    def create_history_tab(self):
        """Create the scan history tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.refresh_history_btn = QPushButton("Refresh History")
        self.refresh_history_btn.clicked.connect(self.refresh_history)
        controls_layout.addWidget(self.refresh_history_btn)
        
        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.clicked.connect(self.clear_history)
        controls_layout.addWidget(self.clear_history_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # History table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Domain", "Base URL", "Scan Date", "Pages Found", "Status", "Actions"
        ])
        layout.addWidget(self.history_table)
        
        return widget
    
    def start_scan(self):
        """Start website scanning."""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a website URL")
            return
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_input.setText(url)
        
        try:
            # Create scanner
            self.scanner = SiteScanner(
                url, 
                max_pages=self.max_pages_input.value(),
                max_depth=self.max_depth_input.value()
            )
            self.scanner.request_delay = self.delay_input.value()
            
            # Create SQL integration if needed
            if self.save_to_db_checkbox.isChecked() and self.db_connector:
                self.scanner_with_sql = SiteScannerWithSQL(url, self.db_connector)
                self.scanner_with_sql.create_tables()
                self.scanner = self.scanner_with_sql.scanner
            
            # Start scan in worker thread
            self.scan_worker = SiteScanWorker(self.scanner)
            self.scan_worker.progress.connect(self.update_progress)
            self.scan_worker.finished.connect(self.scan_finished)
            self.scan_worker.error.connect(self.scan_error)
            
            self.scan_worker.start()
            
            # Update UI
            self.start_scan_btn.setEnabled(False)
            self.stop_scan_btn.setEnabled(True)
            self.export_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.log_output.clear()
            self.log_output.append(f"Starting scan of {url}...")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start scan: {str(e)}")
    
    def stop_scan(self):
        """Stop the current scan."""
        if self.scanner:
            self.scanner.stop_scan()
        
        if self.scan_worker and self.scan_worker.isRunning():
            self.scan_worker.terminate()
            self.scan_worker.wait(5000)
        
        self.start_scan_btn.setEnabled(True)
        self.stop_scan_btn.setEnabled(False)
        self.log_output.append("Scan stopped by user")
    
    def update_progress(self, message, progress):
        """Update scan progress."""
        self.log_output.append(message)
        self.progress_bar.setValue(int(progress * 100))
        self.statusBar().showMessage(message)
    
    def scan_finished(self):
        """Handle scan completion."""
        self.start_scan_btn.setEnabled(True)
        self.stop_scan_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        
        if self.scanner:
            # Update results
            self.update_results_display()
            
            # Save to database if enabled
            if self.scanner_with_sql:
                try:
                    success = self.scanner_with_sql.save_scan_to_db()
                    if success:
                        self.log_output.append("Results saved to database")
                    else:
                        self.log_output.append("Failed to save results to database")
                except Exception as e:
                    self.log_output.append(f"Database save error: {e}")
        
        self.log_output.append("Scan completed!")
        self.statusBar().showMessage("Scan completed")
    
    def scan_error(self, error_message):
        """Handle scan error."""
        self.start_scan_btn.setEnabled(True)
        self.stop_scan_btn.setEnabled(False)
        self.log_output.append(f"Scan error: {error_message}")
        QMessageBox.critical(self, "Scan Error", error_message)
    
    def update_results_display(self):
        """Update the results display with scan data."""
        if not self.scanner:
            return
        
        # Update summary stats
        metrics = self.scanner.get_site_metrics()
        
        self.stats_labels['total_pages'].setText(str(metrics.total_pages))
        self.stats_labels['crawlable_pages'].setText(str(metrics.crawlable_pages))
        self.stats_labels['error_pages'].setText(str(metrics.error_pages))
        self.stats_labels['avg_response_time'].setText(f"{metrics.avg_response_time:.2f}s")
        self.stats_labels['total_links'].setText(str(metrics.total_internal_links + metrics.total_external_links))
        self.stats_labels['unique_domains'].setText(str(len(metrics.unique_domains)))
        
        # Update results table
        self.results_table.setRowCount(len(self.scanner.pages_data))
        
        for row, (url, page_data) in enumerate(self.scanner.pages_data.items()):
            self.results_table.setItem(row, 0, QTableWidgetItem(url))
            self.results_table.setItem(row, 1, QTableWidgetItem(page_data.title[:50]))
            self.results_table.setItem(row, 2, QTableWidgetItem(str(page_data.status_code)))
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{page_data.response_time:.2f}s"))
            self.results_table.setItem(row, 4, QTableWidgetItem(str(len(page_data.internal_links) + len(page_data.external_links))))
            self.results_table.setItem(row, 5, QTableWidgetItem(str(len(page_data.images))))
            self.results_table.setItem(row, 6, QTableWidgetItem(str(len(page_data.errors))))
            self.results_table.setItem(row, 7, QTableWidgetItem(str(len(page_data.h1_tags))))
        
        self.results_table.resizeColumnsToContents()
    
    def start_monitoring(self):
        """Start live database monitoring."""
        if not self.db_connector or not self.db_connector.connected:
            QMessageBox.warning(self, "Error", "No database connection available")
            return
        
        try:
            self.db_connector.start_monitoring(self.monitoring_callback)
            self.refresh_timer.start(5000)  # Update every 5 seconds
            
            self.start_monitoring_btn.setEnabled(False)
            self.stop_monitoring_btn.setEnabled(True)
            self.live_stats_text.append("Live monitoring started...")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start monitoring: {str(e)}")
    
    def stop_monitoring(self):
        """Stop live database monitoring."""
        if self.db_connector:
            self.db_connector.stop_monitoring()
        
        self.refresh_timer.stop()
        self.start_monitoring_btn.setEnabled(True)
        self.stop_monitoring_btn.setEnabled(False)
        self.live_stats_text.append("Live monitoring stopped")
    
    def monitoring_callback(self, stats):
        """Callback for monitoring updates."""
        # This will be called from the monitoring thread
        pass
    
    def update_monitoring_display(self):
        """Update the monitoring display."""
        if not self.db_connector or not self.db_connector.connected:
            return
        
        try:
            stats = self.db_connector.get_statistics()
            
            # Update connection status
            self.db_status_labels['connected'].setText("Connected" if stats.get('connected') else "Disconnected")
            
            if 'uptime_seconds' in stats:
                uptime = int(stats['uptime_seconds'])
                hours, remainder = divmod(uptime, 3600)
                minutes, seconds = divmod(remainder, 60)
                self.db_status_labels['uptime'].setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            
            self.db_status_labels['query_count'].setText(str(stats.get('query_count', 0)))
            self.db_status_labels['error_count'].setText(str(stats.get('error_count', 0)))
            self.db_status_labels['tables'].setText(str(stats.get('total_tables', 0)))
            
            # Update live stats text
            current_time = QTimer().currentTime().toString()
            stats_text = f"[{current_time}] Database Stats:\n"
            for key, value in stats.items():
                stats_text += f"  {key}: {value}\n"
            
            self.live_stats_text.append(stats_text)
            
            # Keep only last 100 lines
            lines = self.live_stats_text.toPlainText().split('\n')
            if len(lines) > 100:
                self.live_stats_text.setPlainText('\n'.join(lines[-100:]))
            
        except Exception as e:
            self.live_stats_text.append(f"Monitoring error: {e}")
    
    def export_results(self):
        """Export scan results to file."""
        if not self.scanner:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Scan Results", "", "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                self.scanner.save_to_file(filename, 'json')
                QMessageBox.information(self, "Success", f"Results exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export results: {str(e)}")
    
    def refresh_history(self):
        """Refresh scan history from database."""
        if not self.scanner_with_sql:
            return
        
        try:
            history = self.scanner_with_sql.get_scan_history()
            
            self.history_table.setRowCount(len(history))
            
            for row, record in enumerate(history):
                self.history_table.setItem(row, 0, QTableWidgetItem(record['domain']))
                self.history_table.setItem(row, 1, QTableWidgetItem(record['base_url']))
                self.history_table.setItem(row, 2, QTableWidgetItem(str(record['scan_date'])))
                self.history_table.setItem(row, 3, QTableWidgetItem(str(record['pages_found'])))
                self.history_table.setItem(row, 4, QTableWidgetItem(record['status']))
                
                # Add action button
                action_btn = QPushButton("View Details")
                action_btn.clicked.connect(lambda checked, r=record: self.view_scan_details(r))
                self.history_table.setCellWidget(row, 5, action_btn)
            
            self.history_table.resizeColumnsToContents()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to refresh history: {str(e)}")
    
    def clear_history(self):
        """Clear scan history from database."""
        reply = QMessageBox.question(
            self, "Confirm", "Are you sure you want to clear all scan history?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes and self.db_connector:
            try:
                self.db_connector.execute_query("DELETE FROM scanned_sites")
                self.refresh_history()
                QMessageBox.information(self, "Success", "Scan history cleared")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear history: {str(e)}")
    
    def view_scan_details(self, record):
        """View details of a specific scan."""
        # This could open a detailed view window
        QMessageBox.information(self, "Scan Details", f"Viewing details for {record['domain']}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        if self.scanner:
            self.scanner.stop_scan()
        
        if self.db_connector:
            self.db_connector.stop_monitoring()
        
        event.accept()