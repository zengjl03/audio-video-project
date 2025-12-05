from pathlib import Path
from typing import List, Dict, Any, Tuple
from loguru import logger
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
from core.pipeline.utils import HighlightExtractorMixin, OmniAudioUnderstandingMixin, OutlineExtractorMixin
from core.utils import Config, timer,Segment,EventItem
from core.extract import EditorManager
import re

from init import setup

load_dotenv()

class ParallelProcessor_V2(PipelineProcessor,OutlineExtractorMixin,OmniAudioUnderstandingMixin):
    def __init__(self, config: Config):
        super().__init__(config)
        if not hasattr(config, 'segment_duration_minutes'):
            raise ValueError("segment_duration_minutes 不能为空")
        self.segment_duration_minutes = int(config.segment_duration_minutes)

    @timer
    def process(self, video_path: Path) -> Tuple[List[str], List[str]]:
        setup(video_path)
        self.video_path = video_path
        self.editor = EditorManager(self.video_path)
        # 检查
        if not self.check_video(self.video_path):
            return
        logger.info(f"开始处理视频: {self.video_path}")

        # 1. 提取整段音频
        audio_path = self.editor.extract_audio()
        if not audio_path:
            logger.error("音频提取失败，终止处理")
            return
        # return
            
        self.audio_path = audio_path

        # 2. 整体转写
        segments:List[Segment] = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error("音频转写失败，终止处理")
            return

        logger.info(f"转写结果: {segments}")
        
        # 1. 识别完整事件（包含时间戳）
        # 使用配置的分块时间间隔
        events: List[EventItem] = self.extract_outline(segments, self.analyzer, segment_duration_minutes=self.segment_duration_minutes)
        logger.info(f'识别出 {len(events)} 个完整事件')
        
        if not events:
            logger.warning("未识别出任何事件，终止后续处理")
            return

        key_events,_ = self.omni_audio_understanding(events)

        final_events = key_events[:]
        
        final_events = sorted(final_events, key=lambda x: x.start_time)

        logger.info('--------------------------------')
        # logger.info(f'关键词筛选的事件: {happy_keywords_events}')
        logger.info(f'omni音频理解筛选的事件: {key_events}')

        names,descs = [],[]

        # 5. 保存精彩片段
        for idx, clip in enumerate(final_events, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            try:
                self.editor.crop_video(outpath, clip.start_time, clip.end_time)
                logger.info(f"已保存精彩片段: {outpath} --> {clip.end_time - clip.start_time} 秒")
                names.append(outpath)
                descs.append(clip.title)
            except Exception as e:
                logger.error(f"保存精彩片段失败: {outpath} --> {e}")

        return names,descs