from pydantic import ValidationError
import time
from dotenv import load_dotenv
from loguru import logger
from core.utils import AnalyzerAPIModelConfig, AnalyzerLocalModelConfig
from typing import Literal, Any, TypedDict
import json
import re
from openai import OpenAI
from functools import lru_cache
from core.utils import OutlineResponse, HighlightResponse

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

    def _loads_json(self, raw_content: str) -> Any:
        s = raw_content.strip()
        if not s:
            return None
        if s.startswith("```"):
            s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
            s = re.sub(r"\s*```$", "", s)
            s = s.strip()
        if s == "null":
            return None
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return None

    def _analyze_api(self, text, cfg):
        """
        使用 OpenAI 客户端直接调用，采用 json_object 模式 + Pydantic 验证
        这是更简单可靠的方案，避免 json_schema 的复杂性
        """
        response_model = cfg["response_model"]
        model_name = getattr(self.config.model_name_config, cfg["model_name_attr"])
        prompt_path = getattr(self.config.prompt_config, cfg["prompt_attr"])

        if response_model is None:
            raise ValueError("response_model 不能为空")
        if not model_name:
            logger.error("未配置模型名称，将使用默认值")
            return self._get_default_response(response_model)
        if not prompt_path:
            logger.error("未配置 prompt 路径，将使用默认值")
            return self._get_default_response(response_model)
        
        # 构建消息（在系统提示中直接加入 JSON 约束，既满足 OpenAI 要求又保持简洁）
        base_system_prompt = self._load_system_prompt(prompt_path)
        json_constraint = (
            "你必须仅输出一个 JSON 对象（json），"
            "不要包含额外文本、说明、注释或代码块标记（例如 ```json）。"
        )
        system_prompt = f"{base_system_prompt.rstrip()}\n\n附加要求（必须遵守）：\n{json_constraint}"
        user_content = json.dumps(text, ensure_ascii=False, indent=2)
        
        client = self._create_openai_client()
        
        # 使用 json_object 模式（简单可靠，兼容性好）
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=1.0,
            max_tokens=4096,
        )
        
        # 提取响应内容
        raw_content = response.choices[0].message.content
        if not raw_content or not raw_content.strip():
            logger.warning("API 返回空内容，使用默认值")
            return self._get_default_response(response_model)
        
        # 解析 JSON
        parsed_json = self._loads_json(raw_content)
        if parsed_json is None:
            logger.error("JSON 解析失败或返回 null，将使用默认值")
            return self._get_default_response(response_model)

        # 验证并转换为 Pydantic 模型，失败就回退到默认值
        try:
            return response_model.model_validate(parsed_json)
        except ValidationError as e:
            logger.error(f"Pydantic 验证失败，将使用默认值: {e.errors()}")
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