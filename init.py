import os
from dotenv import load_dotenv
from loguru import logger
load_dotenv()

def setup_logger():
    # 日志文件路径：默认 log/pipeline.log，支持环境变量 LOG_DIR
    log_dir = os.getenv("LOG_DIR", "log")
    log_file = os.path.join(log_dir, "pipeline.log")
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

def setup():
    setup_logger()