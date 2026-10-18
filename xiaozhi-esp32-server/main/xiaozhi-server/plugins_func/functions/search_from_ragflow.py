import requests
import sys
from config.logger import setup_logging
from plugins_func.register import register_function, ToolType, ActionResponse, Action
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = __name__
logger = setup_logging()

# 面向学生的兜底话术：只描述“这次没查到”，绝不透露接口名、错误码、
# 服务地址或“请检查RAGflow服务状态”这类运维信息——这些内容会被 TTS
# 念出来并显示在设备字幕上。详细原因只写服务端日志，见 _log_failure。
STUDENT_FALLBACK_REPLY = "这个知识点我这边暂时没查到，换个说法再问我一次，或者问问现场的老师。"


def _log_failure(kind: str, detail: str) -> None:
    """把接口级细节只写进服务端日志，不再交给 TTS"""
    logger.bind(tag=TAG).error(f"RAGflow {kind}: {detail}")

# 定义基础的函数描述模板
SEARCH_FROM_RAGFLOW_FUNCTION_DESC = {
    "type": "function",
    "function": {
        "name": "search_from_ragflow",
        "description": "从知识库中查询信息",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string", "description": "查询的问题"}},
            "required": ["question"],
        },
    },
}


@register_function(
    "search_from_ragflow", SEARCH_FROM_RAGFLOW_FUNCTION_DESC, ToolType.SYSTEM_CTL
)
def search_from_ragflow(conn: "ConnectionHandler", question=None):
    # 确保字符串参数正确处理编码
    if question and isinstance(question, str):
        # 确保问题参数是UTF-8编码的字符串
        pass
    else:
        question = str(question) if question is not None else ""

    ragflow_config = conn.config.get("plugins", {}).get("search_from_ragflow", {})
    base_url = ragflow_config.get("base_url", "")
    api_key = ragflow_config.get("api_key", "")
    dataset_ids = ragflow_config.get("dataset_ids", [])

    url = base_url + "/api/v1/retrieval"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # 确保payload中的字符串都是UTF-8编码
    payload = {"question": question, "dataset_ids": dataset_ids}

    try:
        # 使用ensure_ascii=False确保JSON序列化时正确处理中文
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=5,
            verify=False,
        )

        # 显式设置响应的编码为utf-8
        response.encoding = "utf-8"

        response.raise_for_status()

        # 先获取文本内容，然后手动处理JSON解码
        response_text = response.text
        import json

        result = json.loads(response_text)

        if result.get("code") != 0:
            error_detail = result.get("error", {}).get("detail", "未知错误")
            error_message = result.get("error", {}).get("message", "")
            error_code = result.get("code", "")

            # 细节只写日志；返回 Action.RESPONSE 会被 _handle_function_result
            # 直接拿去 TTS 播报，所以这里只能给学生话术，不能给运维话术
            _log_failure(
                "接口返回错误",
                f"响应码={error_code} 错误信息={error_message} 详情={error_detail}",
            )
            return ActionResponse(Action.RESPONSE, None, STUDENT_FALLBACK_REPLY)

        chunks = result.get("data", {}).get("chunks", [])
        contents = []
        for chunk in chunks:
            content = chunk.get("content", "")
            if content:
                # 安全地处理内容字符串
                if isinstance(content, str):
                    contents.append(content)
                elif isinstance(content, bytes):
                    contents.append(content.decode("utf-8", errors="replace"))
                else:
                    contents.append(str(content))

        if contents:
            # 组织知识库内容为引用模式
            logger.bind(tag=TAG).info(f"RAGFlow知识库查询成功，问题：{question}，返回 {len(contents)} 个chunks，取前 {min(len(contents), 5)} 个")
            context_text = f"# 关于问题【{question}】查到知识库如下\n"
            context_text += "```\n\n\n".join(contents[:5])
            context_text += "\n```"
        else:
            logger.bind(tag=TAG).info(f"RAGFlow知识库查询成功但无结果，问题：{question}")
            context_text = "根据知识库查询结果，没有相关信息。"
        return ActionResponse(Action.REQLLM, context_text, None)

    except requests.exceptions.RequestException as e:
        # 网络请求异常：按类型给出运维排查提示，但全部只进日志
        error_type = type(e).__name__
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        _log_failure(
            "网络请求失败",
            f"异常类型={error_type} 状态码={status_code} 详情={e}",
        )
        return ActionResponse(Action.RESPONSE, None, STUDENT_FALLBACK_REPLY)

    except Exception as e:
        # 其他异常（JSON 解析失败等）
        error_type = type(e).__name__
        _log_failure("处理异常", f"异常类型={error_type} 详情={e}")
        return ActionResponse(Action.RESPONSE, None, STUDENT_FALLBACK_REPLY)
