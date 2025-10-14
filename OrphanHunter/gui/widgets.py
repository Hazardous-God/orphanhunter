"""Custom PyQt5 widgets for the System Mapper."""
from PyQt5.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QTextEdit, QWidget, 
    QVBoxLayout, QLabel, QProgressBar
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from typing import Dict, Set

class FileTreeWidget(QTreeWidget):
    """Custom tree widget for displaying file structure with status."""
    
    file_selected = pyqtSignal(str)  # file_key
    files_checked = pyqtSignal(set)  # set of file_keys
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["File/Folder", "Status", "References", "Size"])
        self.setColumnWidth(0, 400)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 80)
        self.setColumnWidth(3, 80)
        self.itemClicked.connect(self._on_item_clicked)
        self.itemChanged.connect(self._on_item_changed)
        self.file_items: Dict[str, QTreeWidgetItem] = {}
    
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click."""
        file_key = item.data(0, Qt.UserRole)
        if file_key:
            self.file_selected.emit(file_key)
    
    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle checkbox state change."""
        if column == 0:
            checked_files = set()
            for file_key, tree_item in self.file_items.items():
                if tree_item.checkState(0) == Qt.Checked:
                    checked_files.add(file_key)
            self.files_checked.emit(checked_files)
    
    def populate_tree(self, files: Dict):
        """Populate tree with file structure."""
        self.clear()
        self.file_items.clear()
        
        # Build directory structure
        dir_items: Dict[str, QTreeWidgetItem] = {}
        
        for file_key, file_info in sorted(files.items()):
            path_parts = file_info.relative_path.parts
            
            # Create directory items if needed
            current_parent = None
            current_path = ""
            
            for part in path_parts[:-1]:  # All but the last (which is the file)
                if current_path:
                    current_path += "/" + part
                else:
                    current_path = part
                
                if current_path not in dir_items:
                    if current_parent is None:
                        dir_item = QTreeWidgetItem(self)
                    else:
                        dir_item = QTreeWidgetItem(current_parent)
                    
                    dir_item.setText(0, part)
                    dir_item.setForeground(0, QColor(100, 100, 255))
                    font = QFont()
                    font.setBold(True)
                    dir_item.setFont(0, font)
                    dir_items[current_path] = dir_item
                    current_parent = dir_item
                else:
                    current_parent = dir_items[current_path]
            
            # Create file item
            if current_parent is None:
                file_item = QTreeWidgetItem(self)
            else:
                file_item = QTreeWidgetItem(current_parent)
            
            file_item.setText(0, file_info.name)
            file_item.setData(0, Qt.UserRole, file_key)
            file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable)
            file_item.setCheckState(0, Qt.Unchecked)
            
            # Status
            if file_info.is_critical:
                status = "Critical"
                file_item.setForeground(1, QColor(255, 0, 0))
            elif file_info.is_navigation:
                status = "Navigation"
                file_item.setForeground(1, QColor(0, 0, 255))
            elif file_info.reference_count == 0:
                status = "Orphaned"
                file_item.setForeground(1, QColor(128, 128, 128))
            else:
                status = "Active"
                file_item.setForeground(1, QColor(0, 150, 0))
            
            file_item.setText(1, status)
            file_item.setText(2, str(file_info.reference_count))
            file_item.setText(3, f"{round(file_info.size/1024, 1)} KB")
            
            self.file_items[file_key] = file_item
        
        self.expandAll()
    
    def get_checked_files(self) -> Set[str]:
        """Get set of checked file keys."""
        checked = set()
        for file_key, item in self.file_items.items():
            if item.checkState(0) == Qt.Checked:
                checked.add(file_key)
        return checked
    
    def set_checked_files(self, file_keys: Set[str]):
        """Set which files are checked."""
        for file_key, item in self.file_items.items():
            if file_key in file_keys:
                item.setCheckState(0, Qt.Checked)
            else:
                item.setCheckState(0, Qt.Unchecked)
    
    def highlight_orphaned(self):
        """Highlight orphaned files."""
        for file_key, item in self.file_items.items():
            if item.text(1) == "Orphaned":
                item.setBackground(0, QColor(255, 255, 200))


class LogConsole(QTextEdit):
    """Console widget for displaying logs."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(200)
        
        # Set monospace font
        font = QFont("Consolas", 9)
        self.setFont(font)
    
    def append_log(self, message: str, level: str = "INFO"):
        """Append a log message with color coding."""
        color_map = {
            "DEBUG": "#888888",
            "INFO": "#000000",
            "WARNING": "#FF8800",
            "ERROR": "#FF0000",
            "CRITICAL": "#AA0000"
        }
        
        color = color_map.get(level, "#000000")
        formatted = f'<span style="color: {color};">[{level}] {message}</span>'
        self.append(formatted)
        
        # Auto-scroll to bottom
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class StatusPanel(QWidget):
    """Status panel showing current operation status."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(self.status_label)
        
        self.detail_label = QLabel("")
        layout.addWidget(self.detail_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def set_status(self, status: str, detail: str = ""):
        """Set status text."""
        self.status_label.setText(status)
        self.detail_label.setText(detail)
    
    def show_progress(self, show: bool = True):
        """Show or hide progress bar."""
        self.progress_bar.setVisible(show)
    
    def set_progress(self, value: int, maximum: int = 100):
        """Set progress bar value."""
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)


class StatsWidget(QWidget):
    """Widget displaying statistics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout()
        
        self.stats_label = QLabel("No data")
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)
        
        self.setLayout(layout)
    
    def update_stats(self, stats: Dict):
        """Update statistics display."""
        lines = []
        for key, value in stats.items():
            formatted_key = key.replace('_', ' ').title()
            lines.append(f"<b>{formatted_key}:</b> {value}")
        
        self.stats_label.setText("<br>".join(lines))

