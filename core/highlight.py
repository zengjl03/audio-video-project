import os
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
        base_url = os.getenv('BASE_URL')
        api_key = os.getenv('OPENAI_API_KEY')
        model_name = os.getenv('OPENAI_MODEL_NAME')
        
        # 导入系统提示词
        from core.prompts.llm_prompt import system_prompt
        from openai import OpenAI
        import json
        
        # 初始化 OpenAI 客户端
        client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        # 构建提示词（替换模板变量）
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
        
        # 移除可能的多余前缀/后缀（比如意外的空行、空格）
        if raw_content.startswith('{') and raw_content.endswith('}'):
            cleaned_content = raw_content
        else:
            # 尝试提取 JSON 结构（处理模型偶尔的格式错误）
            start_idx = raw_content.find('{')
            end_idx = raw_content.rfind('}')
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                cleaned_content = raw_content[start_idx:end_idx+1]
            else:
                print("响应中未找到有效的 JSON 结构")
                return []
        
        # 解析 JSON
        try:
            result = json.loads(cleaned_content)
            return result.get("highlights", [])
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}")
            print(f"原始内容: {cleaned_content}")  # 方便调试查看具体错误内容
            return []

    def _analyze_llm(self, text):
        from core.llm import get_qwen_model
        import json
        from core.prompts.llm_prompt import system_prompt
        qwen_model = get_qwen_model()
        content = qwen_model.chat(system_prompt.replace('{Transcription}', text))
        logger.info(f'llm analyze response: {content.get("response")}')
        try:
            result = json.loads(content.get("response"))
            return result.get("highlights", [])
        except Exception as e:
            logger.warning(f"LLM解析结果异常: {e}")
            return []


if __name__ == "__main__":
    analyzer = AnalyzerManager(mode='local')
    print(analyzer.analyze("""[0.00 - 10.19] 你好，我有一个帽衫，我要在网上问问问，啊，问什么别人的帽衫穿上帽子大大的。
[10.19 - 18.84] 漂漂亮亮的。嗯，那女的呢？我的车上你给我，你看看啊。嗯。
[18.84 - 28.53] 因为我的帽衫穿上之后，像个大耳朵矮人，显得很忠诚。
[28.53 - 36.05] 想欺负你，我等会帮你把“歇夫虐”的图贴上啊，OK吗？
[36.05 - 46.43] OK，你问出了我的疑问，我唱完也这样。到底怎么买到大帽子帽衫？挺着急的。"""))