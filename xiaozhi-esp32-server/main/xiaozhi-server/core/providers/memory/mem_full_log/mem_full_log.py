"""
完整对话记录 Memory Provider（实时写入版）

功能：将所有对话原文实时保存到本地 SQLite 数据库
- 每条消息产生时立即写入 SQLite（WAL 模式），不再等断开连接
- 16台设备同时写入无压力
- 支持通过 db_to_excel.py 导出为 Excel

数据结构：
- conversations 表: 会话级别信息（session_id, device_id, 时间）
- messages 表: 每条消息（role, content, speaker, 时间）

无额外依赖，纯 Python sqlite3
"""

import json
import os
import sqlite3
import threading
from datetime import datetime
from config.config_loader import get_project_dir
from config.logger import setup_logging

from ..base import MemoryProviderBase

TAG = __name__
logger = setup_logging()


class MemoryProvider(MemoryProviderBase):
    """完整对话记录 Memory Provider（实时写入版）

    每条消息通过 Dialogue.put() 回调实时写入 SQLite。
    save_memory 只在断开连接时更新会话元数据（message_count）。
    query_memory 返回空字符串（不影响 LLM 上下文）。
    """

    def __init__(self, config, summary_memory=None):
        super().__init__(config)
        self.db_dir = get_project_dir() + "data/conversations"
        os.makedirs(self.db_dir, exist_ok=True)
        self.db_path = os.path.join(self.db_dir, "conversations.db")
        self._lock = threading.Lock()
        self._turn_counter = 0  # 当前会话的消息轮次计数
        self._init_db()
        logger.bind(tag=TAG).info(f"mem_full_log 初始化完成 (实时写入+WAL), 数据库: {self.db_path}")

    def _init_db(self):
        """初始化 SQLite 数据库表结构 + WAL 模式"""
        with sqlite3.connect(self.db_path) as conn:
            # 启用 WAL 模式：读写互不阻塞，适合多设备并发写入
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL UNIQUE,
                    device_id TEXT,
                    started_at DATETIME NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_id INTEGER DEFAULT 0,
                    role TEXT NOT NULL,
                    content TEXT,
                    speaker TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES conversations(session_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_device
                ON conversations(device_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_time
                ON conversations(started_at)
            """)

    def init_memory(self, role_id, llm, **kwargs):
        """初始化记忆 - role_id 即为 device_id，同时注册实时写入回调"""
        super().init_memory(role_id, llm, **kwargs)

        # 获取 dialogue 对象，注入回调
        dialogue = kwargs.get("dialogue", None)
        if dialogue and hasattr(dialogue, "set_on_message_added"):
            dialogue.set_on_message_added(self._on_message_added)
            logger.bind(tag=TAG).info(f"已注册实时写入回调, device: {role_id}")

    def _extract_speaker(self, content):
        """从 JSON 格式的 content 中提取 speaker 和实际文本"""
        if not content:
            return None, content
        try:
            text = content.strip()
            if text.startswith("{") and text.endswith("}"):
                data = json.loads(text)
                speaker = data.get("speaker", None)
                actual_content = data.get("content", content)
                return speaker, actual_content
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None, content

    def _on_message_added(self, message):
        """Dialogue.put() 回调：每条新消息实时写入 SQLite"""
        if not hasattr(self, "_session_started") or not self._session_started:
            # 首次收到消息，确保会话记录已创建
            self._ensure_conversation_record()
            self._session_started = True

        speaker, actual_content = self._extract_speaker(message.content)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            self._insert_single_message(
                role=message.role,
                content=actual_content or "",
                speaker=speaker or "",
                created_at=now,
            )

    def _ensure_conversation_record(self):
        """确保当前会话的 conversations 记录存在"""
        session_id = getattr(self, "_current_session_id", None)
        if not session_id:
            return

        device_id = self.role_id or "unknown"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR IGNORE INTO conversations
                        (session_id, device_id, started_at, message_count, created_at)
                        VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                    """, (session_id, device_id, now))
            except Exception as e:
                logger.bind(tag=TAG).error(f"创建会话记录失败: {e}")

    def _insert_single_message(self, role, content, speaker, created_at):
        """写入单条消息到 SQLite"""
        session_id = getattr(self, "_current_session_id", None)
        if not session_id:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO messages
                    (session_id, turn_id, role, content, speaker, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, self._turn_counter, role, content, speaker, created_at))
                # 更新消息计数
                conn.execute("""
                    UPDATE conversations SET message_count = message_count + 1
                    WHERE session_id = ?
                """, (session_id,))
                self._turn_counter += 1
        except Exception as e:
            logger.bind(tag=TAG).error(f"实时写入消息失败: {e}")

    async def save_memory(self, msgs, session_id=None):
        """断开连接时调用 — 仅更新会话元数据（数据已在实时写入中完成）"""
        if not msgs or len(msgs) < 2:
            return None

        session_id = session_id or "unknown"
        device_id = self.role_id or "unknown"

        # 记录当前 session_id（给 _on_message_added 使用）
        self._current_session_id = session_id
        self._session_started = False  # 标记会话结束
        self._turn_counter = 0  # 重置轮次计数

        logger.bind(tag=TAG).info(
            f"会话结束确认 - Session: {session_id}, "
            f"Device: {device_id}, Total messages in dialogue: {len(msgs)}"
        )
        return None

    def set_session_id(self, session_id):
        """设置当前会话 ID（由 connection.py 在连接建立时调用）"""
        self._current_session_id = session_id
        self._session_started = False
        self._turn_counter = 0

    async def query_memory(self, query: str) -> str:
        """查询记忆 - 此 Provider 不提供记忆检索，返回空字符串"""
        return ""
