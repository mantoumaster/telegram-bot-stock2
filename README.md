# Telegram 股票資訊機器人

## 功能簡介

這是一個基於 Python 和 `python-telegram-bot` 開發的 **Telegram 股票資訊機器人**，提供即時股票數據查詢、K 線圖生成，以及股價預測功能。  
目前支援 **台股** 和 **美股** 股票。

### 功能列表：
1. **股價查詢與 K 線圖**
   - `/s 股票代碼`：查詢最新股價、開盤價、收盤價、最高價、最低價、成交量，並提供日K、週K 和月K 線圖。

2. **美股新聞查詢**
   - `/n 股票代碼`：查詢美股股票的最新相關新聞。

3. **台股新聞查詢**
   - `/ny 股票代碼`：查詢 Yahoo 台股新聞。

4. **股價預測功能**
   - `/p 股票代碼`：使用 Prophet 模型預測未來 5 天的股價範圍。

5. **其他工具連結**
   - `/h`：顯示其他股票預測工具的連結。

---

## 部署方式

### 使用 Docker 執行

若要快速啟動機器人，可直接從 Docker Hub 下載映像並執行：

```bash
docker pull tbdavid2019/telegram-bot-stock2:latest
```

啟動容器時需指定 Telegram Bot Token：
```
docker run -d --name telegram-bot-stock2 \
  -e TELEGRAM_BOT_TOKEN=<你的 Telegram Bot Token> \
  tbdavid2019/telegram-bot-stock2:latest
```
手動部署

環境需求
	•	Python 3.9+
	•	相關套件（已列於 requirements.txt）

步驟
	1.	安裝必要套件：

pip install -r requirements.txt

	2.	設置環境變數：
創建 .env 檔案，並輸入你的 Telegram Bot Token。

TELEGRAM_BOT_TOKEN=你的 Telegram Bot Token

	3.	啟動機器人：

python main.py

指令列表

指令	功能描述	使用範例
/start	啟動機器人	/start
/s	查詢股價與 K 線圖	/s 2330.TW
/n	查詢美股新聞	/n TSLA
/ny	查詢台股新聞	/ny 2330.TW
/p	預測未來 5 天股價區間	/p TSLA
/h	顯示其他股票工具連結	/h

貢獻

歡迎貢獻！請透過 Pull Request 提交您的修改或改進建議。

英文說明

Telegram Stock Information Bot

Overview

This is a Telegram Stock Information Bot built with Python and python-telegram-bot, capable of retrieving real-time stock data, generating K-line charts, and forecasting stock prices.
It supports Taiwan Stock Exchange (TWSE) and U.S. Stocks.

Features:
	1.	Stock Price and K-line Charts
	•	/s <stock_code>: Retrieve the latest stock price, open, close, high, low prices, trading volume, and generate daily, weekly, and monthly K-line charts.
	2.	U.S. Stock News
	•	/n <stock_code>: Retrieve the latest news for U.S. stocks.
	3.	Taiwan Stock News
	•	/ny <stock_code>: Fetch Taiwan stock news from Yahoo.
	4.	Stock Price Prediction
	•	/p <stock_code>: Predict the next 5 days’ stock price range using the Prophet model.
	5.	Other Tools
	•	/h: Display links to other stock prediction tools.

Deployment

Run with Docker

To quickly start the bot, download the Docker image from Docker Hub:

docker pull tbdavid2019/telegram-bot-stock2:latest

Run the container with your Telegram Bot Token:

docker run -d --name telegram-bot-stock2 \
  -e TELEGRAM_BOT_TOKEN=<your_telegram_bot_token> \
  tbdavid2019/telegram-bot-stock2:latest

Manual Deployment

Requirements
	•	Python 3.9+
	•	Dependencies (provided in requirements.txt)

Steps
	
1.	Install dependencies:
```
pip install -r requirements.txt
```
2.	Configure environment variables:
Create a .env file and add your Telegram Bot Token.

TELEGRAM_BOT_TOKEN=your-telegram-bot-token

3.	Start the bot:

python main.py

Command List

Command	Description	Example Usage

/start	Start the bot	/start

/s	Retrieve stock prices and K-line charts	/s 2330.TW

/n	Fetch U.S. stock news	/n TSLA

/ny	Fetch Taiwan stock news	/ny 2330.TW

/p	Predict stock prices for 5 days	/p TSLA

/h	Show links to other tools	/h

Contribution

Contributions are welcome! Please submit your modifications or suggestions via Pull Requests.



---
