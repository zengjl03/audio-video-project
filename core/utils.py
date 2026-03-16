from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Literal
from loguru import logger
import time
from functools import wraps
from pathlib import Path
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    field_validator,
    model_validator,
)
import csv
from typing import Callable


def _to_str(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return str(v)


def _to_float(v) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except Exception:
        return 0.0


def _to_bool(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "ok", "是", "对"}:
        return True
    if s in {"0", "false", "no", "n", "否", "不", "不是"}:
        return False
    return bool(s)


class EventItem(BaseModel):
    title: str = Field(
        default="",
        description="事件的简短标题，描述这个事件的核心，长度需控制在4-8个汉字或16个字符以内",
        validation_alias=AliasChoices("title", "event_title", "name"),
    )
    description: str = Field(
        default="",
        description="事件的详细描述，说明这个事件的内容",
        validation_alias=AliasChoices("description", "desc", "summary", "reason"),
    )
    start_time: float = Field(
        default=0.0,
        description="完整事件的开始时间（秒数格式）",
        validation_alias=AliasChoices("start_time", "start", "startTime"),
    )
    end_time: float = Field(
        default=0.0,
        description="完整事件的结束时间（秒数格式）",
        validation_alias=AliasChoices("end_time", "end", "endTime"),
    )
    content: str = Field(
        default="",
        description="合并后的完整文本内容（所有相关片段的文本合并）",
        validation_alias=AliasChoices("content", "text", "transcript"),
    )

    # 关键配置：允许额外字段
    model_config = {"extra": "allow"}

    @field_validator("title", "description", "content", mode="before")
    @classmethod
    def _v_str(cls, v):
        return _to_str(v).strip()

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _v_float(cls, v):
        return _to_float(v)

    @model_validator(mode="after")
    def _v_fix(self):
        if not self.title:
            self.title = "事件"
        if not self.content and self.description:
            self.content = self.description
        if self.end_time and self.end_time < self.start_time:
            self.start_time, self.end_time = self.end_time, self.start_time
        if not self.end_time:
            self.end_time = self.start_time
        return self


class OutlineResponse(BaseModel):
    events: List[EventItem] = Field(
        default_factory=list,
        description="事件列表",
        validation_alias=AliasChoices(
            "events", "happy_events", "outline", "items", "data", "results"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _v_coerce_container(cls, data):
        if isinstance(data, list):
            return {"events": data}
        if not isinstance(data, dict):
            return {"events": []}
        if isinstance(data.get("events"), list):
            return data
        # 有些模型会把 events 藏在某个字段里，找一个“值是 list”的字段兜底
        for k in ("happy_events", "outline", "items", "data", "results"):
            if isinstance(data.get(k), list):
                return {"events": data.get(k)}
        for v in data.values():
            if isinstance(v, list):
                return {"events": v}
        return {"events": []}


class HighlightResponse(BaseModel):
    is_highlight: bool = Field(
        default=False,
        description="是否是值得纪念的事件",
        validation_alias=AliasChoices("is_highlight", "highlight", "is_memorable"),
    )
    reason: str = Field(
        default="",
        description="筛选原因，说明为什么这个事件值得纪念",
        validation_alias=AliasChoices("reason", "reason_text", "why", "summary"),
    )

    @field_validator("is_highlight", mode="before")
    @classmethod
    def _v_bool(cls, v):
        return _to_bool(v)

    @field_validator("reason", mode="before")
    @classmethod
    def _v_reason(cls, v):
        return _to_str(v).strip()

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

def track_to_csv(csv_filename: str = 'result/process_log.csv'):
    """装饰器：确保process方法执行后无论成功失败都写入CSV文件"""
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
