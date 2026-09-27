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

# --- СЛОВАРИ И ДАННЫЕ ДЛЯ СТИХОВ ---
SAYORI_WORDS = {"счастье", "солнце", "дружба", "уют", "печенье", "улыбка", "обнимашки", "радость"}
YURI_WORDS = {"дождь", "книга", "чай", "тьма", "тайна", "философия", "ночь", "тишина", "судьба"}
NATSUKI_WORDS = {"сладости", "капкейк", "котик", "манга", "мило", "клубника", "торт", "розовый"}

SAD_WORDS = {
    "боль", "слёзы", "слезы", "тьма", "одиночество", "тоска", "грусть", "печаль", 
    "прощай", "крик", "шрам", "кровь", "тень", "холод", "увядание", "забыт", "мрак", "звонок"
}

LIGHT_TEMPLATES = [
    "В нашем клубе сегодня витают {w1} и {w2},\nМы пишем строки, забывая про тоску.\nПусть греют душу нам {w3} и {w4} в тишине —\nСловно во сне, в моём окне...",
    "Где-то далеко остались {w1} и {w2},\nА в Литературном Клубе снова теплота.\nПусть дарят радость нам {w3} и {w4},\nИ льётся свет сквозь облака!",
    "Мы назовем эти строки: «{w1}» и «{w2}»,\nПусть каждый стих приносит капельку тепла.\nКогда вокруг есть {w3} и {w4},\nДуша Клуба снова ожила!"
]

SAD_TEMPLATES = [
    "Капают капли, скрывая {w1} и {w2},\nВ пустой комнате снова витает тоска.\nЗабытые мысли, лишь {w3} и {w4} вдали —\nМы удержать этот миг не смогли...",
    "Тихо уходит свет, оставляя {w1} и {w2},\nСловно эхо из прошлого, ранит строка.\nКогда в сердце лишь {w3} и {w4} остались опять,\nНам остается только молча ждать...",
    "Сквозь холодный туман пробиваются {w1} и {w2},\nЗастыли слова на обожженном листке.\nЛишь тихий шёпот, где {w3} и {w4} замерли в ночи —\nИ догорает пламя одинокой свечи..."
]

# --- БАЗА ДАННЫХ ДЛЯ ИГР ---
MONIKA_ADVICES = [
    "Помни: если что-то идёт не по плану, сделай паузу, выпей чаю и взгляни на всё с нового ракурса! ✨",
    "Иногда самое важное решение — это просто дать себе отдохнуть. Ты отлично справляешься! 💚",
    "Не бойся ошибок в своём 'коде жизни'. Каждая из них — лишь шаг к созданию идеальной программы! ☕",
    "Каждый день — это новая страница. Какую историю ты напишешь сегодня?",
    "Секрет успеха прост: верь в свои силы и не забывай улыбаться даже в самые пасмурные дни! 🎀"
]

QUIZ_QUESTIONS = [
    {
        "question": "📜 Какой любимый жанр книг предпочитает Юри?",
        "options": ["Комедийная манга", "Глубокий психологический хоррор", "Легкая романтика", "Научная фантастика"],
        "correct": 1
    },
    {
        "question": "🧁 Какой ингредиент Нацуки считала самым секретным для идеального капкейка?",
        "options": ["Соль", "Любовь и ваниль", "Какао", "Клубничный джем"],
        "correct": 1
    },
    {
        "question": "🎀 Кто является основателем и президентом Литературного Клуба?",
        "options": ["Сайори", "Юри", "Моника", "Нацуки"],
        "correct": 2
    }
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
            "✨ **Предложка:** Отправь мне текст, фото или видео, и я передам администраторам!\n"
            "📅 `/mybd ДД.ММ` — записать свой День Рождения.\n\n"
            "🎭 **Мини-игры и развлечения в чате:**\n"
            "• `!стих слово1, слово2, слово3, слово4` — сочинить стихотворение в стиле DDLC\n"
            "• `!капкейк` — угостить Нацуки сладостями\n"
            "• `!моника` или `!совет` — совет дня от Моники\n"
            "• `!печенье` — бросить печеньку в чат для Сайори\n"
            "• `!чай` или `!викторина` — литературная викторина с Юри"
        )
        await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

# --- 1. ГЕНЕРАТОР СТИХОВ ---
@dp.message(F.text.startswith("!стих") | F.text.startswith("/poem"))
async def generate_poem(message: types.Message):
    raw_text = message.text.replace("!стих", "").replace("/poem", "").strip()
    words = [w.strip().lower() for w in raw_text.replace(",", " ").split() if w.strip()]
    
    if len(words) < 4:
        await message.reply(
            "⚠️ Напиши **ровно 4 слова** через запятую или пробел!\n"
            "Пример: `!стих чай, книга, дождь, уют`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    w1, w2, w3, w4 = words[0], words[1], words[2], words[3]
    all_words = set(words)
    sad_score = len(all_words.intersection(SAD_WORDS))

    if sad_score >= 1:
        template = random.choice(SAD_TEMPLATES)
        poem_text = template.format(w1=w1, w2=w2, w3=w3, w4=w4)
        reaction = "💜 **Юри (сочувственно):** 'Это... очень глубокое и трогательное стихотворение. В нём чувствуется настоящая драма и светлая печаль...' ☕"
    else:
        template = random.choice(LIGHT_TEMPLATES)
        poem_text = template.format(w1=w1, w2=w2, w3=w3, w4=w4)

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

# --- 2. ИГРА: УГОСТИ НАЦУКИ КАПКЕЙКОМ ---
@dp.message(F.text.startswith("!капкейк") | F.text.startswith("!нацуки"))
async def cupcake_game(message: types.Message):
    outcome = random.randint(1, 100)
    user_name = message.from_user.first_name

    if outcome <= 25:
        res = (
            f"🧁 **{user_name}** выпекает капкейк...\n\n"
            "💥 **О нет!** Ты передержал его в духовке, и он подгорел!\n"
            "💖 **Нацуки:** *«Эй! Ты что, пытаешься меня отравить?! Иди переделывай!»* 😾"
        )
    elif outcome <= 75:
        res = (
            f"🧁 **{user_name}** угощает Нацуки пышным глазированным капкейком!\n\n"
            "💖 **Нацуки:** *«Н-ну... получилось довольно вкусно! Но не думай, что ты меня этим впечатлил, дурак!»* 😳"
        )
    else:
        res = (
            f"🧁 **{user_name}** создает настоящий клубничный шедевр!\n\n"
            "✨ **Идеально!**\n"
            "💖 **Нацуки (глаза светятся):** *«Вау... Это потрясающе! Ладно, ты официально лучший кулинар в этом клубе!»* 🧁💖"
        )
    await message.answer(res, parse_mode=ParseMode.MARKDOWN)

# --- 3. ИГРА: СОВЕТ ОТ МОНИКИ ---
@dp.message(F.text.startswith("!моника") | F.text.startswith("!совет"))
async def monika_advice(message: types.Message):
    advice = random.choice(MONIKA_ADVICES)
    text = (
        f"💚 **Разговор по душам с Моникой:**\n\n"
        f"*{advice}*\n\n"
        f"— Всегда рядом, твоя Моника. ✨"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# --- 4. ИГРА: ПОЙМАЙ ПЕЧЕНЬКУ САЙОРИ ---
@dp.message(F.text.startswith("!печенье") | F.text.startswith("!сайори"))
async def cookie_drop(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="🍪 Схватить печеньку!", callback_data="grab_cookie")
    
    text = (
        f"💙 **Сайори упустила коробку с печеньем!**\n"
        f"Одна розовая печенька катится по столу... Кто успеет забрать ее первым?"
    )
    await message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data == "grab_cookie")
async def grab_cookie_cb(call: types.CallbackQuery):
    user_name = call.from_user.first_name
    await call.message.edit_text(
        f"🎉 **{user_name}** оказался самым быстрым и схватил печеньку!\n\n"
        f"💙 **Сайори:** *«Э-эй! Это была моя последняя печенька! Ну ладно... приятного аппетита!»* 😋"
    )
    await call.answer()

# --- 5. ИГРА: ВИКТОРИНА С ЮРИ ---
@dp.message(F.text.startswith("!чай") | F.text.startswith("!викторина"))
async def quiz_cmd(message: types.Message):
    q = random.choice(QUIZ_QUESTIONS)
    kb = InlineKeyboardBuilder()
    
    for idx, opt in enumerate(q["options"]):
        # Кодируем правильный ли ответ в callback_data
        is_correct = "1" if idx == q["correct"] else "0"
        kb.button(text=opt, callback_data=f"quiz_{is_correct}")
    
    kb.adjust(1)
    text = f"☕ **Чаепитие и викторина с Юри:**\n\n{q['question']}"
    await message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("quiz_"))
async def quiz_cb(call: types.CallbackQuery):
    status = call.data.split("_")[1]
    if status == "1":
        ans = "💜 **Юри (улыбается):** 'Абсолютно верно! Я впечатлена твоей эрудицией. Держи чашку свежесваренного чая!' ☕✨"
    else:
        ans = "💜 **Юри (смущенно):** 'Ох, к сожалению, это не совсем так... Но не переживай, попробовать ещё раз никогда не поздно!' 🍵"
    
    await call.message.edit_text(f"{call.message.text}\n\n{ans}")
    await call.answer()

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
