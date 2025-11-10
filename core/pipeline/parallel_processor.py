from pathlib import Path
from typing import List, Dict, Any
from loguru import logger
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
from core.utils import Config, timer


load_dotenv()

class ParallelProcessor(PipelineProcessor):
    """多块视频处理器：按配置时长对转写结果切块，逐块分析"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        if not hasattr(config, 'segment_duration_minutes'):
            raise ValueError("segment_duration_minutes 不能为空")
        self.segment_duration_seconds = int(config.segment_duration_minutes) * 60
    
    @timer
    def process(self):
        # 检查
        if not self.check_video(self.video_path):
            return
        logger.info(f"开始处理视频: {self.video_path}")

        # 1. 提取整段音频
        audio_path = self.editor.extract_audio()
        if not audio_path:
            logger.error("音频提取失败，终止处理")
            return
        
        # 2. 整体转写
        segments = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error("音频转写失败，终止处理")
            return
        
        logger.info(f"转写完成，获取到 {len(segments)} 个片段")
        print('segments',segments)
        
        # 1. 识别完整事件（包含时间戳）
        events = self.extract_outline(segments, self.analyzer)
        logger.info(f'识别出 {len(events)} 个完整事件')
        
        if not events:
            logger.warning("未识别出任何事件，终止后续处理")
            return

        # 2. 从事件列表中筛选出有趣的事件
        all_highlights = self.extract_timeline(events, self.analyzer)
        all_highlights.sort(key=lambda x: x.get('start_time', 0))
        logger.info('highlights',all_highlights)

        return

        # logger.info(f"分析完成，得到 {len(all_highlights)} 个精彩片段")
        if not all_highlights:
            logger.warning("未提取到精彩片段")
            return

        # 5. 保存精彩片段
        for idx, clip in enumerate(all_highlights, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            self.editor.crop_video(outpath, clip.get('start'), clip.get('end'))
            logger.info(f"已保存精彩片段: {outpath}")



