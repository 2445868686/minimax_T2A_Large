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
SUCCEED_JSON_FILEPATH = get_path_in_exe_directory("succeed.json")


class StdoutRedirector:
    """
    重定向 stdout，将日志带时间戳和任务编号输出到 log_queue，
    后续 UI 可以从 log_queue 获取日志并显示在文本框上。
    """
    _original_stdout = sys.stdout # Store original stdout at class level

    def write(self, text):
        if text:
            lines = text.split('\n')
            for line in lines:
                line_strip = line.strip()
                if line_strip:
                    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
                    task_id_str = ""
                    current_thread = threading.current_thread()
                    if hasattr(current_thread, "task_id") and current_thread.task_id is not None:
                         task_id_str = f"任务[{current_thread.task_id}]"
                    
                    # Fallback to thread name if task_id is not specific enough or not set
                    thread_name_part = ""
                    if not task_id_str and "ThreadPoolExecutor" in current_thread.name: # Generic thread pool name
                        thread_name_part = f"线程[{current_thread.name.split('_')[-1]}]" # Try to get a unique part
                    elif not task_id_str : # Main thread or other named threads
                         thread_name_part = f"线程[{current_thread.name}]"

                    prefix = task_id_str or thread_name_part # Prioritize task_id
                    
                    formatted_line = f"[{current_time}]{prefix} {line_strip}\n"
                    log_queue.put(formatted_line)
                    # Also write to original stdout for console visibility if needed, or remove this line
                    # self._original_stdout.write(formatted_line)


    def flush(self):
        # self._original_stdout.flush()
        pass

# sys.stdout = StdoutRedirector() # If UI is active, it should manage redirection.

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

def upload_text_file(api_key, group_id, file_path):
    """
    Uploads a text file to the MiniMax API and returns the file_id.
    """
    url = f"https://api.minimax.chat/v1/files/upload?GroupId={group_id}"
    payload = {'purpose': 't2a_async_input'}
    file_name = os.path.basename(file_path)

    #print(f"准备上传文件: {file_name} 到 {url}")

    try:
        with open(file_path, 'rb') as f:
            files = [('file', (file_name, f, 'text/plain'))]
            headers = {
                'Authorization': f'Bearer {api_key}',
            }
            
            response = requests.post(url, headers=headers, data=payload, files=files, timeout=DEFAULT_REQUEST_TIMEOUT)
            response_data = response.json()
            
        if response.status_code == 200 and response_data.get("base_resp", {}).get("status_code") == 0:
            # Corrected: Extract file_id from the 'file' dictionary
            file_object = response_data.get("file", {})
            file_id = file_object.get("file_id")
            
            if file_id:
                print(f"文件 '{file_name}' 上传成功。file_id: {file_id}")
                return file_id
            else:
                # This case should ideally not be reached if base_resp status_code is 0 and file_id is expected.
                print(f"文件上传 '{file_name}' 响应成功但未能从 'file' 对象中解析 file_id。响应: {response_data}")
                return None
        else:
            err_msg = response_data.get("base_resp", {}).get("status_msg", "未知错误")
            api_status_code = response_data.get("base_resp", {}).get("status_code", "N/A")
            print(f"文件上传失败 '{file_name}'。HTTP状态: {response.status_code}, API状态码: {api_status_code}, 消息: {err_msg}. 响应: {response_data}")
            return None

    except requests.exceptions.Timeout:
        print(f"文件上传请求超时 (URL: {url}) 文件: {file_name}")
        return None
    except requests.exceptions.RequestException as e_req:
        print(f"文件上传请求错误 for '{file_name}': {e_req}")
        if hasattr(e_req, 'response') and e_req.response is not None:
            print(f"    响应状态: {e_req.response.status_code}")
            print(f"    响应内容: {e_req.response.text}")
        return None
    except Exception as e:
        print(f"文件上传请求异常 '{file_name}': {e}")
        return None


def create_speech_task(api_key, group_id, model, text_file_id, voice_id="audiobook_male_1",
                       speed=1.0, vol=1.0, pitch=0, sample_rate=32000, bitrate=128000,
                       format="mp3", channel=2, emotion="default"):
    """
    调用接口创建异步文本转语音任务，使用 text_file_id，返回 task_id。
    """
    url = f"https://api.minimax.chat/v1/t2a_async_v2?GroupId={group_id}"
    
    voice_setting = {
        "voice_id": voice_id,
        "speed": float(speed),
        "vol": float(vol), 
        "pitch": int(pitch)
    }
    
    if emotion and emotion.lower() != "default":
        voice_setting["emotion"] = emotion
        
    payload = {
        "model": model,
        "text_file_id": text_file_id, 
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
        print(f"任务创建成功，task_id: {task_id} (使用 file_id: {text_file_id})")
        return task_id
    else:
        err_msg = response_data.get('base_resp', {}).get('status_msg', 'Unknown error')
        err_code = response_data.get('base_resp', {}).get('status_code', 'N/A')
        emotion_log = f", Emotion: {emotion}" if emotion and emotion.lower() != "default" else ""
        print(f"任务创建失败 (Code: {err_code})，错误信息: {err_msg}. Request details: Model={model}, TextFileID={text_file_id}, Voice={voice_id}, Speed={speed}, Vol={vol}, Pitch={pitch}{emotion_log}")
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
    retry_delay_seconds = 5 

    for retry_count in range(max_retries):
        #print(f"查询任务状态 (尝试 {retry_count + 1}/{max_retries})... Task ID: {task_id}")
        try:
            response = requests.get(url, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT)
            response_data = response.json()
        except requests.exceptions.Timeout:
            print(f"任务状态查询请求超时 (URL: {url})，将在 {retry_delay_seconds} 秒后重试...")
            time.sleep(retry_delay_seconds)
            continue
        except Exception as e:
            print(f"任务状态查询请求异常: {e}，将在 {retry_delay_seconds} 秒后重试...")
            time.sleep(retry_delay_seconds)
            continue

        base_resp = response_data.get("base_resp", {})
        if base_resp.get("status_code") == 0:
            status = response_data.get("status")
            file_id = response_data.get("file_id") 
            task_id = response_data.get("task_id", "N/A")
            
            print(f"任务状态: {status}, File ID (音频): {file_id}, 将在 5 秒后再次检查...")

            if status == "Success":
                return file_id
            elif status == "Failed":
                print(f"任务处理失败 (Trace ID: {task_id})。请检查日志或联系支持。")
                return None
            elif status == "Expired":
                print(f"任务已过期 (Trace ID: {task_id})，无法生成语音。")
                return None
            #else: 
                #print(f"任务仍在处理中 (状态: {status})，将在 {retry_delay_seconds} 秒后再次检查...")
        else:
            err_msg = base_resp.get('status_msg', 'Unknown error')
            err_code = base_resp.get('status_code', 'N/A')
            print(f"查询任务状态失败 (Code: {err_code}), 错误信息: {err_msg}。将在 {retry_delay_seconds} 秒后重试...")

        time.sleep(retry_delay_seconds)

    print(f"任务查询达到最大重试次数 ({max_retries}) 或持续超时。Task ID: {task_id}")
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
    actual_download_url = None 
    file_path = None 

    print(f"准备下载文件信息，File ID: {file_id}")
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
            print(f"获取到下载链接: {actual_download_url}")
            if not os.path.exists(save_dir):
                try:
                    os.makedirs(save_dir)
                    print(f"创建目录: {save_dir}")
                except Exception as e_mkdir:
                    print(f"创建保存目录 {save_dir} 失败: {e_mkdir}")
                    return None, actual_download_url 

            file_path = os.path.join(save_dir, file_name_ext)
            
            #print(f"开始下载文件到: {file_path}")
            try:
                download_timeout = (DEFAULT_REQUEST_TIMEOUT[0], 300) 
                file_response = requests.get(actual_download_url, stream=True, timeout=download_timeout)
                file_response.raise_for_status() 
                
                with open(file_path, 'wb') as f:
                    for chunk in file_response.iter_content(chunk_size=8192): 
                        if chunk:
                            f.write(chunk)
                #print(f"文件已成功下载到 {file_path}")
                return file_path, actual_download_url
            except requests.exceptions.Timeout:
                print(f"文件下载请求超时 (URL: {actual_download_url})")
                if os.path.exists(file_path): os.remove(file_path) 
                return None, actual_download_url 
            except requests.exceptions.RequestException as e_req: 
                print(f"文件下载HTTP或其他请求错误: {e_req}")
                if os.path.exists(file_path): os.remove(file_path)
                return None, actual_download_url
            except Exception as e:
                print(f"文件下载时发生一般错误: {e}")
                if os.path.exists(file_path): os.remove(file_path)
                return None, actual_download_url
        else:
            print("检索文件信息成功，但未找到下载链接。")
            return None, None
    else:
        err_msg = response_data.get("base_resp", {}).get("status_msg", "Unknown error")
        err_code = response_data.get("base_resp", {}).get("status_code", "N/A")
        print(f"获取文件信息失败 (Code: {err_code})，错误信息: {err_msg}")
        return None, None

def extract_and_rename(tar_path, extract_dir, new_dir_name):
    """
    解压 tar 文件，并将解压出的第一个目录重命名为 new_dir_name。
    """
    #print(f"准备解压文件: {tar_path} 到目录: {extract_dir}")
    try:
        with tarfile.open(tar_path, 'r') as tar_ref:
            tar_ref.extractall(path=extract_dir)
        #print(f"文件已解压到: {extract_dir}")
    except tarfile.ReadError as e_tar_read:
        print(f"解压失败: 不是有效的TAR文件或文件已损坏. {tar_path} - {e_tar_read}")
        return None
    except Exception as e:
        print(f"解压失败: {e}")
        if os.path.isdir(os.path.join(extract_dir, new_dir_name)):
             shutil.rmtree(os.path.join(extract_dir, new_dir_name), ignore_errors=True)
        return None

    extracted_top_level_items = [os.path.join(extract_dir, item) for item in os.listdir(extract_dir)]
    extracted_dirs = [d for d in extracted_top_level_items if os.path.isdir(d)]

    original_extracted_dirname = None
    if len(extracted_dirs) == 1:
        original_extracted_dirname = extracted_dirs[0]
        #print(f"找到解压后的主目录: {original_extracted_dirname}")
    elif len(extracted_dirs) > 1:
        print(f"警告: 解压后发现多个目录: {extracted_dirs}. 将尝试使用第一个。")
        original_extracted_dirname = extracted_dirs[0] 
    elif not extracted_dirs and any(os.path.isfile(item) for item in extracted_top_level_items):
        print(f"文件直接解压到 {extract_dir}，将使用此目录作为源。")
        original_extracted_dirname = extract_dir 
    else:
        print(f"解压后未在 {extract_dir} 中找到任何目录或文件。")
        return None

    renamed_path_target = os.path.join(os.path.dirname(original_extracted_dirname) if original_extracted_dirname != extract_dir else extract_dir, new_dir_name)
    
    renamed_path = None # Initialize renamed_path
    if original_extracted_dirname == renamed_path_target: 
        #print(f"解压内容已在目标位置/名称: {renamed_path_target}")
        renamed_path = renamed_path_target
    elif original_extracted_dirname == extract_dir and os.path.exists(renamed_path_target) and os.path.isdir(renamed_path_target):
        print(f"文件直接解压，将在 {extract_dir} 中查找 .titles 并创建SRT到 {new_dir_name} 子目录 (如果适用)。")
        renamed_path = extract_dir 
    else:
        if os.path.exists(renamed_path_target):
            print(f"目标路径 {renamed_path_target} 已存在。将尝试删除并替换。")
            try:
                shutil.rmtree(renamed_path_target)
            except Exception as e_rm:
                print(f"删除已存在的目标目录 {renamed_path_target} 失败: {e_rm}")
                return None 
        try:
            shutil.move(original_extracted_dirname, renamed_path_target)
            print(f"解压的目录 '{os.path.basename(original_extracted_dirname)}' 已移动/重命名为 '{new_dir_name}' 位于 '{renamed_path_target}'")
            renamed_path = renamed_path_target
        except Exception as e_mv:
            print(f"目录 {original_extracted_dirname} 移动/重命名为 {renamed_path_target} 失败: {e_mv}")
            return None
            
    try:
        os.remove(tar_path)
        #print(f"已删除原始压缩文件: {tar_path}")
    except Exception as e_rm_tar:
        print(f"删除压缩文件 {tar_path} 失败: {e_rm_tar}")

    return renamed_path


def convert_seconds_to_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000)) 
    if millis == 1000: 
        secs +=1
        millis = 0
        if secs == 60:
            minutes +=1
            secs = 0
            if minutes == 60:
                hours +=1
                minutes = 0
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def json_to_srt(json_data, srt_path):
    srt_output = []
    subtitle_id = 1
    
    if not isinstance(json_data, list):
        print(f"错误: .titles 文件内容不是预期的列表格式。内容: {json_data}")
        if isinstance(json_data, dict):
            for key in ['sentences', 'segments', 'subtitles', 'result_list', 'sentence_list']: 
                if key in json_data and isinstance(json_data[key], list):
                    print(f"找到列表在键 '{key}' 下。使用此列表。")
                    json_data = json_data[key]
                    break
            if not isinstance(json_data, list): 
                 print(f"无法从 .titles 的 JSON 结构中找到字幕列表。跳过 SRT 生成。")
                 return False 
        else: 
            print(f"无法处理 .titles 的 JSON 结构。跳过 SRT 生成。")
            return False


    for item in json_data:
        if not isinstance(item, dict):
            print(f"警告: 字幕条目不是字典格式: {item}。跳过此条目。")
            continue

        text = item.get("text")
        # API seems to use time_begin and time_end in milliseconds
        time_begin_ms = item.get("time_begin") 
        time_end_ms = item.get("time_end")

        if text is None or time_begin_ms is None or time_end_ms is None:
            # Check for alternative naming from some API versions (e.g. 'begin_time', 'end_time')
            if text is None: text = item.get("sentence") # another common name for text
            if time_begin_ms is None: time_begin_ms = item.get("begin_time")
            if time_end_ms is None: time_end_ms = item.get("end_time")

            if text is None or time_begin_ms is None or time_end_ms is None:
                print(f"警告: 字幕条目缺少 text/time_begin/time_end (或备用名): {item}。跳过此条目。")
                continue
        
        if not isinstance(time_begin_ms, (int, float)) or not isinstance(time_end_ms, (int, float)):
            print(f"警告: 时间值不是数字: begin={time_begin_ms}, end={time_end_ms}。跳过此条目。")
            continue

        if text.startswith("\ufeff"): 
            text = text[1:]
        
        start_time = convert_seconds_to_srt_time(time_begin_ms / 1000.0)
        end_time = convert_seconds_to_srt_time(time_end_ms / 1000.0)
        
        srt_output.append(str(subtitle_id))
        srt_output.append(f"{start_time} --> {end_time}")
        srt_output.append(text)
        srt_output.append("") 
        subtitle_id += 1

    if not srt_output:
        print("没有有效的字幕条目可写入 SRT 文件。")
        return False

    try:
        with open(srt_path, 'w', encoding='utf-8') as file:
            file.write("\n".join(srt_output))
        print(f"SRT 文件已保存：{srt_path}")
        return True
    except Exception as e:
        print(f"保存 SRT 文件失败: {e}")
        return False

def process_tar_to_srt(tar_path, temp_extract_base_dir, final_output_base_dir, txt_file_name_for_output_folder):
    """
    Extracts tar, generates SRT from .titles, and moves content to final directory.
    Returns the path to the final processed folder or None on failure.
    """
    extracted_content_path = extract_and_rename(tar_path, temp_extract_base_dir, txt_file_name_for_output_folder)

    if not extracted_content_path:
        print(f"解压或重命名失败 {tar_path}，无法处理 SRT 文件。清理临时目录: {temp_extract_base_dir}")
        if os.path.exists(temp_extract_base_dir):
            shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
        return None

    titles_file_path = None
    possible_titles_filenames = [
        f"{txt_file_name_for_output_folder}.titles", 
        "audio.titles", 
        "output.titles",
        "sentence_with_time.titles",
        "tts_detail.json" # Some APIs might use json extension with titles-like content
    ]
    # Search strategy:
    # 1. Exact match if extracted_content_path is a dir and contains one.
    # 2. Walk if not found at root of extracted_content_path.
    found_titles_in_root = False
    if os.path.isdir(extracted_content_path):
        for pf_name in possible_titles_filenames:
            potential_path = os.path.join(extracted_content_path, pf_name)
            if os.path.isfile(potential_path):
                titles_file_path = potential_path
                print(f"在解压目录根路径找到 .titles/.json 文件: {titles_file_path}")
                found_titles_in_root = True
                break
    
    if not found_titles_in_root:
        for root, _, files in os.walk(extracted_content_path):
            for file_name in files:
                if file_name.endswith((".titles", ".json")): # Broaden search
                     # Prioritize .titles if multiple matches, or specific names
                    is_possible_primary = any(fn_part in file_name for fn_part in ["titles", txt_file_name_for_output_folder, "audio", "output", "sentence"])
                    if titles_file_path and not is_possible_primary and file_name.endswith(".json"):
                        pass # Already found a .titles, prefer that over generic .json
                    else:
                        titles_file_path = os.path.join(root, file_name)
                        #print(f"在子目录中找到 .titles/.json 文件: {titles_file_path}")
                        # If it's a strong match, break early
                        if any(pf_name == file_name for pf_name in possible_titles_filenames):
                            break 
            if titles_file_path and any(pf_name == os.path.basename(titles_file_path) for pf_name in possible_titles_filenames):
                break # Broke from inner, break from outer

    srt_generated = False
    if not titles_file_path:
        print(f"在 {extracted_content_path} 及其子目录中未找到 .titles 或相关 .json 文件。将不生成 SRT 文件。")
    else:
        #print(f"尝试使用文件生成SRT: {titles_file_path}")
        try:
            with open(titles_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if content.startswith('\ufeff'):
                    content = content[len('\ufeff'):]
                json_data = json.loads(content)
                
            srt_filename = f"{txt_file_name_for_output_folder}.srt"
            # SRT should be placed inside the folder that will be moved/is the final content folder.
            # If extracted_content_path is "...\temp_base\output_name", srt goes in there.
            # If extracted_content_path is "...\temp_base" (loose files), srt goes in there too.
            srt_path_final = os.path.join(extracted_content_path, srt_filename) 
            
            if json_to_srt(json_data, srt_path_final):
                srt_generated = True
            else:
                print(f"JSON 到 SRT 转换失败 for {titles_file_path}。")

        except json.JSONDecodeError as e_json:
            print(f"读取或解析 {titles_file_path} 文件失败 (JSONDecodeError): {e_json}")
        except Exception as e:
            print(f"读取 {titles_file_path} 文件或生成 SRT 失败: {e}")

    final_target_dir_path = os.path.join(final_output_base_dir, txt_file_name_for_output_folder)
    #print(f"准备移动处理后的内容从 {extracted_content_path} 到 {final_target_dir_path}")

    if os.path.exists(final_target_dir_path):
        if final_target_dir_path == extracted_content_path: # Source is already the destination
            print(f"内容已在最终目标目录: {final_target_dir_path}。无需移动。")
        else:
            print(f"最终目标目录 {final_target_dir_path} 已存在。将尝试删除并覆盖...")
            try:
                shutil.rmtree(final_target_dir_path)
            except Exception as e_rm_final:
                print(f"删除已存在的最终目录 {final_target_dir_path} 失败: {e_rm_final}。跳过移动。")
                if os.path.exists(temp_extract_base_dir) and temp_extract_base_dir != extracted_content_path: # Clean containing temp
                    shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
                elif os.path.exists(extracted_content_path): # Clean specific extracted temp
                    shutil.rmtree(extracted_content_path, ignore_errors=True)
                return None 
    
    moved_successfully = False
    if final_target_dir_path == extracted_content_path:
        moved_successfully = True # Already there
    else:
        try:
            # If extracted_content_path is the temp_extract_base_dir itself (files were loose)
            # then we need to create final_target_dir_path and move items into it.
            if extracted_content_path == temp_extract_base_dir:
                os.makedirs(final_target_dir_path, exist_ok=True)
                items_to_move = os.listdir(extracted_content_path)
                if not items_to_move:
                     print(f"警告: 临时解压目录 {extracted_content_path} 为空，无法移动项目。")
                for item_name in items_to_move:
                    s_item = os.path.join(extracted_content_path, item_name)
                    d_item = os.path.join(final_target_dir_path, item_name)
                    if os.path.isdir(s_item):
                        shutil.move(s_item, d_item) # Move directory
                    else:
                        shutil.move(s_item, d_item) # Move file
                print(f"处理完成的松散文件已移动到新目录: {final_target_dir_path}")
                moved_successfully = True
            else: # Standard case: extracted_content_path is a subfolder, move it
                shutil.move(extracted_content_path, final_target_dir_path)
                #print(f"处理完成的文件夹已移动到: {final_target_dir_path}")
                moved_successfully = True
        except Exception as e_move:
            print(f"移动文件夹从 {extracted_content_path} 到 {final_target_dir_path} 失败: {e_move}")
            # Fallback cleanup
            if os.path.exists(temp_extract_base_dir) and temp_extract_base_dir != extracted_content_path:
                shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
            elif os.path.exists(extracted_content_path):
                shutil.rmtree(extracted_content_path, ignore_errors=True)
            return None

    # Cleanup the overall temporary base directory (temp_extract_base_dir)
    # This directory was like "output_dir/filename_temp_processing/"
    # If extracted_content_path was "output_dir/filename_temp_processing/filename" (after rename),
    # and that was moved, then "output_dir/filename_temp_processing/" should now be empty or gone.
    # If extracted_content_path was "output_dir/filename_temp_processing/" (loose files),
    # its contents were moved out.
    if moved_successfully and os.path.exists(temp_extract_base_dir):
        try:
            # Only remove if it's truly empty or if it was the direct source of moved items
            if temp_extract_base_dir == extracted_content_path and not os.listdir(temp_extract_base_dir):
                 os.rmdir(temp_extract_base_dir)
                 print(f"已清理空的临时解压目录: {temp_extract_base_dir}")
            elif temp_extract_base_dir != extracted_content_path : # It was a container for the moved extracted_content_path
                shutil.rmtree(temp_extract_base_dir, ignore_errors=True) # ignore_errors because extracted_content_path was inside and moved
                #print(f"已清理临时文件所在的基本目录: {temp_extract_base_dir}")
            elif not os.listdir(temp_extract_base_dir): # Was the source, now empty
                os.rmdir(temp_extract_base_dir)
                print(f"已清理空的临时解压目录 (原为松散文件): {temp_extract_base_dir}")

        except Exception as e_clean:
            print(f"清理临时文件所在的基本目录 {temp_extract_base_dir} 失败或目录不为空: {e_clean}")

    return final_target_dir_path


def process_txt_file(file_info, output_dir, api_key, group_id, model, task_num):
    """
    处理单个 TXT 文件的逻辑：上传文本文件，创建语音任务，下载并处理结果。
    """
    threading.current_thread().task_id = task_num 

    txt_path = file_info['path']
    voice_id = file_info['voice_id']
    voice_display_name = file_info.get('voice_display', voice_id)
    speed = file_info['speed']
    vol = file_info['vol']
    pitch = file_info['pitch']
    emotion_api_value = file_info.get('emotion', "default")
    emotion_display_name = file_info.get('emotion_display', "默认")

    txt_file_name_no_ext = os.path.splitext(os.path.basename(txt_path))[0]
    
    print(f"开始处理文件: {os.path.basename(txt_path)} (Voice: {voice_display_name}, Emotion: {emotion_display_name}, Speed: {speed}, Vol: {vol}, Pitch: {pitch})")

    text_file_id = upload_text_file(api_key, group_id, txt_path)
    if not text_file_id:
        print(f"文件 {txt_file_name_no_ext} 上传失败或未能获取 file_id，跳过。")
        return 

    #print(f"使用 file_id: {text_file_id} 为文件 {txt_file_name_no_ext} 创建语音任务...")
    task_id_created = create_speech_task(api_key, group_id, model, text_file_id=text_file_id,
                                         voice_id=voice_id, speed=speed, vol=vol, pitch=pitch, 
                                         emotion=emotion_api_value)
    if not task_id_created:
        print(f"文件 {txt_file_name_no_ext} 创建语音任务失败 (使用 file_id: {text_file_id})，跳过。")
        return

    #print(f"查询任务状态 Task ID: {task_id_created} for {txt_file_name_no_ext}...")
    retrieved_audio_file_id = get_task_status(api_key, group_id, task_id_created)
    if not retrieved_audio_file_id:
        print(f"文件 {txt_file_name_no_ext} (Task ID: {task_id_created}) 未能获取到生成的音频 file_id，跳过。")
        return

    temp_processing_dir_for_file = os.path.join(output_dir, f"{txt_file_name_no_ext}_temp_processing")
    if os.path.exists(temp_processing_dir_for_file):
        shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True)
    try:
        os.makedirs(temp_processing_dir_for_file, exist_ok=True)
    except Exception as e_mkdir:
        print(f"创建临时目录 {temp_processing_dir_for_file} 失败: {e_mkdir}，跳过。")
        return

    #print(f"下载音频 TAR 文件 (Audio File ID: {retrieved_audio_file_id}) for {txt_file_name_no_ext}...")
    downloaded_tar_path, audio_tar_download_url = download_file(
        api_key, group_id, retrieved_audio_file_id, 
        temp_processing_dir_for_file, 
        txt_file_name_no_ext
    )

    if not downloaded_tar_path:
        print(f"文件 {txt_file_name_no_ext} 下载 TAR 包失败。")
        if audio_tar_download_url:
             log_queue.put(f"文件 {txt_file_name_no_ext} 的 TAR 下载链接为: {audio_tar_download_url} 但下载失败。\n")
        if os.path.exists(temp_processing_dir_for_file): 
            shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True)
        return

    if audio_tar_download_url:
        success_data = {
            "文件名": txt_file_name_no_ext,
            "音色": voice_display_name, "音色ID": voice_id,
            "语速": speed, "音量": vol, "音调": pitch,
            "情绪": emotion_display_name, "情绪(API)": emotion_api_value,
            "模型": model,
            "原始文本路径": txt_path, 
            "上传文本后的FileID": text_file_id, 
            "音频下载链接(tar)": audio_tar_download_url, 
            "生成时间": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_success_record(success_data)

    #print(f"处理 TAR 文件并生成 SRT for {txt_file_name_no_ext}...")
    final_folder_path = process_tar_to_srt(
        downloaded_tar_path,
        temp_processing_dir_for_file, 
        output_dir,                   
        txt_file_name_no_ext          
    )

    if final_folder_path:
        print(f"文件 {txt_file_name_no_ext} 处理完成。输出位于: {final_folder_path}")
    else:
        print(f"文件 {txt_file_name_no_ext} 处理过程中发生错误，未能生成最终输出。TAR包可能位于 {temp_processing_dir_for_file} (如果下载成功)。")

    try:
        delattr(threading.current_thread(), "task_id")
    except AttributeError:
        pass 
    except Exception as e_del_attr:
        print(f"清理线程任务ID时出错: {e_del_attr}")
    
    print(f"文件 {os.path.basename(txt_path)} 的处理流程结束。")


def process_list_of_txt_files(files_and_settings_list, output_dir, group_id, api_key, model, max_workers):
    """
    多线程方式处理提供的 TXT 文件列表及它们各自的设置。
    """
    if not files_and_settings_list:
        print("未提供TXT文件进行处理。")
        return

    #print(f"准备处理 {len(files_and_settings_list)} 个TXT文件。输出将保存到目录: {output_dir}")
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"已创建输出目录: {output_dir}")
        except Exception as e:
            print(f"创建输出目录 {output_dir} 失败: {e}。请检查权限或路径。")
            return

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="TTSWorker") as executor:
        futures = {}
        for i, file_info_dict in enumerate(files_and_settings_list, start=1):
            future = executor.submit(
                process_txt_file,
                file_info_dict, 
                output_dir,
                api_key,
                group_id,
                model,
                i 
            )
            futures[future] = os.path.basename(file_info_dict['path'])

        for future in futures: 
            task_file_basename = futures[future]
            try:
                future.result() 
            except Exception as e:
                print(f"处理文件 {task_file_basename} 时线程池捕获到意外顶层错误: {e}")

    log_queue.put(f"所有 {len(files_and_settings_list)} 个选定文件的处理尝试已完成。\n")
    print(f"所有 {len(files_and_settings_list)} 个选定文件的处理尝试已完成。")
