# 使用官方 Python 3.9 基底映像檔
FROM python:3.11

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案文件
COPY . .

# 設定環境變數
ENV BOT_TOKEN=your-telegram-bot-token
ENV PYTHONUNBUFFERED=1

# 啟動腳本
CMD ["bash", "run.sh"]