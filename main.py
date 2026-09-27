import asyncio
import logging
import random
import json
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8872712620:AAHa6LcIJpWtVDElhKt_watIrvWLoTFuU4A")
ADMIN_ID = 8822516870  # ID глав. админа
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм канала
BDAYS_FILE = "birthdays.json"
PORT = int(os.environ.get("PORT", 8080))
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Словари предпочтений героинь ---
SAYORI_WORDS = {"счастье", "солнце", "дружба", "уют", "печенье", "улыбка", "обнимашки", "радость"}
YURI_WORDS = {"дождь", "книга", "чай", "тьма", "тайна", "философия", "ночь", "тишина", "судьба"}
NATSUKI_WORDS = {"сладости", "капкейк", "котик", "манга", "мило", "клубника", "торт", "розовый"}

# --- Шаблоны стихотворений ---
POEM_TEMPLATES = [
    "Шелест страниц и {w1} вокруг,\nТихо зашёл в наш клуб старый друг.\nВ чашке с {w2} искрится свет,\nДарит {w3} свой мягкий привет.\nВдруг закружится {w4} в тишине —\nСловно во сне, в моём окне...",
    "Когда приходит {w1} невзначай,\nЗаварим мы горячий {w2}.\nЗабудем всё, где {w3} была,\nИ лишь {w4} согреет нам сердца.\nВ Литературном Клубе снова уют,\nЗдесь каждого помнят и очень ждут!",
    "Мы искали {w1} среди ночных теней,\nГде {w2} делала мысли светлей.\nНо нашлась случайно {w3} вдали,\nЧтобы {w4} мы удержать смогли.\nТак рождаются строки этих стихов,\nИз самых простых и искренних слов."
]

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# --- Команда /start ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    if message.chat.type == "private":
        welcome_text = (
            f"Привет, {message.from_user.first_name}! 🎀\n\n"
            f"Это официальный бот Клуба **{CHANNEL_ID}**!\n\n"
            "✨ **Что я умею:**\n"
            "• **Отправь мне любой текст, фото или видео**, и я передам его администраторам в предложку канала!\n"
            "• `/mybd ДД.ММ` — записать свой День Рождения (пример: `/mybd 13.10`)\n\n"
            "🎭 **Фича для чата:**\n"
            "Напиши `!стих слово1, слово2, слово3, слово4`, и я сочиню стихотворение в стиле DDLC!"
        )
        await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

# --- ГЕНЕРАТОР СТИХОВ (Команда !стих или /poem) ---
@dp.message(F.text.startswith("!стих") | F.text.startswith("/poem"))
async def generate_poem(message: types.Message):
    # Извлекаем текст после команды
    raw_text = message.text.replace("!стих", "").replace("/poem", "").strip()
    
    # Разбиваем по запятым или пробелам
    words = [w.strip().lower() for w in raw_text.replace(",", " ").split() if w.strip()]
    
    if len(words) < 4:
        await message.reply(
            "⚠️ Напиши **ровно 4 слова** через запятую или пробел!\n"
            "Пример: `!стих чай, книга, дождь, уют`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Берем первые 4 слова
    w1, w2, w3, w4 = words[0], words[1], words[2], words[3]
    
    # Подставляем в случайный шаблон
    template = random.choice(POEM_TEMPLATES)
    poem_text = template.format(w1=w1, w2=w2, w3=w3, w4=w4)

    # Оцениваем, кому больше понравился стих
    all_words = set(words)
    sayori_score = len(all_words.intersection(SAYORI_WORDS))
    yuri_score = len(all_words.intersection(YURI_WORDS))
    natsuki_score = len(all_words.intersection(NATSUKI_WORDS))

    if sayori_score > yuri_score and sayori_score > natsuki_score:
        reaction = "💙 **Сайори в восторге!** 'Ой, какой милый и тёплый стих! У меня аж настроение поднялось!' 🤗"
    elif yuri_score > sayori_score and yuri_score > natsuki_score:
        reaction = "💜 **Юри оценила:** 'Очень глубокие и метафоричные строки... Поэзия действительно удалась.' ☕"
    elif natsuki_score > sayori_score and natsuki_score > yuri_score:
        reaction = "💖 **Нацуки краснеет:** 'Ну... получилось неплохо! Не то чтобы мне прямо ОЧЕНЬ понравилось, но сойдёт!' 🧁"
    else:
        reaction = "💚 **Моника:** 'Прекрасная работа над слогом! Клуб гордится твоим творчеством!' ✨"

    result_msg = (
        f"📜 **Стихотворение от {message.from_user.first_name}:**\n\n"
        f"*{poem_text}*\n\n"
        f"{reaction}"
    )
    
    await message.answer(result_msg, parse_mode=ParseMode.MARKDOWN)

# --- Запись Дня Рождения ---
@dp.message(Command("mybd"))
async def set_bd_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("⚠️ Укажи дату в формате `ДД.ММ` (пример: `/mybd 13.10`)", parse_mode=ParseMode.MARKDOWN)
        return

    date_str = command.args.strip()
    try:
        datetime.strptime(date_str, "%d.%m")
    except ValueError:
        await message.answer("❌ Неверный формат! Используй `ДД.ММ` (пример: `13.10`)", parse_mode=ParseMode.MARKDOWN)
        return

    bdays = load_json(BDAYS_FILE)
    user = message.from_user
    bdays[str(user.id)] = {
        "date": date_str,
        "name": user.full_name,
        "username": f"@{user.username}" if user.username else user.full_name
    }
    save_json(BDAYS_FILE, bdays)
    await message.answer(f"🎉 Запомнил! Твой День Рождения — **{date_str}**.", parse_mode=ParseMode.MARKDOWN)

# --- ПРЕДЛОЖКА В ЛИЧНЫХ СООБЩЕНИЯХ ---
@dp.message(F.chat.type == "private")
async def handle_suggest(message: types.Message):
    if message.text and message.text.startswith("/"):
        return

    user = message.from_user
    username_str = f"@{user.username}" if user.username else "без юзернейма"
    author_info = f"<b>Автор:</b> {user.full_name} ({username_str}) | ID: <code>{user.id}</code>"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Опубликовать", callback_data=f"pub_{user.id}")
    kb.button(text="❌ Отклонить", callback_data=f"rej_{user.id}")
    kb.adjust(1)

    try:
        if message.text:
            formatted_text = f"📥 <b>Новая предложка:</b>\n\n<blockquote>{message.text}</blockquote>\n\n{author_info}"
            await bot.send_message(ADMIN_ID, formatted_text, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())
        elif message.photo:
            photo_id = message.photo[-1].file_id
            caption = message.caption if message.caption else ""
            formatted_caption = f"📥 <b>Новая предложка (Фото):</b>\n\n<blockquote>{caption}</blockquote>\n\n{author_info}"
            await bot.send_photo(ADMIN_ID, photo_id, caption=formatted_caption, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())
        elif message.video:
            video_id = message.video.file_id
            caption = message.caption if message.caption else ""
            formatted_caption = f"📥 <b>Новая предложка (Видео):</b>\n\n<blockquote>{caption}</blockquote>\n\n{author_info}"
            await bot.send_video(ADMIN_ID, video_id, caption=formatted_caption, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())
        else:
            await message.answer("Поддерживаются только текст, фото и видео.")
            return

        await message.answer("✨ Спасибо! Твой пост отправлен администраторам.")
    except Exception as e:
        logging.error(f"Ошибка предложки: {e}")
        await message.answer("⚠️ Ошибка при отправке.")

@dp.callback_query(F.data.startswith("pub_"))
async def publish_callback(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("✅ Опубликовано!")
    try:
        await bot.send_message(int(user_id), "🎉 Твой пост опубликован в канале!")
    except Exception:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def reject_callback(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("❌ Отклонено.")
    try:
        await bot.send_message(int(user_id), "К сожалению, ваш пост отклонен.")
    except Exception:
        pass
    await call.answer()

# --- Веб-сервер для Render ---
async def handle_ping(request):
    return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
