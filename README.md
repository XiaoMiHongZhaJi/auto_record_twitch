# auto_record_twitch

### 功能描述

一个简易脚本，实现 twitch 开播检测 + 通知 + 录制 + 切成指定长度片段

可选功能：直播结束后合并录像文件 + 上传至YouTube

可配置多个代理地址，自动切换。适合网络不稳的情况。

（去除之前代码中的直播中剩余空间检测功能，不太稳定）

### 使用方式

#### 需要先安装好 ffmpeg 和 yt-dlp

<code>apt install ffmpeg python3 python3-pip -y

pip install yt-dlp
</code>

<hr>

#### 如需自动上传至YouTube，需要下载 `youtubeuploader`

具体配置方式请参考：https://github.com/porjo/youtubeuploader/releases

<hr>

#### 如需手动操作：

录制完成后，使用 `cut_15.sh 第一个片段.mp4` 剪掉第一个片段的 twitch 广告

使用 `merge.sh 第一个片段.mp4 最后一个片段.mp4` 合并多个片段为一个文件

上传至 YouTube `./youtubeuploader -cache yt_request.token -metaJSON yt_meta.json -secrets yt_secrets.json -description '' -filename 2025-05-27.mp4 -title 2025-05-27`