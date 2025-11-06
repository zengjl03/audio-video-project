from pathlib import Path
from abc import ABC, abstractmethod
from loguru import logger
from core.utils import timer
from core.utils import Config

class PipelineProcessor(ABC):
    def __init__(self, config: Config):
        pass
    @abstractmethod
    def process(self):
        pass

    def check_video(self, video_path: Path):
        if not video_path.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return False
        if video_path.suffix.lower() != '.mp4':
            logger.error(f"视频文件格式错误: {video_path}")
            return False
        return True