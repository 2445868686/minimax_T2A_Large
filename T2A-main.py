import requests
import json
import time
import os
import tarfile
import shutil
import concurrent.futures

def read_text_from_file(file_path):
    """
    从txt文件中读取文本内容。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"读取文件失败: {e}")
        return None

def get_task_status(api_key, group_id, task_id):
    """
    查询语音生成任务状态，直到任务完成并返回file_id。
    """
    url = f"https://api.minimaxi.chat/v1/query/t2a_async_query_v2?GroupId={group_id}&task_id={task_id}"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    max_retries = 100
    retry_count = 0
    
    while retry_count < max_retries:
        response = requests.get(url, headers=headers)
        response_data = response.json()
        
        if response_data.get("base_resp", {}).get("status_code") == 0:
            status = response_data.get("status")
            file_id = response_data.get("file_id")
            
            if status == "Success":
                print(f"任务已完成，file_id: {file_id}")
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
    """
    创建语音生成异步任务，并返回 task_id。
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

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    response_data = response.json()

    if response_data.get("base_resp", {}).get("status_code") == 0:
        task_id = response_data.get("task_id")
        print(f"任务创建成功，task_id: {task_id}")
        return task_id
    else:
        print(f"任务创建失败，错误信息: {response_data.get('base_resp', {}).get('status_msg')}")
        return None

def download_file(api_key, group_id, file_id, save_dir, txt_file_name):
    """
    通过 file_id 下载文件。
    """
    url = f'https://api.minimaxi.chat/v1/files/retrieve?GroupId={group_id}&file_id={file_id}'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    response = requests.get(url, headers=headers)
    response_data = response.json()

    if response_data.get("base_resp", {}).get("status_code") == 0:
        file_info = response_data.get("file", {})
        download_url = file_info.get("download_url")
        file_name = f"{txt_file_name}.tar"

        if download_url:
            print(f"文件下载链接: {download_url}")

            if not os.path.exists(save_dir):
                os.makedirs(save_dir)

            file_path = os.path.join(save_dir, file_name)
            file_response = requests.get(download_url, stream=True)

            with open(file_path, 'wb') as f:
                for chunk in file_response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)

            print(f"文件已成功下载到 {file_path}")
            return file_path
        else:
            print("未找到下载链接。")
            return None
    else:
        print(f"获取文件信息失败，错误信息: {response_data.get('base_resp', {}).get('status_msg')}")
        return None

def extract_and_rename(tar_path, extract_to, new_dir_name):
    """
    解压 tar 文件并重命名第一个目录，同时删除 tar 压缩文件。
    """
    if not os.path.exists(extract_to):
        os.makedirs(extract_to)
    
    with tarfile.open(tar_path, 'r') as tar_ref:
        tar_ref.extractall(extract_to)

    print(f"文件已解压到: {extract_to}")

    for item in os.listdir(extract_to):
        item_path = os.path.join(extract_to, item)
        if os.path.isdir(item_path):
            new_path = os.path.join(extract_to, new_dir_name)
            os.rename(item_path, new_path)
            print(f"目录已重命名为: {new_path}")
            break
    else:
        print("未找到需要重命名的目录。")
        return None

    if os.path.exists(tar_path):
        os.remove(tar_path)
        print(f"已删除压缩文件: {tar_path}")
    else:
        print("未找到压缩文件，无法删除。")

    return new_path

def convert_seconds_to_srt_time(seconds):
    """
    将秒数转换为SRT格式的时间（小时:分钟:秒,毫秒）。
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def json_to_srt(json_data, srt_path):
    """
    将 JSON 数据转换为 SRT 格式，并保存到指定文件。
    """
    srt_output = []
    subtitle_id = 1

    for item in json_data:
        text = item["text"]
        # 去除 BOM
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

def process_tar_to_srt(tar_path, output_dir, txt_file_name):
    """
    解压 tar 文件并处理生成 SRT 文件。
    """
    extracted_dir = extract_and_rename(tar_path, output_dir, txt_file_name)
    if not extracted_dir:
        print("解压失败，无法处理 SRT 文件")
        return

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
        return

    with open(titles_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    srt_path = os.path.join(extracted_dir, f"{txt_file_name}.srt")
    json_to_srt(json_data, srt_path)

def process_txt_file(txt_path, api_key, group_id, model, output_dir):
    """
    对单个 txt 文件进行完整的处理，包括：
    1. 读取文本
    2. 创建语音生成任务
    3. 获取文件ID
    4. 下载并解压
    5. 转换成 SRT 文件
    """
    txt_file_name = os.path.splitext(os.path.basename(txt_path))[0]
    text = read_text_from_file(txt_path)

    if not text:
        print(f"无法读取文本文件: {txt_path}")
        return

    task_id = create_speech_task(api_key, group_id, model, text=text)
    if not task_id:
        print(f"文件 {txt_path} 创建任务失败，跳过。")
        return

    file_id = get_task_status(api_key, group_id, task_id)
    if not file_id:
        print(f"文件 {txt_path} 未获取到 file_id，跳过。")
        return

    tar_file_path = download_file(api_key, group_id, file_id, output_dir, txt_file_name)
    if not tar_file_path:
        print(f"文件 {txt_path} 下载 tar 失败，跳过。")
        return

    process_tar_to_srt(tar_file_path, output_dir, txt_file_name)
    print(f"文件 {txt_path} 处理完成。")

def main():
    # 配置参数（根据实际情况进行修改）
    base_dir = "C:\\Users\\heiba\\Downloads\\text"  # 要遍历的txt文件夹路径
    group_id = "1879521961881637056"
    api_key = ("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJHcm91cE5hbWUiOiJCQSBIRUkiLCJVc2VyTmFtZSI6IkJBIEhFSSIsIkFjY291bnQiOiIiLCJTdWJqZWN0SUQiOiIxODc5NTIxOTYxODg1ODMxMzYwIiwiUGhvbmUiOiIiLCJHcm91cElEIjoiMTg3OTUyMTk2MTg4MTYzNzA1NiIsIlBhZ2VOYW1lIjoiIiwiTWFpbCI6ImhlaWJhZ291QGhvdG1haWwuY29tIiwiQ3JlYXRlVGltZSI6IjIwMjUtMDEtMTcgMjI6MDM6MjkiLCJUb2tlblR5cGUiOjEsImlzcyI6Im1pbmltYXgifQ.mAgSKTx9E93IXX4SAAual-Pb3pwwIox2cjBS67pb9r3d0g_f0r-BYNzQIbu5r2vKqbREYa2khiPL1uH8U4DUwWg43i0Sj9DpVOum12NiPESx0GyZUV2sFyJ8apl_h2qqDOTj0LVJVb2gmq4uz6aF_ILjKPiOM3RSkZqqIKYlvy35Sw7WCeyNqiJ0rXoCGM_oG5L4tfIeU1eVnnP5o5nQ4-2Ngqww1idiMjHDH1pSPPbOnO8ixPSQONwUbgjfLxdDTGNmIUvVmJmHxh4OQGvDSex3TJkgs8pGqQG0ch_DGaAkRrmnPsBZsZXk4PeJEiS6IdCe2u7cqlzDgg92mWa5qg")
    model = "speech-01-turbo"
    
    # 输出目录（可以和base_dir相同，或自行指定）
    output_dir = base_dir

    # 找到所有 .txt 文件
    txt_files = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.endswith(".txt")]

    # 使用多线程进行处理
    max_workers = 5  # 线程数量，可根据需要调整
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务到线程池
        futures = {
            executor.submit(process_txt_file, txt_file, api_key, group_id, model, output_dir): txt_file
            for txt_file in txt_files
        }
        
        # 等待所有任务完成并处理结果
        for future in concurrent.futures.as_completed(futures):
            txt_file = futures[future]
            try:
                future.result()  # 获取执行结果，若抛异常则在此触发
            except Exception as e:
                print(f"处理文件 {txt_file} 时发生错误: {e}")

if __name__ == "__main__":
    main()
