"""
LLM 客户端封装

基于 langchain-openai 的 ChatOpenAI，兼容智谱 ChatGLM 的 OpenAI 协议。
通过环境变量 OPEN_AI_API_KEY / OPEN_AI_API_BASE_URL 配置。
"""

import logging
import os

from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# 默认模型配置
DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_TIMEOUT = 30


def get_llm(model: str = None, temperature: float = None, **kwargs) -> ChatOpenAI:
    """
    获取 ChatOpenAI 实例

    Args:
        model: 模型名称，默认 Qwen/Qwen3-8B
        temperature: 温度参数，默认 0.2
        **kwargs: 其他传递给 ChatOpenAI 的参数

    Returns:
        ChatOpenAI 实例
    """
    api_key = os.getenv("OPEN_AI_API_KEY")
    base_url = os.getenv("OPEN_AI_API_BASE_URL")

    if not api_key:
        raise ValueError("环境变量 OPEN_AI_API_KEY 未配置")
    if not base_url:
        raise ValueError("环境变量 OPEN_AI_API_BASE_URL 未配置")

    return ChatOpenAI(
        model=model or os.getenv("LLM_MODEL", DEFAULT_MODEL),
        temperature=temperature if temperature is not None else DEFAULT_TEMPERATURE,
        openai_api_key=api_key,
        openai_api_base=base_url,
        request_timeout=int(os.getenv("LLM_TIMEOUT", DEFAULT_TIMEOUT)),
        **kwargs,
    )
