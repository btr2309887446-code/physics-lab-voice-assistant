from config.logger import setup_logging
from openai import OpenAI
import json
from core.providers.llm.base import LLMProviderBase

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.base_url = config.get("base_url", "http://localhost:11434")
        # Initialize OpenAI client with Ollama base URL
        # 如果没有v1，增加v1
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

        self.client = OpenAI(
            base_url=self.base_url,
            api_key="ollama",  # Ollama doesn't need an API key but OpenAI client requires one
        )

        # 检查是否是qwen3模型（/no_think 软切换是 Qwen3 专属训练指令）
        self.is_qwen3 = self.model_name and self.model_name.lower().startswith("qwen3")
        # 检查是否是 GLM 系列模型（Ollama >= 0.12 通过 API "think": false 关闭思考，
        # GLM 不认识 /no_think；经 OpenAI 兼容层用 extra_body 传入）
        self.is_glm = self.model_name and self.model_name.lower().startswith("glm")

    def _apply_think_control(self, dialogue):
        """思考模式控制：按模型家族选择关闭思考的机制，返回处理后的对话副本"""
        if self.is_qwen3:
            # qwen3：在最后一条用户消息前添加 /no_think 指令
            dialogue_copy = dialogue.copy()
            for i in range(len(dialogue_copy) - 1, -1, -1):
                if dialogue_copy[i]["role"] == "user":
                    dialogue_copy[i]["content"] = (
                        "/no_think " + dialogue_copy[i]["content"]
                    )
                    logger.bind(tag=TAG).debug(f"为qwen3模型添加/no_think指令")
                    break
            return dialogue_copy
        return dialogue

    def _create_completion(self, dialogue, functions=None):
        """统一的补全请求构造：GLM 显式关闭思考，其他模型默认行为"""
        kwargs = dict(model=self.model_name, messages=dialogue, stream=True)
        if functions is not None:
            kwargs["tools"] = functions
        if self.is_glm:
            # Ollama >= 0.12 支持 "think": false；旧版本会忽略该字段（不报错，但不生效）
            kwargs["extra_body"] = {"think": False}
        return self.client.chat.completions.create(**kwargs)

    def response(self, session_id, dialogue, **kwargs):
        dialogue = self._apply_think_control(dialogue)
        responses = self._create_completion(dialogue)
        is_active = True
        # 用于处理跨chunk的标签
        buffer = ""

        for chunk in responses:
            try:
                delta = (
                    chunk.choices[0].delta
                    if getattr(chunk, "choices", None)
                    else None
                )
                content = delta.content if hasattr(delta, "content") else ""

                if content:
                    # 将内容添加到缓冲区
                    buffer += content

                    # 处理缓冲区中的标签
                    while "<think>" in buffer and "</think>" in buffer:
                        # 找到完整的<think></think>标签并移除
                        pre = buffer.split("<think>", 1)[0]
                        post = buffer.split("</think>", 1)[1]
                        buffer = pre + post

                    # 处理只有开始标签的情况
                    if "<think>" in buffer:
                        is_active = False
                        buffer = buffer.split("<think>", 1)[0]

                    # 处理只有结束标签的情况
                    if "</think>" in buffer:
                        is_active = True
                        buffer = buffer.split("</think>", 1)[1]

                    # 如果当前处于活动状态且缓冲区有内容，则输出
                    if is_active and buffer:
                        yield buffer
                        buffer = ""  # 清空缓冲区

            except Exception as e:
                logger.bind(tag=TAG).error(f"Error processing chunk: {e}")

    def response_with_functions(self, session_id, dialogue, functions=None):
        dialogue = self._apply_think_control(dialogue)
        stream = self._create_completion(dialogue, functions=functions)

        is_active = True
        buffer = ""

        for chunk in stream:
            try:
                delta = (
                    chunk.choices[0].delta
                    if getattr(chunk, "choices", None)
                    else None
                )
                content = delta.content if hasattr(delta, "content") else None
                tool_calls = (
                    delta.tool_calls if hasattr(delta, "tool_calls") else None
                )

                # 如果是工具调用，直接传递
                if tool_calls:
                    yield None, tool_calls
                    continue

                # 处理文本内容
                if content:
                    # 将内容添加到缓冲区
                    buffer += content

                    # 处理缓冲区中的标签
                    while "<think>" in buffer and "</think>" in buffer:
                        # 找到完整的<think></think>标签并移除
                        pre = buffer.split("<think>", 1)[0]
                        post = buffer.split("</think>", 1)[1]
                        buffer = pre + post

                    # 处理只有开始标签的情况
                    if "<think>" in buffer:
                        is_active = False
                        buffer = buffer.split("<think>", 1)[0]

                    # 处理只有结束标签的情况
                    if "</think>" in buffer:
                        is_active = True
                        buffer = buffer.split("</think>", 1)[1]

                    # 如果当前处于活动状态且缓冲区有内容，则输出
                    if is_active and buffer:
                        yield buffer, None
                        buffer = ""  # 清空缓冲区
            except Exception as e:
                logger.bind(tag=TAG).error(f"Error processing function chunk: {e}")
                continue
