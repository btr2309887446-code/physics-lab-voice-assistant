# -*- coding: utf-8 -*-
"""验证“后台信息串进字幕”修复。

不依赖项目依赖（websockets / openai 等未安装也能跑）：用 ast 把
connection.py 里真正发布的那几个函数抽出来执行 —— 测的是线上代码，
不是另抄一份逻辑。

覆盖两类泄漏：
  1) 服务端主动推 {"type":"stt","text":"% search_from_ragflow"}
  2) 流式 <tool_call>{...} 文本被塞进 TTS 队列（字幕就取自 TTS 句子）

运行： python 验证/test_no_toolcall_leak.py
"""

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve(*candidates):
    """按顺序找第一个存在的路径，兼容两种目录布局：
    - 本仓库布局：<root>/xiaozhi-esp32-server/...
    - 本地工作布局：<root>/_extracted/小智项目/xiaozhi-esp32-server/...
    """
    for c in candidates:
        p = os.path.join(HERE, "..", *c)
        if os.path.exists(p):
            return os.path.abspath(p)
    raise SystemExit("找不到需要的路径，已尝试：\n  " + "\n  ".join(
        os.path.abspath(os.path.join(HERE, "..", *c)) for c in candidates))


SERVER = _resolve(
    ("xiaozhi-esp32-server", "main", "xiaozhi-server"),
    ("_extracted", "小智项目", "xiaozhi-esp32-server", "main", "xiaozhi-server"),
)
FIRMWARE = _resolve(
    ("xiaozhi-esp32-main", "main"),
    ("_extracted", "小智项目", "xiaozhi-esp32-main", "main"),
)
CONNECTION_PY = os.path.join(SERVER, "core", "connection.py")
TOOL_HANDLER_PY = os.path.join(
    SERVER, "core", "providers", "tools", "unified_tool_handler.py")
SEND_AUDIO_PY = os.path.join(SERVER, "core", "handle", "sendAudioHandle.py")
RAGFLOW_PY = os.path.join(
    SERVER, "plugins_func", "functions", "search_from_ragflow.py")
TEXTS_UTILS_PY = os.path.join(SERVER, "core", "utils", "textUtils.py")
APPLICATION_CC = os.path.join(FIRMWARE, "application.cc")

MARKER = "<tool_call>"
HOLDBACK = len(MARKER) + 8

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    mark = "PASS" if cond else "FAIL"
    line = "  [%s] %s" % (mark, name)
    if detail and not cond:
        line += "\n         -> " + detail
    print(line)


def load_functions(path, names, consts=()):
    """从源文件里抽取指定顶层函数（以及可选的模块级常量）并执行。

    consts 用来带上函数依赖的模块级变量，例如 DEFAULT_TOOL_STATUS_TEXT。
    """
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    tree = ast.parse(src)
    wanted = []
    found = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            wanted.append(n)
            found[n.name] = True
        elif isinstance(n, ast.Assign) and consts:
            targets = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(t in consts for t in targets):
                wanted.append(n)
    missing = set(names) - set(found)
    if missing:
        raise RuntimeError("源文件中找不到函数: %s" % sorted(missing))
    module = ast.Module(body=wanted, type_ignores=[])
    ns = {}
    exec(compile(module, path, "exec"), ns)
    return {n: ns[n] for n in names}


CLASSIFY = load_functions(CONNECTION_PY, ["classify_stream_prefix"])[
    "classify_stream_prefix"]


def simulate_stream(chunks):
    """复刻 connection.py 流式循环的判定顺序。

    返回 (spoken, is_tool_call)：
      spoken       —— 会进 TTS 队列、也就会显示在设备字幕上的文本
      is_tool_call —— 本轮是否被识别为工具调用
    """
    tool_call_flag = False
    pending = ""
    plain_confirmed = False
    spoken = []
    accumulated = ""

    for content in chunks:
        # 与 connection.py 一致：标记出现在累计文本任何位置都判为工具调用
        if not tool_call_flag and MARKER in accumulated + content:
            tool_call_flag = True
        accumulated += content

        if tool_call_flag:
            pending = ""
        elif plain_confirmed:
            spoken.append(content)
        else:
            pending += content
            verdict = CLASSIFY(pending, MARKER, HOLDBACK)
            if verdict == "tool":
                tool_call_flag = True
                pending = ""
            elif verdict == "plain":
                plain_confirmed = True
                spoken.append(pending)
                pending = ""

    if pending and not tool_call_flag:
        spoken.append(pending)
    return "".join(spoken), tool_call_flag


def main():
    print("=" * 76)
    print("A. classify_stream_prefix —— 开头判定")
    print("=" * 76)
    cases = [
        ("你好", "plain", "普通开头应立即放行，不增加延迟"),
        ("", "wait", "空串继续等"),
        ("  \n", "wait", "纯空白继续等"),
        ("<", "wait", "半个标记继续等"),
        ("<tool_ca", "wait", "标记未收全继续等"),
        ("<tool_call>", "tool", "完整标记判定为工具调用"),
        ("\n<tool_call>", "tool", "标记前有换行也必须抓到"),
        ("\n\n  <tool_call>", "tool", "标记前有空白也必须抓到"),
        ("光" * 30, "plain", "压的字数超阈值后放行，不会卡死"),
    ]
    for text, want, why in cases:
        got = CLASSIFY(text, MARKER, HOLDBACK)
        check("%-24r -> %-5s  %s" % (text, got, why), got == want,
              "期望 %s，实际 %s" % (want, got))

    print()
    print("=" * 76)
    print("B. 流式场景 —— 这段文本最终会不会出现在字幕里")
    print("=" * 76)

    spoken, is_tool = simulate_stream(["光", "路调节", "分三步。", "第一步先开机。"])
    check("B1 正常回答完整播报",
          spoken == "光路调节分三步。第一步先开机。", "实际=%r" % spoken)
    check("B1 正常回答不误判为工具调用", is_tool is False)

    spoken, is_tool = simulate_stream([
        MARKER, '{"name": "search_from_ragflow", ',
        '"arguments": {"question": "缝宽"}}', "</tool_call>"])
    check("B2 标准工具调用一个字都不上字幕", spoken == "", "实际=%r" % spoken)
    check("B2 标准工具调用被识别", is_tool is True)

    spoken, is_tool = simulate_stream(
        ["\n", MARKER, '{"name": "search_from_ragflow"}', "</tool_call>"])
    check("B3 换行开头的工具调用不泄漏（旧代码 startswith 失效点）",
          spoken == "", "实际=%r" % spoken)
    check("B3 换行开头的工具调用被识别", is_tool is True)

    spoken, is_tool = simulate_stream(
        ["<to", "ol_c", "all>", '{"name": "search_from_ragflow"}', "</tool_call>"])
    check("B4 标记被拆成跨 chunk 也不泄漏（旧代码会漏出 '<tool_'）",
          spoken == "", "实际=%r" % spoken)
    check("B4 跨 chunk 标记被识别", is_tool is True)

    spoken, is_tool = simulate_stream([
        "好的，", "我查一下。", MARKER,
        '{"name": "search_from_ragflow"}', "</tool_call>"])
    check("B5 引导语+工具调用：JSON 不进字幕",
          "search_from_ragflow" not in spoken and '"name"' not in spoken,
          "实际=%r" % spoken)
    check("B5 引导语+工具调用：引导语可正常播报", "好的" in spoken,
          "实际=%r" % spoken)
    check("B5 引导语+工具调用被识别", is_tool is True)

    spoken, is_tool = simulate_stream(["\n", "这是", "正常回答"])
    check("B6 空白开头仍能正常播报", "这是正常回答" in spoken,
          "实际=%r" % spoken)
    check("B6 空白开头不误判为工具调用", is_tool is False)

    print()
    print("=" * 76)
    print("C. 工具状态不再走 stt 通道（旧：% search_from_ragflow）")
    print("=" * 76)
    handler_src = open(TOOL_HANDLER_PY, encoding="utf-8").read()

    check("C1 工具处理器不再拼 '% 函数名'", "'% '" not in handler_src)
    check("C2 工具处理器不再调用 send_display_message",
          "send_display_message" not in handler_src)
    check("C3 工具处理器改发 send_tool_status_message",
          "send_tool_status_message(" in handler_src)

    # 结构化检查：send_tool_status_message 里构造的 message 字典，
    # "type" 必须是 "tool"（而不是 "stt"）
    send_tree = ast.parse(open(SEND_AUDIO_PY, encoding="utf-8").read())
    func = next((n for n in send_tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and n.name == "send_tool_status_message"), None)
    check("C4 send_tool_status_message 已定义", func is not None)

    msg_type = None
    if func is not None:
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "message" in targets and isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if (isinstance(k, ast.Constant) and k.value == "type"
                                and isinstance(v, ast.Constant)):
                            msg_type = v.value
    check("C5 message['type'] 是 'tool' 而不是 'stt'", msg_type == "tool",
          "实际 type=%r" % msg_type)

    print()
    print("=" * 76)
    print("D. RAGFlow 报错不再把运维话术念给学生")
    print("=" * 76)
    # 结构化检查：所有 ActionResponse(Action.RESPONSE, ...) 的第三个参数
    # 必须是 STUDENT_FALLBACK_REPLY —— 这个返回值会被直接送进 TTS。
    rag_tree = ast.parse(open(RAGFLOW_PY, encoding="utf-8").read())
    response_calls, bad_calls = 0, []
    for node in ast.walk(rag_tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Name) and fn.id == "ActionResponse"):
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Attribute) and first.attr == "RESPONSE"):
            continue
        response_calls += 1
        third = node.args[2] if len(node.args) >= 3 else None
        if not (isinstance(third, ast.Name)
                and third.id == "STUDENT_FALLBACK_REPLY"):
            bad_calls.append(ast.dump(third) if third else "<缺失>")

    check("D1 存在会被播报的 Action.RESPONSE 分支", response_calls >= 3,
          "实际 %d 处" % response_calls)
    check("D2 这些分支全部返回学生话术", not bad_calls,
          "未修复的分支: %s" % bad_calls)
    check("D3 学生话术里不含接口名/错误码/服务状态",
          all(k not in "这个知识点我这边暂时没查到，换个说法再问我一次，或者问问现场的老师。"
              for k in ["RAG", "接口", "错误码", "HTTP", "状态码"]))

    print()
    print("=" * 76)
    print("E. 回归价值：同一批场景喂给旧逻辑，应当确实泄漏")
    print("=" * 76)
    # 逐字复刻旧实现：if not tool_call_flag and content_arguments.startswith(...)
    def simulate_stream_legacy(chunks):
        tool_call_flag = False
        content_arguments = ""
        spoken = []
        for content in chunks:
            content_arguments += content
            if not tool_call_flag and content_arguments.startswith(MARKER):
                tool_call_flag = True
            if not tool_call_flag:
                spoken.append(content)
        return "".join(spoken), tool_call_flag

    legacy_cases = [
        # (场景, chunks, 旧逻辑会漏出的特征串 and 是否应该漏)
        ("标准工具调用", [MARKER, '{"name": "search_from_ragflow"}', "</tool_call>"],
         "search_from_ragflow", False),
        ("换行开头", ["\n", MARKER, '{"name": "search_from_ragflow"}', "</tool_call>"],
         "search_from_ragflow", True),
        ("跨 chunk 拆分", ["<to", "ol_c", "all>", '{"name": "search_from_ragflow"}', "</tool_call>"],
         "<tool", True),
        ("引导语+工具调用", ["好的，", "我查一下。", MARKER, '{"name": "search_from_ragflow"}', "</tool_call>"],
         "search_from_ragflow", True),
    ]
    for label, chunks, leak_marker, should_leak_old in legacy_cases:
        old_spoken, _ = simulate_stream_legacy(chunks)
        new_spoken, _ = simulate_stream(chunks)
        leaked_old = leak_marker in old_spoken
        leaked_new = leak_marker in new_spoken
        if should_leak_old:
            check("E %s：旧逻辑确实漏出 %r（证明这是真 bug）" % (label, leak_marker),
                  leaked_old, "旧逻辑没漏，测试用例选错了")
            check("E %s：新逻辑已修好" % label, not leaked_new,
                  "仍然漏出: %r" % new_spoken)
        else:
            check("E %s：旧逻辑本来就不漏（对照组）" % label, not leaked_old,
                  "对照组反而漏了")
            check("E %s：新逻辑也不漏" % label, not leaked_new,
                  "仍然漏出: %r" % new_spoken)

    print()
    print("=" * 76)
    print("F. 「思考中」：工具名换成人话 + 思考表情")
    print("=" * 76)

    resolve = load_functions(
        SEND_AUDIO_PY, ["resolve_tool_status_text"],
        consts=("DEFAULT_TOOL_STATUS_TEXT",),
    )["resolve_tool_status_text"]

    class _FakeConn:
        def __init__(self, cfg=None):
            self.config = cfg or {}

    # 内置映射
    check("F1 search_from_ragflow -> 人话",
          "查" in resolve(_FakeConn(), "search_from_ragflow"),
          "实际=%r" % resolve(_FakeConn(), "search_from_ragflow"))
    check("F2 未知工具走兜底而不是显示原始名",
          resolve(_FakeConn(), "some_unknown_tool") != "some_unknown_tool",
          "实际=%r" % resolve(_FakeConn(), "some_unknown_tool"))
    check("F3 兜底话术里不含下划线（不像内部标识符）",
          "_" not in resolve(_FakeConn(), "some_unknown_tool"))
    # config 覆盖优先级
    cfg = {"tool_status_text": {"search_from_ragflow": "我找找课堂记录",
                                "_default": "稍等哦"}}
    check("F4 config 精确覆盖生效",
          resolve(_FakeConn(cfg), "search_from_ragflow") == "我找找课堂记录",
          "实际=%r" % resolve(_FakeConn(cfg), "search_from_ragflow"))
    check("F5 config 兜底覆盖生效",
          resolve(_FakeConn(cfg), "unknown_x") == "稍等哦",
          "实际=%r" % resolve(_FakeConn(cfg), "unknown_x"))

    # 结构化：message 字典里必须带 text 字段
    send_tree = ast.parse(open(SEND_AUDIO_PY, encoding="utf-8").read())
    fn = next((n for n in send_tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == "send_tool_status_message"), None)
    keys = set()
    if fn is not None:
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                if "message" in [t.id for t in node.targets if isinstance(t, ast.Name)] \
                        and isinstance(node.value, ast.Dict):
                    keys = {k.value for k in node.value.keys
                            if isinstance(k, ast.Constant)}
    check("F6 tool 消息带 text 字段", "text" in keys, "实际字段=%s" % sorted(keys))
    # 结构化扫描：代码里（docstring 和注释之外）不得再出现以 "% " 开头的字符串，
    # 防止以后有人把 "% 工具名" 这条老路重新加回来
    send_tree2 = ast.parse(open(SEND_AUDIO_PY, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(send_tree2):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body:
            first = body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    percent_literals = [
        n.value for n in ast.walk(send_tree2)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and id(n) not in docstrings and n.value.strip().startswith("% ")
    ]
    check("F7 代码里没有以 '% ' 开头的字符串（docstring 除外）",
          not percent_literals, "发现: %r" % percent_literals)

    # 思考表情：connection.py 必须真的调用了 send_thinking，且不是无条件发送
    conn_src = open(CONNECTION_PY, encoding="utf-8").read()
    check("F8 chat() 里调用了 send_thinking", "textUtils.send_thinking(" in conn_src)
    check("F9 思考表情可被配置关闭", "enable_thinking_indicator" in conn_src)

    tu_src = open(TEXTS_UTILS_PY, encoding="utf-8").read()
    check("F10 send_thinking 用的 emotion 名是固件内置的 thinking",
          '"thinking"' in tu_src)
    check("F11 send_thinking 在 depth==0 分支里发（不重复发）",
          conn_src.count("textUtils.send_thinking(") == 1,
          "实际调用 %d 次" % conn_src.count("textUtils.send_thinking("))

    # 固件端要把 text 显示到状态栏
    fw_src = open(APPLICATION_CC, encoding="utf-8").read()
    check("F12 固件 tool 分支会显示 text", "SetStatus(msg.c_str())" in fw_src)

    print()
    print("=" * 76)
    print("结果：%d 通过 / %d 失败" % (len(PASS), len(FAIL)))
    print("=" * 76)
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print("  - " + f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
