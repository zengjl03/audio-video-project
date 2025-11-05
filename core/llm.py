"""
Qwen3 多轮对话模型封装
支持历史会话、系统提示词、无思考模式
"""
import os
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

llm_model = os.getenv("LLM_MODEL")

if llm_model is None:
    raise ValueError("LLM_MODEL is not set")

model_map = {
    "qwen3-4b": "Qwen/Qwen3-4B",
    "qwen2.5-14b": "Qwen/Qwen2.5-14B-Instruct",
    "qwen2.5-14b-gptq-int4": "Qwen/Qwen2.5-14B-Instruct-GPTQ-Int4",
}

class QwenChatModel:
    def __init__(
        self,
        model_name: str | None,
        device_map: str = "auto",
        torch_dtype: str = "auto"
    ):
        if model_name is None:
            raise ValueError("model_name is required")
        logger.info(f"正在加载模型: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map
        )
        logger.info("模型加载完成")

    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 32768,
        enable_thinking: bool = False,
        **generate_kwargs
    ) -> Dict[str, str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=max_new_tokens,
            **generate_kwargs
        )
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        thinking_content = ""
        if enable_thinking:
            try:
                index = len(output_ids) - output_ids[::-1].index(151668)
                thinking_content = self.tokenizer.decode(
                    output_ids[:index], 
                    skip_special_tokens=True
                ).strip()
            except ValueError:
                index = 0
        else:
            index = 0
        response = self.tokenizer.decode(
            output_ids[index:], 
            skip_special_tokens=True
        ).strip()
        return {
            "response": response,
            "thinking": thinking_content
        }

    def build_history(
        self,
        history: Optional[List[Dict[str, str]]] = None,
        user_msg: str = None,
        assistant_msg: str = None
    ) -> List[Dict[str, str]]:
        if history is None:
            history = []
        
        if user_msg:
            history.append({"role": "user", "content": user_msg})
        if assistant_msg:
            history.append({"role": "assistant", "content": assistant_msg})
        
        return history

_qwen_model: Optional[QwenChatModel] = None

def get_qwen_model() -> QwenChatModel:
    global _qwen_model
    if _qwen_model is None:
        _qwen_model = QwenChatModel(model_name=model_map[llm_model])
    return _qwen_model