#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # 设置为hf的国内镜像网站
import warnings
warnings.filterwarnings("ignore")

from huggingface_hub import snapshot_download

# model_1 = "FireRedTeam/FireRedASR-AED-L"
# model_1 = "Qwen/Qwen2.5-14B-Instruct"
# model_1 = "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4"
model_1 = 'iic/speech_timestamp_prediction-v1-16k-offline'
# model_2 = 'Qwen/Qwen3-4B'
# model_3 = "Systran/faster-whisper-large-v3"
# model_list = [model_1, model_2, model_3]
model_list = [model_1]
# 定义目标文件夹路径：当前目录下的pre_trained文件夹

for model_name in model_list:

    # 循环下载，防止断联
    while True:
        try:
            snapshot_download(
                repo_id=model_name,
                local_dir_use_symlinks=True,  # 使用链接文件节省空间     
                resume_download=True          # 支持断点续传
            )
            break  # 下载完成后退出循环
        except Exception as e:
            print(f"下载中断，重试中... 错误信息: {e}")  # 打印错误信息便于调试