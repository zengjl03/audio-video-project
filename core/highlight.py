from pydantic import ValidationError
import time
from dotenv import load_dotenv
from loguru import logger
from core.utils import AnalyzerAPIModelConfig, AnalyzerLocalModelConfig
from typing import Literal, Any, TypedDict
import json
from openai import OpenAI
from functools import lru_cache
from core.utils import OutlineResponse, HighlightResponse
import re

load_dotenv()

AnalyzeModeLiteral = Literal["outline", "highlight"]


class AnalyzeModeConfig(TypedDict):
    prompt_attr: str
    model_name_attr: str
    response_model: type | None


MODE_CONFIG: dict[AnalyzeModeLiteral, AnalyzeModeConfig] = {
    "outline": {
        "prompt_attr": "outline_prompt",
        "model_name_attr": "outline_model_name",
        "response_model": OutlineResponse,
    },
    "highlight": {
        "prompt_attr": "highlight_prompt",
        "model_name_attr": "highlight_model_name",
        "response_model": HighlightResponse,
    },
}


class AnalyzerManager:
    def __init__(self, config: AnalyzerAPIModelConfig | AnalyzerLocalModelConfig):
        self.config = config
        self.max_retries = 3

    def analyze_outline(self, text: Any):
        return self._analyze(text, "outline")

    def analyze_highlight(self, text: Any):
        return self._analyze(text, "highlight")

    def _analyze(self, text: Any, mode: AnalyzeModeLiteral):
        mode_cfg = MODE_CONFIG[mode]
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                if isinstance(self.config, AnalyzerAPIModelConfig):
                    return self._analyze_api(text, mode_cfg)
                else:
                    return self._analyze_llm(text, mode_cfg)
            except Exception as exc:  # pragma: no cover - 防御性日志
                last_error = exc
                logger.exception(
                    f"analyze[{mode}] 第 {attempt} 次尝试失败，剩余重试次数 {self.max_retries - attempt}"
                )
                if attempt < self.max_retries:
                    time.sleep(0.5)

        if last_error is not None:
            raise last_error
        raise RuntimeError("analyze 失败且未捕获到异常")

    @lru_cache
    def _load_system_prompt(self, prompt_path) -> str:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _create_openai_client(self) -> OpenAI:
        """创建 OpenAI 客户端"""
        return OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
        )

    def _parse_json(self, content: str) -> dict:
        """解析 JSON 内容，处理常见格式问题"""
        # 提取 markdown 代码块中的 JSON
        json_match = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        # 清洗格式问题
        cleaned = content.strip()
        cleaned = re.sub(r",\s*[}\]](?=\s*$)", "", cleaned)  # 移除末尾多余逗号
        cleaned = re.sub(r'"(start_time|end_time)":\s*"([0-9.]+)"', r'"\1": \2', cleaned)  # 修复时间字段类型
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败，返回空结构")
            return {}
    
    def _fix_parsed_json(self, parsed_json: dict, response_model: type) -> dict:
        """修复解析后的 JSON，确保符合 Pydantic 模型要求"""
        if response_model == OutlineResponse:
            if not isinstance(parsed_json, dict):
                parsed_json = {}
            # 确保 events 字段存在且是列表
            if "events" not in parsed_json:
                parsed_json["events"] = []
            elif not isinstance(parsed_json["events"], list):
                parsed_json["events"] = []
            # 修复每个 event 的字段
            for event in parsed_json["events"]:
                if isinstance(event, dict):
                    # 确保时间字段是数字类型
                    for time_key in ["start_time", "end_time"]:
                        if time_key in event and isinstance(event[time_key], str):
                            try:
                                event[time_key] = float(event[time_key])
                            except (ValueError, TypeError):
                                event[time_key] = 0.0
        elif response_model == HighlightResponse:
            if not isinstance(parsed_json, dict):
                parsed_json = {}
            parsed_json.setdefault("is_highlight", False)
            parsed_json.setdefault("reason", "")
        return parsed_json

    def _analyze_api(self, text, cfg):
        """
        使用 OpenAI 客户端直接调用，采用 json_object 模式 + Pydantic 验证
        这是更简单可靠的方案，避免 json_schema 的复杂性
        """
        response_model = cfg["response_model"]
        model_name = getattr(self.config.model_name_config, cfg["model_name_attr"])
        prompt_path = getattr(self.config.prompt_config, cfg["prompt_attr"])
        
        # 构建消息
        system_prompt = self._load_system_prompt(prompt_path)
        user_content = json.dumps(text, ensure_ascii=False, indent=2)
        
        client = self._create_openai_client()
        
        # 使用 json_object 模式（简单可靠，兼容性好）
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=4096,
        )
        
        # 提取响应内容
        raw_content = response.choices[0].message.content
        if not raw_content or not raw_content.strip():
            logger.warning("API 返回空内容，使用默认值")
            return self._get_default_response(response_model)
        
        # 解析 JSON
        try:
            parsed_json = json.loads(raw_content.strip())
        except json.JSONDecodeError:
            parsed_json = self._parse_json(raw_content)
        
        # 修复常见问题
        parsed_json = self._fix_parsed_json(parsed_json, response_model)
        
        # 验证并转换为 Pydantic 模型
        try:
            return response_model.model_validate(parsed_json)
        except ValidationError as e:
            logger.error(f"Pydantic 验证失败: {e.errors()}")
            # 最后尝试：返回默认响应
            return self._get_default_response(response_model)
    
    def _get_default_response(self, response_model: type):
        """获取默认响应"""
        if response_model == OutlineResponse:
            return OutlineResponse(events=[])
        elif response_model == HighlightResponse:
            return HighlightResponse(is_highlight=False, reason="解析失败")
        raise ValueError(f"无法为 {response_model.__name__} 创建默认响应")

    # ========== 本地 LLM 模式 ==========
    def _analyze_llm(
        self, text: Any, cfg: AnalyzeModeConfig
    ) -> Any:
        """
        本地 LLM 模式（待实现）
        """
        raise NotImplementedError("本地 LLM 模式尚未实现")