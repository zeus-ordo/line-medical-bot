"""
LINE 醫療問診 Bot - FastAPI 入口
功能：LINE Webhook + 問診流程 + 完整記錄 + Export API
"""
import os
import hmac
import hashlib
import base64
import csv
import io
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import requests
from dotenv import load_dotenv

from app.flow import FlowEngine
from app.database import Database
from app.intent import IntentClassifier

load_dotenv()

# 初始化元件
db = Database()
flow = FlowEngine("data/flow.csv")
intent_classifier = IntentClassifier()

# LINE 設定
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

def line_reply(reply_token: str, messages: list) -> bool:
    """LINE Reply API（免費）"""
    if not messages:
        return True
    
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # 將訊息拆分為多則（LINE 限制每則最多 5000 字）
    formatted_messages = []
    for msg in messages[:5]:  # 最多 5 則
        if len(msg) > 1000:
            # 長文分段
            for i in range(0, len(msg), 1000):
                formatted_messages.append({"type": "text", "text": msg[i:i+1000]})
        else:
            formatted_messages.append({"type": "text", "text": msg})
    
    payload = {
        "replyToken": reply_token,
        "messages": formatted_messages[:5]
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"LINE Reply Error: {e}")
        return False

def validate_signature(body: bytes, signature: str) -> bool:
    """驗證 LINE Webhook Signature"""
    if not LINE_CHANNEL_SECRET:
        return True  # 開發模式跳過驗證
    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode(),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash).decode()
    return hmac.compare_digest(expected, signature)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """啟動時初始化"""
    # 檢查是否需要重置資料庫（環境變數 RESET_DB=true）
    reset_db = os.getenv("RESET_DB", "false").lower() == "true"
    if reset_db:
        print("🔄 檢測到 RESET_DB=true，正在重置資料庫...")
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "bot.db")
        if os.path.exists(db_path):
            os.remove(db_path)
            print("✅ 舊資料庫已刪除")
    
    db.init_db()
    flow.load()
    print(f"✅ 流程載入完成：共 {len(flow.nodes)} 個節點")
    yield
    # 關閉時清理
    db.close()

app = FastAPI(title="LINE 醫療問診 Bot", lifespan=lifespan)

@app.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: Optional[str] = Header(None, alias="X-Line-Signature")
):
    """LINE Webhook 接收端點 - 醫療問診流程"""
    body = await request.body()
    
    if not validate_signature(body, x_line_signature or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    data = await request.json()
    
    for event in data.get("events", []):
        if event.get("type") != "message":
            continue
        if event.get("message", {}).get("type") != "text":
            continue
        
        # 安全獲取用戶資訊
        source = event.get("source", {})
        user_id = source.get("userId")  # LINE 使用 userId（駝峰命名）
        if not user_id:
            print(f"Warning: No userId in event source: {source}")
            continue
            
        user_input = event.get("message", {}).get("text", "")
        reply_token = event.get("replyToken", "")
        
        if not reply_token:
            print(f"Warning: No reply_token in event")
            continue
        
        # ===== 問診流程處理 =====
        
        # 1. 取得用戶當前題號
        current_node_id = db.get_user_state(user_id)
        current_node = flow.get_node(current_node_id)
        
        # 如果題號不存在，從頭開始
        if not current_node:
            current_node_id = flow.get_start_node()
            current_node = flow.get_node(current_node_id)
        
        # 確保 current_node 存在
        if not current_node:
            return {"status": "error", "message": "Flow not loaded"}
        
        # 檢查是否為新用戶（還沒有對話記錄）
        user_logs = db.get_user_logs(user_id)
        is_new_user = len(user_logs) == 0
        
        if is_new_user:
            # 新用戶：顯示第一題（還沒回答，不跳轉）
            replies = flow.build_reply(current_node)
            is_end = current_node.get("is_end", False)
            tags = current_node.get("tags", {})
            symptom_code = tags.get("code", "")
            action_tag = tags.get("action_tag", "")
            prompt = current_node.get("prompt", "")
            education = current_node.get("education_text", "")
            intent = "new_user"
            next_node_id = current_node_id  # 保持在同一題，等待回答
        else:
            # 已有記錄的用戶：根據回答跳到下一題
            intent = intent_classifier.classify(user_input, current_node)
            next_node_id = flow.get_next_node(current_node, intent, user_input)
            next_node = flow.get_node(next_node_id) if next_node_id else None
            
            if next_node:
                replies = flow.build_reply(next_node)
                is_end = next_node.get("is_end", False)
                tags = next_node.get("tags", {})
                symptom_code = tags.get("code", "")
                action_tag = tags.get("action_tag", "")
                prompt = next_node.get("prompt", "")
                education = next_node.get("education_text", "")
            else:
                # 流程結束
                replies = ["問卷已完成，感謝您的配合！"]
                is_end = True
                symptom_code = ""
                action_tag = ""
                prompt = ""
                education = ""
        
        # 5. 記錄完整對話資訊（含症狀代碼、行動方向）
        db.log_message(
            user_id=user_id,
            node_id=current_node_id,
            symptom_code=current_node.get("tags", {}).get("code", "") if current_node else "",
            action_tag=current_node.get("tags", {}).get("action_tag", "") if current_node else "",
            user_input=user_input,
            bot_reply="\n".join(replies),
            prompt=current_node.get("prompt", "") if current_node else "",
            education_text=current_node.get("education_text", "") if current_node else "",
            intent=intent,
            is_end=is_end
        )
        
        # 6. 更新用戶狀態到下一題
        if next_node_id and not is_end:
            db.update_user_state(user_id, next_node_id)
        else:
            # 標記為完成，下次從頭開始
            db.update_user_state(user_id, "COMPLETED")
        
        # 7. 回覆用戶
        line_reply(reply_token, replies)
    
    return {"status": "ok"}

@app.get("/health")
async def health():
    """健康檢查"""
    return {
        "status": "ok",
        "flow_loaded": flow.is_loaded,
        "total_nodes": len(flow.nodes) if flow.is_loaded else 0,
        "start_node": flow.get_start_node()
    }

@app.get("/export/csv")
async def export_csv():
    """匯出完整對話紀錄（含症狀代碼、行動方向）"""
    logs = db.get_all_logs()
    
    if not logs:
        return {"message": "目前沒有對話紀錄"}
    
    # 建立 CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=logs[0].keys())
    writer.writeheader()
    writer.writerows(logs)
    
    # 回傳檔案
    output.seek(0)
    filename = f"medical_chat_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/export/survey-summary")
async def export_survey_summary():
    """匯出問卷彙總（統計用）"""
    summaries = db.get_survey_summary()
    
    if not summaries:
        return {"message": "目前沒有完成紀錄"}
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=summaries[0].keys())
    writer.writeheader()
    writer.writerows(summaries)
    
    output.seek(0)
    filename = f"survey_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.post("/admin/reset/{user_id}")
async def reset_user(user_id: str):
    """重置特定用戶（重新開始問卷）"""
    db.reset_user(user_id, flow.get_start_node())
    return {"message": f"用戶 {user_id} 已重置，可重新開始問卷"}

@app.get("/admin/user-logs/{user_id}")
async def get_user_logs(user_id: str):
    """查詢特定用戶的對話紀錄"""
    logs = db.get_user_logs(user_id)
    return {
        "user_id": user_id,
        "total_records": len(logs),
        "logs": logs
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
