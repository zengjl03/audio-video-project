import os
from dotenv import load_dotenv
load_dotenv()
from loguru import logger
from core.utils import AnalyzerAPIModelConfig,AnalyzerLocalModelConfig
import json
from core.prompts.llm_prompt import system_prompt

class AnalyzerManager:
    def __init__(self, config: AnalyzerAPIModelConfig | AnalyzerLocalModelConfig):
        self.config = config

    def analyze(self, text):
        if isinstance(self.config, AnalyzerAPIModelConfig):
            return self._analyze_api(text)
        elif isinstance(self.config, AnalyzerLocalModelConfig):
            return self._analyze_llm(text)
    
    def _analyze_api(self, text):
        base_url,api_key,model_name = self.config.base_url,self.config.api_key,self.config.model_name

        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        prompt = system_prompt.replace('{Transcription}',text)
        
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
        try:
            result = json.loads(raw_content)
            return result.get("highlights", [])
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            print(f"原始内容: {raw_content}")  # 方便调试查看具体错误内容
            return []

    def _analyze_llm(self, text):
        from core.llm import get_qwen_model
        
        qwen_model = get_qwen_model(self.config.model_name)
        content = qwen_model.chat(system_prompt.replace('{Transcription}', text))
        logger.info(f'llm analyze response: {content.get("response")}')
        try:
            result = json.loads(content.get("response"))
            return result.get("highlights", [])
        except Exception as e:
            logger.warning(f"LLM解析结果异常: {e}")
            return []