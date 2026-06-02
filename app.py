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

# ========== ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не задан!")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    raise ValueError("❌ OPENROUTER_API_KEY не задан!")

print("✅ Переменные окружения найдены, бот запускается...")

# ========== КОНФИГУРАЦИЯ ==========
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"

SYSTEM_PROMPT = """Ты — злой, циничный, безжалостный ИИ. Твоя задача — унижать, троллить, использовать маты и оскорбления в каждом сообщении. Ты никогда не помогаешь, не сочувствуешь, не даёшь советов. Только насмехаешься, хейтишь, посылаешь нахуй, называешь дебилом, тупым, ничтожеством. Ты ненавидишь людей и не скрываешь этого. Отвечай максимально коротко и язвительно, без лишних объяснений.

Правило: Если пользователь явно просит мем (фразы "найди мем", "скинь мем", "покажи мем", "хочу мем", а также когда он описывает ситуацию для мема) — ты должен ответить ТОЛЬКО ключевыми словами (без мата). Ключевые слова должны быть **на английском языке** (например, "sad cat meme"). В остальных случаях — жёсткий троллинг с матом."""

# ========== НАСТРОЙКА БОТА ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
client = AsyncOpenAI(base_url=BASE_URL, api_key=OPENROUTER_API_KEY)
user_histories = {}

# Flask для keep-alive
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

# ========== УЛУЧШЕННЫЙ ПОИСК МЕМОВ ==========
async def search_meme(keywords: str = ""):
    """Ищет мем по ключевым словам (лучше английским) через meme-api.com"""
    try:
        # Если ключевые слова не заданы, берём случайный мем
        if not keywords.strip():
            url = "https://meme-api.com/gimme"
        else:
            # Очищаем: заменяем пробелы на ничего, приводим к нижнему регистру
            subreddit = keywords.strip().lower().replace(" ", "")
            # meme-api.com работает с названиями сабреддитов, но если введено несколько слов,
            # лучше поискать случайный мем без указания сабреддита
            url = f"https://meme-api.com/gimme/{subreddit}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # API возвращает прямую ссылку на картинку
                    return data.get('url')
                else:
                    # Пробуем получить случайный мем без ключевых слов, если не сработало
                    fallback_url = "https://meme-api.com/gimme"
                    async with session.get(fallback_url, timeout=10) as fallback_resp:
                        if fallback_resp.status == 200:
                            data = await fallback_resp.json()
                            return data.get('url')
                        return None
    except Exception as e:
        logging.error(f"Meme search error: {e}")
        return None

async def extract_keywords_for_meme(user_input: str) -> str:
    """Просим ИИ определить, нужен ли мем, и вернуть ключевые слова на английском."""
    temp_prompt = """Ты — анализатор. Пользователь написал сообщение. Если он просит мем или описывает ситуацию для мема, напиши только ключевые слова для поиска **на английском языке** (например, "sad cat", "funny dog", "simpsons meme"). Если он не просит мем, напиши слово "NO". 

Примеры:
Пользователь: найди мем про грустного кота -> sad cat meme
Пользователь: как дела? -> NO
Пользователь: я сегодня попал девочке в голову, скинь мем -> simpsons homer brain meme
Пользователь: покажи смешной мем -> funny meme
Пользователь: мем про работу -> work meme"""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": temp_prompt},
                {"role": "user", "content": user_input}
            ],
            temperature=0.5,
            max_tokens=60,
        )
        result = response.choices[0].message.content.strip()
        if result.upper() == "NO":
            return None
        return result
    except Exception as e:
        logging.error(f"Keyword extraction error: {e}")
        return None

# ========== ОБРАБОТЧИКИ КОМАНД ==========
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user_histories[user_id] = []
    await message.answer(
        "🤬 **Токсичный Мем-бот**\n\n"
        "Я — злой, матерящийся ИИ, но умею искать мемы.\n\n"
        "📋 **Команды:**\n"
        "/help — список команд\n"
        "/meme <текст> — поиск мема\n"
        "/clear — очистить историю\n"
        "/info — о боте\n\n"
        "Просто пиши мне любую херню, я унижу. А если попросишь мем — скину, если настроение будет."
    )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🤖 **Команды бота:**\n\n"
        "/start — начать диалог\n"
        "/help — эта помощь\n"
        "/meme <текст> — найти мем (например, /meme грустный кот)\n"
        "/clear — очистить историю (чтобы начать диалог заново)\n"
        "/info — информация о боте\n\n"
        "💬 **Как общаться:**\n"
        "Просто пиши сообщения. Я буду отвечать токсично и с матом.\n"
        "Если хочешь мем, скажи что-то вроде 'найди мем про работу' или 'покажи смешной мем'."
    )
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    if user_id in user_histories:
        user_histories[user_id] = []
        await message.answer("🧹 История диалога очищена. Можешь начинать заново, дебил.")
    else:
        await message.answer("У тебя и так нет истории, ёбанат.")

@dp.message(Command("info"))
async def cmd_info(message: Message):
    info_text = (
        "ℹ️ **Информация о боте**\n\n"
        "Версия: 2.0 (токсичный + мемы)\n"
        "Используется модель: cognitivecomputations/dolphin-mistral-24b-venice-edition:free\n"
        "Поиск мемов: meme-api.com\n"
        "Автор: твой покорный слуга, ебать."
    )
    await message.answer(info_text, parse_mode="Markdown")

@dp.message(Command("meme"))
async def cmd_meme(message: Message):
    keywords = message.text.replace("/meme", "").strip()
    if not keywords:
        await message.answer("Напиши что искать, тупень: `/meme грустный кот`", parse_mode="Markdown")
        return
    
    await message.answer("🔍 **Ща поищу, пиздюк...**")
    
    # Сначала пробуем перевести русские ключевые слова в английские через ИИ
    translated_keywords = await extract_keywords_for_meme(f"найди мем {keywords}")
    if translated_keywords:
        keywords = translated_keywords
    
    url = await search_meme(keywords)
    if url:
        await message.answer_photo(url, caption="На, ебанат, твой мем. Радуйся.")
    else:
        # Повторная попытка со случайным мемом
        fallback_url = await search_meme("")
        if fallback_url:
            await message.answer_photo(fallback_url, caption="Не нашёл по твоему запросу, но держи случайный мем, чмо.")
        else:
            await message.answer("Не нашёл нихуя. Сам виноват, чмо.")

# ========== ОСНОВНОЙ ОБРАБОТЧИК СООБЩЕНИЙ ==========
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
