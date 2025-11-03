import os
import logging
from dotenv import load_dotenv
from typing import Literal
load_dotenv()
from loguru import logger
class AnalyzerManager:
    def __init__(self, mode=Literal['api', 'local']):
        self.mode = mode

    def analyze(self, text):
        m = self.mode
        if m == 'api':
            return self._analyze_api(text)
        elif m == 'local':
            return self._analyze_llm(text)
        else:
            raise ValueError(f'Unknown analyze mode: {m}')
    
    def _analyze_api(self, text):
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from pydantic import BaseModel, Field
            from typing import List
            base_url = os.getenv('BASE_URL')
            api_key = os.getenv('OPENAI_API_KEY')
            model_name = os.getenv('OPENAI_MODEL_NAME')
            class Clip(BaseModel):
                start: float = Field(description="片段的开始时间")
                end: float = Field(description="片段的结束时间")
                content: str = Field(description="内容")
            class HighlightsResponse(BaseModel):
                highlights: List[Clip] = Field(description="片段列表")
            
            system_prompt = ""

            llm = ChatOpenAI(
                base_url=base_url, api_key=api_key, model=model_name, temperature=0.7
            )
            prompt = ChatPromptTemplate.from_template(system_prompt)
            chain = prompt | llm.with_structured_output(HighlightsResponse, method="json_mode")
            response = chain.invoke({"Transcription": text})
            return response.highlights
        except Exception as e:
            logger.error(f'API analyze failed: {e}')
            return []

    def _analyze_llm(self, text):
        try:
            from core.llm import Qwen3ChatModel
            import json
            from core.prompts.llm_prompt import system_prompt
            qwen3_model = Qwen3ChatModel(model_name="Qwen/Qwen3-4B")
            content = qwen3_model.chat(system_prompt.replace('{Transcription}', text))
            logger.info(f'llm analyze response: {content.get("response")}')
            try:
                result = json.loads(content.get("response"))
                return result.get("highlights", [])
            except Exception as e:
                logger.warning(f"LLM解析结果异常: {e}")
                return []
        except Exception as e:
            logger.error(f'LLM analyze failed: {e}')
            return []


if __name__ == "__main__":
    analyzer = AnalyzerManager(mode='local')
    print(analyzer.analyze("""[0.00 - 10.19] 你好，我有一个帽衫，我要在网上问问问，啊，问什么别人的帽衫穿上帽子大大的。
[10.19 - 18.84] 漂漂亮亮的。嗯，那女的呢？我的车上你给我，你看看啊。嗯。
[18.84 - 28.53] 因为我的帽衫穿上之后，像个大耳朵矮人，显得很忠诚。
[28.53 - 36.05] 想欺负你，我等会帮你把“歇夫虐”的图贴上啊，OK吗？
[36.05 - 46.43] OK，你问出了我的疑问，我唱完也这样。到底怎么买到大帽子帽衫？挺着急的。"""))