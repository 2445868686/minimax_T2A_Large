# -*- coding: utf-8 -*-
"""
ui.py
存放与 Tkinter 界面相关的逻辑
"""
import os
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
from functions import log_queue, process_all_txt_files

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("语音生成任务处理")
        self.geometry("500x600")

        # 初始化一个音色映射，在界面中使用
        self.voice_mapping = {
            "青涩青年音色": "male-qn-qingse",
            "精英青年音色": "male-qn-jingying",
            "霸道青年音色": "male-qn-badao",
            "青年大学生音色": "male-qn-daxuesheng",
            "少女音色": "female-shaonv",
            "御姐音色": "female-yujie",
            "成熟女性音色": "female-chengshu",
            "甜美女性音色": "female-tianmei",
            "男性主持人": "presenter_male",
            "女性主持人": "presenter_female",
            "男性有声书1": "audiobook_male_1",
            "男性有声书2": "audiobook_male_2",
            "女性有声书1": "audiobook_female_1",
            "女性有声书2": "audiobook_female_2",
            "青涩青年音色-beta": "male-qn-qingse-jingpin",
            "精英青年音色-beta": "male-qn-jingying-jingpin",
            "霸道青年音色-beta": "male-qn-badao-jingpin",
            "青年大学生音色-beta": "male-qn-daxuesheng-jingpin",
            "少女音色-beta": "female-shaonv-jingpin",
            "御姐音色-beta": "female-yujie-jingpin",
            "成熟女性音色-beta": "female-chengshu-jingpin",
            "甜美女性音色-beta": "female-tianmei-jingpin",
            "聪明男童": "clever_boy",
            "可爱男童": "cute_boy",
            "萌萌女童": "lovely_girl",
            "卡通猪小琪": "cartoon_pig"
        }

        # 创建UI控件
        self.create_widgets()

        # 设置日志轮询
        self.poll_log_queue()

    def create_widgets(self):
        param_frame = ttk.LabelFrame(self, text="参数配置")
        param_frame.pack(fill=tk.X, padx=10, pady=5)
        param_frame.columnconfigure(1, weight=1)
        param_frame.columnconfigure(0, weight=0)
        param_frame.columnconfigure(2, weight=0)

        # 1) TXT 文件夹
        ttk.Label(param_frame, text="TXT文件夹:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.base_dir_var = tk.StringVar()
        self.base_dir_entry = ttk.Entry(param_frame, textvariable=self.base_dir_var, width=50)
        self.base_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(param_frame, text="浏览", command=self.choose_directory).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)

        # 2) Group ID
        ttk.Label(param_frame, text="Group ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.group_id_var = tk.StringVar()
        self.group_id_entry = ttk.Entry(param_frame, textvariable=self.group_id_var, width=50)
        self.group_id_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 3) API Key
        ttk.Label(param_frame, text="API Key:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(param_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 4) 模型选择
        ttk.Label(param_frame, text="模型选择:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(
            param_frame, 
            textvariable=self.model_var, 
            state="readonly",
            values=["speech-01-turbo", "speech-01-240228", "speech-01-turbo-240228", "speech-01-hd"]
        )
        self.model_combo.current(0)
        self.model_combo.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 5) 最大线程数
        ttk.Label(param_frame, text="最大线程数:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_workers_var = tk.IntVar(value=5)
        self.max_workers_spin = ttk.Spinbox(param_frame, from_=1, to=100, textvariable=self.max_workers_var, width=10)
        self.max_workers_spin.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        # 6) 语速
        ttk.Label(param_frame, text="语速 (0.5-2):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = tk.Scale(param_frame, variable=self.speed_var, from_=0.5, to=2.0,
                                    orient=tk.HORIZONTAL, resolution=0.1)
        self.speed_scale.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=5)
        self.speed_spin = tk.Spinbox(param_frame, from_=0.5, to=2.0, increment=0.1,
                                     textvariable=self.speed_var, width=5)
        self.speed_spin.grid(row=5, column=2, sticky=tk.W, padx=5, pady=5)

        # 7) 音量
        ttk.Label(param_frame, text="音量 (1-10):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.vol_var = tk.DoubleVar(value=1.0)
        self.vol_scale = tk.Scale(param_frame, variable=self.vol_var, from_=1, to=10,
                                  orient=tk.HORIZONTAL, resolution=1)
        self.vol_scale.grid(row=6, column=1, sticky=tk.EW, padx=5, pady=5)
        self.vol_spin = tk.Spinbox(param_frame, from_=1, to=10, increment=1,
                                   textvariable=self.vol_var, width=5)
        self.vol_spin.grid(row=6, column=2, sticky=tk.W, padx=5, pady=5)

        # 8) 音调
        ttk.Label(param_frame, text="音调 (-12至12):").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.pitch_var = tk.IntVar(value=0)
        self.pitch_scale = tk.Scale(param_frame, variable=self.pitch_var, from_=-12, to=12,
                                    orient=tk.HORIZONTAL, resolution=1)
        self.pitch_scale.grid(row=7, column=1, sticky=tk.EW, padx=5, pady=5)
        self.pitch_spin = tk.Spinbox(param_frame, from_=-12, to=12, increment=1,
                                     textvariable=self.pitch_var, width=5)
        self.pitch_spin.grid(row=7, column=2, sticky=tk.W, padx=5, pady=5)

        # 9) 音色选择
        ttk.Label(param_frame, text="音色选择:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.voice_cn_var = tk.StringVar()
        voice_cn_options = list(self.voice_mapping.keys())
        self.voice_combo = ttk.Combobox(param_frame, textvariable=self.voice_cn_var,
                                        state="readonly", values=voice_cn_options)
        self.voice_combo.set("男性有声书1")
        self.voice_combo.grid(row=8, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 开始处理按钮
        self.start_button = ttk.Button(self, text="开始处理", command=self.start_processing)
        self.start_button.pack(pady=10, anchor="w", padx=10)

        # 日志输出框
        log_frame = ttk.LabelFrame(self, text="日志输出")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, state="disabled", wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def choose_directory(self):
        """
        选择 TXT 文件夹
        """
        dir_selected = filedialog.askdirectory(title="请选择TXT文件夹")
        if dir_selected:
            self.base_dir_var.set(dir_selected)

    def start_processing(self):
        """
        点击开始处理按钮后，执行的操作。
        """
        self.start_button.config(state="disabled")

        base_dir = self.base_dir_var.get().strip()
        group_id = self.group_id_var.get().strip()
        api_key = self.api_key_var.get().strip()
        model = self.model_var.get().strip()
        max_workers = self.max_workers_var.get()
        speed = self.speed_var.get()
        vol = self.vol_var.get()
        pitch = self.pitch_var.get()
        selected_cn_voice = self.voice_cn_var.get()
        voice_id = self.voice_mapping.get(selected_cn_voice, "audiobook_male_1")

        # 简单校验
        if not base_dir or not os.path.exists(base_dir):
            print("请选择正确的TXT文件夹。")
            self.start_button.config(state="normal")
            return
        if not group_id:
            print("请输入Group ID。")
            self.start_button.config(state="normal")
            return
        if not api_key:
            print("请输入API Key。")
            self.start_button.config(state="normal")
            return

        # 新建线程去执行处理，避免阻塞 UI
        threading.Thread(
            target=self.run_processing,
            args=(base_dir, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id),
            daemon=True
        ).start()

    def run_processing(self, base_dir, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id):
        """
        在子线程中处理所有 TXT 文件。
        """
        process_all_txt_files(
            base_dir=base_dir,
            group_id=group_id,
            api_key=api_key,
            model=model,
            max_workers=max_workers,
            speed=speed,
            vol=vol,
            pitch=pitch,
            voice_id=voice_id
        )
        # 所有任务完成后，恢复按钮状态
        self.after(0, lambda: self.start_button.config(state="normal"))

    def poll_log_queue(self):
        """
        定时从 log_queue 中取出日志并显示在日志文本框中。
        """
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
            except:
                break
            else:
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, msg)
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")

        self.after(100, self.poll_log_queue)