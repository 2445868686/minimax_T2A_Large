# -*- coding: utf-8 -*-
"""
本示例代码实现语音生成任务处理，并增加了基于 Tkinter 的图形界面：
1. 参数配置项：
   - TXT文件夹选择（base_dir）
   - group_id（文本框）
   - api_key（密码框）
   - 模型下拉框（可选："speech-01-turbo", "speech-01-240228", "speech-01-turbo-240228", "speech-01-hd"）
   - 最大线程数
   - 语速（范围 [0.5,2]，步进 0.1，默认 1.0）
   - 音量（范围 [1,10]，步进 1，默认 1.0）
   - 音调（范围 [-12,12]，步进 1，默认 0）
   - 音色下拉框（中文显示 → 英文参数映射）
   - 日志输出窗口，显示处理日志，并带有时间戳与任务编号
2. 每个 TXT 文件的处理使用独立的临时目录，避免不同任务间相互干扰，
   最终生成的目录名称为 TXT 文件基本名称（如 "text" 或 "文本1"）。
   在解压后，会查找 .titles 文件并转换生成 SRT 文件。
"""

import os
import json
import time
import tarfile
import shutil
import requests
import concurrent.futures
import threading
import queue
import sys
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext

# =================== 业务逻辑函数 ===================

def read_text_from_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def get_task_status(api_key, group_id, task_id):
    url = f"https://api.minimaxi.chat/v1/query/t2a_async_query_v2?GroupId={group_id}&task_id={task_id}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    max_retries = 100
    retry_count = 0
    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers)
            response_data = response.json()
        except Exception as e:
            print(f"请求异常: {e}")
            time.sleep(5)
            retry_count += 1
            continue
        if response_data.get("base_resp", {}).get("status_code") == 0:
            status = response_data.get("status")
            file_id = response_data.get("file_id")
            if status == "Success":
                print(f"任务状态: Success，file_id: {file_id}")
                return file_id
            elif status == "Failed":
                print("任务失败，请检查任务状态和日志。")
                return None
            elif status == "Expired":
                print("任务已过期，无法生成语音。")
                return None
            else:
                print(f"任务状态: {status}，正在处理中...")
        else:
            print("查询失败，状态代码:", response_data.get("base_resp", {}).get("status_code"))
        time.sleep(5)
        retry_count += 1
    print("任务查询超时，尝试次数过多。")
    return None

def create_speech_task(api_key, group_id, model, text=None, voice_id="audiobook_male_1",
                       speed=1, vol=1, pitch=0, sample_rate=32000, bitrate=128000,
                       format="mp3", channel=2):
    url = f"https://api.minimaxi.chat/v1/t2a_async_v2?GroupId={group_id}"
    payload = {
        "model": model,
        "text": text,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "vol": vol,
            "pitch": pitch
        },
        "audio_setting": {
            "audio_sample_rate": sample_rate,
            "bitrate": bitrate,
            "format": format,
            "channel": channel
        }
    }
    # 不再打印 payload 信息
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response_data = response.json()
    except Exception as e:
        print(f"任务创建请求异常: {e}")
        return None
    if response_data.get("base_resp", {}).get("status_code") == 0:
        task_id = response_data.get("task_id")
        print(f"任务创建成功，task_id: {task_id}")
        return task_id
    else:
        print(f"任务创建失败，错误信息: {response_data.get('base_resp', {}).get('status_msg')}")
        return None

def download_file(api_key, group_id, file_id, save_dir, txt_file_name):
    url = f'https://api.minimaxi.chat/v1/files/retrieve?GroupId={group_id}&file_id={file_id}'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()
    except Exception as e:
        print(f"下载请求异常: {e}")
        return None
    if response_data.get("base_resp", {}).get("status_code") == 0:
        file_info = response_data.get("file", {})
        download_url = file_info.get("download_url")
        file_name = f"{txt_file_name}.tar"
        if download_url:
            #print(f"文件下载链接: {download_url}")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            file_path = os.path.join(save_dir, file_name)
            try:
                file_response = requests.get(download_url, stream=True)
                with open(file_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
            except Exception as e:
                print(f"文件下载异常: {e}")
                return None
            print(f"文件已成功下载到 {file_path}")
            return file_path
        else:
            print("未找到下载链接。")
            return None
    else:
        print(f"获取文件信息失败，错误信息: {response_data.get('base_resp', {}).get('status_msg')}")
        return None

def extract_and_rename(tar_path, extract_dir, new_dir_name):
    """
    在指定的 extract_dir 中解压 tar 文件，并将解压出来的第一个目录重命名为 new_dir_name 。
    """
    try:
        with tarfile.open(tar_path, 'r') as tar_ref:
            tar_ref.extractall(extract_dir)
    except Exception as e:
        print(f"解压失败: {e}")
        return None
    print(f"文件已解压到: {extract_dir}")
    for item in os.listdir(extract_dir):
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path):
            new_path = os.path.join(extract_dir, new_dir_name)
            try:
                os.rename(item_path, new_path)
                #print(f"目录已重命名为: {new_path}")
            except Exception as e:
                print(f"目录重命名失败: {e}")
                return None
            break
    else:
        print("未找到需要重命名的目录。")
        return None
    try:
        os.remove(tar_path)
        #print(f"已删除压缩文件: {tar_path}")
    except Exception as e:
        print(f"删除压缩文件失败: {e}")
    return new_path

def convert_seconds_to_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def json_to_srt(json_data, srt_path):
    srt_output = []
    subtitle_id = 1
    for item in json_data:
        text = item["text"]
        if text.startswith("\ufeff"):
            text = text[1:]
        start_time = convert_seconds_to_srt_time(item["time_begin"] / 1000)
        end_time = convert_seconds_to_srt_time(item["time_end"] / 1000)
        srt_output.append(f"{subtitle_id}")
        srt_output.append(f"{start_time} --> {end_time}")
        srt_output.append(text)
        srt_output.append("")
        subtitle_id += 1
    try:
        with open(srt_path, 'w', encoding='utf-8') as file:
            file.write("\n".join(srt_output))
        print(f"SRT 文件已保存：{srt_path}")
    except Exception as e:
        print(f"保存 SRT 文件失败: {e}")

def process_tar_to_srt(tar_path, temp_dir, output_dir, txt_file_name):
    """
    在已创建的 temp_dir 中解压 tar 文件，并将解压出的目录重命名为 txt_file_name，
    然后查找 .titles 文件转换生成 SRT 文件，
    最后将该目录移动到 output_dir 作为最终结果目录，并删除 temp_dir。
    """
    extracted_dir = extract_and_rename(tar_path, temp_dir, txt_file_name)
    if not extracted_dir:
        print("解压失败，无法处理 SRT 文件")
        return
    # 查找 .titles 文件，并转换生成 SRT 文件
    titles_file = None
    for root, _, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith(".titles"):
                titles_file = os.path.join(root, file)
                break
        if titles_file:
            break
    if not titles_file:
        print("未找到 .titles 文件")
    else:
        try:
            with open(titles_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            print(f"读取 .titles 文件失败: {e}")
        else:
            srt_path = os.path.join(extracted_dir, f"{txt_file_name}.srt")
            json_to_srt(json_data, srt_path)
    final_dir = os.path.join(output_dir, txt_file_name)
    if os.path.exists(final_dir):
        final_dir = os.path.join(output_dir, txt_file_name + "_1")
    shutil.move(extracted_dir, final_dir)
    shutil.rmtree(temp_dir)
    return final_dir

def process_txt_file(txt_path, api_key, group_id, model, output_dir, voice_id, speed, vol, pitch, task_num):
    threading.current_thread().task_id = task_num
    txt_file_name = os.path.splitext(os.path.basename(txt_path))[0]
    text = read_text_from_file(txt_path)
    if not text:
        print(f"任务[{task_num}] 无法读取文本文件: {txt_path}")
        return
    task_id_created = create_speech_task(api_key, group_id, model, text=text, voice_id=voice_id,
                                         speed=speed, vol=vol, pitch=pitch)
    if not task_id_created:
        print(f"任务[{task_num}] 文件 {txt_path} 创建任务失败，跳过。")
        return
    file_id = get_task_status(api_key, group_id, task_id_created)
    if not file_id:
        print(f"任务[{task_num}] 文件 {txt_path} 未获取到 file_id，跳过。")
        return
    # 为当前任务创建专用的临时目录用于下载 tar 文件及解压
    temp_dir = os.path.join(output_dir, txt_file_name + "_temp")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    tar_file_path = download_file(api_key, group_id, file_id, temp_dir, txt_file_name)
    if not tar_file_path:
        print(f"任务[{task_num}] 文件 {txt_path} 下载 tar 失败，跳过。")
        return
    process_tar_to_srt(tar_file_path, temp_dir, output_dir, txt_file_name)
    print(f"任务[{task_num}] 文件 {txt_path} 处理完成。")
    try:
        delattr(threading.current_thread(), "task_id")
    except Exception:
        pass

# =================== 日志重定向（带时间戳和任务编号） ===================

log_queue = queue.Queue()

class StdoutRedirector:
    def write(self, text):
        if text:
            lines = text.split('\n')
            for line in lines:
                line_strip = line.strip()
                if line_strip:
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    task_id = getattr(threading.current_thread(), "task_id", None)
                    prefix = f"任务[{task_id}]" if task_id is not None else ""
                    formatted_line = f"[{current_time}]{prefix} {line_strip}\n"
                    log_queue.put(formatted_line)
    def flush(self):
        pass

sys.stdout = StdoutRedirector()

# =================== UI 界面 ===================

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("语音生成任务处理")
        self.geometry("500x600")
        self.create_widgets()
        self.poll_log_queue()

    def create_widgets(self):
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
        param_frame = ttk.LabelFrame(self, text="参数配置")
        param_frame.pack(fill=tk.X, padx=10, pady=5)
        param_frame.columnconfigure(1, weight=1)
        param_frame.columnconfigure(0, weight=0)
        param_frame.columnconfigure(2, weight=0)

        ttk.Label(param_frame, text="TXT文件夹:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.base_dir_var = tk.StringVar()
        self.base_dir_entry = ttk.Entry(param_frame, textvariable=self.base_dir_var, width=50)
        self.base_dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(param_frame, text="浏览", command=self.choose_directory).grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(param_frame, text="Group ID:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.group_id_var = tk.StringVar()
        self.group_id_entry = ttk.Entry(param_frame, textvariable=self.group_id_var, width=50)
        self.group_id_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(param_frame, text="API Key:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(param_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(param_frame, text="模型选择:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(param_frame, textvariable=self.model_var, state="readonly",
                                        values=["speech-01-turbo", "speech-01-240228", "speech-01-turbo-240228", "speech-01-hd"])
        self.model_combo.current(0)
        self.model_combo.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(param_frame, text="最大线程数:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_workers_var = tk.IntVar(value=5)
        self.max_workers_spin = ttk.Spinbox(param_frame, from_=1, to=100, textvariable=self.max_workers_var, width=10)
        self.max_workers_spin.grid(row=4, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(param_frame, text="语速 (0.5-2):").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_scale = tk.Scale(param_frame, variable=self.speed_var, from_=0.5, to=2.0,
                                    orient=tk.HORIZONTAL, resolution=0.1)
        self.speed_scale.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=5)
        self.speed_spin = tk.Spinbox(param_frame, from_=0.5, to=2.0, increment=0.1,
                                     textvariable=self.speed_var, width=5)
        self.speed_spin.grid(row=5, column=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(param_frame, text="音量 (1-10):").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.vol_var = tk.DoubleVar(value=1.0)
        self.vol_scale = tk.Scale(param_frame, variable=self.vol_var, from_=1, to=10,
                                  orient=tk.HORIZONTAL, resolution=1)
        self.vol_scale.grid(row=6, column=1, sticky=tk.EW, padx=5, pady=5)
        self.vol_spin = tk.Spinbox(param_frame, from_=1, to=10, increment=1,
                                   textvariable=self.vol_var, width=5)
        self.vol_spin.grid(row=6, column=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(param_frame, text="音调 (-12至12):").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
        self.pitch_var = tk.IntVar(value=0)
        self.pitch_scale = tk.Scale(param_frame, variable=self.pitch_var, from_=-12, to=12,
                                    orient=tk.HORIZONTAL, resolution=1)
        self.pitch_scale.grid(row=7, column=1, sticky=tk.EW, padx=5, pady=5)
        self.pitch_spin = tk.Spinbox(param_frame, from_=-12, to=12, increment=1,
                                     textvariable=self.pitch_var, width=5)
        self.pitch_spin.grid(row=7, column=2, sticky=tk.W, padx=5, pady=5)

        ttk.Label(param_frame, text="音色选择:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        self.voice_cn_var = tk.StringVar()
        voice_cn_options = list(self.voice_mapping.keys())
        self.voice_combo = ttk.Combobox(param_frame, textvariable=self.voice_cn_var,
                                        state="readonly", values=voice_cn_options)
        self.voice_combo.set("男性有声书1")
        self.voice_combo.grid(row=8, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        self.start_button = ttk.Button(self, text="开始处理", command=self.start_processing)
        self.start_button.pack(pady=10, anchor="w", padx=10)

        log_frame = ttk.LabelFrame(self, text="日志输出")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, state="disabled", wrap="word")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def choose_directory(self):
        dir_selected = filedialog.askdirectory(title="请选择TXT文件夹")
        if dir_selected:
            self.base_dir_var.set(dir_selected)

    def start_processing(self):
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
        tasks = [os.path.join(base_dir, f) for f in os.listdir(base_dir)
                 if f.lower().endswith(".txt")]
        if not tasks:
            print("未找到TXT文件。")
            self.start_button.config(state="normal")
            return
        print(f"开始处理文件夹: {base_dir}")
        threading.Thread(target=self.process_all, args=(base_dir, group_id, api_key, model,
                                                         max_workers, speed, vol, pitch, voice_id),
                         daemon=True).start()

    def process_all(self, base_dir, group_id, api_key, model, max_workers, speed, vol, pitch, voice_id):
        tasks = [os.path.join(base_dir, f) for f in os.listdir(base_dir)
                 if f.lower().endswith(".txt")]
        if not tasks:
            print("未找到TXT文件。")
            self.after(0, lambda: self.start_button.config(state="normal"))
            return
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, task in enumerate(tasks, start=1):
                future = executor.submit(process_txt_file, task, api_key, group_id, model,
                                           base_dir, voice_id, speed, vol, pitch, i)
                futures[future] = task
            for future in concurrent.futures.as_completed(futures):
                task_file = futures[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"处理文件 {task_file} 时发生错误: {e}")
        print("所有任务处理完成。")
        self.after(0, lambda: self.start_button.config(state="normal"))

    def poll_log_queue(self):
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
            except queue.Empty:
                break
            else:
                self.log_text.config(state="normal")
                self.log_text.insert(tk.END, msg)
                self.log_text.see(tk.END)
                self.log_text.config(state="disabled")
        self.after(100, self.poll_log_queue)

if __name__ == "__main__":
    app = App()
    app.mainloop()
