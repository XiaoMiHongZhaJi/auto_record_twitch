# auto_record_twitch
twitch 开播检测+通知+录制+切成指定长度片段

可配置多个代理地址，适合硬盘不大或网络不稳的情况。

需要先安装好 ffmpeg 和 yt-dlp
<code>
apt install ffmpeg python3 python3-pip -y
pip install yt-dlp
</code>


如果要隐藏 ffmpeg 的输出信息，可以使用 
`python auto_record_twitch.py 2>/dev/null`

录制完成后，使用 `cut_15.sh 第一个片段.mp4` 剪掉第一个片段的 twitch 广告
使用 `merge.sh 第一个片段.mp4 最后一个片段.mp4` 合并多个片段为一个文件
