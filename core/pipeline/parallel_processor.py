from pathlib import Path
from typing import List, Dict, Any, Tuple
from loguru import logger
from dotenv import load_dotenv
from core.pipeline.base import PipelineProcessor
from core.utils import Config, timer,Segment
from core.extract import EditorManager
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
                # 原有关键词
                r"哈哈+",
                r"嘿嘿+",
                r"嘻嘻+",
                r"呵呵+",
                r"笑死+",
                r"好开心+",
                r"太开心了+",
                r"好幸福+",
                r"太幸福了+",
                r"好好玩+",
                r"太好玩了+",
                # 11.13补充
                # 补充：核心夸赞（直接肯定孩子）
                r"太棒了+",
                r"太优秀了+",
                r"真厉害+",
                r"好棒呀+",
                r"真了不起+",
                r"太牛了+",
                r"真乖+",
                r"好聪明+",
                r"太聪明了+",
                r"真能干+",
                r"太能干了+",
                r"真出色+",
                r"太出色了+",
                r"真给力+",
                r"太给力了+",
                # 补充：惊喜感叹（情绪起伏大，带意外感）
                r"哇+",
                r"哇塞+",
                r"天呐+",
                r"我的天+",
                r"太惊喜了+",
                r"太意外了+",
                r"居然这么棒+",
                r"没想到这么厉害+",
                r"太惊喜了+",
                r"真让人惊喜+",
                # 补充：骄傲自豪（家长主观情感强烈）
                r"真为你骄傲+",
                r"太为你自豪了+",
                r"我的宝贝太厉害了+",
                r"不愧是我的孩子+",
                r"太争光了+",
                r"真长脸+",
                r"太让人骄傲了+",
            ]

    def _filter_events_by_happy_keywords(self, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """按照欢乐关键词过滤events，返回(包含关键词的events, 不包含关键词的events)"""
        happy_regex = re.compile('|'.join(self.happy_keywords))
        happy_events = []
        non_happy_events = []
        for event in events:
            content = event.get('content', '')
            if happy_regex.search(content):
                happy_events.append(event)
            else:
                non_happy_events.append(event)
        return happy_events, non_happy_events
    
    @timer
    def process(self, video_path: Path) -> Tuple[List[str], List[str]]:
        self.video_path = video_path    
        self.editor = EditorManager(self.video_path)
        self.video_path = video_path
        # 检查
        if not self.check_video(self.video_path):
            return
        logger.info(f"开始处理视频: {self.video_path}")

        # 1. 提取整段音频
        audio_path = self.editor.extract_audio()
        if not audio_path:
            logger.error("音频提取失败，终止处理")
            return
            
        self.audio_path = audio_path

        # 2. 整体转写
        segments:List[Segment] = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error("音频转写失败，终止处理")
            return

        logger.info(f"转写结果: {segments}")
        
        # 1. 识别完整事件（包含时间戳）
        # 使用配置的分块时间间隔
        events: List[Dict[str, Any]] = self.extract_outline(segments, self.analyzer, segment_duration_minutes=self.segment_duration_minutes)
        logger.info(f'识别出 {len(events)} 个完整事件')
        
        if not events:
            logger.warning("未识别出任何事件，终止后续处理")
            return

        # 这里加一个插件，手动地实现这个哈哈大笑关键词的捕捉
        # final_events,non_happy_events = [],events

        happy_keywords_events,non_happy_keywords_omni_events,highlight_events = [],[],[]

        happy_keywords_events, non_happy_keywords_events = self._filter_events_by_happy_keywords(events)
        logger.info(f"包含欢乐关键词的事件数: {len(happy_keywords_events)}，不包含的事件数: {len(non_happy_keywords_events)}")

        logger.info(f'happy_keywords_events: {happy_keywords_events}')
        logger.info(f'non_happy_keywords_events: {non_happy_keywords_events}')

        final_events = []
        final_events.extend(happy_keywords_events)

        if non_happy_keywords_events:
            # 1. 使用omni音频理解模型进行过滤
            non_happy_keywords_no_omni_events,non_happy_keywords_omni_events = self.omni_audio_understanding(non_happy_keywords_events)
            logger.info(f'non_happy_keywords_no_omni_events: {non_happy_keywords_no_omni_events}')
            logger.info(f'non_happy_keywords_omni_events: {non_happy_keywords_omni_events}')
            final_events.extend(non_happy_keywords_omni_events)
            
            if non_happy_keywords_no_omni_events:
                # 2. 从事件列表中筛选出有趣的事件
                highlight_events = self.extract_timeline(non_happy_keywords_no_omni_events, self.analyzer)
                logger.info(f'highlight_events: {highlight_events}')
                final_events.extend(highlight_events)
        
        final_events = sorted(final_events, key=lambda x: x.get('start_time'))
        logger.info(f'关键词筛选的事件: {happy_keywords_events}')
        logger.info(f'omni音频理解筛选的事件: {non_happy_keywords_omni_events}')
        logger.info(f'llm分析有趣的事件: {highlight_events}')
        # logger.info(f'final_events: {final_events}')

        # import csv
        # with open('final_events.csv', 'a', newline='', encoding='utf-8') as f:
        #     writer = csv.writer(f)
        #     if final_events:
        #         for event in final_events:
        #             writer.writerow([self.video_path.stem, event.get('start_time'), event.get('end_time')])
        #     else:
        #         writer.writerow([self.video_path.stem, 'None', 'None'])

        names,descs = [],[]

        # 5. 保存精彩片段
        for idx, clip in enumerate(final_events, 1):
            outname = f"clip_{self.video_path.stem}_{idx:02d}.mp4"
            outpath = self.output_dir / outname
            self.editor.crop_video(outpath, clip.get('start_time'), clip.get('end_time'))
            logger.info(f"已保存精彩片段: {outpath} --> {clip.get('end_time') - clip.get('start_time')} 秒")

            names.append(outpath)
            descs.append(clip.get('title'))

        return names,descs
            



