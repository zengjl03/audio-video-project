"""
Qwen3 多轮对话模型封装
支持历史会话、系统提示词、无思考模式
"""
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import List, Dict, Optional


class Qwen3ChatModel:
    """Qwen3 对话模型（支持多轮对话）"""
    
    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-4B",
        device_map: str = "auto",
        torch_dtype: str = "auto"
    ):
        """
        初始化模型（只加载一次）
        
        Args:
            model_name: 模型名称
            device_map: 设备映射
            torch_dtype: 数据类型
        """
        print(f"正在加载模型: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map
        )
        print("模型加载完成")
    
    def chat(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        max_new_tokens: int = 32768,
        enable_thinking: bool = False,
        **generate_kwargs
    ) -> Dict[str, str]:
        """
        多轮对话接口
        
        Args:
            prompt: 用户输入
            history: 历史对话 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
            system_prompt: 系统提示词
            max_new_tokens: 最大生成 token 数
            enable_thinking: 是否启用思考模式（默认 False，不思考）
            **generate_kwargs: 其他生成参数
        
        Returns:
            {
                "response": "模型回复",
                "thinking": "思考内容"  # 仅当 enable_thinking=True 时有值
            }
        """
        # 构建消息列表
        messages = []
        
        # 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 添加历史对话
        if history:
            messages.extend(history)
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": prompt})
        
        # 应用对话模板
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=enable_thinking
        )
        
        # 编码输入
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        
        # 生成回复
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=max_new_tokens,
            **generate_kwargs
        )
        
        # 提取新生成的 token
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        
        # 解析思考内容（仅当启用思考模式时）
        thinking_content = ""
        if enable_thinking:
            try:
                # 查找 </think> 标记（token_id: 151668）
                index = len(output_ids) - output_ids[::-1].index(151668)
                thinking_content = self.tokenizer.decode(
                    output_ids[:index], 
                    skip_special_tokens=True
                ).strip()
            except ValueError:
                index = 0
        else:
            index = 0
        
        # 解析回复内容
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
        """
        便捷方法：构建历史对话列表
        
        Args:
            history: 现有历史
            user_msg: 用户消息
            assistant_msg: 助手消息
        
        Returns:
            更新后的历史列表
        """
        if history is None:
            history = []
        
        if user_msg:
            history.append({"role": "user", "content": user_msg})
        if assistant_msg:
            history.append({"role": "assistant", "content": assistant_msg})
        
        return history

_qwen3_model: Optional[Qwen3ChatModel] = None

def get_qwen3_model() -> Qwen3ChatModel:
    """获取全局LLM管理器实例"""
    global _qwen3_model
    if _qwen3_model is None:
        _qwen3_model = Qwen3ChatModel(model_name="Qwen/Qwen3-4B")
    return _qwen3_model