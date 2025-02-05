# -*- coding: utf-8 -*-
"""
functions.py
存放所有业务逻辑函数，包括：
1. 创建语音任务、查询任务状态
2. 文件读取、下载、解压、转换为 SRT
3. 线程池任务处理
4. 日志重定向
"""
import os
import json
import time
import tarfile
import shutil
import requests
import threading
import queue
import sys
from concurrent.futures import ThreadPoolExecutor

# 全局日志队列，用于 UI 日志显示
log_queue = queue.Queue()

class StdoutRedirector:
    """
    重定向 stdout，将日志带时间戳和任务编号输出到 log_queue，
    后续 Tkinter UI 可以从 log_queue 获取日志并显示在文本框上。
    """
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

# 将 stdout 重定向到我们自定义的类
sys.stdout = StdoutRedirector()

def read_text_from_file(file_path):
    """读取 TXT 文件并返回文本内容。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def create_speech_task(api_key, group_id, model, text=None, voice_id="audiobook_male_1",
                       speed=1, vol=1, pitch=0, sample_rate=32000, bitrate=128000,
                       format="mp3", channel=2):
    """
    调用接口创建异步文本转语音任务，返回 task_id。
    """
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
        err_msg = response_data.get('base_resp', {}).get('status_msg')
        print(f"任务创建失败，错误信息: {err_msg}")
        return None

def get_task_status(api_key, group_id, task_id):
    """
    查询异步任务状态，如果成功则返回 file_id，否则返回 None。
    """
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

def download_file(api_key, group_id, file_id, save_dir, txt_file_name):
    """
    下载生成的 TAR 文件，保存到本地。
    """
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
        err_msg = response_data.get("base_resp", {}).get("status_msg")
        print(f"获取文件信息失败，错误信息: {err_msg}")
        return None

def extract_and_rename(tar_path, extract_dir, new_dir_name):
    """
    解压 tar 文件，并将解压出的第一个目录重命名为 new_dir_name。
    """
    try:
        with tarfile.open(tar_path, 'r') as tar_ref:
            tar_ref.extractall(extract_dir)
    except Exception as e:
        print(f"解压失败: {e}")
        return None
    print(f"文件已解压到: {extract_dir}")

    # 寻找解压出来的目录
    for item in os.listdir(extract_dir):
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path):
            new_path = os.path.join(extract_dir, new_dir_name)
            try:
                os.rename(item_path, new_path)
            except Exception as e:
                print(f"目录重命名失败: {e}")
                return None
            break
    else:
        print("未找到需要重命名的目录。")
        return None

    # 删除原 tar 文件
    try:
        os.remove(tar_path)
    except Exception as e:
        print(f"删除压缩文件失败: {e}")
    return new_path

def convert_seconds_to_srt_time(seconds):
    """
    将秒数转换为 SRT 时间格式（HH:MM:SS,mmm）。
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def json_to_srt(json_data, srt_path):
    """
    将JSON格式的字幕信息转换为 .srt 文件并保存。
    """
    srt_output = []
    subtitle_id = 1
    for item in json_data:
        text = item["text"]
        # 移除可能出现的 BOM
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
    解压 tar 文件并转换生成 SRT 文件。
    - 解压至 temp_dir
    - 将解压后的第一个目录重命名为 txt_file_name
    - 查找 .titles 文件转换为 SRT
    - 最后移动到 output_dir，并删除 temp_dir
    """
    extracted_dir = extract_and_rename(tar_path, temp_dir, txt_file_name)
    if not extracted_dir:
        print("解压失败，无法处理 SRT 文件")
        return

    # 查找 .titles 文件
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
            srt_path = os.path.join(extracted_dir, f"{txt_file_name}.srt")
            json_to_srt(json_data, srt_path)
        except Exception as e:
            print(f"读取 .titles 文件失败: {e}")

    final_dir = os.path.join(output_dir, txt_file_name)
    if os.path.exists(final_dir):
        final_dir = os.path.join(output_dir, txt_file_name + "_1")

    shutil.move(extracted_dir, final_dir)
    shutil.rmtree(temp_dir)

    return final_dir

def process_txt_file(txt_path, api_key, group_id, model, output_dir, voice_id, speed, vol, pitch, task_num):
    """
    处理单个 TXT 文件的逻辑：
    1. 读取文本
    2. 创建异步语音任务
    3. 查询任务状态
    4. 下载 tar 文件并解压
    5. 生成 SRT
    """
    # 设置线程标识，供日志前缀使用
    threading.current_thread().task_id = task_num

    txt_file_name = os.path.splitext(os.path.basename(txt_path))[0]
    text = read_text_from_file(txt_path)
    if not text:
        print(f"任务[{task_num}] 无法读取文本文件: {txt_path}")
        return

    # 创建任务
    task_id_created = create_speech_task(api_key, group_id, model, text=text, 
                                         voice_id=voice_id, speed=speed, vol=vol, pitch=pitch)
    if not task_id_created:
        print(f"任务[{task_num}] 文件 {txt_path} 创建任务失败，跳过。")
        return

    # 查询任务状态
    file_id = get_task_status(api_key, group_id, task_id_created)
    if not file_id:
        print(f"任务[{task_num}] 文件 {txt_path} 未获取到 file_id，跳过。")
        return

    # 下载与解压
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

    # 最后尝试移除任务标识
    try:
        delattr(threading.current_thread(), "task_id")
    except Exception:
        pass

def process_all_txt_files(base_dir, group_id, api_key, model,
                          max_workers, speed, vol, pitch, voice_id):
    """
    多线程方式处理所有 TXT 文件。
    """
    tasks = [os.path.join(base_dir, f) 
             for f in os.listdir(base_dir) if f.lower().endswith(".txt")]
    if not tasks:
        print("未找到TXT文件。")
        return

    print(f"开始处理文件夹: {base_dir}")

    # 创建线程池
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, task in enumerate(tasks, start=1):
            future = executor.submit(
                process_txt_file, 
                task, 
                api_key, 
                group_id, 
                model, 
                base_dir, 
                voice_id, 
                speed, 
                vol, 
                pitch, 
                i
            )
            futures[future] = task

        # 等待所有任务完成
        for future in futures:
            task_file = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"处理文件 {task_file} 时发生错误: {e}")

    print("所有任务处理完成。")