import sqlite3
import threading
from datetime import datetime


# ============================================================
# SQLite 配置
# ============================================================

DB_FILE = "bot_data.db"

_db_lock = threading.Lock()


# ============================================================
# 初始化数据库
# ============================================================

def init_database():

    with _db_lock:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS group_messages (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                chat_id INTEGER NOT NULL,

                message_id INTEGER NOT NULL,

                user_name TEXT,

                text TEXT,

                created_at TEXT

            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_group_messages_chat
            ON group_messages(chat_id)
        """)

        conn.commit()

        conn.close()


# ============================================================
# 保存群聊消息
# ============================================================

def save_message(
    chat_id,
    message_id,
    user_name,
    text
):

    if not text:
        return

    with _db_lock:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO group_messages
            (
                chat_id,
                message_id,
                user_name,
                text,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            chat_id,
            message_id,
            user_name,
            text,
            datetime.utcnow().isoformat()
        ))

        conn.commit()

        conn.close()


# ============================================================
# 获取群聊有效消息数量
# ============================================================

def get_message_count(chat_id):

    with _db_lock:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM group_messages
            WHERE chat_id = ?
        """, (
            chat_id,
        ))

        count = cursor.fetchone()[0]

        conn.close()

        return count


# ============================================================
# 获取群聊消息
# ============================================================

def get_messages(chat_id):

    with _db_lock:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                message_id,
                user_name,
                text,
                created_at
            FROM group_messages
            WHERE chat_id = ?
            ORDER BY id ASC
        """, (
            chat_id,
        ))

        rows = cursor.fetchall()

        conn.close()

    return [

        {
            "message_id": row[0],
            "user": row[1],
            "text": row[2],
            "created_at": row[3],
        }

        for row in rows

    ]


# ============================================================
# 删除已经总结的消息
# ============================================================

def clear_messages(chat_id):

    with _db_lock:

        conn = sqlite3.connect(DB_FILE)

        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM group_messages
            WHERE chat_id = ?
        """, (
            chat_id,
        ))

        conn.commit()

        conn.close()


# ============================================================
# 获取并清空
# ============================================================

def get_and_clear_messages(chat_id):

    messages = get_messages(chat_id)

    clear_messages(chat_id)

    return messages
