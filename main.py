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
    try:
        expiration_date = datetime(2025, 6, 31)
        current_date = datetime.now()

        if current_date > expiration_date:
            app_temp = QApplication.instance() # Check if an instance already exists
            if app_temp is None: # If not, create one for the message box
                app_temp = QApplication(sys.argv)

            QMessageBox.warning(
                None, # Parent widget (None for a top-level dialog)
                "软件许可已过期", # Title
                "抱歉，本软件的试用期已结束。\n请联系作者获取更新版本或延长许可。\n\n作者联系方式：[请在此处填写您的联系方式]", # Message
                QMessageBox.Ok # Buttons
            )
            sys.exit() # Exit the application
    except Exception as e:
        # In case of any error during the date check, still try to run the app
        # or log the error, depending on desired behavior.
        # For now, we'll print an error and let it proceed.
        print(f"Error during expiration check: {e}")
        # If you prefer to halt on error, uncomment the next line:
        # sys.exit()

    # --- Proceed to launch application if not expired ---
    app = QApplication.instance() # Use existing instance if created for message box
    if app is None:
        app = QApplication(sys.argv)

    app.setStyle("Fusion")  # 设置一个现代的UI风格

    main_window = MainWindow()
    main_window.show()  # 允许窗口默认可手动调整大小

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
