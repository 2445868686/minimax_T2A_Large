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
    url = f"https://api.minimax.chat/v1/t2a_async_v2?GroupId={group_id}"
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
    url = f"https://api.minimax.chat/v1/query/t2a_async_query_v2?GroupId={group_id}&task_id={task_id}"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    max_retries = 100 #查询任务状态次数，5秒一次
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
    url = f'https://api.minimax.chat/v1/files/retrieve?GroupId={group_id}&file_id={file_id}'
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
        file_name = f"{txt_file_name}.tar" # Use the original TXT file name for the tar
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
            # Log contents before extracting
            # print(f"Tar file contents for {tar_path}: {tar_ref.getnames()}")
            tar_ref.extractall(extract_dir)
    except Exception as e:
        print(f"解压失败: {e}")
        # Attempt to clean up partially extracted directory if it exists
        if os.path.isdir(os.path.join(extract_dir, new_dir_name)): # if rename happened before error
             shutil.rmtree(os.path.join(extract_dir, new_dir_name), ignore_errors=True)
        return None
    print(f"文件已解压到: {extract_dir}")

    extracted_items = os.listdir(extract_dir)
    # Filter out the tar file itself if it was extracted into the same directory (should not happen with extractall)
    extracted_dirs_or_files = [item for item in extracted_items if item != os.path.basename(tar_path)]

    if not extracted_dirs_or_files:
        print(f"解压后未在 {extract_dir} 中找到任何文件或目录。")
        return None

    # Expecting a single directory inside, or files directly
    # The API usually puts content in a directory named by task_id or similar
    # We are trying to rename the *first found directory* to new_dir_name.
    # If no directory, but files are present, this logic might need adjustment.
    # For now, assume the API creates a single top-level directory inside the tar.
    
    renamed_path = None
    for item in extracted_dirs_or_files:
        item_path = os.path.join(extract_dir, item)
        if os.path.isdir(item_path):
            # This is the directory we want to rename
            new_path_target = os.path.join(extract_dir, new_dir_name)
            # Check if target new_dir_name already exists (e.g. from a previous failed attempt)
            if os.path.exists(new_path_target):
                print(f"目标目录 {new_path_target} 已存在，将尝试删除后重命名。")
                try:
                    shutil.rmtree(new_path_target)
                except Exception as e_rm:
                    print(f"删除已存在的目标目录 {new_path_target} 失败: {e_rm}")
                    # Potentially return None or raise error, depending on desired robustness
                    # For now, we'll let the os.rename fail if this occurs and isn't handled
            
            try:
                os.rename(item_path, new_path_target)
                renamed_path = new_path_target
                print(f"解压出的目录 '{item}' 已重命名为 '{new_dir_name}' 位于 '{new_path_target}'")
                break 
            except Exception as e:
                print(f"目录 {item_path} 重命名为 {new_path_target} 失败: {e}")
                return None
    
    if not renamed_path: # No directory was found and renamed
        # This could happen if the tar extracts files directly without a containing folder
        # Or if multiple folders are extracted.
        # For this application, we expect one folder to rename.
        print(f"解压后未找到可重命名的单一目录。检查 {extract_dir} 内容: {extracted_dirs_or_files}")
        # If files were extracted directly, we might want to create new_dir_name and move them
        # For now, stick to the expectation of renaming one directory.
        return None


    # Delete the original tar file
    try:
        os.remove(tar_path)
        print(f"已删除原始压缩文件: {tar_path}")
    except Exception as e:
        print(f"删除压缩文件失败: {e}")
    
    return renamed_path # Return the path of the renamed directory


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

def process_tar_to_srt(tar_path, temp_extract_base_dir, final_output_base_dir, txt_file_name_for_output_folder):
    """
    解压 tar 文件并转换生成 SRT 文件。
    - 解压至 temp_extract_base_dir/<txt_file_name_for_output_folder>_temp_extracted
    - 将解压后的第一个目录重命名为 txt_file_name_for_output_folder (within the temp_extract_base_dir)
    - 查找 .titles 文件转换为 SRT
    - 最后将重命名后的文件夹移动到 final_output_base_dir/<txt_file_name_for_output_folder>，并删除整个 temp_extract_base_dir
    """
    # Create a specific temporary directory for this file's extraction to avoid conflicts
    # e.g., output_dir/file1_temp/file1_extracted_content/
    # The tar itself is downloaded into output_dir/file1_temp/file1.tar
    # extract_and_rename expects tar_path and an extract_dir.
    # Let temp_extract_base_dir be where the .tar is (e.g. output_dir/txt_file_name_temp)
    # And extract_dir for extract_and_rename be this same temp_extract_base_dir.

    # The renamed folder will be at temp_extract_base_dir/txt_file_name_for_output_folder
    renamed_extracted_content_dir = extract_and_rename(tar_path, temp_extract_base_dir, txt_file_name_for_output_folder)
    
    if not renamed_extracted_content_dir:
        print(f"解压或重命名失败 {tar_path}，无法处理 SRT 文件")
        # Clean up the temp_extract_base_dir if extraction failed midway
        if os.path.exists(temp_extract_base_dir):
            shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
        return None

    # Now renamed_extracted_content_dir is like: .../txt_file_name_temp/txt_file_name
    # Find .titles file within this renamed directory
    titles_file = None
    for root, _, files in os.walk(renamed_extracted_content_dir):
        for file in files:
            if file.endswith(".titles"):
                titles_file = os.path.join(root, file)
                break
        if titles_file:
            break

    if not titles_file:
        print(f"在 {renamed_extracted_content_dir} 中未找到 .titles 文件")
    else:
        try:
            with open(titles_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            # Save SRT in the same renamed_extracted_content_dir
            srt_path = os.path.join(renamed_extracted_content_dir, f"{txt_file_name_for_output_folder}.srt")
            json_to_srt(json_data, srt_path)
        except Exception as e:
            print(f"读取 .titles 文件或生成SRT失败: {e}")

    # Move the processed folder (renamed_extracted_content_dir) to its final destination
    # Final destination: final_output_base_dir/txt_file_name_for_output_folder
    final_target_dir_path = os.path.join(final_output_base_dir, txt_file_name_for_output_folder)

    # Handle cases where the final target directory might already exist (e.g., from a re-run)
    if os.path.exists(final_target_dir_path):
        print(f"最终目标目录 {final_target_dir_path} 已存在。正在尝试覆盖...")
        try:
            shutil.rmtree(final_target_dir_path) # Remove existing to avoid move issues
        except Exception as e_rm_final:
            print(f"删除已存在的最终目录 {final_target_dir_path} 失败: {e_rm_final}。跳过移动。")
            # Clean up temp_extract_base_dir and return
            if os.path.exists(temp_extract_base_dir):
                shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
            return None # Indicate failure

    try:
        shutil.move(renamed_extracted_content_dir, final_target_dir_path)
        print(f"处理完成的文件夹已移动到: {final_target_dir_path}")
    except Exception as e_move:
        print(f"移动文件夹 {renamed_extracted_content_dir} 到 {final_target_dir_path} 失败: {e_move}")
        # Clean up temp_extract_base_dir and return
        if os.path.exists(temp_extract_base_dir):
             shutil.rmtree(temp_extract_base_dir, ignore_errors=True)
        return None # Indicate failure

    # Clean up the parent temporary directory (e.g., output_dir/txt_file_name_temp)
    # This directory originally contained the .tar and the renamed_extracted_content_dir before it was moved.
    if os.path.exists(temp_extract_base_dir):
        try:
            shutil.rmtree(temp_extract_base_dir)
            print(f"已清理临时文件夹: {temp_extract_base_dir}")
        except Exception as e_clean:
            print(f"清理临时文件夹 {temp_extract_base_dir} 失败: {e_clean}")
            
    return final_target_dir_path


def process_txt_file(txt_path, output_dir, api_key, group_id, model, voice_id, speed, vol, pitch, task_num):
    """
    处理单个 TXT 文件的逻辑：
    1. 读取文本
    2. 创建异步语音任务
    3. 查询任务状态
    4. 下载 tar 文件并解压
    5. 生成 SRT
    output_dir is the main directory where all final processed folders will be created.
    A temporary sub-directory will be created inside output_dir for each TXT file.
    """
    threading.current_thread().task_id = task_num

    txt_file_name_no_ext = os.path.splitext(os.path.basename(txt_path))[0]
    print(f"任务[{task_num}] 开始处理文件: {txt_path}")
    text = read_text_from_file(txt_path)
    if not text:
        print(f"任务[{task_num}] 无法读取文本文件: {txt_path}，跳过。")
        return

    task_id_created = create_speech_task(api_key, group_id, model, text=text, 
                                         voice_id=voice_id, speed=speed, vol=vol, pitch=pitch)
    if not task_id_created:
        print(f"任务[{task_num}] 文件 {txt_file_name_no_ext} 创建任务失败，跳过。")
        return

    file_id = get_task_status(api_key, group_id, task_id_created)
    if not file_id:
        print(f"任务[{task_num}] 文件 {txt_file_name_no_ext} 未获取到 file_id，跳过。")
        return

    # Create a specific temporary directory for this file's processing, inside the main output_dir
    # e.g. output_dir/MyTextFile_temp/
    # The tar file will be downloaded here.
    # The extraction will happen within this temp_processing_dir.
    # The final processed folder will be output_dir/MyTextFile/
    temp_processing_dir_for_file = os.path.join(output_dir, f"{txt_file_name_no_ext}_temp_processing_files")
    if os.path.exists(temp_processing_dir_for_file):
        shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True) # Clean up from previous runs
    try:
        os.makedirs(temp_processing_dir_for_file, exist_ok=True)
    except Exception as e:
        print(f"任务[{task_num}] 创建临时目录 {temp_processing_dir_for_file} 失败: {e}，跳过。")
        return


    # Download tar to this specific temp directory
    # txt_file_name_no_ext is used for naming the downloaded .tar file
    downloaded_tar_path = download_file(api_key, group_id, file_id, temp_processing_dir_for_file, txt_file_name_no_ext)
    if not downloaded_tar_path:
        print(f"任务[{task_num}] 文件 {txt_file_name_no_ext} 下载 tar 失败，跳过。")
        if os.path.exists(temp_processing_dir_for_file): # Clean up
            shutil.rmtree(temp_processing_dir_for_file, ignore_errors=True)
        return

    # Process tar: extract, rename, convert to SRT, move to final location, and clean up temp_processing_dir_for_file
    # temp_processing_dir_for_file is where tar is, and where extraction initially happens.
    # output_dir is the base for final processed folders.
    # txt_file_name_no_ext is used for the name of the final output folder.
    final_folder_path = process_tar_to_srt(downloaded_tar_path, 
                                           temp_processing_dir_for_file, 
                                           output_dir, 
                                           txt_file_name_no_ext)
    
    if final_folder_path:
        print(f"任务[{task_num}] 文件 {txt_file_name_no_ext} 处理完成。输出位于: {final_folder_path}")
    else:
        print(f"任务[{task_num}] 文件 {txt_file_name_no_ext} 处理过程中发生错误，未能生成最终输出。")
        # temp_processing_dir_for_file should have been cleaned by process_tar_to_srt on failure

    try:
        delattr(threading.current_thread(), "task_id")
    except AttributeError: # Can happen if already deleted or never set
        pass
    except Exception as e: # Catch any other deletion error
        print(f"任务[{task_num}] 清理线程任务ID时出错: {e}")


def process_list_of_txt_files(txt_file_paths, output_dir, group_id, api_key, model,
                               max_workers, speed, vol, pitch, voice_id):
    """
    多线程方式处理提供的 TXT 文件列表。
    txt_file_paths: 包含待处理TXT文件完整路径的列表。
    output_dir: 所有处理结果的总输出目录。
    """
    if not txt_file_paths:
        print("未提供TXT文件进行处理。")
        return

    print(f"准备处理 {len(txt_file_paths)} 个TXT文件。输出将保存到目录: {output_dir}")
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"已创建输出目录: {output_dir}")
        except Exception as e:
            print(f"创建输出目录 {output_dir} 失败: {e}。请检查权限或路径。")
            return
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, txt_full_path in enumerate(txt_file_paths, start=1):
            future = executor.submit(
                process_txt_file, 
                txt_full_path,         # Full path to the TXT file
                output_dir,            # Main output directory
                api_key, 
                group_id, 
                model, 
                voice_id, 
                speed, 
                vol, 
                pitch, 
                i                      # Task number for logging
            )
            futures[future] = os.path.basename(txt_full_path) # Store basename for error reporting

        for future in futures:
            task_file_basename = futures[future]
            try:
                future.result() # Wait for task to complete and retrieve result (or raise exception)
            except Exception as e:
                # The error should ideally be caught and logged within process_txt_file
                # This is a fallback for unexpected errors from the future itself
                print(f"处理文件 {task_file_basename} 时线程池捕获到错误: {e}")

    print(f"所有 {len(txt_file_paths)} 个选定文件的处理尝试已完成。")
