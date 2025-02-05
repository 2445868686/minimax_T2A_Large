# -*- coding: utf-8 -*-
"""
main.py
主程序入口，只负责初始化和启动 Tkinter 应用。
"""
from ui import App

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()