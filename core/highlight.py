from pydantic import BaseModel, Field
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
        )
    
    def _analyze_api(self,text,cfg):
        agent = create_agent(
            model = self._create_llm(cfg),
            tools = [],
            response_format = cfg["response_model"],
        )

        res = agent.invoke({'messages':self._build_messages(text,cfg)})
        return res["structured_response"]

    # ========== 本地 LLM 模式 ==========
    def _analyze_llm(
        self, text: Any, mode: AnalyzeModeLiteral, mode_cfg: AnalyzeModeConfig
    ) -> Any:
        ...