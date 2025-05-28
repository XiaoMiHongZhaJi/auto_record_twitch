import os
import sys
import time
import requests
import json
from datetime import datetime, timedelta
import subprocess
import platform
import shutil
import logging
import psutil

# vps名称
VPS_NAME = 'my_vps'

# 文件名中的主播名字
CHANNEL_NAME = 'et'

# 主播id
CHANNEL_ID = 'et_1231'
# CHANNEL_ID = 'jinnytty'

# 录制文件的路径
FILE_PATH = '/mnt/twitch/et/'

# 完整 twitch URL
URL = 'https://www.twitch.tv/' + CHANNEL_ID

# 代理地址，多个地址使用 , 隔开
PROXY = [
    '',
    'http://127.0.0.1:7890'
]

# 检测开播间隔（秒）
DEFAULT_TIMEOUT = 30

# 分割长度（分钟）
SEGMENT = 60

# 报错提示最短间隔（分钟）
REPEAT_NOTICE = 5

# 通知 URL
NOTIFICATION_URL = 'https://message.chenyifaer.shop/xxxxx/'

# 最小剩余磁盘空间 1GB
MIN_SPACE = 1 * 1024 * 1024 * 1024

# 直播结束后，是否合并上传录像到 YouTube
# 使用 https://github.com/porjo/youtubeuploader/releases
AUTO_MERGE_UPLOAD = True

# 启动时是否检测已有录像并上传
INIT_UPLOAD = True

# 直播结束后，合并文件的延迟时间（检测开播次数）
MERGE_DELAY = 50

proxy = ''
proxy_index = 0
err_count = 0
last_notice_time = None
env = os.environ.copy()
env["HOME"] = "/root"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# 创建一个输出到控制台的handler
console_handler = logging.StreamHandler(sys.stdout)
# 创建一个格式化器
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
# 将格式化器添加到handler
console_handler.setFormatter(formatter)
# 将handler添加到logger
logger.addHandler(console_handler)


# 检查主播是否开播
def check_stream_live():
    global proxy_index, proxy, last_notice_time, err_count
    check_url = 'https://gql.twitch.tv/gql'
    if PROXY is not None:
        if len(PROXY) <= proxy_index:
            proxy_index = 0
        proxy = PROXY[proxy_index]
    proxies = {
        'http': proxy,
        'https': proxy,
    }
    headers = {
        'client-id': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
        'content-type': 'text/plain;charset=UTF-8'
    }
    query = [{
        "operationName": "UseLive",
        "extensions": {
            "persistedQuery": {
                "sha256Hash": "639d5f11bfb8bf3053b424d9ef650d04c4ebb7d94711d644afb08fe9a0fad5d9",
                "version": 1
            }
        },
        "variables": {
            "channelLogin": CHANNEL_ID
        }
    }]

    try:
        response = requests.post(timeout=3, url=check_url, proxies=proxies, headers=headers, data=json.dumps(query))
        response.raise_for_status()
        data = response.json()
        user = data[0]['data']['user']
        logger.info(f"检测 {CHANNEL_NAME} 直播状态，代理地址[{proxy_index}]：{proxy}，返回内容：{user}")
        if user is None:
            err_count = err_count + 1
            err_msg = f"{VPS_NAME} 检测 {CHANNEL_NAME} 直播状态出错\nCHANNEL_ID：{CHANNEL_ID} 可能不存在"
            logger.error(err_msg)
            send_notification("网络错误", err_msg)
            return None
        return user['stream'] is not None

    except Exception as e:
        err_count = err_count + 1
        err_msg = f"{VPS_NAME} 检测开播状态出错[{err_count}]\n代理地址[{proxy_index}]：{proxy}\n{e}"
        logger.error(err_msg)
        if err_count >= 3:
            if last_notice_time is None or (datetime.now() - last_notice_time).total_seconds() > REPEAT_NOTICE * 60:
                send_notification("网络错误", err_msg)
                last_notice_time = datetime.now()
                err_count = 0
            proxy_index = proxy_index + 1

    return None


# 获取磁盘可用空间，单位B
def get_disk_space():
    if platform.system() == 'Windows':
        # Windows 系统
        total, used, free = shutil.disk_usage("/")
    else:
        # Linux 系统
        stat = os.statvfs("/")
        free = stat.f_bfree * stat.f_frsize
    return free


# 计算可录制时间
def calculate_recording_time_gb(gb):
    mb_per_second = 1  # 直播码率8Mbps => 1MB/s
    seconds = gb * 1024  # GB to MB
    total_seconds = seconds / mb_per_second
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    return hours, minutes


# 发送通知
def send_notification(title, message):
    requests.get(NOTIFICATION_URL + title + "/" + message)


# 定义初始磁盘空间检查函数
def check_initial_disk_space():
    while True:
        # 获取磁盘剩余空间
        free = get_disk_space()

        if free > MIN_SPACE:
            return True

        # 如果剩余空间小于指定的最小值，等待一定时间后重试
        err_msg = f"{VPS_NAME} 剩余空间不足\n剩余 {free // (1024 * 1024)} MB\n10 分钟后重试"
        logger.error(err_msg)
        send_notification("空间不足", err_msg)
        time.sleep(10 * 60)  # 休眠10分钟


# 录制直播
def record_stream():
    filename = f'{datetime.now().strftime("%m-%d")}_{datetime.now().strftime("%H-%M-%S")}_{CHANNEL_NAME}'
    start_time = datetime.now()

    if proxy is None or proxy == '':
        proxy_text = ''
    else:
        proxy_text = '--proxy ' + proxy

    yt_dlp_command = f'yt-dlp {proxy_text} {URL} -o - | ffmpeg -i pipe:0 -c copy -f segment -segment_time {SEGMENT * 60} -reset_timestamps 1 {FILE_PATH}{filename}_%02d.mp4'

    process = subprocess.Popen(yt_dlp_command, shell=True)

    process.wait()  # 等待录制结束

    end_time = datetime.now()
    duration = end_time - start_time
    return duration


# 主函数
def main():
    global proxy_index, err_count, last_notice_time
    # 检查文件夹是否存在，如果不存在则创建
    if not os.path.exists(FILE_PATH):
        os.makedirs(FILE_PATH)
    # 检测开播间隔时间
    timeout = DEFAULT_TIMEOUT
    # 是否上传已有文件
    if INIT_UPLOAD:
        merge_delay = 0
    else:
        merge_delay = -1
    # 检查初始磁盘空间
    while check_initial_disk_space():
        live_status = check_stream_live()
        if live_status:

            disk_space_gb = get_disk_space() / (1024 ** 3)
            hours, minutes = calculate_recording_time_gb(disk_space_gb)
            notification_message = f"{URL}\n{VPS_NAME}_{CHANNEL_NAME} 已开播\n剩余空间 {disk_space_gb:.2f} GB\n预计可录制 {hours} : {minutes}\n代理地址[{proxy_index}]：{proxy}"
            logger.info(notification_message)
            if last_notice_time is None or (datetime.now() - last_notice_time).total_seconds() > REPEAT_NOTICE * 60:
                send_notification("开播通知", notification_message)
                last_notice_time = datetime.now()
            merge_delay = MERGE_DELAY

            # 开始录制
            duration = record_stream()

            # 结束录制
            total_seconds = duration.total_seconds()
            logger.info(f"{CHANNEL_NAME} 直播时长 {int(total_seconds)} 秒，代理地址[{proxy_index}]：{proxy}")

            if total_seconds > 30:
                duration_hours = int(total_seconds // 3600)
                duration_minutes = int((total_seconds % 3600) // 60)
                duration_seconds = int((total_seconds % 3600) % 60)

                end_message = f"{VPS_NAME}_{CHANNEL_NAME} 直播已结束\n时长 {duration_hours} : {duration_minutes} : {duration_seconds}\n代理地址[{proxy_index}]：{proxy}"
                logger.info(end_message)
                send_notification("直播结束", end_message)
                timeout = 0
                err_count = 0
            else:
                err_count = err_count + 1
                err_msg = f"{VPS_NAME}_{CHANNEL_NAME} 直播时长 {int(total_seconds)} 秒\n可能是网络错误[{err_count}]\n代理地址[{proxy_index}]：{proxy}，尝试切换代理"
                logger.error(err_msg)
                timeout += 5
                if err_count >= 3:
                    proxy_index = proxy_index + 1
                    send_notification("网络错误", err_msg)
                    err_count = 0

        elif live_status is False:
            err_count = 0
            if merge_delay > 0:
                merge_delay = merge_delay - 1
                logger.info(f"即将合并并上传录像，merge_delay: {merge_delay}")
            elif merge_delay == 0:
                merge_delay = -1
                # 合并视频并上传
                if AUTO_MERGE_UPLOAD:
                    merge_and_upload()

        if timeout < DEFAULT_TIMEOUT:
            timeout += 2

        time.sleep(timeout)


# 配置文件路径
YOUTUBE_UPLOADER_PATH = '/mnt/twitch/auto/'


# 删除旧的文件
def cleanup_old_files(files):
    if len(files) > 22:
        send_notification("录像上传失败", f"录像文件过多，请手动处理")
        return False
    delete_filenames = ""
    for file in files:
        old_file_path = os.path.join(FILE_PATH, file)
        if os.path.isfile(old_file_path):
            if file.find("_uploaded") > -1:
                os.remove(old_file_path)
                logging.info(f"已删除上传过的文件: {file}")
                delete_filenames = delete_filenames + "\n" + file
    if delete_filenames != "":
        send_notification("录像上传", f"已删除上传过的文件：{delete_filenames}")
    return True


# 检查磁盘空间
def check_disk_space(files):
    total_size = sum(os.path.getsize(os.path.join(FILE_PATH, f)) for f in files)
    disk_usage = shutil.disk_usage(FILE_PATH)
    if disk_usage.free < total_size:
        logging.error("空间不足，无法合并文件")
        send_notification("录像上传失败", "空间不足，无法合并文件，剩余(MB)：" + str(disk_usage.free / 1024 / 1024))
        return False
    return True


# 执行FFmpeg命令来去除广告
def remove_ads(file_path):
    output_file = file_path.replace('_00.mp4', '_00_cut.mp4')
    command = ["ffmpeg", '-i', file_path, '-c', 'copy', '-ss', '15', output_file]
    try:
        subprocess.run(command, check=True)
        os.remove(file_path)
        logging.info(f"去除广告成功: {file_path}")
        return output_file  # 返回去广告后的文件路径
    except subprocess.CalledProcessError:
        logging.error(f"去除广告失败: {file_path}")
        send_notification("录像上传失败", "去除广告失败: " + file_path)
        return None


# 合并视频文件
def merge_files(files, title):
    output_filename = title + ".mp4"
    # 如果合并文件已经存在，直接跳过
    output_filepath = os.path.join(FILE_PATH, output_filename)
    if os.path.exists(output_filepath):
        logging.info(f"合并后的文件已存在: {output_filename}, 跳过合并")
        send_notification("录像上传失败", "合并后的文件已存在：\n" + output_filename)
        return None

    # 创建一个临时的文本文件列表
    list_file = os.path.join(FILE_PATH, 'file_list.txt')
    with open(list_file, 'w') as f:
        for file in files:
            f.write(f"file '{os.path.join(FILE_PATH, file)}'\n")

    command = ["ffmpeg", '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', output_filepath]

    try:
        subprocess.run(command, check=True)
        for file in files:
            os.remove(os.path.join(FILE_PATH, file))
        os.remove(list_file)  # 删除临时的列表文件
        logging.info(f"录像已合并，输出文件: {output_filename}")
        send_notification("录像上传", "录像已合并，输出文件：\n" + output_filename)
        return output_filename
    except subprocess.CalledProcessError:
        logging.error("合并录像文件失败")
        return None


# 上传视频到YouTube
def upload_to_youtube(file_name, title):
    file = os.path.join(FILE_PATH, file_name)
    command = [
        YOUTUBE_UPLOADER_PATH + "youtubeuploader",
        '-cache', YOUTUBE_UPLOADER_PATH + "yt_request.token",
        '-metaJSON', YOUTUBE_UPLOADER_PATH + "yt_meta.json",
        '-secrets', YOUTUBE_UPLOADER_PATH + "yt_secrets.json",
        '-description', '',
        '-filename', file,
        '-title', title,
        ]
    logging.info(" ".join(command))

    # 启动 youtubeuploader 进程
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)

    # 实时读取输出
    while True:
        output = process.stdout.readline().strip()
        if output:
            logging.info(output)
            if "Token has been expired or revoked." in output:
                logging.error("Token 已过期或被撤销，删除token文件")
                send_notification("录像上传", "Token 已过期或被撤销：\n" + output)
                os.remove(YOUTUBE_UPLOADER_PATH + 'yt_request.token')
                time.sleep(10)
                return upload_to_youtube(file_name, title)

            if "https://accounts.google.com" in output:
                # 实时捕获到需要授权的提示
                logging.warning("需要授权，访问地址: " + output)
                send_notification("录像上传", "需要授权，访问地址：\n" + output)
        elif process.poll() is not None:
            break

    # 获取返回码，检查是否上传成功
    return_code = process.poll()
    if return_code != 0:
        logging.error("上传失败，返回码：" + str(return_code))
        send_notification("录像上传失败", "上传失败，返回码：" + str(return_code))
        return False
    os.rename(file, file.replace(".mp4", "_uploaded.mp4"))
    logging.info("录像已上传至YouTube")
    send_notification("录像上传", "上传成功：" + file)
    return True


# 主程序逻辑
def merge_and_upload():

    logging.info("准备合并录像文件并上传")
    files = [f for f in os.listdir(FILE_PATH) if f.endswith('.mp4')]
    # 按文件名排序
    files.sort()
    if not files:
        logging.info("没有找到待上传的mp4文件")
        return
    send_notification("录像上传", "准备合并录像文件并上传，文件列表：" + "\n".join(files))

    # 清理上传过的文件
    if not cleanup_old_files(files):
        return

    files = [f for f in os.listdir(FILE_PATH) if f.endswith('.mp4')]
    # 按文件名排序
    files.sort()
    if not files:
        logging.error("没有找到待上传的mp4文件，退出")
        send_notification("录像上传失败", "没有找到待上传的mp4文件")
        return

    # 去除广告并更新files数组
    new_files = []
    for file in files:
        if file.endswith('_00.mp4'):
            new_file = remove_ads(os.path.join(FILE_PATH, file))
            if not new_file:
                return
            new_files.append(os.path.basename(new_file))  # 使用去广告后的文件
        else:
            new_files.append(file)

    upload_title = (datetime.now() - timedelta(hours=12)).strftime('%Y-%m-%d')
    file_count = len(new_files)
    if file_count == 1:
        # 上传文件
        if not upload_to_youtube(new_files[0], upload_title):
            logging.error("录像上传失败")
            return
        logging.info("录像上传完毕")

    # 如果大于一个文件，则进行合并
    elif file_count > 1:

        logging.info("准备合并文件")
        send_notification("录像上传", "准备合并文件")

        # 检查磁盘空间是否足够
        if not check_disk_space(new_files):
            return

        # 合并文件
        if file_count <= 12:
            # 合并为一个文件
            merged_file = merge_files(new_files, upload_title)
            if not merged_file:
                return
            # 上传文件
            if not upload_to_youtube(merged_file, upload_title):
                logging.error("录像上传失败")
                return
            logging.info("录像上传完毕")
        else:
            # 合并为两个文件
            # 01
            part_files = new_files[:12]
            merged_file = merge_files(part_files, upload_title + '_01')
            if not merged_file:
                return
            # 上传文件
            if not upload_to_youtube(merged_file, upload_title + '_01'):
                logging.error("录像上传失败")
                send_notification("录像上传失败", "录像01 上传失败")
                return
            logging.info("录像01 上传完毕")
            # 02
            part_files = new_files[12:]
            merged_file = merge_files(part_files, upload_title + '_02')
            if not merged_file:
                return
            # 上传文件
            if not upload_to_youtube(merged_file, upload_title + '_02'):
                logging.error("录像上传失败")
                send_notification("录像上传失败", "录像02 上传失败")
                return
            logging.info("录像02 上传完毕")

    send_notification("录像上传", "录像上传完毕")


if __name__ == "__main__":
    main()
