# -*- coding: utf-8 -*-
"""
ui.py
存放与 PyQt5 界面相关的逻辑
"""
import sys
import os
import json
import threading
import queue # 保留，因为 functions.py 依赖它

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QSlider,
    QGroupBox, QTextEdit, QFileDialog, QMessageBox, QListWidget, QScrollArea,
    QTabWidget # Added QTabWidget
)
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QIcon

# 从 functions.py 导入必要的模块
# Ensure functions.py is in the same directory or in PYTHONPATH
try:
    from functions import log_queue, process_list_of_txt_files, StdoutRedirector
except ImportError:
    print("Warning: functions.py not found. Using dummy implementations for testing.")
    # Dummy implementations for standalone testing if functions.py is missing
    log_queue = queue.Queue()

    class StdoutRedirector:
        def __init__(self):
            self._original_stdout = sys.stdout # Store original stdout
            self.log_queue = log_queue # Use the global log_queue

        def write(self, text):
            self.log_queue.put(text)
            self._original_stdout.write(text) # Optionally, still print to actual console

        def flush(self):
            self._original_stdout.flush()

    def process_list_of_txt_files(txt_file_paths, output_dir, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id):
        log_queue.put(f"Simulating processing for: {txt_file_paths}\n")
        log_queue.put(f"Params: output_dir={output_dir}, group_id={group_id}, model={model}, voice_id={voice_id}\n")
        for i, f_path in enumerate(txt_file_paths):
            log_queue.put(f"任务[{i+1}/{len(txt_file_paths)}] 开始处理文件: {os.path.basename(f_path)}\n")
            import time # Keep import local to this dummy function
            time.sleep(0.2) # Simulate work
            log_queue.put(f"任务[{i+1}/{len(txt_file_paths)}] 文件 {os.path.basename(f_path)} 处理成功。\n")
        log_queue.put("所有文件模拟处理完成。\n")
        return True

# --- PyQt5 UI 与 functions.py 的日志桥接 ---
class LogEmitter(QObject):
    log_signal = pyqtSignal(str)
    _original_stdout_for_emitter = sys.stdout

    def __init__(self, q_log):
        super().__init__()
        self.log_queue = q_log
        self.running = True

    def poll_log_queue(self):
        while self.running:
            try:
                msg = self.log_queue.get(timeout=0.1)
                if msg:
                    self.log_signal.emit(msg)
            except queue.Empty:
                continue
            except Exception as e:
                LogEmitter._original_stdout_for_emitter.write(f"[LogEmitter Error] {e}\n")


STYLESHEET = """
QMainWindow {
    background-color: #f4f4f4;
}
QTabWidget::pane { /* Style for the tab pane */
    border-top: 1px solid #c0c0c0;
    background: #f4f4f4; /* Match window background or use #ffffff for content area */
}
QTabBar::tab { /* Style for the tab buttons */
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #e8e8e8, stop: 1 #d8d8d8);
    border: 1px solid #c0c0c0;
    border-bottom-color: #c0c0c0; /* Same as top border */
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    min-width: 8ex;
    padding: 5px 10px;
    margin-right: 2px; /* Space between tabs */
    color: #333333;
}
QTabBar::tab:selected, QTabBar::tab:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f8f8f8, stop: 1 #e8e8e8);
    border-color: #a0a0a0;
}
QTabBar::tab:selected {
    border-bottom-color: #f4f4f4; /* Or #ffffff if pane background is white */
    color: #000000;
    font-weight: bold;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #c0c0c0;
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px 0 5px;
    left: 10px;
    color: #222222;
    background-color: #f4f4f4; /* Match pane background */
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}
QLabel {
    font-size: 10pt;
    color: #333333;
    padding-top: 3px;
    margin-bottom: 2px;
}
QLabel#LogLabel { /* Specific style for the log label */
    font-weight: bold;
    margin-top: 8px;
    margin-bottom: 4px;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    font-size: 10pt;
    padding: 5px;
    border: 1px solid #cccccc;
    border-radius: 4px;
    background-color: white;
    min-height: 20px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #0078d4;
}
QPushButton {
    font-size: 10pt;
    padding: 6px 12px;
    border: 1px solid #b0b0b0;
    border-radius: 4px;
    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                      stop: 0 #f0f0f0, stop: 1 #e0e0e0);
    color: #333333;
    min-height: 22px;
}
QPushButton:hover {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                      stop: 0 #e8e8e8, stop: 1 #d8d8d8);
    border-color: #a0a0a0;
}
QPushButton:pressed {
    background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                      stop: 0 #d0d0d0, stop: 1 #c0c0c0);
}
QPushButton#StartButton {
    background-color: #4CAF50; color: white; font-size: 16px; border-radius: 5px; padding: 8px;
}
QListWidget {
    border: 1px solid #cccccc;
    border-radius: 4px;
    background-color: white;
    font-size: 10pt;
}
QTextEdit#LogTextEdit {
    border: 1px solid #cccccc;
    border-radius: 4px;
    background-color: #ffffff;
}
QSlider::groove:horizontal {
    border: 1px solid #bbb;
    background: #e0e0e0;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    border: 1px solid #0078d4;
    width: 16px;
    height: 16px;
    margin: -4px 0;
    border-radius: 8px;
}
/* QScrollArea styling can be removed if not explicitly used elsewhere,
   or kept if QTabWidget internally uses it and needs styling.
   QTabWidget often handles its own scrolling if tabs overflow. */
QWidget#SettingsContainerWidget { /* This ID might be obsolete if not used */
    background-color: transparent; /* Or #f4f4f4 to match tab pane */
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiniMax超长文本语音生成")
        self.setMinimumSize(600, 500) # Adjusted for tabs
  
        self.all_voices_data = []
        self.languages = []
        self.voice_options_for_selected_language = {}
        self.last_opened_dir = os.path.expanduser("~")

        self._original_stdout = sys.stdout
        self._stdout_redirector = StdoutRedirector()
        LogEmitter._original_stdout_for_emitter = self._original_stdout
        
        # Initialize UI elements that will be populated by load_voice_data or used in initUI
        self.language_combo = QComboBox()
        self.voice_combo = QComboBox()
        self.group_id_edit = QLineEdit()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.output_dir_edit = QLineEdit()
        self.output_dir_button = QPushButton("选择输出目录...")
        self.model_combo = QComboBox()
        self.max_workers_spin = QSpinBox()
        self.add_files_button = QPushButton("添加TXT文件...")
        self.file_list_widget = QListWidget()
        self.delete_file_button = QPushButton("删除选中文件")
        self.speed_spin = QDoubleSpinBox()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.vol_spin = QSpinBox()
        self.vol_slider = QSlider(Qt.Horizontal)
        self.pitch_spin = QSpinBox()
        self.pitch_slider = QSlider(Qt.Horizontal)

        self.load_voice_data() # Load data that might be needed by initUI (e.g. for comboboxes)
        self.initUI()
        self.setup_log_monitoring()

        if not self.load_settings():
            if self.languages and self.languages[0] not in ["(音色配置缺失)", "(无可用音色数据)", "(加载错误)", "(无语言分类)"]:
                self.language_combo.setCurrentText(self.languages[0])

        if self.file_list_widget.count() == 0:
            self.file_list_widget.addItem("请添加TXT文件进行处理。")


    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet(STYLESHEET)

        # --- Create TabWidget ---
        tab_widget = QTabWidget()

        # --- Tab 1: 语音合成 (Speech Synthesis) ---
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(5, 10, 5, 5) # Margins for tab content

        # Group: 文件选择与管理 (File Selection & Management)
        file_selection_group = QGroupBox("文件选择与管理")
        file_selection_group_layout = QVBoxLayout()
        
        # Add TXT files button
        self.add_files_button.clicked.connect(self.add_txt_files_to_list)
        add_files_layout = QHBoxLayout()
        add_files_layout.addWidget(self.add_files_button)
        add_files_layout.addStretch()
        file_selection_group_layout.addLayout(add_files_layout)

        file_selection_group_layout.addWidget(QLabel("待处理 TXT 文件列表 (可多选后按Delete键或使用按钮删除):"))
        self.file_list_widget.setMinimumHeight(100)
        self.file_list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.file_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list_widget.keyPressEvent = self.handle_file_list_key_press
        file_selection_group_layout.addWidget(self.file_list_widget)

        self.delete_file_button.clicked.connect(self.delete_selected_file_from_list)
        delete_button_layout = QHBoxLayout()
        delete_button_layout.addStretch()
        delete_button_layout.addWidget(self.delete_file_button)
        file_selection_group_layout.addLayout(delete_button_layout)
        
        file_selection_group.setLayout(file_selection_group_layout)
        tab1_layout.addWidget(file_selection_group)

        # Group: 语音参数自定义 (Audio Parameter Customization)
        audio_params_group = QGroupBox("语音参数自定义")
        audio_params_layout = QFormLayout()
        self.speed_spin.setRange(0.5, 2.0); self.speed_spin.setSingleStep(0.1); self.speed_spin.setValue(1.0)
        self.speed_slider.setRange(5, 20); self.speed_slider.setValue(int(self.speed_spin.value() * 10))
        self.speed_slider.valueChanged.connect(lambda val: self.speed_spin.setValue(val / 10.0))
        self.speed_spin.valueChanged.connect(lambda val: self.speed_slider.setValue(int(val * 10)))
        speed_layout = QHBoxLayout(); speed_layout.addWidget(self.speed_spin, 1); speed_layout.addWidget(self.speed_slider, 3)
        audio_params_layout.addRow("语速 (0.5-2.0):", speed_layout)

        self.vol_spin.setRange(1, 10); self.vol_spin.setValue(1)
        self.vol_slider.setRange(1, 10); self.vol_slider.setValue(self.vol_spin.value())
        self.vol_slider.valueChanged.connect(self.vol_spin.setValue)
        self.vol_spin.valueChanged.connect(self.vol_slider.setValue)
        vol_layout = QHBoxLayout(); vol_layout.addWidget(self.vol_spin, 1); vol_layout.addWidget(self.vol_slider, 3)
        audio_params_layout.addRow("音量 (1-10):", vol_layout)

        self.pitch_spin.setRange(-12, 12); self.pitch_spin.setValue(0)
        self.pitch_slider.setRange(-12, 12); self.pitch_slider.setValue(self.pitch_spin.value())
        self.pitch_slider.valueChanged.connect(self.pitch_spin.setValue)
        self.pitch_spin.valueChanged.connect(self.pitch_slider.setValue)
        pitch_layout = QHBoxLayout(); pitch_layout.addWidget(self.pitch_spin, 1); pitch_layout.addWidget(self.pitch_slider, 3)
        audio_params_layout.addRow("音调 (-12至12):", pitch_layout)
        audio_params_group.setLayout(audio_params_layout)
        tab1_layout.addWidget(audio_params_group)

        # Group: 音色选择 (Voice Selection)
        voice_select_group = QGroupBox("音色选择")
        voice_select_layout = QFormLayout()
        if self.languages: self.language_combo.addItems(self.languages)
        self.language_combo.currentTextChanged.connect(self.on_language_select)
        voice_select_layout.addRow("语言选择:", self.language_combo)
        voice_select_layout.addRow("音色选择:", self.voice_combo)
        voice_select_group.setLayout(voice_select_layout)
        tab1_layout.addWidget(voice_select_group)
        
        tab1_layout.addStretch(1)
        tab_widget.addTab(tab1_widget, "语音合成")

        # --- Tab 2: 配置 (Configuration) ---
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(5, 10, 5, 5)

        # Group: 认证信息 (Authentication Info)
        auth_group = QGroupBox("认证信息")
        auth_layout = QFormLayout()
        auth_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        auth_layout.setLabelAlignment(Qt.AlignLeft)
        auth_layout.addRow("Group ID:", self.group_id_edit)
        auth_layout.addRow("API Key:", self.api_key_edit)
        auth_group.setLayout(auth_layout)
        tab2_layout.addWidget(auth_group)

        # Group: 输出与模型设置 (Output & Model Settings)
        output_model_group = QGroupBox("输出与模型设置")
        output_model_layout = QFormLayout()
        
        self.output_dir_button.clicked.connect(self.choose_output_directory)
        output_dir_hbox = QHBoxLayout()
        output_dir_hbox.addWidget(self.output_dir_edit)
        output_dir_hbox.addWidget(self.output_dir_button)
        output_model_layout.addRow("输出文件夹:", output_dir_hbox)
        
        self.model_combo.addItems(["speech-01-turbo", "speech-02-turbo","speech-01-hd","speech-02-hd","speech-01-240228", "speech-01-turbo-240228",])
        output_model_layout.addRow("模型选择:", self.model_combo)
        
        self.max_workers_spin.setRange(1, 100)
        self.max_workers_spin.setValue(5)
        output_model_layout.addRow("最大线程数:", self.max_workers_spin)
        
        output_model_group.setLayout(output_model_layout)
        tab2_layout.addWidget(output_model_group)

        tab2_layout.addStretch(1)
        tab_widget.addTab(tab2_widget, "配置")

        main_layout.addWidget(tab_widget, 1) # Tab widget gets stretch factor 1

        # --- Start Button (Below tabs) ---
        self.start_button = QPushButton("开始处理")
        self.start_button.setObjectName("StartButton")
        self.start_button.setFixedHeight(45)
        self.start_button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.start_button.clicked.connect(self.start_processing)
        main_layout.addWidget(self.start_button)

        # --- Log Output (Below Start Button) ---
        self.log_label = QLabel("日志输出:")
        self.log_label.setObjectName("LogLabel")
        main_layout.addWidget(self.log_label)

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setObjectName("LogTextEdit")
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setFont(QFont("Courier New", 9))
        self.log_text_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        main_layout.addWidget(self.log_text_edit, 2) # Log QTextEdit gets stretch factor 2


    def handle_file_list_key_press(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_selected_file_from_list()
        else:
            QListWidget.keyPressEvent(self.file_list_widget, event)

    def choose_output_directory(self):
        dir_selected = QFileDialog.getExistingDirectory(
            self,
            "请选择输出文件夹",
            self.output_dir_edit.text() or self.last_opened_dir
        )
        if dir_selected:
            self.output_dir_edit.setText(dir_selected)
            self.log_message_received(f"输出文件夹设置为: {dir_selected}\n")

    def add_txt_files_to_list(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择要处理的TXT文件 (可多选)",
            self.last_opened_dir,
            "TXT Files (*.txt);;All Files (*)"
        )
        if file_paths:
            self.last_opened_dir = os.path.dirname(file_paths[0])
            current_files_in_list = []
            is_first_item_placeholder = False
            if self.file_list_widget.count() > 0:
                first_item_text_check = self.file_list_widget.item(0).text()
                if any(ph in first_item_text_check for ph in ["请添加TXT文件进行处理。", "文件列表为空"]):
                    is_first_item_placeholder = True
            if not is_first_item_placeholder:
                for i in range(self.file_list_widget.count()):
                    current_files_in_list.append(self.file_list_widget.item(i).text())
            if is_first_item_placeholder:
                self.file_list_widget.clear()
            files_added_count = 0
            newly_added_paths = []
            for path in file_paths:
                if path not in current_files_in_list and path not in newly_added_paths :
                    self.file_list_widget.addItem(path)
                    newly_added_paths.append(path)
                    files_added_count += 1
            if files_added_count > 0:
                 self.log_message_received(f"添加了 {files_added_count} 个文件到处理列表。\n")
            if self.file_list_widget.count() == 0:
                 self.file_list_widget.addItem("请添加TXT文件进行处理。")

    def delete_selected_file_from_list(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            if any(ph in item.text() for ph in ["请添加TXT文件进行处理。", "文件列表为空"]): continue
            self.file_list_widget.takeItem(self.file_list_widget.row(item))
            self.log_message_received(f"从列表中移除了: {item.text()}\n")
        if self.file_list_widget.count() == 0:
            self.file_list_widget.addItem("文件列表为空或所有文件已被移除。")

    def start_processing(self):
        output_directory = self.output_dir_edit.text().strip()
        group_id = self.group_id_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText()
        max_workers = self.max_workers_spin.value()
        speed = self.speed_spin.value()
        vol = float(self.vol_spin.value())
        pitch = self.pitch_spin.value()
        selected_voice_display_text = self.voice_combo.currentText()
        voice_id = self.voice_options_for_selected_language.get(selected_voice_display_text)

        if not output_directory or not os.path.isdir(output_directory):
            QMessageBox.warning(self, "验证错误", "请选择一个有效的输出文件夹 (在“配置”选项卡中)。")
            return
        if not group_id:
            QMessageBox.warning(self, "验证错误", "请输入 Group ID (在“配置”选项卡中)。")
            return
        if not api_key:
            QMessageBox.warning(self, "验证错误", "请输入 API Key (在“配置”选项卡中)。")
            return
        if not voice_id:
            if not self.voice_combo.currentText() or self.voice_combo.currentText().startswith("("):
                 QMessageBox.warning(self, "验证错误", "请先选择语言并等待音色加载，或当前语言无可用音色。")
            else:
                QMessageBox.warning(self, "验证错误", "请选择一个有效的音色。")
            return

        files_to_process = []
        for i in range(self.file_list_widget.count()):
            item_text = self.file_list_widget.item(i).text()
            if os.path.isfile(item_text) and item_text.lower().endswith(".txt"):
                files_to_process.append(item_text)
        if not files_to_process:
            QMessageBox.warning(self, "验证错误", "处理列表中没有有效的TXT文件。请先添加文件。")
            return

        self.start_button.setEnabled(False)
        self.log_message_received(f"-------------------- 开始处理 {len(files_to_process)} 个文件 --------------------\n")
        self.log_message_received(f"输出文件夹: {output_directory}\n")
        self.save_settings()
        self.processing_thread = threading.Thread(
            target=self._run_processing_logic,
            args=(files_to_process, output_directory, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id),
            daemon=True
        )
        self.processing_thread.start()

    def _run_processing_logic(self, txt_file_paths, output_dir, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id):
        try:
            process_list_of_txt_files(txt_file_paths=txt_file_paths, output_dir=output_dir, group_id=group_id, api_key=api_key, model=model, max_workers=max_workers, speed=speed, vol=vol, pitch=pitch, voice_id=voice_id)
        except Exception as e:
            log_queue.put(f"处理过程中发生严重错误: {e}\n")
        finally:
            log_queue.put("-------------------- 所有任务处理完成 --------------------\n")
            QTimer.singleShot(0, lambda: self.start_button.setEnabled(True))
            QTimer.singleShot(0, lambda: QMessageBox.information(self, "任务完成", "所有选定TXT文件处理完毕！"))

    def save_settings(self):
        settings = {
            "output_dir": self.output_dir_edit.text(),
            "group_id": self.group_id_edit.text(),
            "api_key": self.api_key_edit.text(),
            "model": self.model_combo.currentText(),
            "max_workers": self.max_workers_spin.value(),
            "speed": self.speed_spin.value(),
            "vol": self.vol_spin.value(),
            "pitch": self.pitch_spin.value(),
            "language": self.language_combo.currentText(),
            "voice": self.voice_combo.currentText(),
            "last_opened_dir": self.last_opened_dir
        }
        try:
            with open("settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log_message_received(f"保存配置失败: {e}\n", error=True)

    def load_settings(self):
        try:
            settings_file = "settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                self.output_dir_edit.setText(settings.get("output_dir", ""))
                self.last_opened_dir = settings.get("last_opened_dir", os.path.expanduser("~"))
                self.group_id_edit.setText(settings.get("group_id", ""))
                self.api_key_edit.setText(settings.get("api_key", ""))
                self.model_combo.setCurrentText(settings.get("model", self.model_combo.itemText(0) if self.model_combo.count() > 0 else ""))
                self.max_workers_spin.setValue(settings.get("max_workers", 5))
                self.speed_spin.setValue(settings.get("speed", 1.0))
                self.vol_spin.setValue(settings.get("vol", 1))
                self.pitch_spin.setValue(settings.get("pitch", 0))
                saved_lang = settings.get("language")
                if self.languages and saved_lang in self.languages:
                    self.language_combo.setCurrentText(saved_lang)
                    QApplication.processEvents() 
                    saved_voice_display_text = settings.get("voice")
                    if saved_voice_display_text:
                        for i in range(self.voice_combo.count()):
                            if self.voice_combo.itemText(i) == saved_voice_display_text:
                                self.voice_combo.setCurrentIndex(i)
                                break
                elif self.languages and self.languages[0] not in ["(音色配置缺失)", "(无可用音色数据)", "(加载错误)", "(无语言分类)"]:
                    self.language_combo.setCurrentText(self.languages[0])
                if hasattr(self, 'log_text_edit') and self.log_text_edit:
                    self.log_message_received("配置已加载。\n")
                else:
                    self._original_stdout.write("配置已加载 (log_text_edit not ready).\n")
                if hasattr(self, 'file_list_widget') and self.file_list_widget.count() == 0:
                    self.file_list_widget.addItem("请添加TXT文件进行处理。")
                return True
            if hasattr(self, 'file_list_widget') and self.file_list_widget.count() == 0:
                 self.file_list_widget.addItem("请添加TXT文件进行处理。")
            return False
        except Exception as e:
            msg = f"加载配置失败: {e}\n"
            if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
            else: self._original_stdout.write(msg)
            if hasattr(self, 'file_list_widget') and self.file_list_widget.count() == 0:
                 self.file_list_widget.addItem("请添加TXT文件进行处理。")
            return False

    def load_voice_data(self):
        try:
            json_file_path = "minimax_all_voices_with_language.json"
            if not os.path.exists(json_file_path):
                msg = f"错误: 音色配置文件 '{json_file_path}' 未找到。\n"
                # Log directly if UI not fully ready
                if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
                elif hasattr(self, '_original_stdout'): self._original_stdout.write(msg)
                else: print(msg) # Fallback
                self.languages = ["(音色配置缺失)"]
                return

            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.all_voices_data = data.get("minimax_system_voice", [])

            if not self.all_voices_data:
                self.languages = ["(无可用音色数据)"]
            else:
                seen_languages = set()
                temp_languages = []
                for voice in self.all_voices_data:
                    lang = voice.get("language")
                    if lang and lang not in seen_languages:
                        temp_languages.append(lang)
                        seen_languages.add(lang)
                if not temp_languages: self.languages = ["(无语言分类)"]
                else: self.languages = sorted(list(temp_languages))
        except Exception as e: # Catch more general exceptions during file loading
            msg = f"加载音色数据时出错: {e}\n"
            if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
            elif hasattr(self, '_original_stdout'): self._original_stdout.write(msg)
            else: print(msg)
            self.languages = ["(加载错误)"]


    def on_language_select(self, selected_language_text=None):
        selected_language = selected_language_text if selected_language_text is not None else self.language_combo.currentText()
        current_voices_display = []
        self.voice_options_for_selected_language = {}
        self.voice_combo.clear()
        for voice in self.all_voices_data:
            if voice.get("language") == selected_language:
                voice_name = voice.get("voice_name", "未知名称")
                voice_id = voice.get("voice_id")
                if voice_id:
                    display_text = f"{voice_name} ({voice_id})"
                    current_voices_display.append(display_text)
                    self.voice_options_for_selected_language[display_text] = voice_id
        self.voice_combo.addItems(sorted(current_voices_display))
        if current_voices_display: self.voice_combo.setCurrentIndex(0)
        else: self.voice_combo.addItem("(无可用音色)")

    def setup_log_monitoring(self):
        sys.stdout = self._stdout_redirector
        self.log_emitter = LogEmitter(log_queue)
        self.log_thread = QThread(self)
        self.log_emitter.moveToThread(self.log_thread)
        self.log_thread.started.connect(self.log_emitter.poll_log_queue)
        self.log_emitter.log_signal.connect(self.log_message_received)
        self.log_thread.start()

    def log_message_received(self, message, error=False):
        if not hasattr(self, 'log_text_edit') or self.log_text_edit is None:
            self._original_stdout.write(f"Early log (UI not ready or log_text_edit is None): {message}")
            return
        current_color = self.log_text_edit.textColor()
        if error: self.log_text_edit.setTextColor(Qt.red)
        else:
            if message.startswith("任务["): self.log_text_edit.setTextColor(Qt.blue)
            elif "Success" in message or "成功" in message or "已保存" in message: self.log_text_edit.setTextColor(Qt.darkGreen)
            elif "Fail" in message or "失败" in message or "错误" in message or "Error" in message or "异常" in message: self.log_text_edit.setTextColor(Qt.red)
            elif "警告" in message or "Warning" in message: self.log_text_edit.setTextColor(Qt.darkYellow)
            else: self.log_text_edit.setTextColor(Qt.black)
        self.log_text_edit.moveCursor(self.log_text_edit.textCursor().End)
        self.log_text_edit.insertPlainText(message)
        self.log_text_edit.setTextColor(current_color)
        self.log_text_edit.moveCursor(self.log_text_edit.textCursor().End)
        QApplication.processEvents()

    def closeEvent(self, event):
        self.save_settings()
        if hasattr(self, 'log_emitter'): self.log_emitter.running = False
        if hasattr(self, 'log_thread') and self.log_thread.isRunning():
            self.log_thread.quit()
            if not self.log_thread.wait(1000):
                self._original_stdout.write("Log thread did not terminate gracefully.\n")
        sys.stdout = self._original_stdout
        super().closeEvent(event)

