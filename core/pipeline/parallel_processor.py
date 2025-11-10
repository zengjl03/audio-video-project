from typing import List, Dict, Any, Tuple
from loguru import logger
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
from core.utils import Config, timer,Segment
import re


load_dotenv()

class ParallelProcessor(PipelineProcessor):
    """多块视频处理器：按配置时长对转写结果切块，逐块分析"""
    
    def __init__(self, config: Config):
        super().__init__(config)
        if not hasattr(config, 'segment_duration_minutes'):
            raise ValueError("segment_duration_minutes 不能为空")
        self.segment_duration_minutes = int(config.segment_duration_minutes)

        self.happy_keywords = [
            r"哈哈+",
            r"嘿嘿+",
            r"嘻嘻+",
            r"呵呵+",
            r"笑死",
            r"笑疯了",
            r"笑了",
            r"好开心",
            r"太开心了",
            r"好幸福",
            r"太幸福了",
            r"好好玩",
            r"太好玩了",
        ]

    def _filter_events_by_happy_keywords(self, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """按照欢乐关键词过滤events，返回(包含关键词的events, 不包含关键词的events)"""
        happy_regex = re.compile('|'.join(self.happy_keywords))
        happy_events = []
        non_happy_events = []
        for event in events:
            content = event.content
            if happy_regex.search(content):
                happy_events.append(event)
            else:
                non_happy_events.append(event)
        return happy_events, non_happy_events
    
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
        segments:List[Segment] = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error("音频转写失败，终止处理")
            return
        
        logger.info(f"转写完成，获取到 {len(segments)} 个片段")
        # print('segments',segments)
        
        # 1. 识别完整事件（包含时间戳）
        # 使用配置的分块时间间隔
        events: List[Dict[str, Any]] = self.extract_outline(segments, self.analyzer, segment_duration_minutes=self.segment_duration_minutes)
        logger.info(f'识别出 {len(events)} 个完整事件')
        
        if not events:
            logger.warning("未识别出任何事件，终止后续处理")
            return

        # 这里加一个插件，手动地实现这个哈哈大笑关键词的捕捉
        happy_events, non_happy_events = self._filter_events_by_happy_keywords(events)
        logger.info(f"包含欢乐关键词的事件数: {len(happy_events)}，不包含的事件数: {len(non_happy_events)}")

        final_events = []
        final_events.extend(happy_events)

        if non_happy_events:
            # 2. 从事件列表中筛选出有趣的事件
            highlight_events = self.extract_timeline(non_happy_events, self.analyzer)
            final_events.extend(highlight_events)

        # 5. 保存精彩片段
        for idx, clip in enumerate(final_events, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            self.editor.crop_video(outpath, clip.get('start_time'), clip.get('end_time'))
            logger.info(f"已保存精彩片段: {outpath} --> {clip.get('end_time') - clip.get('start_time')} 秒")



