from pathlib import Path
import time
from loguru import logger
from core.extract import EditorManager
from core.transcription import TranscriptionManager
from core.highlight import AnalyzerManager
import os
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
load_dotenv()
from core.utils import Config, timer

# 单一串行
class NormalProcessor(PipelineProcessor):
    def __init__(self,config: Config):
        self.video_path = Path(config.video_path)
        self.editor = EditorManager(self.video_path)
        self.transcriber = TranscriptionManager(config.transcription_config)
        self.highlighter = AnalyzerManager(config.analyzer_config)
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @timer
    def process(self):
        # 检查
        if not self.check_video(self.video_path):
            return
        logger.info(f"开始处理视频: {self.video_path}")
        # 1. 音频提取
        audio_path = self.editor.extract_audio()
        if not audio_path:
            logger.error(f"音频提取失败，跳过: {self.video_path}")
            return

        # 2. 音频转写
        segments = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error(f"音频转写失败，跳过: {self.video_path}")
            return

        logger.info(f"segments: {segments}")
        logger.info(f"转写完成，获取到{len(segments)}个片段: {self.video_path}")

        # 3. 拼接带时间文本
        trans_text = ' '.join([f"[{start} - {end}] {text}\n" for text, start, end in segments])

        # 4. 大模型分析精彩片段
        highlights = self.highlighter.analyze(trans_text)

        logger.info(f"分析完成，获取到{len(highlights)}个精彩片段: {self.video_path}")
        if not highlights:
            logger.warning(f"未提取到精彩片段: {self.video_path}")
            return
        
        for idx, clip in enumerate(highlights, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            self.editor.crop_video(outpath, clip.get('start'), clip.get('end'))
            logger.info(f"已保存精彩片段: {outpath}")