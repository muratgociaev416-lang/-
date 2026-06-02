# Toxic Meme Bot

Telegram-бот, который матерится, унижает, но умеет искать мемы по запросу.

## Переменные окружения (Secrets)

- `TELEGRAM_TOKEN` — токен бота от @BotFather
- `OPENROUTER_API_KEY` — ключ с openrouter.ai

## Деплой на Render

1. Загрузите этот репозиторий на GitHub.
2. На Render создайте Web Service, подключите репозиторий.
3. Укажите:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `web: python app.py`
4. Добавьте переменные окружения (TELEGRAM_TOKEN, OPENROUTER_API_KEY).
5. Нажмите Deploy.

Бот будет жить 24/7 (keep-alive через Flask).
