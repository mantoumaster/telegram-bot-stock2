cd /home/bitnami/telegram-bot-stock2
source myenv/bin/activate
nohup python main.py > /tmp/stockapp.log 2>&1 &


sudo docker image prune -f
docker build -t telegram-bot-stock2 .

docker run -d \
  --name telegram-bot-stock2 \
  --env-file .env \
  telegram-bot-stock2

docker run -d \
  --name telegram-bot \
  -e TELEGRAM_BOT_TOKEN=你的Telegram金鑰 \
  -e LLM_API_KEY=你的LLM金鑰 \
  telegram-bot-stock2




docker tag telegram-bot-stock2 tbdavid2019/telegram-bot-stock2:latest
docker push tbdavid2019/telegram-bot-stock2:latest