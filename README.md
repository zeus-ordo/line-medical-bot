# LINE Excel Bot PoC - 最簡版

> 單機、單服務、SQLite、可上雲的 LINE Chatbot PoC

## 核心功能

1. **LINE Webhook** - 收訊、驗簽、回覆
2. **Flow Engine** - 讀 Excel/CSV 控制問答流程
3. **SQLite** - 記錄用戶狀態與對話紀錄
4. **Export API** - 一鍵匯出 CSV

## 檔案結構（4個核心模組）

```
line-excel-bot-poc/
├── app/
│   ├── main.py        # FastAPI + Webhook + Export
│   ├── flow.py        # 流程引擎（讀 Excel/CSV）
│   ├── database.py    # SQLite 操作
│   └── intent.py      # 意圖分類（規則 + OpenAI）
├── data/
│   ├── flow.csv       # 流程定義
│   └── bot.db         # SQLite（自動建立）
├── deploy/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt
└── README.md
```

## 快速開始

### 1. 環境變數

建立 `.env`：

```bash
LINE_CHANNEL_ACCESS_TOKEN=你的_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET=你的_CHANNEL_SECRET
OPENAI_API_KEY=你的_OPENAI_API_KEY（選填）
PORT=8000
```

### 2. 啟動服務

```bash
pip install -r requirements.txt
python -m app.main
```

### 3. 設定 LINE Webhook

設定 Webhook URL: `https://你的網域/webhook`

## Excel/CSV 流程設計

編輯 `data/flow.csv`：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `node_id` | 節點 ID | start, q1, end |
| `type` | 節點類型 | greeting/question/message/close |
| `content` | 回覆內容 | 請問您的年齡？ |
| `choices` | 選項 | 是\|yes,否\|no |
| `next_yes` | 選「是」下一節點 | next_node_id |
| `next_no` | 選「否」下一節點 | next_node_id |
| `next_default` | 預設下一節點 | next_node_id |
| `next_[key]` | 特定選項下一節點 | next_node_id |

## API 端點

| 端點 | 說明 |
|------|------|
| `POST /webhook` | LINE Webhook |
| `GET /health` | 健康檢查 |
| `GET /export/csv` | 匯出對話紀錄 |
| `POST /admin/reset/{user_id}` | 重置用戶狀態 |

## 資料流程

```
使用者傳訊息 → LINE Webhook
                    ↓
            找到 user 的 current_node
                    ↓
            讀取節點的問題/選項
                    ↓
            判定意圖（規則 → OpenAI）
                    ↓
            寫入 MessageLog
                    ↓
            更新 ConversationState
                    ↓
            回覆下一題（或 END）
```

## Docker 部署（Ubuntu VM）

```bash
cd deploy
docker-compose up -d
```

## 匯出對話紀錄

```bash
curl -O http://localhost:8000/export/csv
```

## License

MIT
