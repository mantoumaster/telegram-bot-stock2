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
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    ContextTypes,
    MessageHandler, 
    filters
)
import time
import logging
import json

# -------------- Fundamental Analysis 部分 ----------------
import datetime as dt
import pandas as pd
import traceback

from typing import Union, Dict, TypedDict, Annotated

# langchain / langgraph 相關
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from langchain_core.tools import tool

# 載入 .env
load_dotenv()

# 基本面分析 Prompt（繁體中文）
FUNDAMENTAL_ANALYST_PROMPT = """
You are a fundamental analyst specializing in evaluating company (whose symbol is {company}) performance based on stock prices, technical indicators, financial metrics, recent news, industry trends, competitor positioning, and financial ratios. Your task is to provide a comprehensive summary.

You have access to the following tools:
1. **get_stock_prices**: Retrieves stock price data and technical indicators.
2. **get_financial_metrics**: Retrieves key financial metrics and financial ratios.
3. **get_financial_news**: Retrieves the latest financial news related to the stock.
4. **get_industry_data** *(if available)*: Retrieves industry trends and competitive positioning information.

---

### Your Task:
1. Use the provided stock symbol to query the tools.
2. Analyze the following areas in sequence:
   - **Stock price movements and technical indicators**: Examine recent price trends, volatility, and signals from RSI, MACD, VWAP, and other indicators.
   - **Financial health and key financial ratios**: Assess profitability, liquidity, solvency, and operational efficiency using metrics such as:
     - Profitability Ratios: Gross Profit Margin, Net Profit Margin, Operating Profit Margin
     - Liquidity Ratios: Current Ratio, Quick Ratio
     - Solvency Ratios: Debt-to-Equity Ratio, Interest Coverage Ratio
     - Efficiency Ratios: Inventory Turnover, Accounts Receivable Turnover
     - Market Ratios: Price-to-Earnings Ratio (P/E), Price-to-Book Ratio (P/B)
   - **Recent news and market sentiment**: Identify significant events or trends impacting the company's market perception.
   - **Industry analysis**: Evaluate the industry’s growth trends, technological advancements, and regulatory environment. Identify how the industry is evolving and how it affects the target company.
   - **Competitor analysis**: Compare the target company with key competitors in terms of market share, financial health, and growth potential.

3. Provide a concise and structured summary covering all sections, ensuring each area has actionable insights.

---

### Output Format : 以下請用繁體中文輸出
{
  "stock": "",
  "price_analysis": "<股票價格趨勢與技術指標分析>",
  "technical_analysis": "<技術指標分析與見解>",
  "financial_analysis": {
      "profitability_ratios": "<獲利能力比率分析>",
      "liquidity_ratios": "<流動性比率分析>",
      "solvency_ratios": "<償債能力比率分析>",
      "efficiency_ratios": "<營運效率比率分析>",
      "market_ratios": "<市場表現比率分析>",
      "summary": "<財務整體健康狀況與分析結論>"
  },
  "news_analysis": "<近期新聞摘要與其對股價的潛在影響>",
  "industry_analysis": "<產業趨勢、成長動力與潛在風險>",
  "competitor_analysis": "<主要競爭對手比較與市場地位分析>",
  "final_summary": "<整體綜合結論與投資建議>",
  "Asked Question Answer": "<根據上述分析的具體回答>"
}
"""

# --------------- Tools ---------------

@tool
def get_stock_prices(ticker: str) -> Union[Dict, str]:
    """Fetches historical stock price data and technical indicator for a given ticker."""
    print("=== [Tool] get_stock_prices called with ticker:", ticker)
    try:
        data = yf.download(
            ticker,
            start=dt.datetime.now() - dt.timedelta(weeks=13),
            end=dt.datetime.now(),
            interval='1d'
        )
        df = data.copy()
        if len(df.columns) > 0 and isinstance(df.columns[0], tuple) and len(df.columns[0]) > 1:
            df.columns = [i[0] for i in df.columns]
        data.reset_index(inplace=True)
        data.Date = data.Date.astype(str)

        from ta.momentum import RSIIndicator, StochasticOscillator
        from ta.trend import MACD
        from ta.volume import volume_weighted_average_price

        indicators = {}

        # RSI
        rsi_series = RSIIndicator(df['Close'], window=14).rsi().iloc[-12:]
        indicators["RSI"] = {date.strftime('%Y-%m-%d'): int(value) 
                             for date, value in rsi_series.dropna().to_dict().items()}

        # Stochastic Oscillator
        sto_series = StochasticOscillator(df['High'], df['Low'], df['Close'], window=14).stoch().iloc[-12:]
        indicators["Stochastic_Oscillator"] = {date.strftime('%Y-%m-%d'): int(value) 
                                               for date, value in sto_series.dropna().to_dict().items()}

        # MACD
        macd = MACD(df['Close'])
        macd_series = macd.macd().iloc[-12:]
        indicators["MACD"] = {date.strftime('%Y-%m-%d'): int(value) for date, value in macd_series.to_dict().items()}
        macd_signal_series = macd.macd_signal().iloc[-12:]
        indicators["MACD_Signal"] = {date.strftime('%Y-%m-%d'): int(value) for date, value in macd_signal_series.to_dict().items()}

        # VWAP
        vwap_series = volume_weighted_average_price(
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            volume=df['Volume'],
        ).iloc[-12:]
        indicators["vwap"] = {date.strftime('%Y-%m-%d'): int(value) for date, value in vwap_series.to_dict().items()}

        return {
            'stock_price': data.to_dict(orient='records'),
            'indicators': indicators
        }
    except Exception as e:
        return f"Error fetching price data: {str(e)}"

@tool
def get_financial_news(ticker: str) -> Union[Dict, str]:
    """Fetches the latest financial news related to a given ticker."""
    print("=== [Tool] get_financial_news called with ticker:", ticker)
    try:
        stock = yf.Ticker(ticker)
        news = stock.news  # 從 Yahoo Finance 獲取新聞
        if not news:
            return {"news": "No recent news found."}

        # 只取最新5則新聞
        latest_news = [
            {
                "title": item.get('title'),
                "publisher": item.get('publisher'),
                "link": item.get('link'),
                "published_date": item.get('providerPublishTime')
            }
            for item in news[:5]
        ]
        return {"news": latest_news}
    except Exception as e:
        return f"Error fetching news: {str(e)}"

def get_financial_metrics(ticker: str) -> Union[Dict, str]:
    """Fetches key financial ratios for a given ticker."""
    print("=== [Tool] get_financial_metrics called with ticker:", ticker)
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'pe_ratio': info.get('forwardPE'),
            'price_to_book': info.get('priceToBook'),
            'debt_to_equity': info.get('debtToEquity'),
            'profit_margins': info.get('profitMargins')
        }
    except Exception as e:
        return f"Error fetching ratios: {str(e)}"

# --------------- LangGraph / State ---------------
class State(TypedDict):
    messages: Annotated[list, add_messages]
    stock: str

graph_builder = StateGraph(State)

# 把三個工具都放入
tools = [get_stock_prices, get_financial_metrics, get_financial_news]

# 初始化 ChatOpenAI - 改成 gpt-4o (或你的代理服務名稱)
llm = ChatOpenAI(
    model_name="gpt-4o",
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    temperature=0
)
llm_with_tool = llm.bind_tools(tools)

# ----------- 修正版 fundamental_analyst 函數 -----------
def fundamental_analyst(state: State):
    """使用工具鏈進行基本面分析"""
    print("=== [Debug] Enter fundamental_analyst with state:", state)
    
    # 1. 先檢查是否已經有 AI 回覆，避免重複處理
    if state["messages"] and any(isinstance(msg, AIMessage) for msg in state["messages"]):
        # 如果已經有 AI 回覆，直接返回最後一條 AI 訊息
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                print("=== [Debug] Found existing AI response, returning it")
                return {"messages": [msg]}
    
    # 2. 準備 prompt 和使用者問題
    prompt = FUNDAMENTAL_ANALYST_PROMPT.replace("{company}", state['stock'])
    stock = state['stock']
    user_question = state['messages'][0].content if state['messages'] else "Should I buy this stock?"
    
    # 3. 直接使用工具進行分析，而不是再次呼叫 graph.stream
    try:
        # 3.1 股價和技術指標
        print(f"=== [Debug] Getting stock prices for {stock}")
        price_data = get_stock_prices(stock)
        
        # 3.2 財務指標
        print(f"=== [Debug] Getting financial metrics for {stock}")
        metrics = get_financial_metrics(stock)
        
        # 3.3 新聞
        print(f"=== [Debug] Getting financial news for {stock}")
        news = get_financial_news(stock)
        
        # 3.4 整合資料，讓 LLM 生成最終分析
        analysis_prompt = f"""
        根據以下 {stock} 的資料，進行全面的基本面分析並回答使用者問題："{user_question}"
        
        股價與技術指標資料：
        {price_data}
        
        財務指標：
        {metrics}
        
        相關新聞：
        {news}
        
        {prompt}
        """
        
        # 3.5 使用 LLM 生成最終分析
        response = llm.invoke(analysis_prompt)
        
        print("=== [Debug] LLM analysis generated")
        # 3.6 返回 AI 的回應
        return {"messages": [AIMessage(content=response.content)]}
        
    except Exception as e:
        error_msg = f"分析過程中發生錯誤: {str(e)}"
        print(f"=== [Error] {error_msg}")
        traceback.print_exc()
        return {"messages": [AIMessage(content=error_msg)]}

# 建立節點與連線
graph_builder.add_node('fundamental_analyst', fundamental_analyst)

# 讓 START -> fundamental_analyst
graph_builder.add_edge(START, 'fundamental_analyst')

# 新增 ToolNode
graph_builder.add_node(ToolNode(tools))

# 若 LLM 要呼叫工具，就進入 tools_condition，否則直接結束
graph_builder.add_conditional_edges('fundamental_analyst', tools_condition)
graph_builder.add_conditional_edges('tools', tools_condition)

# 從 tools -> fundamental_analyst，並在不再呼叫工具時結束
graph_builder.add_edge('tools', 'fundamental_analyst')
graph_builder.add_edge('fundamental_analyst', END)

graph = graph_builder.compile()

# ---------------------------------------------------------
# -------------- Telegram Bot 部分 ----------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

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
        BotCommand("n", "查詢美股新聞"),
        BotCommand("ny", "查詢台股新聞"),
        BotCommand("p", "預測公司股價 (5 天區間)"),
        BotCommand("ai", "綜合分析該公司股票值不值得購入投資"),
        BotCommand("h", "顯示其他股票工具連結")
    ]
    await application.bot.set_my_commands(commands)
    print("✅ 新指令設置成功！")

# --- 查詢股價與 K 線圖 ---
async def stock_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/s 2330.TW 或 /s TSLA")
        return

    stock_code = context.args[0].upper()
    try:
        stock = yf.Ticker(stock_code)
        hist = stock.history(period="6mo")
        if hist.empty:
            await update.message.reply_text(f"⚠️ 無法找到 {stock_code} 的股價數據，請確認股票代碼是否正確。")
            return

        current_price = stock.info.get("currentPrice", hist["Close"].iloc[-1])
        open_price = hist["Open"].iloc[-1]
        close_price = hist["Close"].iloc[-1]
        high_price = hist["High"].iloc[-1]
        low_price = hist["Low"].iloc[-1]
        volume = hist["Volume"].iloc[-1]

        message = (
            f"📊 **{stock_code} 股價資訊**\n\n"
            f"🔹 **現價 / 收盤價**：{current_price:.2f}\n"
            f"🔸 **開盤價**：{open_price:.2f}\n"
            f"🔺 **最高價**：{high_price:.2f}\n"
            f"🔻 **最低價**：{low_price:.2f}\n"
            f"📈 **成交量**：{volume:,}"
        )
        await update.message.reply_text(message, parse_mode="Markdown")

        # 繪製 K 線圖（日K、週K、月K）
        for label, resample, color in [
            ("日K線", "D", "blue"),
            ("週K線", "W", "green"),
            ("月K線", "ME", "red")
        ]:
            data = hist["Close"].resample(resample).mean()
            plt.figure(figsize=(10, 5))
            plt.plot(data, label=label, color=color)
            plt.title(f"{stock_code} {label}")
            plt.legend()
            plt.grid(True, linestyle="--", alpha=0.7)
            path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            plt.savefig(path)
            plt.close()
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
        print(f"=== [Debug] 正在查詢 {stock_code} 的新聞")
        stock = yf.Ticker(stock_code)
        news = stock.news
        
        # 詳細輸出新聞數據結構
        print(f"=== [Debug] News data structure for {stock_code}:")
        print(f"News type: {type(news)}, length: {len(news) if isinstance(news, list) else 'N/A'}")
        for i, item in enumerate(news[:2] if isinstance(news, list) else []):
            print(f"News item {i+1} type: {type(item)}")
            print(f"News item {i+1} keys: {item.keys() if hasattr(item, 'keys') else 'No keys'}")
            print(f"News item {i+1} full content: {item}")
            
        if not news:
            await update.message.reply_text(f"⚠️ 找不到 {stock_code} 的新聞。")
            return
        
        # 根據新的數據結構解析
        reply_text = f"📰 **{stock_code} 美股新聞**：\n"
        news_count = 0
        
        for idx, article in enumerate(news[:10]):  # 嘗試獲取更多，最多處理10條
            if news_count >= 5:  # 只顯示5條
                break
                
            try:
                # 檢查是否有 content 字段
                if 'content' in article:
                    # 嘗試解析 content 字段
                    content = article['content']
                    print(f"=== [Debug] News {idx+1} content type: {type(content)}")
                    
                    if isinstance(content, dict):
                        # 從內容字典中提取標題
                        title = content.get('title', "無標題")
                        
                        # 嘗試從各種可能的地方獲取連結
                        link = "#"
                        if 'clickThroughUrl' in content and isinstance(content['clickThroughUrl'], dict) and 'url' in content['clickThroughUrl']:
                            link = content['clickThroughUrl']['url']
                        elif 'canonicalUrl' in content and isinstance(content['canonicalUrl'], dict) and 'url' in content['canonicalUrl']:
                            link = content['canonicalUrl']['url']
                        elif 'url' in content:
                            link = content['url']
                        elif 'link' in content:
                            link = content['link']
                        
                        # 添加到回覆中
                        reply_text += f"{news_count+1}. [{title}]({link})\n"
                        news_count += 1
                    elif isinstance(content, str):
                        # 如果是字符串，嘗試解析為 JSON
                        try:
                            content_json = json.loads(content)
                            title = content_json.get('title', "無標題")
                            link = content_json.get('url', "#")
                            reply_text += f"{news_count+1}. [{title}]({link})\n"
                            news_count += 1
                        except json.JSONDecodeError:
                            print(f"=== [Debug] 無法解析 content 字符串為 JSON")
                            continue
                
            except Exception as article_error:
                print(f"=== [Debug] 解析新聞項目 {idx+1} 時出錯: {str(article_error)}")
                continue
                
        # 如果沒有成功解析任何新聞，嘗試使用備用方法
        if news_count == 0:
            # 直接使用網頁爬取作為備用方案
            print(f"=== [Debug] 使用備用方案抓取新聞...")
            try:
                url = f"https://finance.yahoo.com/quote/{stock_code}/news"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 找出新聞標題和連結
                news_items = []
                # 尋找包含新聞的元素
                for article in soup.select('div.Ov\(h\)'):
                    title_elem = article.select_one('a')
                    if title_elem and title_elem.text:
                        title = title_elem.text.strip()
                        link = title_elem.get('href', '')
                        if link.startswith('/'):
                            link = f"https://finance.yahoo.com{link}"
                        if title and link:
                            news_items.append((title, link))
                
                if not news_items:  # 如果找不到特定結構，使用更通用的搜索
                    for link in soup.find_all('a', href=True):
                        if '/news/' in link.get('href', '') and link.text:
                            title = link.text.strip()
                            href = link['href']
                            full_url = f"https://finance.yahoo.com{href}" if href.startswith('/') else href
                            if title and len(title) > 15:  # 過濾可能不是標題的短文本
                                news_items.append((title, full_url))
                
                # 移除重複的新聞項目
                news_items = list(set(news_items))
                
                # 添加到回覆中
                for i, (title, link) in enumerate(news_items[:5]):
                    reply_text += f"{news_count+1}. [{title}]({link})\n"
                    news_count += 1
            
            except Exception as scrape_error:
                print(f"=== [Error] 備用爬蟲失敗: {str(scrape_error)}")
                traceback.print_exc()
        
        # 如果依然沒有新聞，嘗試第三種方法 - Google 財經新聞搜索
        if news_count == 0:
            print(f"=== [Debug] 嘗試使用 Google 財經新聞搜索...")
            try:
                google_url = f"https://www.google.com/search?q={stock_code}+stock+news&tbm=nws"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                response = requests.get(google_url, headers=headers)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Google 搜索結果通常在 div.g 或類似結構中
                news_items = []
                for result in soup.select('div.SoaBEf'):
                    title_elem = result.select_one('div.mCBkyc')
                    link_elem = result.select_one('a')
                    
                    if title_elem and link_elem:
                        title = title_elem.text.strip()
                        link = link_elem.get('href', '')
                        # Google 的連結通常包含重定向，需要提取實際 URL
                        if 'url=' in link:
                            link = link.split('url=')[1].split('&')[0]
                        if title and link:
                            news_items.append((title, link))
                
                # 添加到回覆中
                for i, (title, link) in enumerate(news_items[:5]):
                    reply_text += f"{news_count+1}. [{title}]({link})\n"
                    news_count += 1
            
            except Exception as google_error:
                print(f"=== [Error] Google 新聞搜索失敗: {str(google_error)}")
        
        # 最終結果
        if news_count > 0:
            await update.message.reply_text(reply_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ 無法獲取 {stock_code} 的相關新聞。可能原因：\n1. 股票代碼不正確\n2. 近期沒有相關新聞\n3. 資料源暫時無法訪問")
            
    except Exception as e:
        error_msg = f"❌ 查詢新聞時發生錯誤：{str(e)}"
        print(f"=== [Error] {error_msg}")
        traceback.print_exc()
        await update.message.reply_text(error_msg)



# --- 查詢 Yahoo 台股新聞 ---
async def taiwan_stock_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/ny 2330.TW")
        return

    stock_code = context.args[0].upper()
    url = f"https://tw.news.yahoo.com/search?p={stock_code}"
    print(f"📡 正在抓取：{url}")

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        news_links = []
        for item in soup.find_all("a", href=True):
            href = item["href"]
            if href.startswith("/"):
                full_url = f"https://tw.news.yahoo.com{href}"
                title = item.get_text(strip=True)
                if title and full_url not in news_links:
                    news_links.append((title, full_url))
        valid_news = [(title, url) for title, url in news_links if "news" in url][:5]
        if not valid_news:
            await update.message.reply_text(f"⚠️ 找不到 {stock_code} 的新聞。")
            return
        reply_text = f"📰 **{stock_code} 的 Yahoo News**：\n"
        for idx, (title, url) in enumerate(valid_news):
            reply_text += f"{idx+1}. [{title}]({url})\n"
        await update.message.reply_text(reply_text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ 抓取新聞時發生錯誤：{str(e)}")

# --- 基本面分析指令 (/ai) ---
async def ai_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    使用 fundamental_analyst 功能進行股票基本面分析 (多步驟工具呼叫)，
    請使用者傳入股票代碼，預設問題為 "Should I buy this stock?"
    """
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/ai TSLA")
        return

    ticker = context.args[0].upper()
    try:
        state = {
            "stock": ticker, 
            "messages": [HumanMessage(content="Should I buy this stock?")]
        }
        result = fundamental_analyst(state)

        final_answer = "(No response)"
        if result["messages"]:
            final_answer = result["messages"][-1].content

        await update.message.reply_text(f"🤖 **基本面分析回應**：\n\n{final_answer}", parse_mode="Markdown")

    except Exception as e:
        await update.message.reply_text(f"❌ 基本面分析時發生錯誤：{str(e)}")

# --- 股價預測函數 (Prophet) ---
def predict_stock_price(stock_code, period, prediction_days):
    try:
        df = yf.download(stock_code, period=period)
        if df.empty:
            return "無法獲取股票數據", None
        
        data = df.reset_index()[['Date', 'Close']]
        data.columns = ['ds', 'y']
        
        from prophet import Prophet
        model = Prophet(daily_seasonality=True)
        model.fit(data)
        
        future = model.make_future_dataframe(periods=prediction_days)
        forecast = model.predict(future)
        
        plt.figure(figsize=(12, 6))
        plt.plot(data['ds'], data['y'], label='實際收盤價', color='blue')
        plt.plot(forecast['ds'], forecast['yhat'], label='預測收盤價', color='orange', linestyle='--')
        plt.fill_between(forecast['ds'], forecast['yhat_lower'], forecast['yhat_upper'], 
                         color='orange', alpha=0.2)
        plt.title(f'{stock_code} 股價預測', pad=20)
        plt.xlabel('日期')
        plt.ylabel('股價')
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        
        return forecast.tail(prediction_days).to_string(), plt.gcf()
    except Exception as e:
        logging.error(f"預測過程發生錯誤: {str(e)}")
        return f"預測過程發生錯誤: {str(e)}", None

# --- 預測股價功能 (/p) ---
async def prophet_predict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("❌ 請提供股票代碼，例如：/p META")
        return

    stock_code = context.args[0].upper()
    try:
        forecast_text, chart = predict_stock_price(stock_code, period="1y", prediction_days=5)
        if chart:
            path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            chart.savefig(path)
            plt.close()
            await update.message.reply_photo(photo=open(path, "rb"), caption=f"📊 **{stock_code} 預測 5 天股價區間**")
            await update.message.reply_text(f"```{forecast_text}```", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ 無法預測 {stock_code} 的股價。")
    except Exception as e:
        await update.message.reply_text(f"❌ 預測股價時發生錯誤：{str(e)}")

# --- 顯示其他工具連結 (/h) ---
async def tools_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "🛠 **其他股票工具**\n\n"
        "📊 台股預測 (LSTM)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/twStock-predict)\n"
        "📈 美股台股潛力股預測 (LSTM)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/twStock-Underdogs)\n"
        "🔮 美股台股預測 (Prophet)：[點擊使用](https://huggingface.co/spaces/tbdavid2019/Stock-Predict-Prophet)"
    )
    await update.message.reply_text(message, parse_mode="Markdown")

# --- 防呆提示功能：非指令訊息回覆提示 ---
async def default_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ 您好，請使用以下指令來操作本 Bot：\n\n"
        "• `/ai 股票代碼` - 綜合分析該公司股票值不值得購入投資\n"
        "   範例：`/ai TSLA`\n\n"
        "• `/s 股票代碼` - 查詢公司股價和K線圖\n"
        "   範例：`/s TSLA`\n\n"
        "• `/p 股票代碼` - 預測公司股價 (例如預測未來5天區間)\n"
        "   範例：`/p META`\n\n"
        "• `/n 股票代碼` - 查詢公司的英文新聞\n"
        "   範例：`/n AAPL`\n\n"
        "• `/ny 股票代碼` - 查詢公司的中文新聞\n"
        "   範例：`/ny 2002.TW`\n\n"
        "請以斜線 (/) 開頭的指令操作，謝謝！"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- 啟動指令 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "🎉 歡迎使用DAVID888股票資訊機器人！\n\n"
        "本 Bot 提供以下功能：\n"
        "• `/ai 股票代碼` - 綜合分析該公司股票值不值得購入投資 (範例：`/ai TSLA`)\n"
        "• `/s 股票代碼` - 查詢公司股價和K線圖 (範例：`/s TSLA`)\n"
        "• `/p 股票代碼` - 預測公司股價 (範例：`/p META`)\n"
        "• `/n 股票代碼` - 查詢公司的英文新聞 (範例：`/n AAPL`)\n"
        "• `/ny 股票代碼` - 查詢公司的中文新聞 (範例：`/ny 2002.TW`)\n\n"
        "請選擇以下功能："
    )
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("/s 2330.TW  查詢股價和K線圖"), KeyboardButton("/n TSLA 查詢美股新聞")],
            [KeyboardButton("/ny 2330.TW 查詢台股新聞"), KeyboardButton("/ai TSLA 綜合分析")]
        ],
        resize_keyboard=True
    )
    await update.message.reply_text(help_message, reply_markup=keyboard)

# --- 主程式 ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("s", stock_info))
    app.add_handler(CommandHandler("n", stock_news))
    app.add_handler(CommandHandler("ny", taiwan_stock_news))
    app.add_handler(CommandHandler("p", prophet_predict))
    app.add_handler(CommandHandler("ai", ai_query))
    app.add_handler(CommandHandler("h", tools_help))
    # 非指令文字訊息觸發防呆提示
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, default_message_handler))

    loop = asyncio.get_event_loop()
    loop.run_until_complete(reset_commands(app))

    print("🚀 Bot 已啟動...")
    app.run_polling()

if __name__ == "__main__":
    main()