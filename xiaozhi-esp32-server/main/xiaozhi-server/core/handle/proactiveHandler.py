"""
主动提问处理器（Proactive Question Handler）— 时间表触发模型 v2

功能：老师在智控台预设时间表（开始/结束时间 + 提问间隔 + 固定台词），
服务器到点自动触发 AI 主动提问，播报固定台词给学生。

触发条件（全部满足才触发）：
    1. 服务器当前时间在 [start_time, end_time] 窗口内
    2. 距上次主动提问 >= interval 秒（进入窗口时重置基准，等一个 interval 才第一次问）
    3. 当前无对话进行中（client_is_speaking=False，不打断 AI 播报）
    4. 连接未在退出流程（close_after_chat/is_exiting 为 False）

触发动作：
    - speak_txt 播报固定台词（自动进 dialogue 历史 + 自动上报聊天记录，走标准 TTS 管线）
    - 设 conn.awaiting_proactive_response=True，让 chat() 给 LLM 的最后一条 user 消息
      加 [主动提问回应] 前缀（只给 LLM 看，dialogue/智控台存干净原文）

时间单位：本模块用 datetime.now() 取服务器本地时间，秒数比较；不依赖
ConnectionHandler 的毫秒时间戳（与 v1 沉默检测模型不同）。

挂载方式：connection.py 连接建立后调用 start_proactive_task(conn)。

配置来源（优先级从高到低）：
    1. 智控台下发的 agent_config（private_config["proactive"]）
    2. 本文件 DEFAULT_CONFIG
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.connection import ConnectionHandler

TAG = "ProactiveHandler"

# 检查循环间隔（秒）
CHECK_INTERVAL = 5


# 默认配置（智控台未下发时的兜底值；enabled 默认关，必须显式开启）
DEFAULT_CONFIG = {
    "enabled": False,
    "start_time": "00:00",   # HH:MM，服务器本地时区
    "end_time": "23:59",
    "interval": 900,         # 提问间隔（秒），900 = 15 分钟
    "script": "",            # 单条固定台词（单条循环模式）
    "weekdays": [],          # 星期几触发，[1,2,3,4,5] = 周一到周五；空列表 = 每天
}


def _truthy(val) -> bool:
    """容错解析开关值：智控台 JSON 可能下发 bool 或字符串。"""
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def _to_float(val, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _get_proactive_config(conn: "ConnectionHandler") -> dict:
    """合并配置：DEFAULT_CONFIG < 智控台 agent_config（conn.config['proactive']）。"""
    cfg = dict(DEFAULT_CONFIG)
    server_cfg = conn.config.get("proactive")
    if isinstance(server_cfg, dict):
        cfg.update(server_cfg)
    return cfg


def _parse_hhmm(time_str: str, default: float) -> float:
    """HH:MM → 当天秒数（0-86399）。解析失败返回 default。"""
    try:
        parts = str(time_str).strip().split(":")
        if len(parts) != 2:
            return default
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return float(h * 3600 + m * 60)
    except (ValueError, AttributeError, TypeError):
        pass
    return default


def _in_time_window(now_secs: float, start_secs: float, end_secs: float) -> bool:
    """判断当前秒数是否在时间窗口内。支持跨日窗口（start > end 视为跨日，如 23:00-01:00）。"""
    if start_secs <= end_secs:
        return start_secs <= now_secs < end_secs
    else:
        # 跨日窗口
        return now_secs >= start_secs or now_secs < end_secs


def _parse_weekdays(val) -> set:
    """解析星期配置 → {1..7} 集合（ISO：1=周一 7=周日）。

    接受格式：[] / None → 空集（每天触发）；
    [1,3,5] / ["1","3","5"] / "1,3,5" / "monday,wednesday" 均可。
    全部非法值 → 空集（容错为每天，与默认一致）。
    """
    if not val:
        return set()
    if isinstance(val, str):
        val = val.replace("，", ",").split(",")
    if not isinstance(val, (list, tuple, set)):
        return set()
    name_map = {
        "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6, "sun": 7,
    }
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}
    result = set()
    for item in val:
        item_str = str(item).strip().lower()
        if not item_str:
            continue
        try:
            d = int(item_str)
            if 1 <= d <= 7:
                result.add(d)
            continue
        except ValueError:
            pass
        for prefix, num in name_map.items():
            if item_str.startswith(prefix):  # 英文：前缀匹配（mon→monday）
                result.add(num)
                break
        else:
            for cn, num in cn_map.items():
                if cn in item_str:  # 中文：包含匹配（六→周六/礼拜六）
                    result.add(num)
                    break
    return result


async def _wait_modules_ready(conn: "ConnectionHandler") -> bool:
    """等待 TTS / dialogue 模块初始化完成（后台初始化是异步的），最多等 30s。"""
    for _ in range(60):
        if conn.stop_event.is_set():
            return False
        if conn.tts is not None and conn.dialogue is not None:
            return True
        await asyncio.sleep(0.5)
    return conn.tts is not None and conn.dialogue is not None


async def _proactive_loop(conn: "ConnectionHandler"):
    """主动提问时间表触发主循环。connection.py 在连接建立后 create_task 本协程。"""
    try:
        ready = await _wait_modules_ready(conn)
        if not ready:
            conn.logger.bind(tag=TAG).warning("模块未就绪，主动提问不启动")
            return

        cfg = _get_proactive_config(conn)
        if not _truthy(cfg.get("enabled", False)):
            conn.logger.bind(tag=TAG).debug(
                f"主动提问未启用 (enabled={cfg.get('enabled')})"
            )
            return

        start_secs = _parse_hhmm(cfg.get("start_time", "00:00"), 0.0)
        end_secs = _parse_hhmm(cfg.get("end_time", "23:59"), 86399.0)
        interval = _to_float(cfg.get("interval", 900), 900.0)
        script = str(cfg.get("script", "") or "").strip()
        weekdays = _parse_weekdays(cfg.get("weekdays"))

        if not script:
            conn.logger.bind(tag=TAG).warning("主动提问已启用但 script 为空，不启动")
            return

        # 连接级状态初始化
        conn.proactive_last_ask_time = 0.0
        conn.proactive_in_window = False
        conn.awaiting_proactive_response = False
        conn.last_proactive_question = ""

        conn.logger.bind(tag=TAG).info(
            f"主动提问已启动: 窗口 {cfg.get('start_time')}-{cfg.get('end_time')} "
            f"星期 {weekdays if weekdays else '每天'} "
            f"间隔 {interval:.0f}s 台词='{script[:40]}'"
        )

        while not conn.stop_event.is_set():
            await asyncio.sleep(CHECK_INTERVAL)

            now_dt = datetime.now()
            # 星期判定：配置了 weekdays 且今天不在其中 → 本周期直接跳过
            if weekdays and now_dt.isoweekday() not in weekdays:
                if conn.proactive_in_window:
                    conn.proactive_in_window = False
                continue
            now_secs = now_dt.hour * 3600 + now_dt.minute * 60 + now_dt.second
            in_window = _in_time_window(now_secs, start_secs, end_secs)

            # 窗口状态转换：进入窗口时重置计时基准（等一个 interval 后才第一次提问）
            if in_window and not conn.proactive_in_window:
                conn.proactive_in_window = True
                conn.proactive_last_ask_time = time.time()
                conn.logger.bind(tag=TAG).debug("进入提问时间窗口，重置计时基准")
                continue
            if not in_window and conn.proactive_in_window:
                conn.proactive_in_window = False
                conn.logger.bind(tag=TAG).debug("离开提问时间窗口")
                continue
            if not in_window:
                continue

            # ---- 连接保活：窗口内每周期刷新活动时间戳 ----
            # 原因：服务器空闲回收机制（120s 告别 / 180s 强关）在无人说话时会
            # 杀掉连接，导致 interval > 180s 时主动提问永远等不到触发时刻。
            # 窗口内由本循环持续"续命"，窗口外不续命（连接照常回收，省资源）。
            conn.last_activity_time = time.time() * 1000  # 该字段为毫秒

            # interval 判定
            now = time.time()
            if conn.proactive_last_ask_time > 0 and (
                now - conn.proactive_last_ask_time < interval
            ):
                continue

            # ---- 规则③：提问即点名 ----
            # 到达下个提问时刻，先检查上次提问是否得到回应（awaiting 旗还立着
            # = 整整一个 interval 无任何学生输入）→ 不再提问，告别+断开。
            # 判定必须在 interval 判定之后，才是"下个倒计时结束时"的语义。
            if conn.awaiting_proactive_response:
                conn.proactive_in_window = False  # 防告别播报期间本循环再介入
                conn.close_after_chat = True       # 播报完成后由既有流程断开 WS
                conn.client_abort = False
                # 先清等待旗：startToChat 的告别指令会走 chat()，若旗仍立着
                # 会被误判为"收到学生回应"打出误导日志（2026-09-06 实测发现）
                conn.awaiting_proactive_response = False
                # 照抄 receiveAudioHandle 空闲告别的做法：startToChat 播告别语，
                # 走完整 TTS 流程，播完自动断开（close_after_chat 语义）
                end_prompt = conn.config.get("end_prompt", {})
                prompt = None
                if isinstance(end_prompt, dict):
                    prompt = end_prompt.get("prompt")
                if not prompt:
                    # 指令式 prompt（startToChat 会将其作为用户消息走 LLM，
                    # 由 LLM 生成告别语——照抄空闲告别的先例做法）
                    prompt = (
                        "请你用一句简短温暖的话与学生道别（学生暂时没有回应，可能不在），"
                        "提醒他需要时随时可以再叫你，然后结束本次对话。"
                    )
                from core.handle.receiveAudioHandle import startToChat
                conn.logger.bind(tag=TAG).info(
                    "[PROACTIVE] 提问后一个间隔内无学生回应，告别并断开连接以释放资源"
                )
                await startToChat(conn, prompt)
                return

            # 无对话守卫：不打断 AI 播报 / 不在退出流程
            if conn.client_is_speaking:
                continue
            if conn.close_after_chat or getattr(conn, "is_exiting", False):
                continue

            # ---- 触发：speak_txt 播报固定台词 ----
            # speak_txt 惰性导入：避免本模块顶层拉起 intentHandler 的重依赖链
            # speak_txt 内部会 dialogue.put(assistant) 进历史 + 触发 TTS 管线自动上报聊天记录
            from core.handle.intentHandler import speak_txt

            conn.client_abort = False
            conn.sentence_id = uuid.uuid4().hex
            speak_txt(conn, script)

            conn.proactive_last_ask_time = time.time()
            conn.awaiting_proactive_response = True
            conn.last_proactive_question = script

            conn.logger.bind(tag=TAG).info(
                f"[PROACTIVE] 时间表触发主动提问: '{script[:40]}' "
                f"(窗口内, 间隔 {interval:.0f}s 已到)"
            )

    except asyncio.CancelledError:
        pass
    except Exception as e:
        try:
            conn.logger.bind(tag=TAG).error(f"主动提问循环异常退出: {e}")
        except Exception:
            pass


def start_proactive_task(conn: "ConnectionHandler"):
    """连接建立后调用，启动主动提问时间表检测协程。

    在 connection.py 的 _check_timeout 启动处之后调用。
    返回 task 对象（调用方可不持有引用，协程自管理生命周期）。
    """
    # 预初始化连接级状态（_proactive_loop 内还会再设一次，这里防止 race）
    conn.proactive_last_ask_time = 0.0
    conn.proactive_in_window = False
    conn.awaiting_proactive_response = False
    conn.last_proactive_question = ""
    return asyncio.create_task(_proactive_loop(conn))
