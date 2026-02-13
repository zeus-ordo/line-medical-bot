# LINE 醫療問診 Bot - 部署手冊

> 本手冊適合**非技術人員**，跟著步驟即可完成部署

---

## 📋 前置準備（请先準備好這些）

### 1. 必要項目

| 項目 | 說明 | 去哪裡取得 |
|------|------|-----------|
| **LINE 帳號** | 個人帳號即可 | 手機上應該有了 |
| **電腦** | Windows/Mac 都可以 | - |
| **信用卡** | 租伺服器用 | - |

### 2. 預算

- **伺服器費用**：約 $6 美金/月（約台幣 180 元）
- **LINE Messaging API**：免費（每月前 1000 則訊息）
- **OpenAI API**（可選）：依使用量約 $0.1-1 美金/月

---

## 🚀 部署步驟（總共 5 大步驟）

---

## 步驟 1：建立 LINE Bot 帳號（約 10 分鐘）

### 1.1 進入 LINE Developers

1. 打開瀏覽器，前往：https://developers.line.biz/
2. 點右上角「Log in」，用 LINE 帳號登入

### 1.2 建立 Provider

1. 點「Create New Provider」
2. 輸入名稱，例如：`我的診所`
3. 點「Create」

### 1.3 建立 Channel（機器人）

1. 點「Create a new channel」
2. 選擇 **「Messaging API」**
3. 填寫基本資料：
   - Channel name：問診機器人
   - Channel description：健康問診服務
   - Category：Health & Fitness
   - Subcategory：Medical
4. 點「Create」

### 1.4 取得重要憑證（⚠️ 請複製保存）

1. 進入剛建立的 Channel
2. 左側選單點「Messaging API」
3. 找到這兩個值並**複製保存**：
   - **Channel Access Token**（點 Issue 產生長期 Token）
   - **Channel Secret**（在 Basic settings 頁面）

### 1.5 設定 Webhook（暫時隨便填）

1. 在 Messaging API 頁面
2. 找到 Webhook URL，暫時填入：`https://example.com/webhook`
3. 開啟「Use webhook」開關
4. **等等會再回來改成正確網址**

---

## 步驟 2：租用雲端伺服器（約 15 分鐘）

### 2.1 選擇廠商（推薦 DigitalOcean）

1. 前往：https://www.digitalocean.com/
2. 註冊帳號（需要信用卡驗證）
3. 點「Create」→「Droplets」

### 2.2 設定伺服器

| 設定項目 | 建議選項 |
|---------|---------|
| Region | Singapore（亞洲較快）|
| OS | Ubuntu 22.04 (LTS) |
| Plan | Basic |
| CPU | Regular Intel with SSD |
| Size | **$6/月** (1 GB RAM / 1 CPU / 25 GB SSD) |
| Authentication | **Password**（輸入一組密碼並記住）|
| Hostname | line-bot（隨便取）|

4. 點「Create Droplet」
5. 等待 1-2 分鐘，伺服器就建立好了

### 2.3 取得伺服器 IP

1. 在 Droplets 列表看到你的伺服器
2. 複製 **IPv4 地址**（例如：`128.199.123.45`）
3. **這個 IP 等等會用到**

---

## 步驟 3：連線到伺服器並安裝（約 20 分鐘）

### 3.1 下載連線工具

**Windows 用戶**：
1. 下載 PuTTY：https://www.putty.org/
2. 安裝並開啟

**Mac 用戶**：
1. 打開「終端機」（Terminal）
2. 內建就有，不用安裝

### 3.2 連線到伺服器

**Windows (PuTTY)**：
1. 開啟 PuTTY
2. Host Name：輸入你的 IP（例如 `128.199.123.45`）
3. Port：22
4. 點「Open」
5. 登入帳號：`root`
6. 密碼：輸入你在 2.2 設定的密碼（輸入時不會顯示，沒關係）

**Mac (Terminal)**：
```bash
ssh root@你的IP
# 例如：ssh root@128.199.123.45
# 輸入密碼（不會顯示）
```

### 3.3 安裝 Docker（複製貼上以下指令）

連線成功後，依序執行這些指令（一行一行貼上）：

```bash
# 更新系統
apt-get update

# 安裝 Docker
curl -fsSL https://get.docker.com | sh

# 啟動 Docker
systemctl start docker
systemctl enable docker

# 安裝 docker-compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 確認安裝成功
docker --version
docker-compose --version
```

看到版本號表示成功！

---

## 步驟 4：上傳並啟動機器人（約 15 分鐘）

### 4.1 將專案上傳到伺服器

**方法 A：使用 Git（推薦）**

如果你會用 Git：
```bash
cd ~
git clone https://github.com/你的帳號/line-excel-bot-poc.git
cd line-excel-bot-poc
```

**方法 B：手動上傳（不會 Git 的話）**

**Windows**：
1. 下載 WinSCP：https://winscp.net/
2. 安裝後開啟
3. 檔案協定：SFTP
4. 主機名稱：你的 IP
5. 使用者名稱：root
6. 密碼：你的密碼
7. 登入後，把 `line-excel-bot-poc` 資料夾拖曳到右側 `/root/`

**Mac**：
```bash
# 在本地電腦開啟終端機，執行：
scp -r line-excel-bot-poc root@你的IP:~/
# 例如：scp -r line-excel-bot-poc root@128.199.123.45:~/
```

### 4.2 設定環境變數

在伺服器上執行：

```bash
cd ~/line-excel-bot-poc

# 建立環境變數檔案
cat > .env << 'EOF'
LINE_CHANNEL_ACCESS_TOKEN=你的_CHANNEL_ACCESS_TOKEN
LINE_CHANNEL_SECRET=你的_CHANNEL_SECRET
OPENAI_API_KEY=你的_OPENAI_API_KEY（沒有就留空）
PORT=8000
EOF
```

**注意**：把 `你的_CHANNEL_ACCESS_TOKEN` 等換成實際的值

### 4.3 修改問卷內容（可選）

```bash
# 編輯問卷內容
nano data/flow.csv
```

會看到範例問卷，請根據需求修改：
- 第一行是欄位名稱，**不要改**
- 每一行是一個問題
- 修改完按 `Ctrl+O` 存檔，`Ctrl+X` 離開

### 4.4 啟動機器人！

```bash
cd deploy
docker-compose up -d
```

等待 1-2 分鐘，讓它下載並啟動。

### 4.5 確認啟動成功

```bash
# 測試健康檢查
curl http://localhost:8000/health
```

應該看到：
```json
{"status": "ok", "flow_loaded": true, "total_nodes": 7, ...}
```

---

## 步驟 5：設定 LINE Webhook（約 5 分鐘）

### 5.1 回到 LINE Developers

1. 前往 https://developers.line.biz/
2. 進入你的 Channel → Messaging API

### 5.2 設定正確的 Webhook URL

1. 找到「Webhook URL」欄位
2. 填入：`http://你的IP:8000/webhook`
   - 例如：`http://128.199.123.45:8000/webhook`
3. 點「Update」
4. 點「Verify」驗證

### 5.3 關閉自動回覆（重要）

1. 在 Messaging API 頁面
2. 找到「Auto-reply messages」
3. 選擇 **Disabled**
4. 找到「Greeting messages」
5. 選擇 **Disabled**

這樣機器人才會回覆你設定的內容，而不是 LINE 預設的。

### 5.4 加入好友測試

1. 在 Basic settings 頁面，找到 QR code
2. 用 LINE 掃描加入好友
3. 傳送訊息測試！

---

## 🎉 完成！你應該看到：

- ✅ 加入 LINE 好友後，收到第一題問候
- ✅ 回答「是/否」後，自動跳到下一題
- ✅ 最後顯示衛教內容
- ✅ 對話紀錄保存在伺服器

---

## 📊 常用維護指令

### 查看機器人狀態
```bash
cd ~/line-excel-bot-poc/deploy
docker-compose ps
```

### 重啟機器人
```bash
cd ~/line-excel-bot-poc/deploy
docker-compose restart
```

### 查看日誌（有問題時用）
```bash
cd ~/line-excel-bot-poc/deploy
docker-compose logs -f
```
按 `Ctrl+C` 離開

### 停止機器人
```bash
cd ~/line-excel-bot-poc/deploy
docker-compose down
```

### 匯出對話紀錄
在瀏覽器輸入：
```
http://你的IP:8000/export/csv
```
會自動下載 CSV 檔案

---

## 🔧 修改問卷內容

### 編輯 Excel/CSV

1. 用 Excel 或記事本開啟 `data/flow.csv`
2. 修改內容
3. 存檔
4. 重新上傳到伺服器（覆蓋原檔）
5. 重啟機器人：
   ```bash
   cd ~/line-excel-bot-poc/deploy
   docker-compose restart
   ```

### Excel 格式說明

| 欄位 | 說明 | 範例 |
|------|------|------|
| 序號 | 題號（數字） | 1, 2, 3... |
| 判斷問題 | 問使用者的話 | 請問您今天是否有發燒？ |
| 症狀代碼 | 內部編號 | FEVER-01 |
| 建議行動方向 | 分類標籤 | 初步風險評估 |
| 內容說明（衛教） | 回覆的衛教文字 | 發燒可能是感染的徵兆... |
| 肯定→分支 | 回答「是」跳到哪題 | 2 |
| 否定→分支 | 回答「否」跳到哪題 | 5 |

---

## ❗ 常見問題

### Q1: 機器人沒有回覆？

**檢查步驟：**
1. 確認伺服器有在運行：
   ```bash
   curl http://localhost:8000/health
   ```
2. 確認 LINE Webhook URL 正確（要有 `http://`）
3. 確認 Auto-reply 已關閉
4. 查看日誌找錯誤：
   ```bash
   docker-compose logs
   ```

### Q2: 如何備份資料？

```bash
# 備份 SQLite 資料庫
cp ~/line-excel-bot-poc/data/bot.db ~/bot-backup-$(date +%Y%m%d).db
```

### Q3: 如何更新程式？

```bash
cd ~/line-excel-bot-poc
git pull  # 如果有用 Git
docker-compose -f deploy/docker-compose.yml restart
```

### Q4: 免費的替代方案？

如果不想花錢租伺服器，可以用：
- **Heroku**（免費但會睡著，回覆慢）
- **Render**（免費但有啟動延遲）
- **Google Cloud Run**（有免費額度）

但正式使用建議還是租 $6/月的 VM 最穩定。

### Q5: 沒有 OpenAI Key 可以用嗎？

**可以！**
- 系統會用「規則判定」（是/否/數字）
- 只是對於模糊回答（如「好像有」）可能無法準確判定
- OpenAI 只是輔助，非必要

---

## 📞 需要幫助？

如果遇到問題：
1. 先查看「常用維護指令」的日誌
2. 確認每個步驟都有正確執行
3. 檢查環境變數是否設定正確（`.env` 檔案）

---

## 📝 檢查清單

部署完成後，確認以下項目：

- [ ] LINE Channel 已建立
- [ ] 已取得 Channel Access Token
- [ ] 已取得 Channel Secret
- [ ] 已租用 VM 並取得 IP
- [ ] 已安裝 Docker
- [ ] 已上傳專案到 VM
- [ ] 已設定 .env 環境變數
- [ ] 已啟動 docker-compose
- [ ] LINE Webhook URL 已設定為正確 IP
- [ ] 已關閉 Auto-reply
- [ ] 已加入好友並成功收到第一則訊息
- [ ] 已測試回答問題並正確跳轉
- [ ] 已測試匯出 CSV 功能

---

**恭喜你完成部署！** 🎊
