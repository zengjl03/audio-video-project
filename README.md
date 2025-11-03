项目目录说明
```bash
.
├── audio # 视频提取音频的存放文件夹
├── core # 核心代码 --> 包含分离音频、视频裁剪（extract.py)、音频转写（transcription.py)、精彩片段提取（highlight.py)
├── log # 日志文件
├── processed # 处理后的视频存放文件夹
├── Qwen # 模型文件
│   └── Qwen3-4B
├── Systran # 模型文件
│   └── faster-whisper-large-v3
└── video # 测试视频
└── download.py # 下载模型
└── main.py # 主程序
└── README.md # 项目说明
└── requirements.txt # 项目依赖
└── environment.yml # 项目环境
```


1. 可以通过pip创建环境、也可以通过conda创建环境（推荐）

使用pip
```bash
pip install -r requirements.txt
```
使用conda
```bash
conda env create -f environment.yml
```
测试时使用的是cuda11.8
```bash
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch-c nvidia
```

2. 下载模型（直接运行main.py也会自动下载模型）
```bash
python download.py
```

3.运行
配置好环境后，可以直接运行main.py

测试时可以在main.py中修改video_path为测试视频路径
```python
if __name__ == "__main__":
    from loguru import logger
    from init import setup
    # 初始化
    setup()

    subprocess.run(["python", "download.py"])

    video_path = "video/test1.mp4"
    pipeline(video_path)
```

```bash
python main.py
```