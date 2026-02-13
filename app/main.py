"""
FastAPI + LINE Bot + Admin Dashboard
醫療問診 LINE Bot - 含管理後台
"""
import os
import sys
import csv
import json
import io
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database
from app.flow import FlowEngine
from app.intent import IntentClassifier

# Initialize FastAPI
app = FastAPI(title="UTI Medical Bot", version="2.0")

# Initialize components
db = Database()
flow_engine = FlowEngine(os.path.join(os.path.dirname(__file__), "..", "data", "flow.csv"))
intent_classifier = IntentClassifier()

# LINE Bot Config
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")

# Initialize on startup
@app.on_event("startup")
async def startup():
    """Initialize database and flow engine"""
    db.init_db()
    flow_engine.load()
    print(f"✅ Loaded {len(flow_engine.nodes)} flow nodes")
    print(f"✅ Database initialized at {db.db_path}")

# ============ LINE Webhook Handlers ============

@app.post("/webhook")
async def line_webhook(request: Request):
    """LINE Bot webhook endpoint"""
    try:
        body = await request.json()
        events = body.get("events", [])
        
        for event in events:
            if event.get("type") == "message":
                message = event.get("message", {})
                if message.get("type") == "text":
                    await handle_text_message(event)
        
        return {"status": "ok"}
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

async def handle_text_message(event: dict):
    """Handle incoming text message"""
    user_id = event["source"].get("userId", "unknown")
    text = event["message"].get("text", "").strip()
    reply_token = event.get("replyToken", "")
    
    if not reply_token:
        print("No reply token, skipping reply")
        return
    
    # Get current node
    current_node_id = db.get_user_state(user_id, default=flow_engine.get_start_node())
    current_node = flow_engine.get_node(current_node_id)
    
    if not current_node:
        # Reset if node not found
        current_node_id = flow_engine.get_start_node()
        current_node = flow_engine.get_node(current_node_id)
        if not current_node:
            print(f"Start node not found: {current_node_id}")
            return
        db.update_user_state(user_id, current_node_id)
    
    # Check if this is the first message (start of conversation)
    logs = db.get_user_logs(user_id)
    is_first_message = len(logs) == 0
    
    if is_first_message:
        # Send welcome + first question
        reply_messages = flow_engine.build_reply(current_node)
        await send_line_reply(reply_token, reply_messages)
        
        # Log the first question (bot message)
        db.log_message(
            user_id=user_id,
            node_id=current_node_id,
            symptom_code=current_node.get("tags", {}).get("code", "") if current_node.get("tags") else "",
            action_tag=current_node.get("tags", {}).get("action_tag", "") if current_node.get("tags") else "",
            user_input="[START]",
            bot_reply=current_node.get("prompt", ""),
            prompt=current_node.get("prompt", ""),
            education_text=current_node.get("education_text", ""),
            intent="start",
            is_end=current_node.get("is_end", False)
        )
        return
    
    # Classify intent and get next node
    intent = intent_classifier.classify(text, current_node)
    next_node_id = flow_engine.get_next_node(current_node, intent, text)
    
    # Build reply
    if next_node_id:
        next_node = flow_engine.get_node(next_node_id)
        if not next_node:
            print(f"Next node not found: {next_node_id}")
            return
        reply_messages = flow_engine.build_reply(next_node)
        
        # Log the conversation
        db.log_message(
            user_id=user_id,
            node_id=current_node_id,
            symptom_code=current_node.get("tags", {}).get("code", "") if current_node.get("tags") else "",
            action_tag=current_node.get("tags", {}).get("action_tag", "") if current_node.get("tags") else "",
            user_input=text,
            bot_reply=" | ".join(reply_messages),
            prompt=current_node.get("prompt", ""),
            education_text=current_node.get("education_text", ""),
            intent=intent,
            is_end=current_node.get("is_end", False)
        )
        
        # Update user state
        db.update_user_state(user_id, next_node_id)
        
        # Send reply
        await send_line_reply(reply_token, reply_messages)
        
        # Check if survey is complete
        if next_node.get("is_end", False):
            # Log completion
            db.log_message(
                user_id=user_id,
                node_id=next_node_id,
                symptom_code=next_node.get("tags", {}).get("code", "") if next_node.get("tags") else "",
                action_tag=next_node.get("tags", {}).get("action_tag", "") if next_node.get("tags") else "",
                user_input="[END]",
                bot_reply=next_node.get("education_text", ""),
                prompt=next_node.get("prompt", ""),
                education_text=next_node.get("education_text", ""),
                intent="end",
                is_end=True
            )
    else:
        # End of flow - no next node
        reply_messages = flow_engine.build_reply(current_node)
        await send_line_reply(reply_token, reply_messages)

async def send_line_reply(reply_token: str, messages: List[str]):
    """Send reply to LINE"""
    import requests
    
    if not LINE_CHANNEL_ACCESS_TOKEN:
        print("⚠️ LINE_CHANNEL_ACCESS_TOKEN not set")
        return
    
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Convert messages to LINE format
    line_messages = [{"type": "text", "text": msg} for msg in messages if msg]
    
    payload = {
        "replyToken": reply_token,
        "messages": line_messages[:5]  # LINE allows max 5 messages
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"LINE API error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Send reply error: {e}")

# ============ Admin Dashboard (Embedded HTML) ============

ADMIN_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UTI 問診 Bot 後台管理</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container { max-width: 1400px; margin: 0 auto; }
        
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        
        /* Tabs */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .tab-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s;
        }
        
        .tab-btn:hover { background: rgba(255,255,255,0.3); }
        .tab-btn.active { background: white; color: #667eea; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s;
        }
        
        .stat-card:hover { transform: translateY(-5px); }
        
        .stat-card h3 {
            color: #666;
            font-size: 0.9em;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .stat-value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
        }
        
        /* Charts Section */
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .chart-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .chart-card h3 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.2em;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
        }
        
        /* Actions & Filters */
        .section {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 25px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            margin-right: 10px;
            margin-bottom: 10px;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, #ffa502 0%, #ff7f00 100%);
        }
        
        input, select {
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 1em;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        /* Tables */
        .table-container {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow-x: auto;
            max-height: 600px;
            overflow-y: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }
        
        tr:hover { background: #f5f5f5; }
        
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        
        .badge-success { background: #d4edda; color: #155724; }
        .badge-danger { background: #f8d7da; color: #721c24; }
        .badge-info { background: #d1ecf1; color: #0c5460; }
        
        .loading {
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
            color: #666;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .success {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        @media (max-width: 768px) {
            .stats-grid, .charts-grid { grid-template-columns: 1fr; }
            h1 { font-size: 1.8em; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 UTI 問診 Bot 後台管理</h1>
        
        <!-- Tabs -->
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('overview')">📊 總覽</button>
            <button class="tab-btn" onclick="showTab('charts')">📈 圖表分析</button>
            <button class="tab-btn" onclick="showTab('users')">👥 用戶管理</button>
            <button class="tab-btn" onclick="showTab('logs')">📝 對話記錄</button>
        </div>
        
        <!-- Overview Tab -->
        <div id="overview" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>總用戶數</h3>
                    <div class="stat-value" id="totalUsers">-</div>
                </div>
                <div class="stat-card">
                    <h3>今日對話數</h3>
                    <div class="stat-value" id="todayChats">-</div>
                </div>
                <div class="stat-card">
                    <h3>完成問卷數</h3>
                    <div class="stat-value" id="completedSurveys">-</div>
                </div>
                <div class="stat-card">
                    <h3>平均對話輪數</h3>
                    <div class="stat-value" id="avgRounds">-</div>
                </div>
            </div>
            
            <div class="section">
                <button class="btn" onclick="refreshData()">🔄 重新整理</button>
                <button class="btn" onclick="exportCSV()">📥 匯出 CSV</button>
            </div>
        </div>
        
        <!-- Charts Tab -->
        <div id="charts" class="tab-content">
            <div class="charts-grid">
                <div class="chart-card">
                    <h3>📊 每日趨勢</h3>
                    <div class="chart-container">
                        <canvas id="dailyChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>🎯 節點分佈</h3>
                    <div class="chart-container">
                        <canvas id="nodeChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>💭 意圖分佈</h3>
                    <div class="chart-container">
                        <canvas id="intentChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <h3>✅ 完成率</h3>
                    <div class="chart-container">
                        <canvas id="completionChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Users Tab -->
        <div id="users" class="tab-content">
            <div class="section">
                <h3>🔍 搜尋用戶</h3>
                <input type="text" id="userSearch" placeholder="輸入用戶ID...">
                <button class="btn" onclick="searchUser()">搜尋</button>
                <button class="btn btn-danger" onclick="deleteAllData()">⚠️ 清除所有資料</button>
            </div>
            
            <div id="userResult"></div>
            
            <div class="table-container">
                <h3 style="margin-bottom: 15px;">👥 用戶列表</h3>
                <table id="usersTable">
                    <thead>
                        <tr>
                            <th>用戶 ID</th>
                            <th>對話數</th>
                            <th>當前節點</th>
                            <th>首次對話</th>
                            <th>最後對話</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody id="usersBody"></tbody>
                </table>
            </div>
        </div>
        
        <!-- Logs Tab -->
        <div id="logs" class="tab-content">
            <div class="section">
                <input type="text" id="filterUser" placeholder="搜尋用戶 ID...">
                <select id="filterNode">
                    <option value="">全部題號</option>
                </select>
                <input type="date" id="filterDate">
                <button class="btn" onclick="filterLogs()">篩選</button>
                <button class="btn" onclick="resetFilters()">重設</button>
            </div>
            
            <div class="table-container">
                <table id="logsTable">
                    <thead>
                        <tr>
                            <th>時間</th>
                            <th>用戶 ID</th>
                            <th>題號</th>
                            <th>症狀代碼</th>
                            <th>用戶回答</th>
                            <th>機器人回覆</th>
                            <th>意圖</th>
                        </tr>
                    </thead>
                    <tbody id="logsBody"></tbody>
                </table>
            </div>
        </div>
    </div>
    
    <script>
        let allData = [];
        let charts = {};
        
        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            if (tabName === 'charts') {
                setTimeout(loadCharts, 100);
            }
        }
        
        // Load overview data
        async function loadData() {
            try {
                const response = await fetch('/api/admin/stats');
                const data = await response.json();
                
                allData = data.logs || [];
                
                // Update stats
                document.getElementById('totalUsers').textContent = data.total_users || 0;
                document.getElementById('todayChats').textContent = data.today_chats || 0;
                document.getElementById('completedSurveys').textContent = data.completed_surveys || 0;
                document.getElementById('avgRounds').textContent = data.avg_rounds || 0;
                
                // Populate filters
                const nodes = [...new Set(allData.map(d => d.node_id))].sort();
                const nodeSelect = document.getElementById('filterNode');
                nodeSelect.innerHTML = '<option value="">全部題號</option>';
                nodes.forEach(node => {
                    if (node) nodeSelect.innerHTML += `<option value="${node}">題號 ${node}</option>`;
                });
                
                // Render logs
                renderLogs(allData);
                
                // Load users
                loadUsers();
            } catch (error) {
                console.error('Load error:', error);
            }
        }
        
        // Load charts
        async function loadCharts() {
            try {
                const response = await fetch('/api/admin/charts');
                const data = await response.json();
                
                // Daily trend chart
                const dailyCtx = document.getElementById('dailyChart').getContext('2d');
                if (charts.daily) charts.daily.destroy();
                charts.daily = new Chart(dailyCtx, {
                    type: 'line',
                    data: {
                        labels: data.daily.labels,
                        datasets: [{
                            label: '對話數',
                            data: data.daily.data,
                            borderColor: '#667eea',
                            backgroundColor: 'rgba(102, 126, 234, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            y: { beginAtZero: true, ticks: { stepSize: 1 } }
                        }
                    }
                });
                
                // Node distribution chart
                const nodeCtx = document.getElementById('nodeChart').getContext('2d');
                if (charts.node) charts.node.destroy();
                charts.node = new Chart(nodeCtx, {
                    type: 'doughnut',
                    data: {
                        labels: data.nodes.labels,
                        datasets: [{
                            data: data.nodes.data,
                            backgroundColor: [
                                '#667eea', '#764ba2', '#f093fb', '#f5576c',
                                '#4facfe', '#00f2fe', '#43e97b', '#fa709a'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });
                
                // Intent distribution chart
                const intentCtx = document.getElementById('intentChart').getContext('2d');
                if (charts.intent) charts.intent.destroy();
                charts.intent = new Chart(intentCtx, {
                    type: 'bar',
                    data: {
                        labels: data.intents.labels,
                        datasets: [{
                            label: '次數',
                            data: data.intents.data,
                            backgroundColor: '#667eea'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true } }
                    }
                });
                
                // Completion rate chart
                const completionCtx = document.getElementById('completionChart').getContext('2d');
                if (charts.completion) charts.completion.destroy();
                charts.completion = new Chart(completionCtx, {
                    type: 'pie',
                    data: {
                        labels: ['已完成', '進行中'],
                        datasets: [{
                            data: [data.completion.completed, data.completion.in_progress],
                            backgroundColor: ['#43e97b', '#ffa502']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });
            } catch (error) {
                console.error('Charts error:', error);
            }
        }
        
        // Render logs table
        function renderLogs(data) {
            const tbody = document.getElementById('logsBody');
            tbody.innerHTML = '';
            
            data.slice(0, 100).forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${formatDate(row.created_at)}</td>
                    <td>${row.user_id ? row.user_id.substring(0, 15) + '...' : '-'}</td>
                    <td>${row.node_id || '-'}</td>
                    <td><span class="badge badge-info">${row.symptom_code || '-'}</span></td>
                    <td>${row.user_input || '-'}</td>
                    <td>${row.bot_reply ? row.bot_reply.substring(0, 50) + '...' : '-'}</td>
                    <td>${row.intent || '-'}</td>
                `;
                tbody.appendChild(tr);
            });
        }
        
        // Load users
        async function loadUsers() {
            try {
                const response = await fetch('/api/admin/users');
                const users = await response.json();
                
                const tbody = document.getElementById('usersBody');
                tbody.innerHTML = '';
                
                users.forEach(user => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${user.user_id.substring(0, 20)}...</td>
                        <td>${user.message_count}</td>
                        <td>${user.current_node || '-'}</td>
                        <td>${formatDate(user.first_message)}</td>
                        <td>${formatDate(user.last_message)}</td>
                        <td>
                            <button class="btn btn-warning" onclick="resetUser('${user.user_id}')">重置</button>
                            <button class="btn btn-danger" onclick="deleteUser('${user.user_id}')">刪除</button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (error) {
                console.error('Users error:', error);
            }
        }
        
        // Search user
        async function searchUser() {
            const userId = document.getElementById('userSearch').value;
            if (!userId) return;
            
            try {
                const response = await fetch(`/api/admin/user/${encodeURIComponent(userId)}`);
                const user = await response.json();
                
                const resultDiv = document.getElementById('userResult');
                if (user.error) {
                    resultDiv.innerHTML = `<div class="error">❌ ${user.error}</div>`;
                } else {
                    resultDiv.innerHTML = `
                        <div class="section">
                            <h3>用戶資訊</h3>
                            <p><strong>ID:</strong> ${user.user_id}</p>
                            <p><strong>對話數:</strong> ${user.message_count}</p>
                            <p><strong>當前節點:</strong> ${user.current_node || '-'}</p>
                            <p><strong>首次對話:</strong> ${formatDate(user.first_message)}</p>
                            <p><strong>最後對話:</strong> ${formatDate(user.last_message)}</p>
                            <button class="btn btn-warning" onclick="resetUser('${user.user_id}')">重置問卷</button>
                            <button class="btn btn-danger" onclick="deleteUser('${user.user_id}')">刪除用戶</button>
                        </div>
                    `;
                }
            } catch (error) {
                document.getElementById('userResult').innerHTML = `<div class="error">搜尋失敗</div>`;
            }
        }
        
        // Delete user
        async function deleteUser(userId) {
            if (!confirm('確定要刪除此用戶的所有資料嗎？此操作無法撤銷。')) return;
            
            try {
                const response = await fetch(`/api/admin/delete-user/${encodeURIComponent(userId)}`, {
                    method: 'DELETE'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('✅ 用戶已刪除');
                    loadUsers();
                    loadData();
                    document.getElementById('userResult').innerHTML = '<div class="success">✅ 用戶已刪除</div>';
                } else {
                    alert('❌ 刪除失敗: ' + result.message);
                }
            } catch (error) {
                alert('❌ 刪除失敗');
            }
        }
        
        // Reset user
        async function resetUser(userId) {
            if (!confirm('確定要重置此用戶的問卷進度嗎？')) return;
            
            try {
                const response = await fetch(`/api/admin/reset-user/${encodeURIComponent(userId)}`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('✅ 用戶已重置');
                    loadUsers();
                } else {
                    alert('❌ 重置失敗');
                }
            } catch (error) {
                alert('❌ 重置失敗');
            }
        }
        
        // Delete all data
        async function deleteAllData() {
            if (!confirm('⚠️ 警告：這將刪除所有用戶資料和對話記錄！\n\n此操作無法撤銷，確定要繼續嗎？')) return;
            if (!confirm('最後確認：你真的要清除所有資料嗎？')) return;
            
            try {
                const response = await fetch('/api/admin/delete-all', { method: 'DELETE' });
                const result = await response.json();
                
                if (result.success) {
                    alert('✅ 所有資料已清除');
                    loadUsers();
                    loadData();
                } else {
                    alert('❌ 清除失敗: ' + result.message);
                }
            } catch (error) {
                alert('❌ 清除失敗');
            }
        }
        
        // Filter logs
        function filterLogs() {
            const userFilter = document.getElementById('filterUser').value.toLowerCase();
            const nodeFilter = document.getElementById('filterNode').value;
            const dateFilter = document.getElementById('filterDate').value;
            
            const filtered = allData.filter(row => {
                const matchUser = !userFilter || (row.user_id && row.user_id.toLowerCase().includes(userFilter));
                const matchNode = !nodeFilter || row.node_id === nodeFilter;
                const matchDate = !dateFilter || (row.created_at && row.created_at.includes(dateFilter));
                return matchUser && matchNode && matchDate;
            });
            
            renderLogs(filtered);
        }
        
        function resetFilters() {
            document.getElementById('filterUser').value = '';
            document.getElementById('filterNode').value = '';
            document.getElementById('filterDate').value = '';
            renderLogs(allData);
        }
        
        function formatDate(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleString('zh-TW', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        }
        
        function refreshData() {
            loadData();
            alert('✅ 資料已重新整理');
        }
        
        function exportCSV() {
            window.open('/export/csv', '_blank');
        }
        
        // Initialize
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>'''

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard():
    """Admin dashboard with embedded HTML"""
    return HTMLResponse(content=ADMIN_HTML)

@app.get("/")
async def root():
    """Root endpoint - redirect to admin"""
    return {"message": "UTI Medical Bot API", "admin_url": "/admin", "webhook_url": "/webhook"}

# ============ API Endpoints ============

@app.get("/api/admin/stats")
async def get_stats():
    """Get admin statistics"""
    try:
        logs = db.get_all_logs()
        
        # Calculate stats
        total_users = len(set(log["user_id"] for log in logs if log["user_id"]))
        
        today = datetime.now().strftime("%Y-%m-%d")
        today_chats = len([log for log in logs if log.get("created_at", "").startswith(today)])
        
        surveys = db.get_survey_summary()
        completed_surveys = len([s for s in surveys if s.get("completed")])
        
        # Average rounds per user
        user_counts = {}
        for log in logs:
            uid = log.get("user_id")
            if uid:
                user_counts[uid] = user_counts.get(uid, 0) + 1
        avg_rounds = round(sum(user_counts.values()) / len(user_counts), 1) if user_counts else 0
        
        return {
            "total_users": total_users,
            "today_chats": today_chats,
            "completed_surveys": completed_surveys,
            "avg_rounds": avg_rounds,
            "logs": logs[:100]  # Limit to 100 for performance
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/admin/charts")
async def get_chart_data():
    """Get data for charts"""
    try:
        logs = db.get_all_logs()
        surveys = db.get_survey_summary()
        
        # Daily trend (last 7 days)
        daily_data = {}
        today = datetime.now()
        for i in range(7):
            date = (today - timedelta(days=i)).strftime("%m/%d")
            daily_data[date] = 0
        
        for log in logs:
            created = log.get("created_at", "")
            if created:
                date = datetime.fromisoformat(created.replace('Z', '+00:00')).strftime("%m/%d")
                if date in daily_data:
                    daily_data[date] += 1
        
        daily_labels = list(daily_data.keys())[::-1]
        daily_values = list(daily_data.values())[::-1]
        
        # Node distribution
        node_counts = {}
        for log in logs:
            node = log.get("node_id", "未知")
            node_counts[node] = node_counts.get(node, 0) + 1
        
        node_labels = list(node_counts.keys())[:8]
        node_values = [node_counts[k] for k in node_labels]
        
        # Intent distribution
        intent_counts = {}
        for log in logs:
            intent = log.get("intent", "unknown") or "unknown"
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        intent_labels = list(intent_counts.keys())[:6]
        intent_values = [intent_counts[k] for k in intent_labels]
        
        # Completion rate
        completed = len([s for s in surveys if s.get("completed")])
        in_progress = len(surveys) - completed if len(surveys) > 0 else 1
        
        return {
            "daily": {"labels": daily_labels, "data": daily_values},
            "nodes": {"labels": node_labels, "data": node_values},
            "intents": {"labels": intent_labels, "data": intent_values},
            "completion": {"completed": completed, "in_progress": max(1, in_progress)}
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/admin/users")
async def get_users():
    """Get all users with summary"""
    try:
        logs = db.get_all_logs()
        
        # Group by user
        user_data = {}
        for log in logs:
            uid = log.get("user_id")
            if not uid:
                continue
            
            if uid not in user_data:
                user_data[uid] = {
                    "user_id": uid,
                    "message_count": 0,
                    "first_message": log.get("created_at"),
                    "last_message": log.get("created_at"),
                    "current_node": None
                }
            
            user_data[uid]["message_count"] += 1
            
            created = log.get("created_at")
            if created:
                if created < user_data[uid]["first_message"]:
                    user_data[uid]["first_message"] = created
                if created > user_data[uid]["last_message"]:
                    user_data[uid]["last_message"] = created
        
        # Get current nodes
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, current_node FROM user_states")
        for row in cursor.fetchall():
            uid = row["user_id"]
            if uid in user_data:
                user_data[uid]["current_node"] = row["current_node"]
        
        return list(user_data.values())
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/admin/user/{user_id}")
async def get_user(user_id: str):
    """Get specific user details"""
    try:
        logs = db.get_user_logs(user_id)
        
        if not logs:
            return {"error": "User not found"}
        
        conn = db._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT current_node FROM user_states WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        current_node = row["current_node"] if row else None
        
        return {
            "user_id": user_id,
            "message_count": len(logs),
            "current_node": current_node,
            "first_message": logs[0].get("created_at") if logs else None,
            "last_message": logs[-1].get("created_at") if logs else None
        }
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/admin/delete-user/{user_id}")
async def delete_user(user_id: str):
    """Delete specific user data"""
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        # Delete logs
        cursor.execute("DELETE FROM message_logs WHERE user_id = ?", (user_id,))
        
        # Delete state
        cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        
        # Delete survey
        cursor.execute("DELETE FROM user_surveys WHERE user_id = ?", (user_id,))
        
        conn.commit()
        
        return {"success": True, "message": f"User {user_id} deleted"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/admin/reset-user/{user_id}")
async def reset_user(user_id: str):
    """Reset user to start node"""
    try:
        db.reset_user(user_id, flow_engine.get_start_node())
        return {"success": True, "message": f"User {user_id} reset"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.delete("/api/admin/delete-all")
async def delete_all():
    """Delete all data"""
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM message_logs")
        cursor.execute("DELETE FROM user_states")
        cursor.execute("DELETE FROM user_surveys")
        
        conn.commit()
        
        return {"success": True, "message": "All data deleted"}
    except Exception as e:
        return {"success": False, "message": str(e)}

# ============ Export ============

@app.get("/export/csv")
async def export_csv():
    """Export all data as CSV"""
    try:
        logs = db.get_all_logs()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "ID", "User ID", "Node ID", "Symptom Code", "Action Tag",
            "User Input", "Bot Reply", "Prompt", "Education Text",
            "Intent", "Is End", "Created At"
        ])
        
        # Data
        for log in logs:
            writer.writerow([
                log.get("id"),
                log.get("user_id"),
                log.get("node_id"),
                log.get("symptom_code"),
                log.get("action_tag"),
                log.get("user_input"),
                log.get("bot_reply"),
                log.get("prompt"),
                log.get("education_text"),
                log.get("intent"),
                log.get("is_end"),
                log.get("created_at")
            ])
        
        output.seek(0)
        
        # Create response with filename including timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"uti_bot_export_{timestamp}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return {"error": str(e)}

# ============ Main ============

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
