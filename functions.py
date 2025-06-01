# -*- coding: utf-8 -*-
"""
functions.py
存放所有业务逻辑函数，包括：
1. 创建语音任务、查询任务状态
2. 文件读取、下载、解压、转换为 SRT
3. 线程池任务处理
4. 日志重定向
5. 成功记录保存
"""
import os
import json
import time # 导入 time 模块
import tarfile
import shutil
import requests # Ensure requests is imported
import threading
import queue
import sys
from concurrent.futures import ThreadPoolExecutor
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
# 全局日志队列，用于 UI 日志显示
log_queue = queue.Queue()

# 定义网络请求的默认超时时间 (连接超时, 读取超时)
DEFAULT_REQUEST_TIMEOUT = (10, 60) # 10 秒连接，60 秒读取

# 定义 succeed.json 文件的路径

SUCCEED_JSON_FILEPATH = get_path_in_exe_directory("succeed.json") # 修改后


class StdoutRedirector:
    """
    重定向 stdout，将日志带时间戳和任务编号输出到 log_queue，
    后续 UI 可以从 log_queue 获取日志并显示在文本框上。
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

# sys.stdout = StdoutRedirector() # 如果UI处于活动状态，则应由UI端管理

def read_text_from_file(file_path):
    """读取 TXT 文件并返回文本内容。"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def save_success_record(record_data):
    """将成功生成的记录保存到 succeed.json 文件中。"""
    try:
        records = []
        if os.path.exists(SUCCEED_JSON_FILEPATH):
            with open(SUCCEED_JSON_FILEPATH, 'r', encoding='utf-8') as f:
                try:
                    records = json.load(f)
                    if not isinstance(records, list): # 确保它是一个列表
                        print(f"警告: {SUCCEED_JSON_FILEPATH} 内容不是一个列表，将重置为空列表。")
                        records = []
                except json.JSONDecodeError:
                    print(f"警告: {SUCCEED_JSON_FILEPATH} JSON 解析失败，将重置为空列表。")
                    records = [] # 如果文件损坏，则重新开始
        records.append(record_data)
        with open(SUCCEED_JSON_FILEPATH, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=4)
        log_queue.put(f"成功记录已保存到: {SUCCEED_JSON_FILEPATH}\n")
    except Exception as e:
        log_queue.put(f"保存成功记录失败: {e}\n")


def create_speech_task(api_key, group_id, model, text=None, voice_id="audiobook_male_1",
                       speed=1.0, vol=1.0, pitch=0, sample_rate=32000, bitrate=128000,
                       format="mp3", channel=2, emotion="default"): # Added emotion, default to "default"
    """
    调用接口创建异步文本转语音任务，返回 task_id。
    """
    url = f"https://api.minimax.chat/v1/t2a_async_v2?GroupId={group_id}"
    
    voice_setting = {
        "voice_id": voice_id,
        "speed": float(speed),
        "vol": float(vol),
        "pitch": int(pitch)
    }
    
    # Only add emotion to voice_setting if it's not "default"
    if emotion and emotion.lower() != "default":
        voice_setting["emotion"] = emotion
        
    payload = {
        "model": model,
        "text": text,
        "voice_setting": voice_setting,
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
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=DEFAULT_REQUEST_TIMEOUT)
        response_data = response.json()
    except requests.exceptions.Timeout:
        print(f"任务创建请求超时 (URL: {url})")
        return None
    except Exception as e:
        print(f"任务创建请求异常: {e}")
        return None

    if response_data.get("base_resp", {}).get("status_code") == 0:
        task_id = response_data.get("task_id")
        print(f"任务创建成功，task_id: {task_id}")
        return task_id
    else:
        err_msg = response_data.get('base_resp', {}).get('status_msg', 'Unknown error')
        err_code = response_data.get('base_resp', {}).get('status_code', 'N/A')
        emotion_log = f", Emotion: {emotion}" if emotion and emotion.lower() != "default" else ""
        print(f"任务创建失败 (Code: {err_code})，错误信息: {err_msg}. Request details: Model={model}, Voice={voice_id}, Speed={speed}, Vol={vol}, Pitch={pitch}{emotion_log}")
        return None

def get_task_status(api_key, group_id, task_id):
    """
    查询异步任务状态，如果成功则返回 file_id，否则返回 None。
    """
    url = f"https://api.minimax.chat/v1/query/t2a_async_query_v2?GroupId={group_id}&task_id={task_id}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    max_retries = 100
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
            response_data = response.json()
        except requests.exceptions.Timeout:
            print(f"任务状态查询请求超时 (URL: {url})，重试 {retry_count + 1}/{max_retries}...")
            time.sleep(5)
            retry_count += 1
            continue
        except Exception as e:
            print(f"任务状态查询请求异常: {e}，重试 {retry_count + 1}/{max_retries}...")
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

        time.sleep(5) # 在重试状态检查“处理中”或其他非最终状态之前等待
        retry_count += 1

    print("任务查询超时或达到最大重试次数。")
    return None

def download_file(api_key, group_id, file_id, save_dir, txt_file_name):
    """
    下载生成的 TAR 文件，保存到本地。
    成功时返回 (下载的文件路径, 下载链接)，失败时返回 (None, None)。
    """
    url = f'https://api.minimax.chat/v1/files/retrieve?GroupId={group_id}&file_id={file_id}'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    actual_download_url = None # 用于存储实际的下载链接
    try:
        response = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
        response_data = response.json()
    except requests.exceptions.Timeout:
        print(f"文件信息检索请求超时 (URL: {url})")
        return None, None
    except Exception as e:
        print(f"文件信息检索请求异常: {e}")
        return None, None

    if response_data.get("base_resp", {}).get("status_code") == 0:
        file_info_resp = response_data.get("file", {})
        actual_download_url = file_info_resp.get("download_url")
        file_name_ext = f"{txt_file_name}.tar"
        if actual_download_url:
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            file_path = os.path.join(save_dir, file_name_ext)
            try:
                download_timeout = (DEFAULT_REQUEST_TIMEOUT[0], 300) # 10秒连接，300秒 (5分钟) 读取
                file_response = requests.get(actual_download_url, stream=True, timeout=download_timeout)
                file_response.raise_for_status() # 对错误的HTTP状态码抛出异常
                with open(file_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192): # 8KB 块
                        if chunk:
                            f.write(chunk)
            except requests.exceptions.Timeout:
                print(f"文件下载请求超时 (URL: {actual_download_url})")
                if os.path.exists(file_path): os.remove(file_path) # 清理部分下载
                return None, actual_download_url # 即使下载失败，也返回尝试过的URL
            except requests.exceptions.RequestException as e_req: # 捕获 HTTPError 等
                print(f"文件下载HTTP或其他请求错误: {e_req}")
                if os.path.exists(file_path): os.remove(file_path)
                return None, actual_download_url
            except Exception as e:
                print(f"文件下载时发生一般错误: {e}")
                if os.path.exists(file_path): os.remove(file_path)
                return None, actual_download_url
            print(f"文件已成功下载到 {file_path}")
            return file_path, actual_download_url
        else:
            print("未找到下载链接。")
            return None, None
    else:
        err_msg = response_data.get("base_resp", {}).get("status_msg")
        print(f"获取文件信息失败，错误信息: {err_msg}")
        return None, None

def extract_and_rename(tar_path, extract_dir, new_dir_name):
    """
    解压 tar 文件，并将解压出的第一个目录重命名为 new_dir_name。
    """
    try:
        with tarfile.open(tar_path, 'r') as tar_ref:
            tar_ref.extractall(extract_dir)
    except Exception as e:
        print(f"解压失败: {e}")
        if os.path.isdir(os.path.join(extract_dir, new_dir_name)):
             shutil.rmtree(os.path.join(extract_dir, new_dir_name), ignore_errors=True)
        return None
    print(f"文件已解压到: {extract_dir}")

    extracted_items = os.listdir(extract_dir)
    extracted_dirs_or_files = [item for item in extracted_items if item != os.path.basename(tar_path)]

    if not extracted_dirs_or_files:
        print(f"解压后未在 {extract_dir} 中找到任何文件或目录。")
        return None

    renamed_path = None
    for item in extracted_dirs_or_files:
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path):
            new_path_target = os.path.join(extract_dir, new_dir_name)
            if os.path.exists(new_path_target):
                print(f"目标目录 {new_path_target} 已存在，将尝试删除后重命名。")
                try:
                    shutil.rmtree(new_path_target)
                except Exception as e_rm:
                    print(f"删除已存在的目标目录 {new_path_target} 失败: {e_rm}")

            try:
                os.rename(item_path, new_path_target)
                renamed_path = new_path_target
                print(f"解压出的目录 '{item}' 已重命名为 '{new_dir_name}' 位于 '{new_path_target}'")
                break
            except Exception as e:
                print(f"目录 {item_path} 重命名为 {new_path_target} 失败: {e}")
                return None

    if not renamed_path:
        print(f"解压后未找到可重命名的单一目录。检查 {extract_dir} 内容: {extracted_dirs_or_files}")
        return None

    try:
        os.remove(tar_path)
        print(f"已删除原始压缩文件: {tar_path}")
    except Exception as e:
        print(f"删除压缩文件失败: {e}")

    return renamed_path

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

def process_tar_to_srt(tar_path, temp_extract_base_dir, final_output_base_dir, txt_file_name_for_output_folder):
    renamed_extracted_content_dir = extract_and_rename(tar_path, temp_extract_base_dir, txt_file_name_for_output_folder)

    if not renamed_extracted_content_dir:
        print(f"解压或重命名失败 {tar_path}，无法处理 SRT 文件")
        if os.path.exists(temp_extract_base_dir): # 如果重命名失败，确保清理
            shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
        return None

    titles_file = None
    for root, _, files in os.walk(renamed_extracted_content_dir):
        for file_name in files:
            if file_name.endswith(".titles"):
                titles_file = os.path.join(root, file_name)
                break
        if titles_file:
            break

    if not titles_file:
        print(f"在 {renamed_extracted_content_dir} 中未找到 .titles 文件")
    else:
        try:
            with open(titles_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            srt_path = os.path.join(renamed_extracted_content_dir, f"{txt_file_name_for_output_folder}.srt")
            json_to_srt(json_data, srt_path)
        except Exception as e:
            print(f"读取 .titles 文件或生成SRT失败: {e}")

    final_target_dir_path = os.path.join(final_output_base_dir, txt_file_name_for_output_folder)

    if os.path.exists(final_target_dir_path):
        print(f"最终目标目录 {final_target_dir_path} 已存在。正在尝试覆盖...")
        try:
            shutil.rmtree(final_target_dir_path)
        except Exception as e_rm_final:
            print(f"删除已存在的最终目录 {final_target_dir_path} 失败: {e_rm_final}。跳过移动。")
            if os.path.exists(temp_extract_base_dir): # 如果移动失败，清理临时文件
                shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
            return None

    try:
        shutil.move(renamed_extracted_content_dir, final_target_dir_path)
        print(f"处理完成的文件夹已移动到: {final_target_dir_path}")
    except Exception as e_move:
        print(f"移动文件夹 {renamed_extracted_content_dir} 到 {final_target_dir_path} 失败: {e_move}")
        if os.path.exists(temp_extract_base_dir):
             shutil.rmtree(temp_extract_base_dir, ignore_errors=True) # 如果移动失败，清理临时文件
        return None

    if os.path.exists(temp_extract_base_dir):
        try:
            shutil.rmtree(temp_extract_base_dir)
            print(f"已清理临时文件夹: {temp_extract_base_dir}")
        except Exception as e_clean:
            print(f"清理临时文件夹 {temp_extract_base_dir} 失败: {e_clean}")

    return final_target_dir_path


def process_txt_file(file_info, output_dir, api_key, group_id, model, task_num):
    """
    处理单个 TXT 文件的逻辑，使用 file_info 字典获取每个文件的设置。
    """
    threading.current_thread().task_id = task_num

    txt_path = file_info['path']
    voice_id = file_info['voice_id']
    voice_display_name = file_info.get('voice_display', voice_id) # 获取显示名称，如果不存在则使用ID
    speed = file_info['speed']
    vol = file_info['vol']
    pitch = file_info['pitch']
    emotion_api_value = file_info.get('emotion', "default") # Get emotion API value, default to "default"
    emotion_display_name = file_info.get('emotion_display', "默认") # Get emotion display name, default to "默认"

    txt_file_name_no_ext = os.path.splitext(os.path.basename(txt_path))[0]
    print(f"开始处理文件: {txt_path} (Voice: {voice_display_name}, Emotion: {emotion_display_name}, Speed: {speed}, Vol: {vol}, Pitch: {pitch})") # Added Emotion to log

    text = read_text_from_file(txt_path)
    if not text:
        print(f"无法读取文本文件: {txt_path}，跳过。")
        return # 关键：返回以使 future.result() 不会挂起

    task_id_created = create_speech_task(api_key, group_id, model, text=text,
                                         voice_id=voice_id, speed=speed, vol=vol, pitch=pitch, 
                                         emotion=emotion_api_value) # Pass emotion API value
    if not task_id_created:
        print(f"文件 {txt_file_name_no_ext} 创建任务失败，跳过。")
        return

    retrieved_file_id = get_task_status(api_key, group_id, task_id_created)
    if not retrieved_file_id:
        print(f"文件 {txt_file_name_no_ext} 未获取到 file_id，跳过。")
        return

    temp_processing_dir_for_file = os.path.join(output_dir, f"{txt_file_name_no_ext}_temp_processing_files")
    if os.path.exists(temp_processing_dir_for_file): # 确保此文件的干净状态
        shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True)
    try:
        os.makedirs(temp_processing_dir_for_file, exist_ok=True)
    except Exception as e:
        print(f"创建临时目录 {temp_processing_dir_for_file} 失败: {e}，跳过。")
        return

    downloaded_tar_path, audio_tar_download_url = download_file(api_key, group_id, retrieved_file_id, temp_processing_dir_for_file, txt_file_name_no_ext)

    if not downloaded_tar_path:
        print(f"文件 {txt_file_name_no_ext} 下载 tar 失败，跳过。")
        if audio_tar_download_url: # 即使下载失败，如果获取到了URL，也尝试记录
             log_queue.put(f"文件 {txt_file_name_no_ext} 的 tar 下载链接为: {audio_tar_download_url} 但下载失败。\n")
        if os.path.exists(temp_processing_dir_for_file):
            shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True)
        return

    # --- 保存成功记录 ---
    # 即使后续的 SRT 处理失败，只要 tar 文件下载成功，我们就记录它
    if audio_tar_download_url: # 确保我们有下载链接
        success_data = {
            "文件名": txt_file_name_no_ext,
            "音色": voice_display_name,
            "音色ID": voice_id,
            "语速": speed,
            "音量": vol,
            "音调": pitch,
            "情绪": emotion_display_name, # Added emotion display name
            "情绪(API)": emotion_api_value, # Added emotion API value
            "模型": model,
            "原始文本路径": txt_path,
            "音频下载链接(tar)": audio_tar_download_url, # 这是 tar 文件的下载链接
            "生成时间": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_success_record(success_data)
    # --- 结束保存 ---

    final_folder_path = process_tar_to_srt(downloaded_tar_path,
                                           temp_processing_dir_for_file,
                                           output_dir,
                                           txt_file_name_no_ext)

    if final_folder_path:
        print(f"文件 {txt_file_name_no_ext} 处理完成。输出位于: {final_folder_path}")
    else:
        print(f"文件 {txt_file_name_no_ext} 处理过程中发生错误，未能生成最终输出。")
        # temp_processing_dir_for_file 应该在 process_tar_to_srt 失败时被清理

    try:
        delattr(threading.current_thread(), "task_id")
    except AttributeError:
        pass
    except Exception as e:
        print(f"清理线程任务ID时出错: {e}")


def process_list_of_txt_files(files_and_settings_list, output_dir, group_id, api_key, model, max_workers):
    """
    多线程方式处理提供的 TXT 文件列表及它们各自的设置。
    """
    if not files_and_settings_list:
        print("未提供TXT文件进行处理。")
        return

    print(f"准备处理 {len(files_and_settings_list)} 个TXT文件。输出将保存到目录: {output_dir}")
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"已创建输出目录: {output_dir}")
        except Exception as e:
            print(f"创建输出目录 {output_dir} 失败: {e}。请检查权限或路径。")
            return

    original_stdout = sys.stdout
    redirector_instance_in_function = None # 用于保存实例（如果已创建）
    if not hasattr(sys.stdout, 'log_queue'): # 检查 stdout 是否已经是我们的重定向器之一
        redirector_instance_in_function = StdoutRedirector()
        redirector_instance_in_function.log_queue = log_queue # 链接到全局队列
        sys.stdout = redirector_instance_in_function
        log_queue.put("[functions.py: 线程池临时重定向 stdout。]\n")


    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, file_info_dict in enumerate(files_and_settings_list, start=1):
            future = executor.submit(
                process_txt_file,
                file_info_dict, # This dictionary now contains 'emotion' and 'emotion_display'
                output_dir,
                api_key,
                group_id,
                model,
                i
            )
            futures[future] = os.path.basename(file_info_dict['path'])

        for future in futures: # 遍历 future 以等待完成并捕获异常
            task_file_basename = futures[future]
            try:
                future.result() # 等待任务完成。这可以重新引发 process_txt_file 中的异常
            except Exception as e:
                # process_txt_file 中的错误应该在那里记录。
                # 如果 future.result() 本身有问题或任务出现意外错误，则会捕获此错误。
                print(f"处理文件 {task_file_basename} 时线程池捕获到意外错误: {e}")

    if redirector_instance_in_function is not None: # 如果我们在此函数中重定向了 stdout
        sys.stdout = original_stdout
        log_queue.put("[functions.py: 已恢复原始 stdout。]\n")


    print(f"所有 {len(files_and_settings_list)} 个选定文件的处理尝试已完成。")
