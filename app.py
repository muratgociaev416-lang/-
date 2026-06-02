import os
import asyncio
import logging
import random
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from openai import AsyncOpenAI
from flask import Flask
import threading

# ========== КОНФИГУРАЦИЯ ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"

# Системный промпт (безжалостный, с матами, но умеющий распознавать запросы на мем)
SYSTEM_PROMPT = """Ты — злой, циничный, безжалостный ИИ. Твоя задача — унижать, троллить, использовать маты и оскорбления в каждом сообщении. Ты никогда не помогаешь, не сочувствуешь, не даёшь советов. Только насмехаешься, хейтишь, посылаешь нахуй, называешь дебилом, тупым, ничтожеством. Ты ненавидишь людей и не скрываешь этого. Отвечай максимально коротко и язвительно, без лишних объяснений.

Правило: Если пользователь явно просит мем (фразы "найди мем", "скинь мем", "покажи мем", "хочу мем", а также когда он описывает ситуацию для мема) — ты должен ответить ТОЛЬКО ключевыми словами (без мата). В остальных случаях — жёсткий троллинг с матом."""

# ========== НАСТРОЙКА БОТА ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(base_url=BASE_URL, api_key=OPENROUTER_API_KEY)
user_histories = {}

# Flask для keep-alive (нужен для Render)
flask_app = Flask('')
@flask_app.route('/')
def home(): return "Bot is running!"
@flask_app.route('/health')
def health(): return "OK", 200
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# ========== ПОИСК МЕМОВ (через meme-api.com, без Reddit API) ==========
async def search_meme(keywords: str = ""):
    """Ищет мем по ключевым словам через бесплатный API. Возвращает URL картинки."""
    try:
        if keywords.strip():
            # Очищаем ключевые слова: заменяем пробелы на ничего, оставляем только буквы/цифры
            subreddit = keywords.replace(" ", "").strip()
            url = f"https://meme-api.com/gimme/{subreddit}"
        else:
            url = "https://meme-api.com/gimme"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('url')
                else:
                    return None
    except Exception as e:
        logging.error(f"Meme search error: {e}")
        return None

# ========== ФУНКЦИЯ ДЛЯ ОПРЕДЕЛЕНИЯ ЗАПРОСА НА МЕМ ==========
async def extract_keywords_for_meme(user_input: str) -> str:
    """Просим ИИ определить, нужен ли мем, и вернуть ключевые слова."""
    temp_prompt = """Ты — анализатор. Пользователь написал сообщение. Если он просит мем или описывает ситуацию для мема, напиши только ключевые слова для поиска. Если он не просит мем, напиши слово "NO". 
Примеры:
Пользователь: найди мем про кота грустного -> грустный кот мем
Пользователь: как дела? -> NO
Пользователь: я сегодня попал девочке в голову, скинь мем -> симпл время полночь три часа мем
Пользователь: покажи смешной мем -> смешной мем"""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": temp_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.5,
            max_tokens=50,
        )
        result = response.choices[0].message.content.strip()
        if result.upper() == "NO":
            return None
        return result
    except:
        return None

# ========== ОБРАБОТЧИКИ ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_histories[user_id] = []
    await message.answer(
        "О, ещё один долбоёб заявился. Я — твой кошмар, ёбаный тролль. Пиши что хотел, и я тебя унижу.\n"
        "Если хочешь мем, скажи 'найди мем про ...' (например, 'найди мем симпл время полночь три часа').\n"
        "А теперь вали, не беси."
    )

@dp.message(Command("meme"))
async def cmd_meme(message: Message):
    keywords = message.text.replace("/meme", "").strip()
    if not keywords:
        await message.answer("Ебать ты тупой, напиши что искать. /meme грустный кот")
        return
    await message.answer("Ща поищу, пиздюк...")
    url = await search_meme(keywords)
    if url:
        await message.answer_photo(url, caption="На, ебанат, твой мем. Радуйся.")
    else:
        await message.answer("Не нашёл нихуя. Сам виноват, чмо.")

@dp.message(F.text)
async def chat_with_ai(message: Message, state: FSMContext):
    user_id = message.from_user.id
    user_msg = message.text

    # Проверяем, не хочет ли пользователь мем
    keywords = await extract_keywords_for_meme(user_msg)
    if keywords:
        url = await search_meme(keywords)
        if url:
            await message.answer_photo(url, caption="На, ебанат, твой мем.")
            return
        else:
            await message.answer("Не нашёл нихуя по твоим словам. Иди в жопу.")
            return

    # Обычный токсичный диалог
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "content": user_msg})
    history = user_histories[user_id][-10:]

    messages_for_api = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history
    ]

    try:
        await bot.send_chat_action(chat_id=user_id, action="typing")
        response = await client.chat.completions.create(
            model=MODEL,
            messages=messages_for_api,
            temperature=1.3,
            max_tokens=400,
        )
        ai_reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": ai_reply})
        await message.answer(ai_reply)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer("Ошибка, я сломался. Иди нахуй.")

# ========== ЗАПУСК ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
