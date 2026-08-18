import sqlite3
from contextlib import closing

from config import (
    DATABASE_PATH,
    MAX_HISTORY,
)


# ============================================================
# 数据库连接
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# 初始化数据库
# ============================================================

def init_database():

    with closing(get_connection()) as conn:

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER,
                user_name TEXT,
                text TEXT,
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_messages_chat
            ON group_messages(chat_id)
        """)

        conn.commit()


# ============================================================
# 添加群聊消息
# ============================================================

def add_message(
    chat_id,
    user_id,
    user_name,
    text,
    message_id
):

    if not text:
        return

    with closing(get_connection()) as conn:

        conn.execute(
            """
            INSERT INTO group_messages
            (
                chat_id,
                user_id,
                user_name,
                text,
                message_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                user_id,
                user_name,
                text,
                message_id
            )
        )

        # ----------------------------------------------------
        # 只保留最近 MAX_HISTORY 条
        # ----------------------------------------------------

        conn.execute(
            """
            DELETE FROM group_messages
            WHERE chat_id = ?
            AND id NOT IN (
                SELECT id
                FROM group_messages
                WHERE chat_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (
                chat_id,
                chat_id,
                MAX_HISTORY
            )
        )

        conn.commit()


# ============================================================
# 获取群聊历史
# ============================================================

def get_messages(
    chat_id,
    limit=None
):

    if limit is None:
        limit = MAX_HISTORY

    with closing(get_connection()) as conn:

        rows = conn.execute(
            """
            SELECT
                id,
                chat_id,
                user_id,
                user_name,
                text,
                message_id,
                created_at
            FROM group_messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                chat_id,
                limit
            )
        ).fetchall()


    # 数据库按倒序取出
    # 总结时重新恢复正常时间顺序

    rows = list(reversed(rows))

    return [dict(row) for row in rows]


# ============================================================
# 判断是否属于无意义打招呼
# ============================================================

def is_meaningless_greeting(text):

    if not text:
        return True

    normalized = (
        text
        .strip()
        .lower()
        .replace(" ", "")
        .replace("　", "")
        .replace("！", "")
        .replace("!", "")
        .replace("？", "")
        .replace("?", "")
        .replace("。", "")
        .replace(".", "")
    )


    greetings = {

        "你好",
        "您好",
        "嗨",
        "哈喽",
        "hello",
        "hi",
        "hey",
        "早",
        "早上好",
        "晚上好",
        "午安",
        "晚安",
        "在吗",
        "有人吗",
        "大家好",
        "各位好",
        "yo",

    }


    return normalized in greetings


# ============================================================
# 获取用于总结的消息
#
# 自动过滤：
# - 单纯打招呼
# - 空消息
# - 命令
# ============================================================

def get_summary_messages(
    chat_id,
    limit=None
):

    messages = get_messages(
        chat_id,
        limit
    )


    result = []


    for item in messages:

        text = item.get(
            "text",
            ""
        ).strip()


        if not text:
            continue


        if text.startswith("/"):
            continue


        if is_meaningless_greeting(text):
            continue


        result.append(item)


    return result


# ============================================================
# 清理指定群聊历史
# ============================================================

def clear_messages(chat_id):

    with closing(get_connection()) as conn:

        conn.execute(
            """
            DELETE FROM group_messages
            WHERE chat_id = ?
            """,
            (chat_id,)
        )

        conn.commit()
