from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal
from loguru import logger
import time
from functools import wraps
from pathlib import Path
from pydantic import BaseModel, Field
import csv
from typing import Callable

class EventItem(BaseModel):
    title: str = Field(description="事件的简短标题，描述这个事件的核心，长度需控制在4-8个汉字或16个字符以内")
    description: str = Field(description="事件的详细描述，说明这个事件的内容")
    start_time: float = Field(description="完整事件的开始时间（秒数格式）")
    end_time: float = Field(description="完整事件的结束时间（秒数格式）")
    content: str = Field(description="合并后的完整文本内容（所有相关片段的文本合并）")

    # 关键配置：允许额外字段
    model_config = {"extra": "allow"}


class OutlineResponse(BaseModel):
    events: List[EventItem] = Field(description="事件列表")


class HighlightResponse(BaseModel):
    is_highlight: bool = Field(description="是否是值得纪念的事件")
    reason: str = Field(description="筛选原因，说明为什么这个事件值得纪念")

def timer(func):
    """计算函数执行时间的装饰器"""
    @wraps(func) 
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"函数 {func.__name__} 执行完成，耗时: {elapsed_time:.6f} 秒")
        return result
    return wrapper

def track_to_csv(csv_filename: str = 'final_events.csv'):
    """装饰器：确保process方法执行后无论成功失败都写入CSV文件"""
    print('111')
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, video_path: Path, *args, **kwargs):
            # 初始化final_events为None，用于跟踪处理结果
            self.final_events = None
            # 执行原始的process方法
            result = func(self, video_path, *args, **kwargs)
            with open(csv_filename, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if self.final_events is not None:
                    for clip in self.final_events:
                        writer.writerow([self.video_path.stem, clip.start_time, clip.end_time])
                else:
                    writer.writerow([self.video_path.stem, 'None', 'None'])
            return result
        return wrapper
    return decorator

@dataclass
class Segment:
    text:str
    start_time:float
    end_time:float

@dataclass
class SegmentWithSpk(Segment):
    spk_id:int

@dataclass
class SegmentWithEmotion(Segment):
    emotion:str

class TranscriptionModel(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str) -> List[Segment]:
        """
        转写音频文件
        :param audio_path: 音频文件路径
        :return: 转写结果，格式为 [[文本, 开始时间(秒), 结束时间(秒)], ...]
        """
        pass

@dataclass
class TranscriptionLocalModelConfig:
    mode:str = 'local'
    model_name: Literal["paraformer-zh", "large-v3", "sense-voice-small", "firered-asr"] = "paraformer-zh"

@dataclass
class TranscriptionAPIModelConfig:
    mode:str = "api"

@dataclass
class AnalyzerPromptConfig:
    outline_prompt:Path
    highlight_prompt:Path | None = None

@dataclass
class AnalyzerModelNameConfig:
    outline_model_name:str
    highlight_model_name:str | None = None

@dataclass
class AnalyzerAPIModelConfig:
    api_key:str
    base_url:str
    prompt_config:AnalyzerPromptConfig
    model_name_config:AnalyzerModelNameConfig
    mode:str = 'api'

@dataclass
class AnalyzerLocalModelConfig:
    prompt_config:AnalyzerPromptConfig
    model_name_config:AnalyzerModelNameConfig
    mode:str = 'local'

@dataclass
class Config:
    transcription_config: TranscriptionLocalModelConfig | TranscriptionAPIModelConfig
    analyzer_config: AnalyzerAPIModelConfig | AnalyzerLocalModelConfig
    output_dir:str

    # extra配置
    segment_duration_minutes:int | None = None
