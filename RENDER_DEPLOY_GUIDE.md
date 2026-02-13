# Render 免費部署指南

> 5分鐘內完成部署，完全免費！（適合測試和 Demo）

---

## ⚠️ 重要提醒

**Render 免費版的限制：**
- ✅ 完全免費，無需信用卡
- ⚠️ **15分鐘沒人連線會休眠**（省電模式）
- ⚠️ **第一次傳訊息要等 10-30 秒**（喚醒時間）
- ✅ 之後的回覆就會正常速度

**適合場景：**
- 功能測試
- Demo 給老闆/客戶看
- 開發階段驗證
- 低頻率使用（一天幾則訊息）

**不適合：**
- 正式營運（使用者會覺得回覆很慢）
- 高頻率使用（每 15 分鐘都要喚醒）

---

## 🚀 部署步驟（總共 5 步）

---

## 步驟 1：準備 GitHub 倉庫（2分鐘）

### 1.1 建立 GitHub 倉庫

1. 前往 https://github.com/new
2. Repository name：輸入 `line-medical-bot`
3. 選擇 **Private**（私人倉庫，比較安全）
4. 點「Create repository」

### 1.2 推送程式碼到 GitHub

在本地專案目錄執行：

```bash
# 進入專案目錄
cd line-excel-bot-poc

# 初始化 Git
git init

# 加入所有檔案
git add .

# 提交
git commit -m "Initial commit"

# 連結遠端倉庫（把 xxxx 換成你的 GitHub 帳號）
git remote add origin https://github.com/xxxx/line-medical-bot.git

# 推送
git branch -M main
git push -u origin main
```

**完成後：** 在 GitHub 上可以看到你的程式碼

---

## 步驟 2：註冊 Render 帳號（1分鐘）

1. 前往 https://render.com/
2. 點「Get Started for Free」
3. 選擇「Sign up with GitHub」
4. 授權 Render 存取你的 GitHub
5. 完成註冊！

---

## 步驟 3：建立 Web Service（2分鐘）

### 3.1 建立新服務

1. 在 Render Dashboard，點「New +」按鈕
2. 選擇「Web Service」

### 3.2 連結 GitHub

1. 找到你的 `line-medical-bot` 倉庫
2. 點「Connect」

### 3.3 設定部署參數

| 設定欄位 | 填寫內容 |
|---------|---------|
| **Name** | line-medical-bot（或你想要的名稱） |
| **Region** | **Singapore (Southeast Asia)** ⭐ 選這個最近 |
| **Branch** | main |
| **Runtime** | **Docker** |
| **Dockerfile Path** | `./deploy/Dockerfile` |

其他保持預設，點「Create Web Service」

---

## 步驟 4：設定環境變數（1分鐘）

### 4.1 進入環境變數設定

服務建立後，會自動開始部署。同時我們來設定環境變數：

1. 在左側選單點「Environment」
2. 點「Add Environment Variable」

### 4.2 加入以下變數

| Key | Value | 說明 |
|-----|-------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | 你的 Channel Access Token | 從 LINE Developers 複製 |
| `LINE_CHANNEL_SECRET` | 你的 Channel Secret | 從 LINE Developers 複製 |
| `OPENAI_API_KEY` | 你的 OpenAI Key（可選）| 沒有就不填 |
| `PORT` | `8000` | 固定填 8000 |

**如何取得 LINE 憑證：**
1. 前往 https://developers.line.biz/
2. 進入你的 Channel
3. Messaging API → Channel Access Token（點 Issue）
4. Basic Settings → Channel Secret

### 4.3 儲存並重新部署

1. 點「Save Changes」
2. 回到「Overview」頁面
3. 點「Manual Deploy」→「Deploy latest commit」

---

## 步驟 5：設定 LINE Webhook（1分鐘）

### 5.1 取得 Render 網址

1. 等待部署完成（約 2-3 分鐘）
2. 在 Overview 頁面，看到網址：
   ```
   https://line-medical-bot-xxx.onrender.com
   ```
3. 複製這個網址

### 5.2 設定 LINE Webhook

1. 前往 https://developers.line.biz/
2. 進入你的 Channel → Messaging API
3. 找到「Webhook URL」
4. 填入：`https://line-medical-bot-xxx.onrender.com/webhook`
   - **注意**：要加上 `/webhook`
5. 開啟「Use webhook」開關
6. 點「Verify」驗證

### 5.3 關閉自動回覆（重要！）

1. 在 Messaging API 頁面
2. 找到「Auto-reply messages」→ 選 **Disabled**
3. 找到「Greeting messages」→ 選 **Disabled**

---

## ✅ 完成！測試你的 Bot

1. 用 LINE 掃描 QR code 加入好友
2. 傳送任意訊息
3. **第一次會等 10-30 秒**（因為在喚醒）
4. 之後應該會正常收到回覆

---

## 🔧 常用操作

### 查看日誌（有問題時用）

1. 在 Render Dashboard 點你的服務
2. 點「Logs」頁籤
3. 可以看到所有執行紀錄

### 重新部署

修改程式碼後推送到 GitHub，Render 會自動重新部署：

```bash
git add .
git commit -m "更新問卷內容"
git push
```

Render 會自動偵測並重新部署（約 2-3 分鐘）

### 手動觸發部署

1. 在 Render Dashboard
2. 點「Manual Deploy」
3. 選「Deploy latest commit」

---

## ⚠️ 重要注意事項

### 1. 休眠問題

**現象：** 15分鐘沒人傳訊息，Bot 會進入休眠
**影響：** 下次傳訊息要等 10-30 秒才回覆
**解決方案：**
- 免費版無法避免，這是 Render 的設計
- 升級到付費版（$7/月）可解決
- 或改用 DigitalOcean $6/月

### 2. 網址會變嗎？

**不會！** 只要你不改服務名稱，網址是固定的：
```
https://line-medical-bot-xxx.onrender.com
```

### 3. 資料會遺失嗎？

**會！** Render 免費版的檔案儲存不是永久的：
- 每次重新部署會重置
- 休眠後喚醒資料還在（但重部署會清掉）
- **解決方案：** 使用外部資料庫（如 Render PostgreSQL 免費版）

**簡易解決方案：**
如果你只是測試，沒關係。正式使用請改用 DigitalOcean。

### 4. 免費版限制

| 項目 | 限制 |
|------|------|
| 運行時間 | 750 小時/月（足夠用） |
| 頻寬 | 100GB/月（足夠用） |
| 硬碟 | 512MB（足夠用） |
| 休眠 | 15分鐘無連線後休眠 |

---

## 🆚 Render vs DigitalOcean

| 比較項目 | Render 免費版 | DigitalOcean $6/月 |
|---------|--------------|-------------------|
| **費用** | $0 | $6/月 |
| **休眠** | 會休眠（回覆慢） | 不會休眠 |
| **網址** | onrender.com | 你的專屬 IP |
| **資料持久** | 重部署會清空 | 永久儲存 |
| **速度** | 新加坡節點快 | 新加坡節點快 |
| **專業度** | 測試用 | 正式營運用 |

---

## 🎯 建議使用流程

### Phase 1：測試（1-2 週）
- 使用 **Render 免費版**
- 測試所有功能是否正常
- 調整問卷內容
- Demo 給相關人員

### Phase 2：正式上線
- 註冊 **DigitalOcean**（新戶有 $200 試用金）
- 照著 DEPLOY_GUIDE.md 部署
- 把 LINE Webhook 換成 DigitalOcean 的 IP
- 停用 Render 服務

---

## ❓ 常見問題

**Q: 為什麼第一次回覆這麼慢？**
> 因為 Render 免費版 15分鐘沒人連線會休眠。這是為了省資源，喚醒需要時間。

**Q: 如何讓 Bot 不要休眠？**
> 免費版無法避免。升級 Render 付費版（$7/月）或改用 DigitalOcean $6/月。

**Q: 我的對話紀錄會不見嗎？**
> 在 Render 免費版上，**每次重新部署都會清空資料庫**。如果要保留紀錄，需要：
> 1. 使用 Render PostgreSQL（免費版可申請）
> 2. 或定期下載備份 `/export/csv`
> 3. 或直接改用 DigitalOcean

**Q: 如何備份資料？**
> 定期訪問：`https://你的網址.onrender.com/export/csv` 下載備份。

**Q: 可以同時用 Render + DigitalOcean 嗎？**
> 可以！先用 Render 測試，確定沒問題後再搬到 DigitalOcean。LINE Webhook 可以隨時改網址。

---

## 🚀 快速檢查清單

部署完成後確認：

- [ ] GitHub 倉庫已建立並推送程式碼
- [ ] Render 帳號已註冊
- [ ] Web Service 已建立（選 Singapore 節點）
- [ ] 環境變數已設定（LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET）
- [ ] 服務狀態顯示 "Live"
- [ ] LINE Webhook URL 已更新為 Render 網址
- [ ] LINE Auto-reply 已關閉
- [ ] 已加入 LINE 好友並收到第一則訊息
- [ ] 知道第一次回覆會慢（10-30 秒）

---

## 📞 需要幫助？

如果遇到問題：
1. 查看 Render Logs 頁面的錯誤訊息
2. 確認環境變數是否正確設定
3. 確認 LINE Webhook URL 是否正確（要加 /webhook）

---

**現在開始部署吧！** 🎉
