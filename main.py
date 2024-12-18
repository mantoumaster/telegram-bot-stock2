import os
import asyncio
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.font_manager as fm
import tempfile
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update, BotCommand, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import time
import logging
from prophet import Prophet  


# 載入 .env 檔案中的環境變數
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# 設定 logging 基本配置
logging.basicConfig(
    level=logging.INFO,  # 設定日誌級別
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# 設定字體
def setup_font():
    try:
        url_font = "https://drive.google.com/uc?id=1eGAsTN1HBpJAkeVM57_C7ccp7hbgSz3_"
        response_font = requests.get(url_font)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp_file:
            tmp_file.write(response_font.content)
            tmp_file_path = tmp_file.name
        fm.fontManager.addfont(tmp_file_path)
        mpl.rc("font", family="Taipei Sans TC Beta")
        print("✅ 字體設置成功：Taipei Sans TC Beta")
    except Exception as e:
        print(f"⚠️ 字體設置失敗: {str(e)}")
        mpl.rc("font", family="SimHei")

setup_font()

# --- 清除並重設 Bot 指令 ---
async def reset_commands(application):
    commands = [
        BotCommand("start", "啟動機器人"),
        BotCommand("s", "查詢股價和K線圖"),
        BotCommand("p", "Prophet 預測股價 (5 天區間)"),
        BotCommand("n", "查詢美股新聞"),
        BotCommand("ny", "查詢台股新聞"),
        BotCommand("h", "顯示其他股票工具連結"),
    ]
    await application.bot.set_my_commands(commands)
    print("✅ 新指令設置成功！")

# --- 查詢股價與 K 線圖 ---
# --- 查詢股價與 K 線圖 ---
async def stock_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/s 2330.TW 或 /s TSLA")
        return

    stock_code = context.args[0].upper()
    try:
        # 取得股價數據
        stock = yf.Ticker(stock_code)
        hist = stock.history(period="6mo")  # 取得最近6個月的股價數據

        if hist.empty:
            await update.message.reply_text(f"⚠️ 無法找到 {stock_code} 的股價數據，請確認股票代碼是否正確。")
            return

        # 提取報價資訊
        current_price = stock.info.get("currentPrice", hist["Close"].iloc[-1])  # 現價
        open_price = hist["Open"].iloc[-1]  # 開盤價
        close_price = hist["Close"].iloc[-1]  # 收盤價
        high_price = hist["High"].iloc[-1]  # 最高價
        low_price = hist["Low"].iloc[-1]  # 最低價
        volume = hist["Volume"].iloc[-1]  # 成交量

        # 組合股價資訊訊息
        message = (
            f"📊 **{stock_code} 股價資訊**\n\n"
            f"🔹 **現價 / 收盤價**：{current_price:.2f}\n"
            f"🔸 **開盤價**：{open_price:.2f}\n"
            f"🔺 **最高價**：{high_price:.2f}\n"
            f"🔻 **最低價**：{low_price:.2f}\n"
            f"📈 **成交量**：{volume:,}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")

        # 繪製日K、週K、月K圖
        for label, resample, color in [
            ("日K線", "D", "blue"),
            ("週K線", "W", "green"),
            ("月K線", "ME", "red")
        ]:
            # K 線圖邏輯，使用原本正常的繪圖邏輯
            data = hist["Close"].resample(resample).mean()
            plt.figure(figsize=(10, 5))
            plt.plot(data, label=label, color=color)
            plt.title(f"{stock_code} {label}")
            plt.legend()
            plt.grid(True, linestyle="--", alpha=0.7)
            path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            plt.savefig(path)
            plt.close()

            # 發送圖表
            await update.message.reply_photo(photo=open(path, "rb"), caption=f"📊 {label}")

    except Exception as e:
        await update.message.reply_text(f"❌ 查詢股價時發生錯誤：{str(e)}")

# --- 查詢美股新聞 ---
async def stock_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/n TSLA")
        return

    stock_code = context.args[0].upper()
    try:
        stock = yf.Ticker(stock_code)
        news = stock.news

        if not news:
            await update.message.reply_text(f"⚠️ 找不到 {stock_code} 的新聞。")
            return

        reply_text = f"📰 **{stock_code} 美股新聞**：\n"
        for idx, article in enumerate(news[:5]):
            title = article.get("title", "無標題")
            link = article.get("link", "#")
            reply_text += f"{idx+1}. [{title}]({link})\n"

        await update.message.reply_text(reply_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 查詢新聞時發生錯誤：{str(e)}")

import requests
from bs4 import BeautifulSoup
import time
from telegram import Update
from telegram.ext import ContextTypes

# --- 查詢 Yahoo 台股新聞 ---
async def taiwan_stock_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    從 Yahoo News 搜尋特定股票代碼的新聞，並返回前 5 則標題和連結
    """
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/ny 2330.TW")
        return

    stock_code = context.args[0].upper()
    url = f"https://tw.news.yahoo.com/search?p={stock_code}"
    print(f"📡 正在抓取：{url}")

    try:
        # 發送 HTTP 請求
        response = requests.get(url)
        response.raise_for_status()  # 確保請求成功
        soup = BeautifulSoup(response.text, "html.parser")

        # 抓取所有符合條件的新聞連結
        news_links = []
        for item in soup.find_all("a", href=True):
            href = item["href"]
            if href.startswith("/"):  # 抓取相對路徑
                full_url = f"https://tw.news.yahoo.com{href}"
                title = item.get_text(strip=True)
                if title and full_url not in news_links:
                    news_links.append((title, full_url))

        # 篩選出有效的新聞標題和連結（前 5 則）
        valid_news = [(title, url) for title, url in news_links if "news" in url][:5]

        if not valid_news:
            await update.message.reply_text(f"⚠️ 找不到 {stock_code} 的新聞。")
            return

        # 組合新聞訊息
        reply_text = f"📰 **{stock_code} 的 Yahoo News**：\n"
        for idx, (title, url) in enumerate(valid_news):
            reply_text += f"{idx+1}. [{title}]({url})\n"

        # 發送新聞訊息
        await update.message.reply_text(reply_text, parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ 抓取新聞時發生錯誤：{str(e)}")

# --- 啟動指令 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = "🎉 歡迎使用股票資訊機器人！請選擇以下功能："
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("/s 2330.TW  查詢股價和K線圖"), KeyboardButton("/n TSLA 查詢美股新聞")],
            [KeyboardButton("/ny 2330.TW 查詢台股新聞")],
        ],
        resize_keyboard=True
    )

    await update.message.reply_text(help_message, reply_markup=keyboard)

# --- 股價預測函數 ---
def predict_stock_price(stock_code, period, prediction_days):
    try:
        # 下載股票數據
        df = yf.download(stock_code, period=period)
        if df.empty:
            return "無法獲取股票數據", None
        
        # 準備數據
        data = df.reset_index()
        data = data[['Date', 'Close']]
        data.columns = ['ds', 'y']
        
        # 訓練 Prophet 模型
        model = Prophet(daily_seasonality=True)
        model.fit(data)
        
        # 創建未來日期
        future = model.make_future_dataframe(periods=prediction_days)
        forecast = model.predict(future)
        
        # 繪製圖表
        plt.figure(figsize=(12, 6))
        
        # 繪製實際數據
        plt.plot(data['ds'], data['y'], 
                label='實際收盤價', 
                color='blue')
        
        # 繪製預測數據
        plt.plot(forecast['ds'], forecast['yhat'],
                label='預測收盤價',
                color='orange',
                linestyle='--')
        
        # 新增預測區間
        plt.fill_between(forecast['ds'],
                        forecast['yhat_lower'],
                        forecast['yhat_upper'],
                        color='orange',
                        alpha=0.2)
        
        # 設置圖表格式
        plt.title(f'{stock_code} 股價預測', pad=20)
        plt.xlabel('日期')
        plt.ylabel('股價')
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        # 返回預測結果和圖表
        return forecast.tail(prediction_days).to_string(), plt.gcf()
        
    except Exception as e:
        logging.error(f"預測過程發生錯誤: {str(e)}")
        return f"預測過程發生錯誤: {str(e)}", None

# --- 預測股價功能 ---
async def prophet_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/p TSLA")
        return

    stock_code = context.args[0].upper()
    try:
        # 使用 Prophet 進行預測
        forecast_text, chart = predict_stock_price(stock_code, period="1y", prediction_days=5)

        if chart:
            # 儲存圖表
            path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            chart.savefig(path)
            plt.close()
            
            # 發送預測結果和圖表
            await update.message.reply_photo(photo=open(path, "rb"), caption=f"📊 **{stock_code} 預測 5 天股價區間**")
            await update.message.reply_text(f"```{forecast_text}```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ 無法預測 {stock_code} 的股價。")

    except Exception as e:
        await update.message.reply_text(f"❌ 預測股價時發生錯誤：{str(e)}")

# --- 顯示其他預測工具 ---
async def tools_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🛠 **其他股票工具**\n\n"
        "📊 台股預測 (LSTM)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/twStock-predict)\n"
        "📈 美股台股潛力股預測 (LSTM)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/twStock-Underdogs)\n"
        "🔮 美股台股預測 (Prophet)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/Stock-Predict-Prophet)"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

# --- 主程式 ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("s", stock_info))
    app.add_handler(CommandHandler("n", stock_news))
    app.add_handler(CommandHandler("ny", taiwan_stock_news))
    app.add_handler(CommandHandler("h", tools_help))  # 新增 /h 功能
    app.add_handler(CommandHandler("p", prophet_predict))  # 新增 /p 功能

    loop = asyncio.get_event_loop()
    loop.run_until_complete(reset_commands(app))

    print("🚀 Bot 已啟動...")
    app.run_polling()

if __name__ == "__main__":
    main()