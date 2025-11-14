import os
from dotenv import load_dotenv
from loguru import logger
from pathlib import Path
load_dotenv()
import time

def setup_logger():
    # 日志文件路径：默认 log/pipeline.log，支持环境变量 LOG_DIR
    log_dir = Path(os.getenv("LOG_DIR", "log"))
    log_prefix = os.getenv("LOG_PREFIX", "pipeline")
    log_file = log_dir / f"{log_prefix}_{time.strftime('%Y%m%d_%H%M%S')}.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # 配置 loguru：输出到文件 + 控制台，自动轮转
    logger.add(
        log_file,  # 日志文件路径
        level="INFO",  # 日志级别（INFO及以上）
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",  # 格式
        rotation="10 MB",  # 当文件达到10MB时自动切割
        retention="7 days",  # 保留7天的日志
        encoding="utf-8"  # 编码
    )
    # 控制台输出（默认已开启，这里可自定义格式）
    logger.remove(0)  # 移除默认控制台输出（可选）
    logger.add(
        sink=lambda msg: print(msg, end=""),  # 自定义控制台输出
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <level>{message}</level>"
    )

    return log_file

def mkdir():
    dirs = ['video', 'audio']
    for dir in dirs:
        if not Path(dir).exists():
            Path(dir).mkdir(parents=True, exist_ok=True)

def setup():
    mkdir()
    log_file = setup_logger()
    logger.info(f"日志文件已保存至: {log_file}")