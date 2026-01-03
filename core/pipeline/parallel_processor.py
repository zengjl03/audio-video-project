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

class ParallelProcessor(PipelineProcessor,OutlineExtractorMixin, HighlightExtractorMixin, OmniAudioUnderstandingMixin):
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

    def _filter_events_by_happy_keywords(self, events: List[EventItem]) -> Tuple[List[EventItem], List[EventItem]]:
        """按照欢乐关键词过滤events，返回(包含关键词的events, 不包含关键词的events)"""
        happy_regex = re.compile('|'.join(self.happy_keywords))
        happy_events = []
        non_happy_events = []
        for event in events:
            content = event.content.strip()
            if happy_regex.search(content):
                happy_events.append(event)
            else:
                non_happy_events.append(event)
        return happy_events, non_happy_events
    
    @timer
    def process(self, video_path: Path) -> Tuple[List[str], List[str]]:
        setup(video_path)
        names,descs = [],[]
        self.video_path = video_path
        self.editor = EditorManager(self.video_path)
        # 检查
        if not self.check_video(self.video_path):
            return names,descs
        logger.info(f"开始处理视频: {self.video_path}")

        # 1. 提取整段音频
        audio_path = self.editor.extract_audio()
        if not audio_path:
            logger.error("音频提取失败，终止处理")
            return names,descs
        # return
            
        self.audio_path = audio_path

        # 2. 整体转写
        segments:List[Segment] = self.transcriber.transcribe(audio_path)
        if not segments:
            logger.error("音频转写失败，终止处理")
            return names,descs

        logger.info(f"转写结果: {segments}")
        
        # 1. 识别完整事件（包含时间戳）
        # 使用配置的分块时间间隔
        events: List[EventItem] = self.extract_outline(segments, self.analyzer, segment_duration_minutes=self.segment_duration_minutes)
        logger.info(f'识别出 {len(events)} 个完整事件')
        
        if not events:
            logger.warning("未识别出任何事件，终止后续处理")
            return names,descs

        # 这里加一个插件，手动地实现这个哈哈大笑关键词的捕捉
        # final_events,non_happy_events = [],events

        # events = [EventItem(title='讨论Demo问题', description='会议开始，讨论当前Demo存在的问题以及进展，特别是关于实时视频和演示效果的反馈。', start_time=0.0, end_time=11.83, content='嗯。我现在先听听你们说，现在这个特别是你这个 demo 现在有什么问题吗？或者说到什么程度了？你感觉。我感觉。'), EventItem(title='对Demo进展的看法', description='参会者表达了对Demo进展的不同看法，有人认为可以了，有人觉得想多了。', start_time=35.81, end_time=45.42, content='这回我觉得是你认为那也行，这回也行了呢。想多了，他，嗯。'), EventItem(title='实时视频功能讨论', description='讨论Demo是否能看实时视频，并对演示方式提出建议，例如不 要一起播放，一个一个来。', start_time=63.61, end_time=100.23, content='嗯。这现在能看实时视频吗？你这个应该可以看，你看，你看，你看。来，不要我，我需要你。嗯，我先问一下那个怀孕的。对。你别，你别一起播，一个一个来。到 时候你估计得一一起播才能看出问题来，我感觉。为什么？因为单独的声音，太简单了。现在，上回不是说，一个没。'), EventItem(title='语音补充方案', description='讨论上次提出的语音补充方案，以及通过均值、方差判断语音是否结束的 机制。', start_time=138.12, end_time=184.0, content='上次我们说，上次我们说那个，加上声音，人人有没有声音那个没加是吧？现在还没有因为。你一说还得等等半天，没有结果，还得等，那一下子印象就很差。嗯，就是得有一个机制判断 它这个结束了，是吧？'), EventItem(title='PPT演示与解决方案', description='讨论PPT演示内容，包括介绍解决方案，以及测试集和评估方式的讨论。', start_time=244.24, end_time=254.48, content='这样就非常直观的一个演示，你 P P T 归 P P T 了，就是 P P T 我们可以介绍一下。PPT我们可以介绍一下我们的解决方案，然后最后告诉你。'), EventItem(title='项目进展与演示计划', description='讨论项目遇到的问题以及解决进展，强调时间紧迫性，需要在12号之前跟投资人演示，并暂时搁置人脸相关项目。', start_time=301.44, end_time=365.64, content='不是我上周没搞这个，就上周这个这个最大的问题还是上周那个错误的问题，不是这这些东西导致的。不是这个导致，那也是他在解决啊，那你你没干这个事。不是啊，他这边只是知道知道有问题，不知道是怎么怎么有有问题的。不行啊，反正这样你要等五分钟肯定是不行的啊。这这个我们已经快没时间了，大家抓紧一点。就是等他们那边硬件一旦好了，估计十二号吧。一旦好了，我们可能很快就要跟投资人演示。所以所以一周一周时间过得很快的。你你现在那个人脸那个事情还有在进行吗？那个在在去那个在在日常用远日常中一直都不好。那个占你很多时间吗？好像占了一些。那个反正暂时也无那个项目什么，你到十二号之前都就忙这个事情吧，先那个先不管了。还有十二号还有九天，就一周时间了，大概有。我们争取下周三一定要拿。'), EventItem(title='语音分析模块讨论', description='讨论语音分析模块，以及声音干扰对结果的影响。', start_time=385.45, end_time=434.08, content='啊，那个重新跑一遍，因为因为刚不是有人说话嘛。影响了吗？那肯定啊，因为因为这里面的那个核心的模块不是语言分析吗？不都串了。这一。嗯，你离得这么近，肯定是你的声音，是主导啊，干扰啊，就是。比第二好点，那你你 这是炒米价。'), EventItem(title='APP实时流演示', description='黄域演示APP实时流功能，但由于没有电脑无法观看。', start_time=470.6, end_time=507.26, content='先先问一下黄域那边，你那个APP现在改改成能看实时流了吗？呃，可 以看了，我可以给你演示一下，不过我还没有。嗯，行，OK，我现在会议共享了，你们能看到吗？嗯，我们没有用电脑。啊，那行，那那就，那我。'), EventItem(title='指标评估的讨论', description='讨论指标评估的有效性，强调产品应用中 的实际感受比学术指标更重要。', start_time=700.22, end_time=750.1, content='就是这个，就这里边充斥了大量的可对可错的东西。嗯，看你那个，反正这个东西是，它是放在学术里面，这个东西还是进行个深深入嘛，真正的，就真正的好坏 ，实际上，是用到是哪里才能才能刻画，什么时代，用到是哪里，用你自己亲身感受才能刻画，那个指标。在我看来，这种这种任务，这种指标只是用来唬申报人的这种任务。我们是在做产品，我们不是做申报人。啊对，但是现在现在我们拿到的那个测试集与评估方式，它就是个故意，现在就是和人的感受。我们应该展示的是一个你这个测试集是什么样子的，然后在那个测试集上，准确率召回是什么。'), EventItem(title='测试机使用和产品考量', description='讨论测试机的使用情况， 以及产品上线后用户体验的考虑。', start_time=913.56, end_time=962.21, content='嗯，或者隔壁房间不是有那个测试机吗？那有人在用吗？那两个，那两个机器有，有个长的那个目前是在闲着。然后，你这里。那他们嗯，那这个后面是产品测还得考虑，如果到时候我们真播出去有用户的话，那你，嗯，这还是。'), EventItem(title='模型与接口的讨论', description='讨论模型是Python代码还是PS调用。', start_time=985.31, end_time=998.19, content='Python 的，你签那如果是接口，你估计就是个 Python 代码吧？是不是。是拍一下吗？模型是拍出来的，没有模型还有模型，就是调用那PS。'), EventItem(title='细节呈现与合同', description='讨论是否使用山药泥，以及将细节呈现给孩子和合同签署的问题。', start_time=1021.32, end_time=1033.57, content='有没有用那个山药泥啊？还有就是，那现在那个那个签了那个约是是，是哪儿。'), EventItem(title='最终合同等待', description='表示最终合同还未出。', start_time=1057.27, end_time=1069.74, content='对对对，然后只要把那个细节给孩子看就行。还没出。')]

        key_events,non_key_events = self.omni_audio_understanding(events)

        final_events = key_events[:]

        if non_key_events:
            highlight_events = self.extract_timeline(non_key_events, self.analyzer)
            final_events.extend(highlight_events)

        # happy_keywords_events,non_happy_keywords_omni_events,highlight_events = [],[],[]

        # happy_keywords_events, non_happy_keywords_events = self._filter_events_by_happy_keywords(events)
        # logger.info(f"包含欢乐关键词的事件数: {len(happy_keywords_events)}，不包含的事件数: {len(non_happy_keywords_events)}")

        # logger.info(f'happy_keywords_events: {happy_keywords_events}')
        # logger.info(f'non_happy_keywords_events: {non_happy_keywords_events}')

        # final_events = []
        # final_events.extend(happy_keywords_events)

        # if non_happy_keywords_events:
        #     # 1. 使用omni音频理解模型进行过滤
        #     non_happy_keywords_no_omni_events,non_happy_keywords_omni_events = self.omni_audio_understanding(non_happy_keywords_events)
        #     logger.info(f'non_happy_keywords_no_omni_events: {non_happy_keywords_no_omni_events}')
        #     logger.info(f'non_happy_keywords_omni_events: {non_happy_keywords_omni_events}')

        #     final_events.extend(non_happy_keywords_omni_events)
            
        #     if non_happy_keywords_no_omni_events:
        #         # 2. 从事件列表中筛选出有趣的事件
        #         highlight_events = self.extract_timeline(non_happy_keywords_no_omni_events, self.analyzer)
        #         logger.info(f'highlight_events: {highlight_events}')
        #         final_events.extend(highlight_events)
        
        final_events = sorted(final_events, key=lambda x: x.start_time)

        logger.info('--------------------------------')
        # logger.info(f'关键词筛选的事件: {happy_keywords_events}')
        logger.info(f'omni音频理解筛选的事件: {key_events}')
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
            



