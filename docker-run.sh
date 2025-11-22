#!/bin/bash

# 檢查 .env 檔案是否存在
if [ ! -f .env ]; then
    echo "❌ 錯誤：找不到 .env 檔案"
    echo "請先複製 .env.example 為 .env，並填入正確的環境變數值"
    echo "執行：cp .env.example .env"
    exit 1
fi

# 載入 .env 檔案
source .env

# 檢查必要的環境變數
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "❌ 錯誤：TELEGRAM_BOT_TOKEN 未設定"
    exit 1
fi

# 建立 Docker 映像檔
echo "🔨 正在建立 Docker 映像檔..."
docker build -t telegram-bot-stock .

# 執行 Docker 容器，並傳入環境變數
echo "🚀 正在啟動 Docker 容器..."
docker run -d \
    --name telegram-bot-stock \
    --restart unless-stopped \
    -e TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -e OPENAI_MODEL="${OPENAI_MODEL:-gpt-4o}" \
    -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
    -e DIFY_API_KEY="$DIFY_API_KEY" \
    -e DIFY_BASE_URL="${DIFY_BASE_URL:-http://llm.glsoft.ai/v1/chat-messages}" \
    telegram-bot-stock

echo "✅ Docker 容器已啟動！"
echo "📊 查看日誌：docker logs -f telegram-bot-stock"
echo "🛑 停止容器：docker stop telegram-bot-stock"
echo "🗑️  刪除容器：docker rm telegram-bot-stock"
