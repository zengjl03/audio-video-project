from pydantic import BaseModel, Field, ValidationError
import time
from dotenv import load_dotenv
from loguru import logger
from core.utils import AnalyzerAPIModelConfig, AnalyzerLocalModelConfig
from typing import Literal, List, Dict, Any, TypedDict
import json
from langchain_openai import ChatOpenAI
from functools import lru_cache
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain.agents import create_agent
from core.utils import OutlineResponse, HighlightResponse
from langchain_core.utils.json import parse_json_markdown
import re

load_dotenv()

AnalyzeModeLiteral = Literal["outline", "highlight"]


class AnalyzeModeConfig(TypedDict):
    prompt_attr: str
    model_name_attr: str
    response_model: type | None


MODE_CONFIG: Dict[AnalyzeModeLiteral, AnalyzeModeConfig] = {
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

    def _build_messages(
        self, text, cfg
    ) -> List[BaseMessage]:
        prompt_path = getattr(self.config.prompt_config, cfg["prompt_attr"])
        system_message = SystemMessage(content=self._load_system_prompt(prompt_path))
        human_message = HumanMessage(
            content=json.dumps(text, ensure_ascii=False, indent=2)
        )
        return [system_message, human_message]

    @lru_cache
    def _load_system_prompt(self, prompt_path) -> str:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _create_llm(self, cfg) -> ChatOpenAI:
        model_name = getattr(
            self.config.model_name_config, cfg["model_name_attr"]
        )
        return ChatOpenAI(
            model=model_name,
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            response_format={"type": "json_object"},
            temperature=0.0,  # 极低温度，避免模型创意性输出格式错误
            max_tokens=8000,   # 足够的输出长度，避免JSON截断
        )

    def _clean_and_fix_json(self, raw_str: str) -> dict:
        """清洗并修复模型返回的JSON字符串（解决偶发解析问题）"""
        if isinstance(raw_str, dict):
            return raw_str
        
        # 步骤1：提取markdown代码块内的JSON
        json_match = re.search(r"```(?:json)?\s*(.+?)\s*```", raw_str, re.DOTALL)
        if json_match:
            raw_str = json_match.group(1)
        
        # 步骤2：清洗常见格式问题
        cleaned = raw_str.strip()
        cleaned = re.sub(r",\s*}", "}", cleaned)  # 移除末尾多余逗号
        cleaned = re.sub(r",\s*]", "]", cleaned)
        cleaned = cleaned.replace("：", ":").replace("，", ",").replace("（", "(").replace("）", ")")  # 全角转半角
        cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)  # 移除不可见字符
        # 强制start_time/end_time为数字（修复字符串类型问题）
        cleaned = re.sub(r'"(start_time|end_time)":\s*"([0-9.]+)"', r'"\1": \2', cleaned)

        # 步骤3：容错解析
        try:
            return parse_json_markdown(cleaned)  # LangChain内置鲁棒解析
        except:
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                logger.error(f"JSON解析失败，返回空结构 | 原始内容：{raw_str[:200]}")
                return {"events": []}

    def _analyze_api(self,text,cfg):
        agent = create_agent(
            model = self._create_llm(cfg),
            tools = []
        )

        try:
            # 调用Agent
            res = agent.invoke({'messages': self._build_messages(text, cfg)})
            
            ai_message = None
            # 方式1：按类型筛选（最可靠）
            from langchain_core.messages import AIMessage
            for msg in res.get("messages", []):
                if isinstance(msg, AIMessage):
                    ai_message = msg
                    break
            # 方式2：兜底取最后一个消息（兼容所有情况）
            if ai_message is None and res.get("messages"):
                ai_message = res["messages"][-1]
            
            if not ai_message:
                raise ValueError("响应中未找到 AIMessage")
            
            # 步骤2：提取 AIMessage 的 content（模型返回的 JSON 字符串）
            raw_json_str = ai_message.content.strip()
            if not raw_json_str:
                raise ValueError("AIMessage.content 为空")
            
            # 步骤2：清洗并修复JSON
            cleaned_json = self._clean_and_fix_json(raw_json_str)
            response_model = cfg["response_model"]
            
            # 步骤3：解析为目标Pydantic模型
            try:
                validated_resp = response_model.model_validate(cleaned_json)
                return validated_resp
            except ValidationError as e:
                logger.error(f"解析{response_model.__name__}失败 | 错误：{e.errors()} | JSON：{cleaned_json}")
                # 兜底：返回空的合规模型
                return response_model(events=[]) if response_model == OutlineResponse else response_model()
        
        except Exception as e:
            logger.error(f"analyze_api失败: {str(e)}", exc_info=True)
            raise e

    # ========== 本地 LLM 模式 ==========
    def _analyze_llm(
        self, text: Any, mode: AnalyzeModeLiteral, mode_cfg: AnalyzeModeConfig
    ) -> Any:
        ...