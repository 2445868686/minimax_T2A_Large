# -*- coding: utf-8 -*-
"""
main.py
主程序入口，只负责初始化和启动 PyQt5 应用。
"""
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox # Added QMessageBox
from ui import MainWindow  # 从 ui.py 导入 MainWindow
from datetime import datetime # Added datetime

def main():
    # --- Expiration Check ---
    
    app = QApplication.instance() # Use existing instance if created for message box
    if app is None:
        app = QApplication(sys.argv)

    app.setStyle("Fusion")  # 设置一个现代的UI风格

    main_window = MainWindow()
    main_window.show()  # 允许窗口默认可手动调整大小

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
