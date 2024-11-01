#!/bin/bash

# 检查是否有输入参数
if [ "$#" -eq 0 ]; then
    echo "错误：请提供文件名。"
    echo "使用方法: $0 <文件名>"
    exit 1
fi

# 循环处理每个输入文件
while [ "$#" -gt 0 ]; do
    # 检查文件是否存在
    if [ ! -f "$1" ]; then
        echo "错误：文件 '$1' 不存在。"
        shift
        continue
    fi

    # 获取文件的基本名称
    base_filename=$(basename "$1" | sed 's/\.[^.]*$//')

    # 构建输出音频文件名
    output_file="${base_filename}_15.mp4"

    # 检查目标音频文件是否已存在
    if [ -f "$output_file" ]; then
        echo "错误：文件 '$output_file' 已存在。跳过提取操作。"
        shift
        continue
    fi

    # 使用 FFmpeg 提取音频
    ffmpeg -i "$1" -ss 15 -c copy "$output_file"

    # 检查 FFmpeg 是否成功
    if [ $? -ne 0 ]; then
        echo "错误：视频剪切失败。"
        sleep 4
    else
        echo "视频已成功剪切到 '$output_file'，即将删除源文件 '$1'。"
        sleep 2
        rm -r "$1"
    fi

    # 处理下一个文件
    shift
done
