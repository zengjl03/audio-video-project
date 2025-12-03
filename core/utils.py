from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Literal
from loguru import logger
import time
from functools import wraps
from pathlib import Path
from pydantic import BaseModel, Field

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

@dataclass
class Segment:
    text:str
    start_time:float
    end_time:float

@dataclass
class SegmentWithSpk(Segment):
    spk_id:int

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
    highlight_prompt:Path

@dataclass
class AnalyzerModelNameConfig:
    outline_model_name:str
    highlight_model_name:str

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
