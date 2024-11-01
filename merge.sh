#!/bin/bash

# 检查输入参数
if [ $# -ne 2 ]; then
    echo "Usage: $0 <start_file> <end_file>"
    echo "Example: $0 09-08_21-30-16_et_00_cut_from_15.mp4 09-08_21-30-16_et_06.mp4"
    exit 1
fi

start_file=$1
end_file=$2

# 获取文件夹下所有mp4文件，按文件名排序
mp4_files=$(ls *.mp4 | sort)

# 计算待合并文件的总大小
total_size=0
add_files=0
for file in $mp4_files; do
    if [[ "$file" == "$start_file" ]]; then
        add_files=1
    fi

    if [ $add_files -eq 1 ]; then
        file_size=$(stat -c%s "$file")
        total_size=$((total_size + file_size))
    fi

    if [[ "$file" == "$end_file" ]]; then
        break
    fi
done

# 将总大小转换为GB
total_size_gb=$((total_size / 1024 / 1024 / 1024))

# 获取文件系统的剩余空间 (单位: GB)
available_space=$(df --output=avail -k . | tail -1)
available_space=$((available_space * 1024))  # 转换为字节
available_space_gb=$((available_space / 1024 / 1024 / 1024))

# 检查剩余空间是否足够
if [ $available_space -lt $total_size ]; then
    echo "Error: Not enough space to merge files. Required: $total_size_gb GB, Available: $available_space_gb GB."
    exit 1
fi
echo "Enough space to merge files. Required: $total_size_gb GB, Available: $available_space_gb GB."

# 生成合并文件的列表
concat_file_list="file_list.txt"
rm -f $concat_file_list

# 标记是否开始添加文件
add_files=0

for file in $mp4_files; do
    # 当到达start_file时，开始添加文件
    if [[ "$file" == "$start_file" ]]; then
        add_files=1
    fi

    # 如果已经开始，添加文件到列表
    if [ $add_files -eq 1 ]; then
        echo "file '$file'" >> $concat_file_list
    fi

    # 当到达end_file时，停止添加并跳出循环
    if [[ "$file" == "$end_file" ]]; then
        break
    fi
done

# 检查是否生成了文件列表
if [ ! -s $concat_file_list ]; then
    echo "No files found between $start_file and $end_file"
    exit 1
fi

# 合并文件
output_file="merged_$(basename "$start_file" .mp4)_to_$(basename "$end_file" .mp4).mp4"
cat $concat_file_list
echo 即将执行 ffmpeg -f concat -safe 0 -i $concat_file_list -c copy $output_file
sleep 2
echo 正在执行 ffmpeg -f concat -safe 0 -i $concat_file_list -c copy $output_file
sleep 1
ffmpeg -f concat -safe 0 -i $concat_file_list -c copy $output_file

# 清理
rm -f $concat_file_list

echo "Merged file created: $output_file"
