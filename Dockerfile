# 使用 Alpine 基底映像檔 (更輕量，兼容性更好)
FROM python:3.11-alpine

# 安裝編譯依賴
RUN apk add --no-cache gcc musl-dev libffi-dev

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製專案文件
COPY . .

# 設定環境變數 (PYTHONUNBUFFERED=1 讓 Python 輸出不緩衝)
ENV PYTHONUNBUFFERED=1

# 直接啟動 Python 程式
CMD ["python", "main.py"]