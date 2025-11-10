from pathlib import Path
from abc import ABC, abstractmethod
from loguru import logger
from core.utils import timer
from core.utils import Config
from core.extract import EditorManager
from core.transcription import TranscriptionManager
from core.highlight import AnalyzerManager
from core.pipeline.utils import OutlineExtractorMixin, TimelineExtractorMixin

class PipelineProcessor(ABC, OutlineExtractorMixin, TimelineExtractorMixin):
    def __init__(self, config: Config):
        self.video_path = Path(config.video_path)
        self.editor = EditorManager(self.video_path)
        self.transcriber = TranscriptionManager(config.transcription_config)
        self.analyzer = AnalyzerManager(config.analyzer_config)
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

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

    