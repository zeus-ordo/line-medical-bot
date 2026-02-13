"""
SQLite 資料庫 - 醫療問診記錄
記錄用戶狀態 + 完整對話記錄（含症狀代碼、行動方向）
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bot.db")

class Database:
    """SQLite 資料庫管理"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
    
    def _get_conn(self) -> sqlite3.Connection:
        """取得連線（單一連線模式）"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def init_db(self):
        """初始化資料表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 用戶狀態表 - 記錄當前進行到第幾題
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id TEXT PRIMARY KEY,
                current_node TEXT NOT NULL DEFAULT '1',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 對話記錄表 - 詳細記錄每題的回答
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                node_id TEXT,                    -- 題號（序號）
                symptom_code TEXT,               -- 症狀代碼（如 UTI-A1）
                action_tag TEXT,                 -- 建議行動方向
                user_input TEXT,                 -- 用戶回答
                bot_reply TEXT,                  -- 機器人回覆（衛教文字）
                prompt TEXT,                     -- 原始問題
                education_text TEXT,             -- 衛教內容
                intent TEXT,                     -- 判定意圖
                is_end BOOLEAN DEFAULT 0,        -- 是否結束節點
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 用戶問卷結果彙總表 - 方便統計分析
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                survey_data TEXT,                -- JSON 格式儲存所有回答
                final_action TEXT,               -- 最終建議行動
                completed BOOLEAN DEFAULT 0,     -- 是否完成
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # 索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_user_time 
            ON message_logs(user_id, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_symptom 
            ON message_logs(symptom_code)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_surveys_user 
            ON user_surveys(user_id)
        """)
        
        conn.commit()
    
    def get_user_state(self, user_id: str, default: str = "1") -> str:
        """取得用戶當前節點（題號）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT current_node FROM user_states WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return row["current_node"]
        
        # 新用戶，建立記錄
        cursor.execute(
            "INSERT INTO user_states (user_id, current_node) VALUES (?, ?)",
            (user_id, default)
        )
        conn.commit()
        return default
    
    def update_user_state(self, user_id: str, node_id: str):
        """更新用戶狀態（進入下一題）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO user_states (user_id, current_node, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_node = excluded.current_node,
                updated_at = excluded.updated_at
            """,
            (user_id, node_id, datetime.now())
        )
        conn.commit()
    
    def log_message(
        self, 
        user_id: str, 
        node_id: str,
        symptom_code: str,
        action_tag: str, 
        user_input: str, 
        bot_reply: str,
        prompt: str = "",
        education_text: str = "",
        intent: str = "",
        is_end: bool = False
    ):
        """
        記錄對話 - 包含完整的醫療問診資訊
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT INTO message_logs 
            (user_id, node_id, symptom_code, action_tag, user_input, bot_reply, 
             prompt, education_text, intent, is_end, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, node_id, symptom_code, action_tag, user_input, bot_reply,
             prompt, education_text, intent, is_end, datetime.now())
        )
        conn.commit()
        
        # 如果是結束節點，更新問卷彙總
        if is_end:
            self._update_survey_completion(user_id, action_tag)
    
    def _update_survey_completion(self, user_id: str, final_action: str):
        """更新用戶問卷完成狀態"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 取得該用戶所有回答
        logs = self.get_user_logs(user_id)
        survey_data = {
            log["node_id"]: {
                "question": log["prompt"],
                "answer": log["user_input"],
                "symptom_code": log["symptom_code"],
                "action_tag": log["action_tag"]
            }
            for log in logs
        }
        
        cursor.execute(
            """
            INSERT INTO user_surveys (user_id, survey_data, final_action, completed, completed_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                survey_data = excluded.survey_data,
                final_action = excluded.final_action,
                completed = 1,
                completed_at = excluded.completed_at
            """,
            (user_id, json.dumps(survey_data, ensure_ascii=False), final_action, datetime.now())
        )
        conn.commit()
    
    def get_all_logs(self) -> List[Dict[str, Any]]:
        """取得所有對話記錄（匯出用）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id,
                user_id,
                node_id,
                symptom_code,
                action_tag,
                user_input,
                bot_reply,
                prompt,
                education_text,
                intent,
                is_end,
                created_at
            FROM message_logs
            ORDER BY created_at DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_user_logs(self, user_id: str) -> List[Dict[str, Any]]:
        """取得特定用戶的完整對話記錄"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM message_logs 
            WHERE user_id = ? 
            ORDER BY created_at ASC
            """,
            (user_id,)
        )
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def get_survey_summary(self) -> List[Dict[str, Any]]:
        """取得問卷彙總（統計用）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                user_id,
                final_action,
                completed,
                created_at,
                completed_at
            FROM user_surveys
            ORDER BY completed_at DESC
        """)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def reset_user(self, user_id: str, start_node: str = "1"):
        """重置用戶狀態（重新開始問卷）"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 重置當前節點
        cursor.execute(
            """
            INSERT INTO user_states (user_id, current_node)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                current_node = excluded.current_node
            """,
            (user_id, start_node)
        )
        
        # 刪除舊的對話記錄（可選）
        # cursor.execute("DELETE FROM message_logs WHERE user_id = ?", (user_id,))
        
        conn.commit()
    
    def close(self):
        """關閉連線"""
        if self._conn:
            self._conn.close()
            self._conn = None
