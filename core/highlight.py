import os
import time
from dotenv import load_dotenv
load_dotenv()
from loguru import logger
from core.utils import AnalyzerAPIModelConfig,AnalyzerLocalModelConfig
from typing import Literal
import json

class AnalyzerManager:
    def __init__(self, config: AnalyzerAPIModelConfig | AnalyzerLocalModelConfig):
        self.config = config
        self.max_retries = 3

    def analyze(self, text, mode:Literal["outline","highlight"] = "highlight"):
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if isinstance(self.config, AnalyzerAPIModelConfig):
                    return self._analyze_api(text, mode)
                elif isinstance(self.config, AnalyzerLocalModelConfig):
                    return self._analyze_llm(text, mode)
            except Exception as exc:
                last_error = exc
                logger.exception(
                    f"analyze 第 {attempt} 次尝试失败，剩余重试次数 {self.max_retries - attempt}"
                )
                if attempt < self.max_retries:
                    time.sleep(0.5)
        raise last_error

    def _build_full_input(self, text, mode:Literal["outline","highlight"] = "highlight"):
        if mode == "outline":
            prompt_path = self.config.prompt_config.outline_prompt
        elif mode == "highlight":
            prompt_path = self.config.prompt_config.highlight_prompt
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt = f.read()
        if text:
            if isinstance(text, dict):
                return f"{prompt}\n\n输入内容：\n{json.dumps(text, ensure_ascii=False, indent=2)}"
            else:
                return f"{prompt}\n\n输入内容：\n{text}"
        return prompt
    
    def _analyze_api(self, text, mode:Literal["outline","highlight"] = "highlight"):
        base_url,api_key,model_name = self.config.base_url,self.config.api_key,self.config.model_name

        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        prompt = self._build_full_input(text, mode)
        
        # 调用 API（使用 JSON 模式强制结构化输出）
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.7,
            response_format={"type": "json_object"},  # 强制返回 JSON 格式
            messages=[
                {"role": "user", "content": prompt}  # 你的 system_prompt 已经包含完整指令，无需额外系统消息
            ]
        )
        # 提取并清洗响应内容（关键改进点）
        raw_content = response.choices[0].message.content.strip()
        logger.info(f'llm analyze response: {raw_content}')
        return raw_content

    def _analyze_llm(self, text, mode:Literal["outline","highlight"] = "highlight"):
        from core.llm import get_qwen_model
        prompt = self._build_full_input(text, mode)

        qwen_model = get_qwen_model(self.config.model_name)
        content = qwen_model.chat(prompt)
        logger.info(f'llm analyze response: {content.get("response")}')
        return content