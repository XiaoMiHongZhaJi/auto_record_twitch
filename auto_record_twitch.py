import os
import sys
import time
import requests
import json
from datetime import datetime
import subprocess
import platform
import shutil
import logging
import threading

# vps名称
VPS_NAME = 'my_vps'

# 文件名中的主播名字
CHANNEL_NAME = 'et'

# 主播id
CHANNEL_ID = 'et_1231'
# CHANNEL_ID = 'jinnytty'

# 录制文件的路径
FILE_PATH = '/mnt/twitch/'

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
ERR_NOTICE = 5

# 通知 URL
NOTIFICATION_URL = 'https://message.chenyifaer.shop/xxxxx/'

# 最小磁盘空间 1GB
min_space = 1 * 1024 * 1024 * 1024


proxy = ''
proxy_index = 0
err_count = 0
last_err_time = None

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
    global proxy_index, proxy, last_err_time, err_count
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
            err_msg = f"{VPS_NAME} 检测 {CHANNEL_NAME} 直播状态出错，CHANNEL_ID：{CHANNEL_ID} 可能不存在"
            logger.error(err_msg)
            send_notification("网络错误", err_msg)
            return False
        err_count = 0
        return user['stream'] is not None

    except Exception as e:
        err_count = err_count + 1
        err_msg = f"{VPS_NAME} 检测开播状态出错[{err_count}]，代理地址[{proxy_index}]：{proxy}\n{e}"
        logger.error(err_msg)
        if err_count >= 3:
            if last_err_time is None or (datetime.now() - last_err_time).total_seconds() > ERR_NOTICE * 60:
                send_notification("网络错误", err_msg)
                last_err_time = datetime.now()
            proxy_index = proxy_index + 1

    return False


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


stop_event = threading.Event()
# 定义磁盘空间监控的函数
def monitor_disk_space(interval, process):
    logger.info("start monitor_disk_space_thread")
    while not stop_event.is_set():
        # 获取磁盘剩余空间
        free = get_disk_space()
        logger.info(f"free_disk_space: {free // (1024 * 1024)} MB")

        # 如果剩余空间小于指定的最小值，终止主程序
        if free < min_space:
            err_msg = f"{VPS_NAME} 剩余空间不足，剩余 {free // (1024 * 1024)} MB， 请在 10 分钟内释放磁盘空间，否则录制将被停止，以保证最后一个录像片段可用"
            logger.error(err_msg)
            send_notification("空间不足", err_msg)
            time.sleep(10 * 60)
            # 获取磁盘剩余空间
            free = get_disk_space()
            logger.info(f"free_disk_space again: {free // (1024 * 1024)} MB")
            if free < min_space:
                subprocess.Popen("ps -ef | grep 'ffmpeg -y -hide_banner' | grep -v grep | awk '{print $2}' | xargs kill -12", shell=True).wait()
                
                err_msg = f"{VPS_NAME} 剩余空间不足，剩余 {free // (1024 * 1024)} MB，录像已停止"
                logger.error(err_msg)
                send_notification("空间不足", err_msg)
                
                break

        # 等待指定的间隔时间
        time.sleep(interval)
        
    logger.info("stop monitor_disk_space_thread")


# 定义初始磁盘空间检查函数
def check_initial_disk_space():
    while True:
        # 获取磁盘剩余空间
        free = get_disk_space()

        if free > min_space:
            return True
        
        # 如果剩余空间小于指定的最小值，等待一定时间后重试
        err_msg = f"{VPS_NAME} 剩余空间不足，剩余 {free // (1024 * 1024)} MB，10 分钟后重试"
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

    # 定义停止事件
    stop_event = threading.Event()
    
    monitor_thread = threading.Thread(target=monitor_disk_space, args=(1 * 60, process))
    monitor_thread.start()

    process.wait()  # 等待录制结束

    # 停止 monitor_thread
    stop_event.set()
    monitor_thread.join()

    end_time = datetime.now()
    duration = end_time - start_time
    return duration


# 主函数
def main():
    global proxy_index, err_count
    timeout = DEFAULT_TIMEOUT
    # 检查文件夹是否存在，如果不存在则创建
    if not os.path.exists(FILE_PATH):
        os.makedirs(FILE_PATH)

    # 检查初始磁盘空间
    while check_initial_disk_space():

        if check_stream_live():

            disk_space_gb = get_disk_space() / (1024 ** 3)
            hours, minutes = calculate_recording_time_gb(disk_space_gb)
            notification_message = f"{VPS_NAME} {CHANNEL_NAME} 已开播，剩余空间 {disk_space_gb:.2f} GB，预计可录制 {hours} : {minutes}，代理地址[{proxy_index}]：{proxy}"
            logger.info(notification_message)
            send_notification("开播通知", notification_message)

            # 开始录制
            duration = record_stream()
            total_seconds = duration.total_seconds()
            logger.info(f"{CHANNEL_NAME} 直播时长 {int(total_seconds)} 秒，代理地址[{proxy_index}]：{proxy}")

            if total_seconds > 10:
                duration_hours = int(total_seconds // 3600)
                duration_minutes = int((total_seconds % 3600) // 60)

                end_message = f"{VPS_NAME} {CHANNEL_NAME} 直播已结束，时长 {duration_hours} : {duration_minutes}，代理地址[{proxy_index}]：{proxy}"
                logger.info(end_message)
                send_notification("直播结束", end_message)
                timeout = 1
            else:
                err_count = err_count + 1
                err_msg = f"{VPS_NAME} {CHANNEL_NAME} 直播时长 {int(total_seconds)} 秒[{err_count}]，可能是网络错误，代理地址[{proxy_index}]：{proxy}，尝试切换代理"
                logger.error(err_msg)
                timeout = 1
                if err_count >= 3:
                    proxy_index = proxy_index + 1
                    send_notification("网络错误", err_msg)

        if timeout < DEFAULT_TIMEOUT:
            timeout += 2

        time.sleep(timeout)


if __name__ == "__main__":
    main()
