FROM python:3.11-slim

WORKDIR /app

# 安裝相依套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製程式碼
COPY app/ ./app/
COPY data/ ./data/

# 建立資料目錄
RUN mkdir -p data

EXPOSE 8000

CMD ["python", "-m", "app.main"]
