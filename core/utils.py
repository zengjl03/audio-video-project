from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Literal
from loguru import logger
import time
from functools import wraps
from pathlib import Path

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

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time
        }

@dataclass
class SegmentWithSpk(Segment):
    spk_id:int

    def to_dict(self) -> Dict:
        return {
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "spk_id": self.spk_id
        }

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
class AnalyzerAPIModelConfig:
    api_key:str
    base_url:str
    model_name:str
    prompt_config:AnalyzerPromptConfig
    mode:str = 'api'

@dataclass
class AnalyzerLocalModelConfig:
    prompt_config:AnalyzerPromptConfig
    mode:str = 'local'
    model_name:Literal["qwen3-4b","qwen2.5-14b-instruct","qwen2.5-14b-instruct-gptq-int4"] = "qwen3-4b"

@dataclass
class Config:
    video_path:str
    transcription_config: TranscriptionLocalModelConfig | TranscriptionAPIModelConfig
    analyzer_config: AnalyzerAPIModelConfig | AnalyzerLocalModelConfig
    output_dir:str

    # extra配置
    segment_duration_minutes:int | None = None
