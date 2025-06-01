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
    QTabWidget
)
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont, QIcon

def get_path_in_exe_directory(filename):
    """
    获取与可执行文件（或开发时的脚本）在同一目录下的文件的绝对路径。
    """
    if getattr(sys, 'frozen', False):
        # 程序被打包成 EXE (sys.frozen 为 True)
        application_path = os.path.dirname(sys.executable)
    else:
        # 程序作为普通脚本运行 (开发环境)
        # 假设脚本从项目根目录运行，JSON文件也位于此处
        application_path = os.path.abspath(".")
    return os.path.join(application_path, filename)

# --- Define Global Paths Here ---
MINIMAX_VOICES_JSON_PATH = get_path_in_exe_directory("minimax_all_voices_with_language.json")
SETTINGS_JSON_PATH = get_path_in_exe_directory("settings.json")

# 从 functions.py 导入必要的模块
try:
    from functions import log_queue, process_list_of_txt_files, StdoutRedirector #
except ImportError:
    print("Warning: functions.py not found. Using dummy implementations for testing.")
    log_queue = queue.Queue()

    class StdoutRedirector:
        def __init__(self):
            self._original_stdout = sys.stdout
            self.log_queue = log_queue
        def write(self, text):
            self.log_queue.put(text)
            self._original_stdout.write(text)
        def flush(self):
            self._original_stdout.flush()

    def process_list_of_txt_files(files_and_settings_list, output_dir, group_id, api_key, model, max_workers):
        log_queue.put(f"Simulating processing for {len(files_and_settings_list)} files.\n")
        log_queue.put(f"Params: output_dir={output_dir}, group_id={group_id}, model={model}\n")
        for i, file_info in enumerate(files_and_settings_list):
            f_path = file_info['path']
            log_queue.put(f"任务[{i+1}/{len(files_and_settings_list)}] 开始模拟处理文件: {os.path.basename(f_path)} with settings: {file_info}\n")
            import time
            time.sleep(0.2) # Simulate work
            log_queue.put(f"任务[{i+1}/{len(files_and_settings_list)}] 文件 {os.path.basename(f_path)} 模拟处理成功。\n")
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
QPushButton#StartButton:disabled { /* Style when button is disabled */
    background-color: #b0b0b0; /* Greyed out */
    color: #707070;
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
QWidget#SettingsContainerWidget { 
    background-color: transparent; 
}
"""

PLACEHOLDER_TEXT_EMPTY_LIST = "请添加TXT文件进行处理。"
PLACEHOLDER_TEXT_ALL_REMOVED = "文件列表为空或所有文件已被移除。"

# Emotion mapping: Display Text (Chinese) -> API Value (English)
EMOTION_MAP = {
    "默认": "default",
    "中性": "neutral",
    "高兴": "happy",
    "悲伤": "sad",
    "愤怒": "angry",
    "害怕": "fearful",
    "厌恶": "disgusted",
    "惊讶": "surprised"
}
# Reverse map for loading settings or displaying: API Value -> Display Text
REVERSE_EMOTION_MAP = {v: k for k, v in EMOTION_MAP.items()}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MiniMax超长文本语音生成")
        self.setMinimumSize(600, 500) 
  
        self.all_voices_data = []
        self.languages = []
        self.voice_options_for_selected_language = {}
        self.last_opened_dir = os.path.expanduser("~")

        self._original_stdout = sys.stdout
        self._stdout_redirector = StdoutRedirector()
        LogEmitter._original_stdout_for_emitter = self._original_stdout
        
        # Stores dicts: {'path': str, 'language': str, 'voice_id': str, 'voice_display': str, 
        # 'speed': float, 'vol': int, 'pitch': int, 'emotion': str (API value), 'emotion_display': str (UI text)}
        self.file_data_list = [] 
        self.current_selected_file_row = -1
        self.updating_controls_programmatically = False # Flag to prevent update loops

        # Initialize UI elements
        self.language_combo = QComboBox()
        self.voice_combo = QComboBox()
        self.emotion_combo = QComboBox() # New emotion combo box
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

        self.load_voice_data() 
        self.initUI()
        self.setup_log_monitoring()

        if not self.load_settings(): # Applies global defaults
            if self.languages and self.languages[0] not in ["(音色配置缺失)", "(无可用音色数据)", "(加载错误)", "(无语言分类)"]:
                self.language_combo.setCurrentText(self.languages[0]) # Triggers on_language_select
            self.emotion_combo.setCurrentIndex(0) # Set default emotion if settings not loaded (will be "默认")

        self.update_file_list_placeholder()


    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.setStyleSheet(STYLESHEET)
        tab_widget = QTabWidget()

        # --- Tab 1: 语音合成 (Speech Synthesis) ---
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(5, 10, 5, 5)

        file_selection_group = QGroupBox("文件选择与管理")
        file_selection_group_layout = QVBoxLayout()
        
        self.add_files_button.clicked.connect(self.add_txt_files_to_list)
        add_files_layout = QHBoxLayout()
        add_files_layout.addWidget(self.add_files_button)
        add_files_layout.addStretch()
        file_selection_group_layout.addLayout(add_files_layout)

        file_selection_group_layout.addWidget(QLabel("待处理 TXT 文件列表 (可多选删除, 单击可修改下方参数):"))
        self.file_list_widget.setMinimumHeight(100)
        self.file_list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.MinimumExpanding)
        self.file_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.file_list_widget.keyPressEvent = self.handle_file_list_key_press
        self.file_list_widget.currentItemChanged.connect(self.on_file_selection_changed) # Connect selection change
        file_selection_group_layout.addWidget(self.file_list_widget)

        self.delete_file_button.clicked.connect(self.delete_selected_files_from_list)
        delete_button_layout = QHBoxLayout()
        delete_button_layout.addStretch()
        delete_button_layout.addWidget(self.delete_file_button)
        file_selection_group_layout.addLayout(delete_button_layout)
        
        file_selection_group.setLayout(file_selection_group_layout)
        tab1_layout.addWidget(file_selection_group)


        voice_select_group = QGroupBox("选中文件的音色与情感 (或新文件默认)") # Updated GroupBox title
        voice_select_layout = QFormLayout()
        if self.languages: self.language_combo.addItems(self.languages)
        self.language_combo.currentTextChanged.connect(self.on_language_combo_changed) 
        voice_select_layout.addRow("语言选择:", self.language_combo)
        
        self.voice_combo.currentTextChanged.connect(self.on_voice_combo_changed)
        voice_select_layout.addRow("音色选择:", self.voice_combo)

        # Add emotion combo box
        self.emotion_combo.addItems(EMOTION_MAP.keys()) # Populate with Chinese display names
        self.emotion_combo.currentTextChanged.connect(self.on_emotion_combo_changed)
        voice_select_layout.addRow("情感选择:", self.emotion_combo)

        voice_select_group.setLayout(voice_select_layout)
        tab1_layout.addWidget(voice_select_group)
        
        tab1_layout.addStretch(1)
        tab_widget.addTab(tab1_widget, "语音合成")

        audio_params_group = QGroupBox("选中文件的语音参数 (或新文件默认参数)")
        audio_params_layout = QFormLayout()
        
        self.speed_spin.setRange(0.5, 2.0); self.speed_spin.setSingleStep(0.1); self.speed_spin.setValue(1.0)
        self.speed_slider.setRange(5, 20); self.speed_slider.setValue(int(self.speed_spin.value() * 10))
        self.speed_slider.valueChanged.connect(lambda val: self.speed_spin.setValue(val / 10.0))
        self.speed_spin.valueChanged.connect(lambda val: self.speed_slider.setValue(int(val * 10)))
        self.speed_spin.valueChanged.connect(lambda val: self.update_selected_file_parameter('speed', val))
        speed_layout = QHBoxLayout(); speed_layout.addWidget(self.speed_spin, 1); speed_layout.addWidget(self.speed_slider, 3)
        audio_params_layout.addRow("语速 (0.5-2.0):", speed_layout)

        self.vol_spin.setRange(1, 10); self.vol_spin.setValue(1)
        self.vol_slider.setRange(1, 10); self.vol_slider.setValue(self.vol_spin.value())
        self.vol_slider.valueChanged.connect(self.vol_spin.setValue)
        self.vol_spin.valueChanged.connect(self.vol_slider.setValue)
        self.vol_spin.valueChanged.connect(lambda val: self.update_selected_file_parameter('vol', val))
        vol_layout = QHBoxLayout(); vol_layout.addWidget(self.vol_spin, 1); vol_layout.addWidget(self.vol_slider, 3)
        audio_params_layout.addRow("音量 (1-10):", vol_layout)

        self.pitch_spin.setRange(-12, 12); self.pitch_spin.setValue(0)
        self.pitch_slider.setRange(-12, 12); self.pitch_slider.setValue(self.pitch_spin.value())
        self.pitch_slider.valueChanged.connect(self.pitch_spin.setValue)
        self.pitch_spin.valueChanged.connect(self.pitch_slider.setValue)
        self.pitch_spin.valueChanged.connect(lambda val: self.update_selected_file_parameter('pitch', val))
        pitch_layout = QHBoxLayout(); pitch_layout.addWidget(self.pitch_spin, 1); pitch_layout.addWidget(self.pitch_slider, 3)
        audio_params_layout.addRow("音调 (-12至12):", pitch_layout)
        audio_params_group.setLayout(audio_params_layout)
        tab1_layout.addWidget(audio_params_group)
        # --- Tab 2: 配置 (Configuration) ---
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(5, 10, 5, 5)

        auth_group = QGroupBox("认证信息")
        auth_layout = QFormLayout()
        auth_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)
        auth_layout.setLabelAlignment(Qt.AlignLeft)
        auth_layout.addRow("Group ID:", self.group_id_edit)
        auth_layout.addRow("API Key:", self.api_key_edit)
        auth_group.setLayout(auth_layout)
        tab2_layout.addWidget(auth_group)

        output_model_group = QGroupBox("输出与通用模型设置")
        output_model_layout = QFormLayout()
        
        self.output_dir_button.clicked.connect(self.choose_output_directory)
        output_dir_hbox = QHBoxLayout()
        output_dir_hbox.addWidget(self.output_dir_edit)
        output_dir_hbox.addWidget(self.output_dir_button)
        output_model_layout.addRow("输出文件夹:", output_dir_hbox)
        
        self.model_combo.addItems(["speech-01-turbo", "speech-02-turbo","speech-01-hd","speech-02-hd","speech-01-240228", "speech-01-turbo-240228",])
        output_model_layout.addRow("通用模型选择:", self.model_combo) 
        
        self.max_workers_spin.setRange(1, 100)
        self.max_workers_spin.setValue(5)
        output_model_layout.addRow("最大线程数:", self.max_workers_spin)
        
        output_model_group.setLayout(output_model_layout)
        tab2_layout.addWidget(output_model_group)

        tab2_layout.addStretch(1)
        tab_widget.addTab(tab2_widget, "配置")

        main_layout.addWidget(tab_widget, 1) 

        self.start_button = QPushButton("开始处理")
        self.start_button.setObjectName("StartButton")
        self.start_button.setFixedHeight(45)
        self.start_button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
        self.start_button.clicked.connect(self.start_processing)
        main_layout.addWidget(self.start_button)

        self.log_label = QLabel("日志输出:")
        self.log_label.setObjectName("LogLabel")
        main_layout.addWidget(self.log_label)

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setObjectName("LogTextEdit")
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setFont(QFont("Courier New", 9))
        self.log_text_edit.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        main_layout.addWidget(self.log_text_edit, 2)

    def update_file_list_placeholder(self):
        self.file_list_widget.blockSignals(True)
        if not self.file_data_list:
            if self.file_list_widget.count() == 0 or self.file_list_widget.item(0).text() != PLACEHOLDER_TEXT_EMPTY_LIST :
                self.file_list_widget.clear()
                self.file_list_widget.addItem(PLACEHOLDER_TEXT_EMPTY_LIST)
                self.file_list_widget.item(0).setForeground(Qt.gray)
        elif self.file_list_widget.count() == 1 and self.file_list_widget.item(0).text() in [PLACEHOLDER_TEXT_EMPTY_LIST, PLACEHOLDER_TEXT_ALL_REMOVED]:
            self.file_list_widget.clear() 
            for file_info in self.file_data_list:
                 self.file_list_widget.addItem(self.get_display_text_for_file_info(file_info))
        self.file_list_widget.blockSignals(False)


    def get_display_text_for_file_info(self, file_info):
        base_name = os.path.basename(file_info['path'])
        voice_name_part = file_info['voice_display'].split('(')[0].strip() if file_info['voice_display'] else "N/A"
        emotion_display = file_info.get('emotion_display', "默认") # Default to "默认" if not present
        return f"{base_name} (Voice: {voice_name_part}, Emo: {emotion_display}, Spd: {file_info['speed']:.1f}, Vol: {file_info['vol']}, Pitch: {file_info['pitch']})"


    def refresh_file_list_display(self):
        self.file_list_widget.blockSignals(True)
        current_row = self.file_list_widget.currentRow()
        self.file_list_widget.clear()
        if not self.file_data_list:
            self.update_file_list_placeholder()
        else:
            for file_info in self.file_data_list:
                self.file_list_widget.addItem(self.get_display_text_for_file_info(file_info))
            if 0 <= current_row < len(self.file_data_list):
                 self.file_list_widget.setCurrentRow(current_row)
            elif len(self.file_data_list) > 0 :
                 self.file_list_widget.setCurrentRow(0)

        self.file_list_widget.blockSignals(False)
        if self.file_list_widget.currentRow() != current_row and len(self.file_data_list) > 0 : 
            QTimer.singleShot(0, lambda: self.on_file_selection_changed(self.file_list_widget.currentItem(), None))


    def on_file_selection_changed(self, current_item, previous_item):
        if not current_item or not self.file_data_list or current_item.text() in [PLACEHOLDER_TEXT_EMPTY_LIST, PLACEHOLDER_TEXT_ALL_REMOVED]:
            self.current_selected_file_row = -1
            return

        row = self.file_list_widget.row(current_item)
        if 0 <= row < len(self.file_data_list):
            self.current_selected_file_row = row
            file_info = self.file_data_list[row]
            
            self.updating_controls_programmatically = True 
            
            self.language_combo.setCurrentText(file_info['language'])
            # Defer voice and emotion setting until language combo has settled
            QTimer.singleShot(0, lambda: self._finish_loading_file_settings(file_info))
        else:
            self.current_selected_file_row = -1

    def _finish_loading_file_settings(self, file_info):
        self.voice_combo.setCurrentText(file_info['voice_display'])
        self.emotion_combo.setCurrentText(file_info.get('emotion_display', "默认")) # Load emotion, default to "默认"
        self.speed_spin.setValue(file_info['speed'])
        self.vol_spin.setValue(file_info['vol'])
        self.pitch_spin.setValue(file_info['pitch'])
        
        self.updating_controls_programmatically = False 

    def update_selected_file_parameter(self, param_name, param_value):
        if self.updating_controls_programmatically or self.current_selected_file_row == -1:
            return
        if 0 <= self.current_selected_file_row < len(self.file_data_list):
            file_info = self.file_data_list[self.current_selected_file_row]
            changed = False
            if param_name == 'language':
                if file_info['language'] != param_value:
                    file_info['language'] = param_value
                    changed = True 
            elif param_name == 'voice_display':
                if file_info['voice_display'] != param_value:
                    file_info['voice_display'] = param_value
                    file_info['voice_id'] = self.voice_options_for_selected_language.get(param_value)
                    changed = True
            elif param_name == 'emotion_display': # Handle emotion change
                api_emotion_value = EMOTION_MAP.get(param_value, "default") # Default to "default"
                if file_info.get('emotion_display') != param_value or file_info.get('emotion') != api_emotion_value:
                    file_info['emotion_display'] = param_value
                    file_info['emotion'] = api_emotion_value
                    changed = True
            elif param_name in ['speed', 'vol', 'pitch']:
                 if file_info[param_name] != param_value:
                    file_info[param_name] = param_value
                    changed = True
            
            if changed:
                self.refresh_file_list_display() 


    def on_language_combo_changed(self, lang_text):
        self._populate_voices_for_language(lang_text) 
        if not self.updating_controls_programmatically and self.current_selected_file_row != -1:
            file_info = self.file_data_list[self.current_selected_file_row]
            file_info['language'] = lang_text
            if self.voice_combo.count() > 0:
                new_voice_display = self.voice_combo.itemText(0) 
                self.voice_combo.setCurrentIndex(0) 
                file_info['voice_display'] = new_voice_display
                file_info['voice_id'] = self.voice_options_for_selected_language.get(new_voice_display)
            else:
                file_info['voice_display'] = "(无可用音色)"
                file_info['voice_id'] = None
            self.refresh_file_list_display()


    def on_voice_combo_changed(self, voice_display_text):
        if not self.updating_controls_programmatically and self.current_selected_file_row != -1:
            self.update_selected_file_parameter('voice_display', voice_display_text)

    def on_emotion_combo_changed(self, emotion_display_text): # New handler for emotion
        if not self.updating_controls_programmatically and self.current_selected_file_row != -1:
            self.update_selected_file_parameter('emotion_display', emotion_display_text)


    def _populate_voices_for_language(self, selected_language_text):
        self.voice_combo.blockSignals(True)
        current_voices_display = []
        self.voice_options_for_selected_language = {}
        self.voice_combo.clear()
        for voice in self.all_voices_data:
            if voice.get("language") == selected_language_text:
                voice_name = voice.get("voice_name", "未知名称")
                voice_id = voice.get("voice_id")
                if voice_id:
                    display_text = f"{voice_name} ({voice_id})"
                    current_voices_display.append(display_text)
                    self.voice_options_for_selected_language[display_text] = voice_id
        
        sorted_voices = sorted(current_voices_display)
        if sorted_voices:
            self.voice_combo.addItems(sorted_voices)
            self.voice_combo.setCurrentIndex(0) 
        else:
            self.voice_combo.addItem("(无可用音色)")
        self.voice_combo.blockSignals(False)


    def handle_file_list_key_press(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_selected_files_from_list()
        else:
            QListWidget.keyPressEvent(self.file_list_widget, event)

    def choose_output_directory(self):
        dir_selected = QFileDialog.getExistingDirectory(
            self, "请选择输出文件夹", self.output_dir_edit.text() or self.last_opened_dir )
        if dir_selected:
            self.output_dir_edit.setText(dir_selected)
            self.log_message_received(f"输出文件夹设置为: {dir_selected}\n")

    def add_txt_files_to_list(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要处理的TXT文件 (可多选)", self.last_opened_dir, "TXT Files (*.txt);;All Files (*)" )
        
        if file_paths:
            self.last_opened_dir = os.path.dirname(file_paths[0])
            
            if self.file_list_widget.count() == 1 and self.file_list_widget.item(0).text() in [PLACEHOLDER_TEXT_EMPTY_LIST, PLACEHOLDER_TEXT_ALL_REMOVED]:
                self.file_list_widget.clear()

            files_added_count = 0
            existing_paths_in_data = {fi['path'] for fi in self.file_data_list}

            for path in file_paths:
                if path not in existing_paths_in_data:
                    current_lang = self.language_combo.currentText()
                    current_voice_display = self.voice_combo.currentText() 
                    current_voice_id = self.voice_options_for_selected_language.get(current_voice_display)
                    
                    if not current_voice_id and self.voice_combo.count() > 0 and not current_voice_display.startswith("("):
                        current_voice_display = self.voice_combo.itemText(0)
                        current_voice_id = self.voice_options_for_selected_language.get(current_voice_display)
                    
                    current_emotion_display = self.emotion_combo.currentText()
                    current_emotion_api = EMOTION_MAP.get(current_emotion_display, "default") # Default to "default"

                    file_info = {
                        'path': path,
                        'language': current_lang,
                        'voice_display': current_voice_display if current_voice_id else "(无可用音色)",
                        'voice_id': current_voice_id,
                        'speed': self.speed_spin.value(),
                        'vol': self.vol_spin.value(),
                        'pitch': self.pitch_spin.value(),
                        'emotion_display': current_emotion_display, # Add emotion display
                        'emotion': current_emotion_api # Add emotion API value
                    }
                    self.file_data_list.append(file_info)
                    files_added_count += 1
            
            if files_added_count > 0:
                self.log_message_received(f"添加了 {files_added_count} 个文件到处理列表。\n")
            
            self.refresh_file_list_display()
            self.update_file_list_placeholder() 

    def delete_selected_files_from_list(self):
        selected_items = self.file_list_widget.selectedItems()
        if not selected_items: return

        rows_to_delete = sorted([self.file_list_widget.row(item) for item in selected_items], reverse=True)
        
        deleted_count = 0
        for row in rows_to_delete:
            if 0 <= row < len(self.file_data_list): 
                removed_file_info = self.file_data_list.pop(row)
                self.log_message_received(f"从列表中移除了: {os.path.basename(removed_file_info['path'])}\n")
                deleted_count +=1

        if deleted_count > 0:
            self.current_selected_file_row = -1 
            self.refresh_file_list_display()

        self.update_file_list_placeholder()
        if not self.file_data_list and deleted_count > 0 : 
             self.file_list_widget.clear()
             self.file_list_widget.addItem(PLACEHOLDER_TEXT_ALL_REMOVED)
             self.file_list_widget.item(0).setForeground(Qt.gray)


    def start_processing(self):
        output_directory = self.output_dir_edit.text().strip()
        group_id = self.group_id_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        model = self.model_combo.currentText() 
        max_workers = self.max_workers_spin.value()

        if not output_directory or not os.path.isdir(output_directory):
            QMessageBox.warning(self, "验证错误", "请选择一个有效的输出文件夹 (在“配置”选项卡中)。")
            return
        if not group_id:
            QMessageBox.warning(self, "验证错误", "请输入 Group ID (在“配置”选项卡中)。")
            return
        if not api_key:
            QMessageBox.warning(self, "验证错误", "请输入 API Key (在“配置”选项卡中)。")
            return

        if not self.file_data_list:
            QMessageBox.warning(self, "验证错误", "处理列表中没有文件。请先添加文件。")
            return
        
        for idx, file_info in enumerate(self.file_data_list):
            if not file_info['voice_id']:
                QMessageBox.warning(self, "验证错误", f"文件 '{os.path.basename(file_info['path'])}' (列表中的第 {idx+1}项) 没有选择有效的音色。请选中该文件并选择音色。")
                self.file_list_widget.setCurrentRow(idx) 
                return
            # Emotion is now part of file_info, ensure it's there (though add_txt_files_to_list should guarantee it)
            if not file_info.get('emotion') or not file_info.get('emotion_display'):
                # This should ideally not happen if defaults are set correctly.
                QMessageBox.warning(self, "验证错误", f"文件 '{os.path.basename(file_info['path'])}' (列表中的第 {idx+1}项) 情感参数缺失。请重新添加或检查。")
                self.file_list_widget.setCurrentRow(idx)
                return
            if not os.path.isfile(file_info['path']) or not file_info['path'].lower().endswith(".txt"):
                QMessageBox.warning(self, "验证错误", f"文件 '{os.path.basename(file_info['path'])}' (列表中的第 {idx+1}项) 不是一个有效的 TXT 文件。")
                self.file_list_widget.setCurrentRow(idx)
                return


        self.start_button.setEnabled(False)
        self.start_button.setText("处理中...") 
        self.log_message_received(f"-------------------- 开始处理 {len(self.file_data_list)} 个文件 --------------------\n")
        self.log_message_received(f"输出文件夹: {output_directory}\n")
        self.save_settings() 

        files_and_settings_to_process = [dict(fi) for fi in self.file_data_list]

        self.processing_thread = threading.Thread(
            target=self._run_processing_logic,
            args=(files_and_settings_to_process, output_directory, group_id, api_key, model, max_workers),
            daemon=True
        )
        self.processing_thread.start()

    def on_processing_finished(self):
        """Called from the main thread after processing is done."""
        self.start_button.setEnabled(True)
        self.start_button.setText("开始处理")
        QMessageBox.information(self, "任务完成", "所有选定TXT文件处理完毕！")

    def _run_processing_logic(self, files_and_settings_list, output_dir, group_id, api_key, model, max_workers):
        try:
            process_list_of_txt_files(
                files_and_settings_list=files_and_settings_list, 
                output_dir=output_dir, 
                group_id=group_id, 
                api_key=api_key, 
                model=model, 
                max_workers=max_workers
            ) #
        except Exception as e:
            log_queue.put(f"处理过程中发生严重错误: {e}\n")
        finally:
            log_queue.put("-------------------- 所有任务处理完成 --------------------\n")
            QTimer.singleShot(0, self.on_processing_finished)


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
            "emotion": self.emotion_combo.currentText(), # Save default emotion display text
            "last_opened_dir": self.last_opened_dir
        }
        try:
            with open(SETTINGS_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            self.log_message_received(f"保存配置失败: {e}\n", error=True)

    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_JSON_PATH):
                with open(SETTINGS_JSON_PATH, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                
                self.updating_controls_programmatically = True 

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
                elif self.languages and self.languages[0] not in ["(音色配置缺失)", "(无可用音色数据)", "(加载错误)", "(无语言分类)"]:
                    self.language_combo.setCurrentText(self.languages[0])
                
                QApplication.processEvents() 
                
                saved_voice_display_text = settings.get("voice")
                if saved_voice_display_text:
                    for i in range(self.voice_combo.count()):
                        if self.voice_combo.itemText(i) == saved_voice_display_text:
                            self.voice_combo.setCurrentIndex(i)
                            break
                
                saved_emotion_display_text = settings.get("emotion", "默认") # Load emotion display text, default to "默认"
                if saved_emotion_display_text in EMOTION_MAP:
                    self.emotion_combo.setCurrentText(saved_emotion_display_text)
                else: # Fallback to first item ("默认") if saved one is not valid
                    self.emotion_combo.setCurrentIndex(0)

                self.updating_controls_programmatically = False

                if hasattr(self, 'log_text_edit') and self.log_text_edit:
                    self.log_message_received("配置已加载。\n")
                else:
                    self._original_stdout.write("配置已加载 (log_text_edit not ready).\n")
                
                self.update_file_list_placeholder()
                return True
            
            self.update_file_list_placeholder()
            return False
        except Exception as e:
            msg = f"加载配置失败: {e}\n"
            if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
            else: self._original_stdout.write(msg)
            self.update_file_list_placeholder()
            self.updating_controls_programmatically = False 
            return False

    def load_voice_data(self):
        try:
            json_file_path = get_path_in_exe_directory(MINIMAX_VOICES_JSON_PATH) # 修改后
            if not os.path.exists(json_file_path):
                msg = f"错误: 音色配置文件 '{json_file_path}' 未找到。\n"
                if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
                elif hasattr(self, '_original_stdout'): self._original_stdout.write(msg)
                else: print(msg) 
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
        except Exception as e: 
            msg = f"加载音色数据时出错: {e}\n"
            if hasattr(self, 'log_text_edit') and self.log_text_edit: self.log_message_received(msg, error=True)
            elif hasattr(self, '_original_stdout'): self._original_stdout.write(msg)
            else: print(msg)
            self.languages = ["(加载错误)"]


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
        self.log_text_edit.setTextColor(current_color) # Reset to default or previous color
        self.log_text_edit.moveCursor(self.log_text_edit.textCursor().End)
        QApplication.processEvents()

    def closeEvent(self, event):
        self.save_settings() # Save global settings
        if hasattr(self, 'log_emitter'): self.log_emitter.running = False
        if hasattr(self, 'log_thread') and self.log_thread.isRunning():
            self.log_thread.quit()
            if not self.log_thread.wait(1000):
                self._original_stdout.write("Log thread did not terminate gracefully.\n")
        sys.stdout = self._original_stdout
        super().closeEvent(event)
