# -*- coding: utf-8 -*-

__author__ = 'GIS Innovation Sdn. Bhd.'
__date__ = '2025-04-17'
__copyright__ = '(C) 2025 by GIS Innovation Sdn. Bhd.'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

# ---------------------------------------------------------
# Code By Lyes - Ver 0.3
# Changelog:
# - Added comprehensive error handling using the traceback module.
# - Included detailed error reporting with line numbers in error message boxes.
# - Removed all QMessageBox.information instances.
# ---------------------------------------------------------

import traceback
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTabWidget, QLabel, QSizePolicy, QToolButton, QMessageBox, QCheckBox,
    QTreeView, QListWidget, QListWidgetItem, QSplitter
)
from qgis.PyQt.QtCore import Qt, QCoreApplication, QVariant, QDir, QFileInfo, QSize
from qgis.PyQt.QtGui import QStandardItemModel, QStandardItem, QIcon, QPainter, QColor
from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterString, QgsProcessingParameterFeatureSink,
    QgsProcessingOutputString, QgsProcessing, QgsVectorLayer,
    QgsVectorFileWriter, Qgis, QgsMessageLog, QgsProcessingParameterDefinition
)
from qgis.gui import QgsFileWidget
from processing.gui.wrappers import WidgetWrapper
import os
import re
import tempfile
import subprocess
import uuid
import shutil
import xml.etree.ElementTree as ET
import win32api
from qgis import core
from qgis.utils import iface
import configparser

class CollapsibleGroupBox(QGroupBox):
    def __init__(self, title):
        super().__init__()
        self.setTitle("")  # Keep the QGroupBox title empty

        # Create a widget to hold the header
        self.header_widget = QWidget(self)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(0, 0, 0, 0)
        self.header_layout.setSpacing(0)

        # Create the toggle button (arrow)
        self.toggle_button = QToolButton(self)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setArrowType(Qt.RightArrow)  # Start with the right arrow (collapsed)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.clicked.connect(self.toggle)

        # Create the title label
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("QLabel { border: none; padding-left: 5px; }")

        # Add arrow and label to header
        self.header_layout.addWidget(self.toggle_button)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()

        # Create the layout for the group box
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.addWidget(self.header_widget)
        
        # Content widget
        self.content = QWidget(self)
        self.content.setLayout(QVBoxLayout())
        self.content.setVisible(False)
        self.layout.addWidget(self.content)

    def toggle(self):
        """Toggle the group box visibility."""
        if self.toggle_button.isChecked():
            self.toggle_button.setArrowType(Qt.DownArrow)  # Change to down arrow (expanded)
            self.content.setVisible(True)
        else:
            self.toggle_button.setArrowType(Qt.RightArrow)  # Change back to right arrow (collapsed)
            self.content.setVisible(False)

    def add_widget(self, widget):
        self.content.layout().addWidget(widget)

    def expand(self):
        """Expand the group box to show the content."""
        self.toggle_button.setArrowType(Qt.DownArrow)  # Change to down arrow (expanded)
        self.content.setVisible(True)
        self.toggle_button.setChecked(True)

class QGISFMEFormAlgorithmAlgorithm(QgsProcessingAlgorithm):
    INPUT_LAYER = 'INPUT_LAYER'
    OUTPUT_LAYER = 'OUTPUT_LAYER'
    OUTPUT_TEXT = 'OUTPUT_TEXT'
    COMMAND = 'COMMAND'

    class CustomParametersWidget(WidgetWrapper): 
        def createWidget(self, **kwargs):
           # Store the widget instance
           self.fme_lister_widget = FMEFileLister()
           # Connect a signal from the UI to notify the wrapper of changes
           try:
               self.fme_lister_widget.command_display_box.textChanged.connect(self.parameterChanged)
           except AttributeError:
               # Fallback or log if the signal/widget doesn't exist as expected
               QgsMessageLog.logMessage("Could not connect command_display_box textChanged signal", "FME Connector", level=Qgis.Warning)
           return self.fme_lister_widget

        def value(self):
            """Return the current command string and paths from the FMEFileLister UI."""
            if hasattr(self, 'fme_lister_widget') and self.fme_lister_widget:
                # Get the command text from the display box
                command_text = self.fme_lister_widget.command_display_box.toPlainText()
                
                # Get the paths from the paths table
                fme_exe_path = ""
                fmw_path = ""
                try:
                    fme_exe_item = self.fme_lister_widget.paths_table.item(0, 0)
                    fmw_item = self.fme_lister_widget.paths_table.item(0, 1)
                    if fme_exe_item and fme_exe_item.text() != "Not set":
                        fme_exe_path = fme_exe_item.text()
                    if fmw_item and fmw_item.text() != "Not set":
                        fmw_path = fmw_item.text()
                except Exception as e:
                    QgsMessageLog.logMessage(f"Error getting paths from table: {str(e)}", "FME Connector", level=Qgis.Warning)
                
                # Encode the paths in the command text with special markers
                if fme_exe_path or fmw_path:
                    command_text += f"\n###PATHS_INFO###\n{fme_exe_path}\n{fmw_path}"
                
                return command_text
            return "" # Return empty string if widget not created yet

        def setValue(self, value):
            """Set the command string in the FMEFileLister UI and restore UI state."""
            if hasattr(self, 'fme_lister_widget') and self.fme_lister_widget:
                # Check if the value contains paths info markers
                paths_info = None
                command_text = value
                
                # Extract paths info if present
                if "###PATHS_INFO###" in value:
                    parts = value.split("###PATHS_INFO###")
                    command_text = parts[0].strip()
                    if len(parts) > 1 and parts[1].strip():
                        path_lines = parts[1].strip().split("\n")
                        if len(path_lines) >= 2:
                            paths_info = path_lines
                
                # Set the command text (without the paths info)
                self.fme_lister_widget.command_display_box.setPlainText(command_text)
                
                # Try to parse the command to restore workspace path and parameters
                if command_text and len(command_text) > 0:
                    try:
                        # Parse the command to extract workspace path
                        import re
                        workspace_match = re.search(r'"([^"]+\.fmw)"', command_text)
                        if workspace_match:
                            workspace_path = workspace_match.group(1)
                            
                            # Update the paths table with the FMW path
                            self.fme_lister_widget.paths_table.setItem(0, 1, QTableWidgetItem(workspace_path))
                            
                            # Extract parameters from command string
                            param_matches = re.findall(r'--(\w+)\s+"([^"]*)"', command_text)
                            
                            # Clear user parameters table
                            self.fme_lister_widget.user_parameters_table.setRowCount(0)
                            
                            # Add each parameter to the user parameters table
                            for param_name, param_value in param_matches:
                                row = self.fme_lister_widget.user_parameters_table.rowCount()
                                self.fme_lister_widget.user_parameters_table.insertRow(row)
                                self.fme_lister_widget.user_parameters_table.setItem(row, 0, QTableWidgetItem(param_name))
                                self.fme_lister_widget.user_parameters_table.setItem(row, 1, QTableWidgetItem(param_value))
                                
                        # If we have paths info, restore it to the paths table
                        if paths_info:
                            # First path is fme.exe path
                            if paths_info[0]:
                                self.fme_lister_widget.fme_exe_path = paths_info[0]
                                self.fme_lister_widget.paths_table.setItem(0, 0, QTableWidgetItem(paths_info[0]))
                            
                            # Second path is fmw path (if not already set from command parsing)
                            if len(paths_info) > 1 and paths_info[1] and not workspace_match:
                                self.fme_lister_widget.paths_table.setItem(0, 1, QTableWidgetItem(paths_info[1]))
                    except Exception as e:
                        # Log any errors but don't crash
                        QgsMessageLog.logMessage(f"Error parsing command: {str(e)}", "FME Connector", level=Qgis.Warning)
                
        def postInitialize(self, param):
            """Called after the widget is initialized with a parameter."""
            # This method is called when the widget is initialized in the model designer
            # We can use it to perform additional setup if needed
            pass
            
        def setComboValue(self, value):
            """Set the value for a combo box (required for model designer compatibility)."""
            self.setValue(value)
            
        def getAsString(self):
            """Return the value as a string for serialization in the model."""
            return self.value()
            
        def createBatchWidget(self):
            """Create a widget for batch processing mode."""
            from qgis.PyQt.QtWidgets import QPlainTextEdit
            # For batch mode, we'll use a simple text editor
            self.batch_widget = QPlainTextEdit()
            if hasattr(self, 'param') and self.param:
                self.batch_widget.setPlainText(self.param.defaultValue() or '')
            return self.batch_widget
            
        def batchValue(self):
            """Get the value from the batch widget."""
            if hasattr(self, 'batch_widget') and self.batch_widget:
                return self.batch_widget.toPlainText()
            return ''
            
        def setBatchValue(self, value):
            """Set the value in the batch widget."""
            if hasattr(self, 'batch_widget') and self.batch_widget:
                self.batch_widget.setPlainText(value)

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return QGISFMEFormAlgorithmAlgorithm()

    def name(self):
        return 'fmeformconnector'

    def displayName(self):
        return self.tr('QGIS-FME Form Connector Algorithm')

    def group(self):
        return ''

    def groupId(self):
        return ''
        
    def icon(self):
        """Returns the algorithm icon for display in the toolbox and model designer"""
        import os
        from qgis.PyQt.QtGui import QIcon
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(plugin_dir, 'icon.png')
        
        # Check if the icon file exists
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # Return a default icon if the file doesn't exist
            return QIcon()
        
    def svgIconPath(self):
        """Returns the path to an SVG icon for the model designer"""
        # Return None since we're using a PNG icon, not an SVG
        # The model designer will use the QIcon from the icon() method instead
        return None

    def initAlgorithm(self, config=None):
        # Layer selection parameter
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LAYER,
                self.tr('Input Layer'),
                [QgsProcessing.TypeVectorAnyGeometry],
                optional=False  # Make input required
            )
        )

        # Output layer parameter
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LAYER,
                self.tr('Output Layer')
            )
        )

        # Command string parameter (multi-line) using Custom Widget
        command_param = QgsProcessingParameterString(
            self.COMMAND,
            self.tr('Set FME Workspace Parameters'), # Updated label as requested
            multiLine=True, # Keep multiline for potential display
            defaultValue='"C:\\Program Files\\FME\\fme.exe" "path/to/workspace.fmw"' # Default value to make it non-mandatory
        )
        # Reference the nested CustomParametersWidget class
        command_param.setMetadata({'widget_wrapper': {'class': self.CustomParametersWidget}})
        self.addParameter(command_param)

        # Output text parameter
        self.addOutput(
            QgsProcessingOutputString(
                self.OUTPUT_TEXT,
                self.tr('Processing Log')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Executes an FME command line, optionally using QGIS layers as input,
        and outputting the result as a new layer or for chaining in the model designer.
        """
        import subprocess
        import tempfile
        import uuid
        import os
        import re
        from qgis.core import QgsVectorFileWriter, QgsVectorLayer, QgsProcessingException, QgsFeatureSink
        try:
            # Get parameters
            command = self.parameterAsString(parameters, self.COMMAND, context)
            input_source = self.parameterAsSource(parameters, self.INPUT_LAYER, context)
            output_layer_param = self.OUTPUT_LAYER
            
            # Check if the command contains the default placeholder workspace path
            if 'path/to/workspace.fmw' in command:
                feedback.reportError('Please select a valid FME workspace file. The default placeholder workspace path cannot be used.')
                raise QgsProcessingException('Invalid FME workspace path. Please configure the algorithm with a valid workspace.')

            # Remove any ###PATHS_INFO### block from the command string before execution
            if '###PATHS_INFO###' in command:
                command = command.split('###PATHS_INFO###')[0].strip()

            # Convert input to QgsVectorLayer if needed
            input_layer = input_source
            if input_layer is not None and not isinstance(input_layer, QgsVectorLayer):
                # Create memory layer from source
                fields = input_layer.fields()
                crs = input_layer.sourceCrs()
                wkb = input_layer.wkbType()
                from qgis.core import QgsVectorLayer, QgsWkbTypes
                mem_layer = QgsVectorLayer(f"{QgsWkbTypes.displayString(wkb)}?crs={crs.authid()}", "temp_export", "memory")
                mem_layer.dataProvider().addAttributes(fields)
                mem_layer.updateFields()
                feats = [f for f in input_layer.getFeatures()]
                mem_layer.dataProvider().addFeatures(feats)
                mem_layer.updateExtents()
                input_layer = mem_layer

            # Generate unique temp file paths for input/output GeoJSON
            unique_id = uuid.uuid4().hex
            temp_dir = tempfile.gettempdir()
            input_geojson = os.path.join(temp_dir, f"fme_input_{unique_id}.geojson")
            output_geojson = os.path.join(temp_dir, f"fme_output_{unique_id}.geojson")

            # Export input layer to GeoJSON
            if input_layer is not None:
                QgsVectorFileWriter.writeAsVectorFormat(
                    input_layer, input_geojson, "utf-8", input_layer.sourceCrs(), "GeoJSON"
                )

            # Check if the command already contains the dataset parameters
            source_dataset_exists = re.search(r'--SourceDataset_GEOJSON\s+"[^"]+"', command) is not None
            dest_dataset_exists = re.search(r'--DestDataset_GEOJSON\s+"[^"]+"', command) is not None
            
            # Start with the original command
            cmd = command
            
            # If the parameters exist, substitute them
            if source_dataset_exists:
                cmd = re.sub(
                    r'--SourceDataset_GEOJSON\s+"[^"]+"',
                    lambda m: f'--SourceDataset_GEOJSON "{input_geojson}"',
                    cmd
                )
            else:
                # Otherwise, append them to the command
                cmd += f' --SourceDataset_GEOJSON "{input_geojson}"'
                
            if dest_dataset_exists:
                cmd = re.sub(
                    r'--DestDataset_GEOJSON\s+"[^"]+"',
                    lambda m: f'--DestDataset_GEOJSON "{output_geojson}"',
                    cmd
                )
            else:
                # Otherwise, append them to the command
                cmd += f' --DestDataset_GEOJSON "{output_geojson}"'

            feedback.pushInfo(f"Running FME command: {cmd}")
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            feedback.pushInfo(result.stdout)
            if result.stderr:
                feedback.reportError(result.stderr)

            # Load output GeoJSON as layer
            output_layer = QgsVectorLayer(output_geojson, "FME Output", "ogr")
            if not output_layer.isValid():
                QgsMessageLog.logMessage(f"FME output could not be loaded from {output_geojson}. FME log was:\n{result.stdout}", "FME Connector", level=Qgis.Critical)
                raise QgsProcessingException("FME output could not be loaded. See log for details.")

            # Create the output sink based on FME output layer's schema
            (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT_LAYER, context,
                                                   output_layer.fields(),
                                                   output_layer.wkbType(),
                                                   output_layer.sourceCrs())
            for f in output_layer.getFeatures():
                sink.addFeature(f, QgsFeatureSink.FastInsert)

            # Optionally, clean up temp files (uncomment if desired)
            # os.remove(input_geojson)
            # os.remove(output_geojson)

            QgsMessageLog.logMessage(f"Returning OUTPUT_LAYER sink id: {dest_id}", "FME Connector", level=Qgis.Info)
            QgsMessageLog.logMessage(f"Returning OUTPUT_TEXT log (length {len(result.stdout)} chars)", "FME Connector", level=Qgis.Info)
            # Return the sink ID for OUTPUT_LAYER (for chaining), and log for OUTPUT_TEXT
            return {self.OUTPUT_LAYER: dest_id, self.OUTPUT_TEXT: result.stdout}
        except Exception as e:
            QgsMessageLog.logMessage(f"Error in processAlgorithm: {str(e)}\n\nTraceback:\n{traceback.format_exc()}", "FME Connector", level=Qgis.Info)
            raise e

class FMEFileLister(QWidget):
    INI_FILENAME = 'fme_settings.ini'
    INI_SECTION = 'FME'
    INI_KEY = 'exe_path'

    def open_workspace_in_fme(self):
        """Open the selected workspace in FME Workbench using fmeworkbench.exe (from same folder as fme.exe)."""
        import subprocess
        from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
        import os
        # Get the workspace path from the paths table
        workspace_item = self.paths_table.item(0, 1)
        workspace_path = workspace_item.text() if workspace_item else ""
        if not workspace_path or workspace_path == "Not set":
            QMessageBox.warning(self, "No Workspace Selected", "Please select a workspace to open.")
            return
        # Debug: log the path being used
        QgsMessageLog.logMessage(f"[FME Connector] Attempting to open workspace: {workspace_path}", "FME Connector", level=Qgis.Info)
        if not os.path.exists(workspace_path):
            QMessageBox.warning(self, "Workspace Not Found", f"Workspace file does not exist:\n{workspace_path}")
            QgsMessageLog.logMessage(f"[FME Connector] Workspace file does not exist: {workspace_path}", "FME Connector", level=Qgis.Warning)
            return
        # Try to find fmeworkbench.exe in the same folder as fme.exe
        workbench_exe = None
        fme_exe = self.fme_exe_path
        if fme_exe and os.path.exists(fme_exe):
            workbench_exe = os.path.join(os.path.dirname(fme_exe), 'fmeworkbench.exe')
            if not os.path.exists(workbench_exe):
                workbench_exe = None
        if not workbench_exe:
            exe_path, _ = QFileDialog.getOpenFileName(self, "Select FME Workbench Executable", os.path.dirname(fme_exe) if fme_exe else "C:/Program Files/FME/", "FME Workbench Executable (fmeworkbench.exe)")
            if exe_path and os.path.basename(exe_path).lower() == 'fmeworkbench.exe':
                workbench_exe = exe_path
                # Save for session
                self.fmeworkbench_exe_path = exe_path
            elif exe_path:
                QMessageBox.warning(self, "Invalid Selection", "Please select the correct fmeworkbench.exe file.")
                return
            else:
                return
        # Launch FME Workbench with the workspace
        try:
            subprocess.Popen([workbench_exe, workspace_path])
        except Exception as e:
            QMessageBox.critical(self, "Error Launching FME Workbench", f"Failed to launch FME Workbench:\n{str(e)}")

    def select_fme_exe_from_table(self):
        exe_path, _ = QFileDialog.getOpenFileName(self, "Select FME Executable", "C:/Program Files/FME/", "FME Executable (fme.exe)")
        if exe_path and os.path.basename(exe_path).lower() == 'fme.exe':
            self.fme_exe_path = exe_path
            self.paths_table.setItem(0, 0, QTableWidgetItem(self.fme_exe_path))
            # Not saving to INI file automatically
        elif exe_path:
            QMessageBox.warning(self, "Invalid Selection", "Please select the correct fme.exe file.")

    def __init__(self):
        super().__init__()
        self.selected_directory = ""
        self.temp_input_path = None
        self.temp_output_path = None
        self.fme_exe_path = None
        self.fmeworkbench_exe_path = None  # Store user-selected workbench path for session
        self.setLayout(self.build_ui())
        self.load_fme_exe_path()
        
    def build_ui(self):
        layout = QVBoxLayout()
        
        # Create vertical splitter for overall layout
        vertical_splitter = QSplitter(Qt.Vertical)
        vertical_splitter.setStyleSheet("""
            QSplitter::handle {
                background: transparent;
                margin: 1px;
            }
            QSplitter::handle:vertical:hover {
                background: #ccc;
            }
        """)
        
        # Create icons for use in the UI
        # Create yellow folder icon (Windows-like yellow)
        folder_pixmap = QIcon(":/images/themes/default/mIconFolder.svg").pixmap(16, 16)
        painter = QPainter(folder_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(folder_pixmap.rect(), QColor(255, 201, 14))  # Windows-like yellow
        painter.end()
        self.folder_icon = QIcon(folder_pixmap)
        
        # Get drive and FMW file icons
        self.drive_icon = QIcon(":/images/themes/default/mIconDriveHarddisk.svg")
        self.fmw_icon = QIcon(":/images/themes/default/mIconFile.svg")
        
        # Create tree model and prepare drives list
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Name'])
        
        # Add all available drives
        drives = win32api.GetLogicalDriveStrings()
        drives = drives.split('\000')[:-1]
        
        for drive in drives:
            drive_item = QStandardItem(self.drive_icon, drive)
            drive_item.setData(drive, Qt.UserRole)
            self.tree_model.appendRow(drive_item)
            # Add a dummy item to show the expand arrow
            dummy = QStandardItem("")
            drive_item.appendRow(dummy)
        
        # Bottom part
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create a QTabWidget to hold multiple tabs
        self.tabs = QTabWidget()
        
        # Main content tab
        main_content_tab = QWidget()
        main_content_layout = QVBoxLayout()
        main_content_tab.setLayout(main_content_layout)
        
        # Create collapsible group box for workspace selection
        self.workspace_params_group = CollapsibleGroupBox("Select Workspace")
        
        # Add directory and workspace selector (horizontal splitter)
        selector_splitter = QSplitter(Qt.Horizontal)
        selector_splitter.setStyleSheet("""
            QSplitter::handle {
                background: transparent;
                margin: 1px;
            }
            QSplitter::handle:horizontal:hover {
                background: #ccc;
            }
        """)
        
        # Left side: Directory Tree
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add directory label
        dir_label = QLabel("Select a Directory:")
        left_layout.addWidget(dir_label)
        
        # Create tree view for directory browsing
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.tree_model)
        self.tree_view.clicked.connect(self.on_directory_changed)
        self.tree_view.expanded.connect(self.on_item_expanded)
        self.tree_view.setHeaderHidden(False)
        self.tree_view.setColumnWidth(0, 250)
        self.tree_view.setIconSize(QSize(16, 16))
        # Prevent editing (renaming) on double-click
        from qgis.PyQt.QtWidgets import QAbstractItemView
        self.tree_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Allow double-click to expand/collapse folders (default behavior)
        self.tree_view.setExpandsOnDoubleClick(True)
        left_layout.addWidget(self.tree_view)
        
        # Right side: FMW Files List
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add workspace label
        workspace_label = QLabel("Select Workspace:")
        right_layout.addWidget(workspace_label)
        
        # Create list widget for FMW files
        self.fmw_list = QListWidget()
        self.fmw_list.setIconSize(QSize(16, 16))
        self.fmw_list.itemClicked.connect(self.on_fmw_selected)
        self.fmw_list.itemDoubleClicked.connect(self.on_fmw_double_clicked)
        right_layout.addWidget(self.fmw_list)
        
        # Add widgets to the selector splitter
        selector_splitter.addWidget(left_widget)
        selector_splitter.addWidget(right_widget)
        selector_splitter.setStretchFactor(0, 1)
        selector_splitter.setStretchFactor(1, 1)
        
        # Add the selector splitter to the collapsible group
        self.workspace_params_group.add_widget(selector_splitter)
        
        # Add the collapsible group to the main content layout
        main_content_layout.addWidget(self.workspace_params_group)
        
        # Expand the group by default
        self.workspace_params_group.expand()

        # Call update_dataset_paths when a new workspace is selected
        self.fmw_list.itemClicked.connect(lambda item: self.update_dataset_paths())
        # Optionally, connect to other relevant triggers (e.g., input changes)

        # Group for User Parameters Table
        self.user_parameters_group = CollapsibleGroupBox("User Parameters")
        self.user_parameters_table = QTableWidget(0, 2)
        self.user_parameters_table.setHorizontalHeaderLabels(["Parameter", "Value"])
        self.user_parameters_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.user_parameters_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.user_parameters_table.itemChanged.connect(self.update_command_display)
        
        # Add user parameters table
        self.user_parameters_group.add_widget(self.user_parameters_table)
        
        main_content_layout.addWidget(self.user_parameters_group)

        # Group for Paths Table
        self.paths_group = CollapsibleGroupBox("Paths")
        self.paths_table = QTableWidget(1, 2)
        self.paths_table.setHorizontalHeaderLabels(["FME Executable Path", "FMW Path"])
        self.paths_table.setItem(0, 0, QTableWidgetItem(self.fme_exe_path or "Not set"))
        self.paths_table.setItem(0, 1, QTableWidgetItem("Not set"))  # Placeholder for FMW path
        
        # Configure columns to start with equal width but allow manual resizing
        table_width = self.paths_table.width()
        column_width = table_width // 2
        self.paths_table.setColumnWidth(0, column_width)
        self.paths_table.setColumnWidth(1, column_width)
        self.paths_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.paths_table.horizontalHeader().setStretchLastSection(True)
        
        self.paths_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.paths_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.paths_group.add_widget(self.paths_table)
        
        # Adjust the height of the paths table to fit 1.5 rows
        self.paths_table.setMinimumHeight(int(self.paths_table.horizontalHeader().height() + self.paths_table.rowHeight(0) * 1.5))
        self.paths_table.setMaximumHeight(self.paths_table.minimumHeight())
        
        # Create button layout for the paths group
        button_layout = QHBoxLayout()
        
        # Add "Save FME.exe path" button
        self.save_fme_path_button = QPushButton("Save fme.exe path as default location")
        self.save_fme_path_button.clicked.connect(self.save_fme_exe_path)
        button_layout.addWidget(self.save_fme_path_button)
        
        # Add "Open Workspace" button
        self.open_workspace_button = QPushButton("Open Workspace in FME Workbench")
        self.open_workspace_button.clicked.connect(self.open_workspace_in_fme)
        button_layout.addWidget(self.open_workspace_button)
        
        # Add the button layout to the paths group
        button_container = QWidget()
        button_container.setLayout(button_layout)
        self.paths_group.add_widget(button_container)
        
        main_content_layout.addWidget(self.paths_group)

        # Group for FME Command
        self.command_group = CollapsibleGroupBox("FME Command")
        self.command_display_box = QPlainTextEdit()
        self.command_display_box.setReadOnly(False)
        self.command_display_box.setPlaceholderText("Enter or modify FME command here.")
        self.command_display_box.textChanged.connect(self.on_command_text_changed)
        self.command_group.add_widget(self.command_display_box)
        main_content_layout.addWidget(self.command_group)

        # Add the main content tab
        self.tabs.addTab(main_content_tab, "Main")

        # Add the About tab
        about_tab = QWidget()
        about_layout = QVBoxLayout()
        about_tab.setLayout(about_layout)

        about_text = QLabel(
            "FME Workspace Connector\n\n"
            "This plugin allows you to:\n"
            "• Browse and select FME workspaces\n"
            "• View workspace parameters and datasets\n"
            "• Configure and run FME transformations\n\n"
            "Version: 0.3\n"
            "Author: Lyes"
        )
        about_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        about_layout.addWidget(about_text)
        
        self.tabs.addTab(about_tab, "About")

        # Add the tabs to the bottom layout
        bottom_layout.addWidget(self.tabs)
        
        # Add bottom widget to vertical splitter
        vertical_splitter.addWidget(bottom_widget)
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 2)
        
        layout.addWidget(vertical_splitter)
        return layout

    def populate_tree(self, parent_item, path):
        """Populate the tree view with subdirectories"""
        dir = QDir(path)
        dir.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot)
        dir_list = dir.entryList()
        
        for dir_name in dir_list:
            full_path = os.path.join(path, dir_name)
            if os.access(full_path, os.R_OK):  # Check if we have read access
                child = QStandardItem(self.folder_icon, dir_name)
                child.setData(full_path, Qt.UserRole)
                parent_item.appendRow(child)
                # Add a dummy item to show the expand arrow
                dummy = QStandardItem("")
                child.appendRow(dummy)


    def on_item_expanded(self, index):
        """Handle item expansion"""
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return
            
        path = item.data(Qt.UserRole)
        if not path:  # For root item
            path = item.text()
            
        if path:
            # Remove all children first
            item.removeRows(0, item.rowCount())
            
            # Repopulate with actual contents
            self.populate_tree(item, path)

    def on_directory_selected(self, path):
        """Handle directory selection from QgsFileWidget"""
        if not path:
            return
            
        self.selected_directory = path
        self.list_fmw_files()
        
    def on_workspace_selected(self, path):
        """Handle workspace selection from QgsFileWidget"""
        if not path:
            return
            
        try:
            # Load FMW information
            self.load_fmw_info(path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading FMW file: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")
    
    def on_directory_changed(self, index):
        """Handle directory selection from tree view"""
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return
            
        path = item.data(Qt.UserRole)
        if not path:  # For root item
            path = item.text()
            
        self.selected_directory = path
        self.list_fmw_files()

    def list_fmw_files(self):
        """List all FMW files in the selected directory"""
        self.fmw_list.clear()
        if not self.selected_directory:
            return
            
        dir = QDir(self.selected_directory)
        dir.setNameFilters(['*.fmw'])
        files = dir.entryList(QDir.Files)
        
        for file in files:
            item = QListWidgetItem(self.fmw_icon, file)
            full_path = os.path.join(self.selected_directory, file)
            item.setData(Qt.UserRole, full_path)
            item.setToolTip(full_path)
            self.fmw_list.addItem(item)
            
        if self.fmw_list.count() > 0:
            self.fmw_list.setCurrentRow(0)

    def on_fmw_double_clicked(self, item):
        """Handle double click on FMW file"""
        file_path = item.data(Qt.UserRole)
        if file_path:
            # Here you can implement what happens when an FMW file is double-clicked
            pass

    def on_fmw_selected(self, item):
        """Handle FMW selection from list widget"""
        if not item:
            return
        
        fmw_path = item.data(Qt.UserRole)
        if not fmw_path:
            return
        
        # Update the paths table with the FMW path
        self.paths_table.setItem(0, 1, QTableWidgetItem(fmw_path))
        
        try:
            # Load FMW information
            self.load_fmw_info(fmw_path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading FMW file: {str(e)}\n\nTraceback:\n{traceback.format_exc()}")

    def load_fmw_info(self, fmw_path):
        """Load and parse the FMW file content (ported from reference)."""
        import re, os
        try:
            QgsMessageLog.logMessage(f"Loading FMW info from: {fmw_path}", "FME Connector", level=Qgis.Info)
            
            # Temporarily disconnect signals to prevent premature updates
            try:
                self.user_parameters_table.itemChanged.disconnect(self.update_command_display)
            except TypeError: # Signal not connected
                pass
                
            try:
                with open(fmw_path, 'r', encoding='utf-8', errors='ignore') as f:
                    fmw_content = f.read()
                    
                    # Clear tables
                    self.user_parameters_table.setRowCount(0)

                    header_lines = []
                    header_started = False
                    command_line_found = False
                    fme_path_extracted = False # Flag extraction success

                    # First pass: get FME path and workspace path
                    for index, line in enumerate(fmw_content.split('\n')):
                        if line.startswith("#! <WORKSPACE"):
                            header_started = True
                        if header_started:
                            # Stop parsing header at preview image
                            if line.startswith("#!   A0_PREVIEW_IMAGE"):
                                break 
                            header_lines.append(line)

                            if not command_line_found and "Command line to run this workspace:" in line:
                                command_line_found = True
                                command_lines = []
                                i = index + 1
                                # Collect subsequent comment lines for the command
                                while i < len(fmw_content.split('\n')) and fmw_content.split('\n')[i].strip().startswith("#"):
                                    command_line_part = fmw_content.split('\n')[i].strip().lstrip("#").strip()
                                    if command_line_part:
                                        command_lines.append(command_line_part)
                                    i += 1
                                command_line = " ".join(command_lines)
                                
                                # Use regex to extract the first quoted part (FME path)
                                match = re.match(r'^"([^"]+)"', command_line) 
                                if match:
                                    fme_path = match.group(1)
                                    if fme_path:
                                        QgsMessageLog.logMessage(f"Extracted FME Path: {fme_path}", "FME Connector", level=Qgis.Info)
                                    else:
                                        QgsMessageLog.logMessage("Extracted FME path is empty.", "FME Connector", level=Qgis.Warning)
                                else:
                                    QgsMessageLog.logMessage(f"Could not parse FME path from command line comment: {command_line}", "FME Connector", level=Qgis.Warning)
                                # Don't break here, continue parsing header lines until A0_PREVIEW_IMAGE

                    # Log if extraction failed after checking relevant header lines
                    if not fme_path_extracted:
                         QgsMessageLog.logMessage("Failed to find or parse FME executable path from workspace header comment.", "FME Connector", level=Qgis.Warning)

                    # Second pass: extract parameters with exact names
                    for line in fmw_content.split('\n'):
                        if line.strip().startswith("#") and "--" in line and "Dataset_" not in line:
                            param_match = re.search(r'--(\w+)(?:\s+"([^"]*)")?', line)
                            if param_match:
                                param_name, param_value = param_match.groups()
                                # Check if param_value is the placeholder like "$(param_name)"
                                if param_value == f"$({param_name})":
                                    print(f"Skipping placeholder parameter: {param_name}") # Debug/Info
                                    continue # Don't add it to the user table
                                
                                row = self.user_parameters_table.rowCount()
                                self.user_parameters_table.insertRow(row)
                                self.user_parameters_table.setItem(row, 0, QTableWidgetItem(param_name))
                                self.user_parameters_table.setItem(row, 1, QTableWidgetItem(param_value if param_value else ""))

                    # Update dataset paths AFTER tables are populated
                    self.update_dataset_paths()
                    
            except Exception as e:
                import traceback
                QgsMessageLog.logMessage(f"Error loading FMW info: {str(e)}\n\nTraceback:\n{traceback.format_exc()}", "FME Connector", level=Qgis.Critical) # Log as Critical
                # Clear potentially partially populated tables on error
                self.user_parameters_table.setRowCount(0)

        finally:
            # Reconnect signals
            self.user_parameters_table.itemChanged.connect(self.update_command_display)
            # Update command display once after everything is done
            self.update_command_display()            

    def adjust_table_height(self, table):
        """Adjust table height based on content."""
        if table.rowCount() > 0:
            height = table.horizontalHeader().height() + table.rowHeight(0) * min(table.rowCount(), 5)
        else:
            height = table.horizontalHeader().height() + 2
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    def build_fme_command(self):
        """Build the FME command line string based on current settings."""
        try:
            # Get the current workspace path from the paths table
            workspace_path = self.paths_table.item(0, 1).text()
            if workspace_path == "Not set":
                return "Error: No workspace selected"

            # Always take FME executable path and workspace path from the paths table
            fme_path = self.paths_table.item(0, 0).text()
            workspace_path = self.paths_table.item(0, 1).text()
            if not fme_path or fme_path == "Not set" or not os.path.exists(fme_path):
                fme_path = os.getenv('FME_HOME', r'C:\Program Files\FME\fme.exe')
                if not os.path.exists(fme_path):
                    return "Error: FME executable not found"
            if not workspace_path or workspace_path == "Not set":
                return "Error: No workspace selected"

            # Do NOT regenerate dataset paths here! Assume they are up to date.
            # Only use the current temp_input_path and temp_output_path

            command_parts = [f'"{fme_path}" "{workspace_path}"']
            
            # Add dataset parameters if available
            if hasattr(self, 'temp_input_path') and self.temp_input_path:
                command_parts.append(f'--SourceDataset_GEOJSON "{self.temp_input_path}"')
            if hasattr(self, 'temp_output_path') and self.temp_output_path:
                command_parts.append(f'--DestDataset_GEOJSON "{self.temp_output_path}"')
            
            # Add user parameters
            for row in range(self.user_parameters_table.rowCount()):
                param_name_item = self.user_parameters_table.item(row, 0)
                param_value_item = self.user_parameters_table.item(row, 1)
                if param_name_item and param_value_item:
                    param_name = param_name_item.text().strip()
                    param_value = param_value_item.text().strip()
                    if param_name:
                        if param_value:
                            command_parts.append(f'--{param_name} "{param_value}"')
                        else:
                            # Always provide a value for each parameter (empty string) to avoid FME odd argument count error
                            command_parts.append(f'--{param_name} ""')

            # Join all parts with spaces
            return " ".join(command_parts)
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Error building FME command: {str(e)}", "FME Connector", level=Qgis.Critical)
            import traceback
            QgsMessageLog.logMessage(f"Traceback: {traceback.format_exc()}", "FME Connector", level=Qgis.Critical)
            return f"Error building command: {str(e)}"  

    def update_command_display(self):
        """Update the command display box with the current FME command."""
        command = self.build_fme_command()
        if command:
            # Only update if the current text is different to avoid cursor position reset
            current_text = self.command_display_box.toPlainText()
            if current_text != command:
                self.command_display_box.setPlainText(command)
        else:
            self.command_display_box.clear()

    def on_command_text_changed(self):
        """Handle manual changes to the command text."""
        # This method is called when the user manually edits the command
        # We don't need to do anything here since we'll use the text directly
        # when executing the command
        pass

    def save_fme_exe_path(self):
        """Save the selected fme.exe path to an ini file in the plugin directory."""
        # Get the path from the table cell 0,0
        cell_item = self.paths_table.item(0, 0)
        if cell_item and cell_item.text() != "Not set":
            path_to_save = cell_item.text()
            self.fme_exe_path = path_to_save  # Update instance variable
            
            config = configparser.ConfigParser()
            config[self.INI_SECTION] = {self.INI_KEY: path_to_save}
            ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.INI_FILENAME)
            with open(ini_path, 'w') as configfile:
                config.write(configfile)
            QMessageBox.information(self, "Path Saved", f"FME executable path has been saved as default:\n{path_to_save}")
        else:
            QMessageBox.warning(self, "No Path Selected", "Please select an FME executable path first.")

    def load_fme_exe_path(self):
        """Load the fme.exe path from the ini file if it exists and update the paths table."""
        ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.INI_FILENAME)
        if os.path.exists(ini_path):
            config = configparser.ConfigParser()
            config.read(ini_path)
            if self.INI_SECTION in config and self.INI_KEY in config[self.INI_SECTION]:
                self.fme_exe_path = config[self.INI_SECTION][self.INI_KEY]
                if os.path.exists(self.fme_exe_path):
                    self.paths_table.setItem(0, 0, QTableWidgetItem(self.fme_exe_path))
                else:
                    self.paths_table.setItem(0, 0, QTableWidgetItem("FME Executable: Not found (please re-select)"))
            else:
                self.paths_table.setItem(0, 0, QTableWidgetItem("FME Executable: Not selected"))
        else:
            self.paths_table.setItem(0, 0, QTableWidgetItem("FME Executable: Not selected"))

    def update_dataset_paths(self):
        """Update the source and destination dataset paths with the correct filename format"""
        try:
            # Generate unique filenames
            input_filename, output_filename = self.generate_filename_pair()
            
            # Get QGIS temp folder using settings directory
            from qgis.core import QgsApplication
            temp_folder = os.path.join(QgsApplication.qgisSettingsDirPath(), "temp")
            # Ensure temp_folder exists
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)
            
            # Create full paths using os.path.join for cross-platform compatibility
            input_path = os.path.join(temp_folder, input_filename)
            output_path = os.path.join(temp_folder, output_filename)
            
            # Use forward slashes for FME compatibility if needed, but Python handles mixed
            input_path = input_path.replace("\\", "/")
            output_path = output_path.replace("\\", "/")
            
            # Store temp paths
            self.temp_input_path = input_path
            self.temp_output_path = output_path
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error updating dataset paths: {str(e)}")
            # Optionally, log the full traceback for detailed debugging
            import traceback
            QgsMessageLog.logMessage(f"Dataset path update error: {traceback.format_exc()}", "FME Connector", level=Qgis.Critical)

    def load_output_to_qgis(self):
        """Load the FME output file into QGIS with a creative layer name."""
        pass

    def generate_filename_pair(self):
        """Generate a pair of input/output filenames with the format YYYYMMDD_xxxxx_line2_[input/output].geojson"""
        from datetime import datetime
        import random
        import string
        import os
        from qgis.core import QgsApplication

        # Get current date in YYYYMMDD format
        current_date = datetime.now().strftime("%Y%m%d")
        
        # Get QGIS temp folder
        temp_folder = QgsApplication.qgisSettingsDirPath() + "temp/"
        os.makedirs(temp_folder, exist_ok=True)
        
        # Generate random chars until we get a unique one
        while True:
            # Generate 5 random lowercase alphanumeric characters
            chars = string.ascii_lowercase + string.digits
            random_chars = ''.join(random.choice(chars) for _ in range(5))
            
            # Create base filename
            base_filename = f"{current_date}_{random_chars}_line2"
            
            # Generate input and output filenames
            input_filename = f"{base_filename}_input.geojson"
            output_filename = f"{base_filename}_output.geojson"
            
            # Check if files already exist in the temp directory
            input_path = os.path.join(temp_folder, input_filename)
            output_path = os.path.join(temp_folder, output_filename)
            
            # If neither file exists, we can use these names
            if not os.path.exists(input_path) and not os.path.exists(output_path):
                break
        
        return input_filename, output_filename

    def adjust_fme_exe_column_width(self):
        content_width = self.paths_table.fontMetrics().horizontalAdvance(self.paths_table.item(0, 0).text())
        max_width = self.paths_table.width() // 2
        self.paths_table.setColumnWidth(0, min(content_width, max_width))

    def __init__(self):
        super().__init__()
        self.selected_directory = ""
        self.temp_input_path = None
        self.temp_output_path = None
        self.fme_exe_path = None
        self.fmeworkbench_exe_path = None  # Store user-selected workbench path for session
        self.setLayout(self.build_ui())
        self.load_fme_exe_path()
        self.paths_table.itemChanged.connect(lambda item: self.adjust_fme_exe_column_width() if item.row() == 0 and item.column() == 0 else None)
        self.paths_table.cellDoubleClicked.connect(lambda row, col: self.select_fme_exe_from_table() if row == 0 and col == 0 else None)
        self.adjust_fme_exe_column_width()