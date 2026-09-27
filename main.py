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
from aiogram.types import BotCommand
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

MONIKA_ADVICES = [
    "Помни: если что-то идёт не по плану, сделай паузу, выпей чаю и взгляни на всё с нового ракурса! ✨",
    "Иногда самое важное решение — это просто дать себе отдохнуть. Ты отлично справляешься! 💚",
    "Не бойся ошибок в своём 'коде жизни'. Каждая из них — лишь шаг к созданию идеальной программы! ☕",
    "Каждый день — это новая страница. Какую историю ты напишешь сегодня?",
    "Секрет успеха прост: верь в свои силы и не забывай улыбаться даже в самые пасмурные дни! 🎀"
]

# --- 15 ВОПРОСОВ ДЛЯ ВИКТОРИНЫ ЮРИ ---
QUIZ_QUESTIONS = [
    {"question": "📜 Какой любимый жанр книг предпочитает Юри?", "options": ["Комедийная манга", "Глубокий психологический хоррор", "Легкая романтика", "Научная фантастика"], "correct": 1},
    {"question": "🧁 Какой ингредиент Нацуки считает секретным для идеального капкейка?", "options": ["Соль", "Любовь и внимание к деталям", "Какао", "Клубничный джем"], "correct": 1},
    {"question": "🎀 Кто является основателем и президентом Литературного Клуба?", "options": ["Сайори", "Юри", "Моника", "Нацуки"], "correct": 2},
    {"question": "☕ Из какого растения получают зеленый, черный и белый чай?", "options": ["Камелия китайская", "Мелисса", "Альпийская роза", "Жасмин"], "correct": 0},
    {"question": "🍵 Как называется традиционный японский порошковый зеленый чай?", "options": ["Сенча", "Матча", "Улун", "Пуэр"], "correct": 1},
    {"question": "🌿 Какое эфирное масло придает чаю 'Эрл Грей' его фирменный цитрусовый аромат?", "options": ["Лайм", "Бергамотовая цедра", "Масло бергамота", "Грейпфрут"], "correct": 2},
    {"question": "🔥 Что произойдет, если заварить зеленый чай крутым кипятком (100°C)?", "options": ["Он станет сладким", "Он станет горьким и потеряет аромат", "Ничего не изменится", "Он превратится в улун"], "correct": 1},
    {"question": "🇬🇧 В какой стране зародилась традиция 'High Tea' (Высокого чая)?", "options": ["Китай", "Япония", "Великобритания", "Индия"], "correct": 2},
    {"question": "🌺 Какой чай имеет ярко-синий цвет благодаря цветку Клитории тройчатой?", "options": ["Каркаде", "Анчан", "Ройбос", "Мате"], "correct": 1},
    {"question": "🪵 Какой чай обладает дымным ароматом из-за сушки над сосновыми дровами?", "options": ["Лапсанг Сушонг", "Дарджилинг", "Ассам", "Гунпаудер"], "correct": 0},
    {"question": "🏺 Как называется традиционная посуда из глины для китайских чайных церемоний?", "options": ["Исинский чайник", "Пиала", "Самовар", "Термос"], "correct": 0},
    {"question": "🍂 Какой вид чая выдерживается и ферментируется годами, улучшая вкус?", "options": ["Зеленый", "Белый", "Пуэр", "Желтый"], "correct": 2},
    {"question": "🥛 Что традиционно добавляют в индийский чай Масала?", "options": ["Лимон и мяту", "Молоко и специи", "Сок яблока", "Шоколад"], "correct": 1},
    {"question": "❄️ Как называется холодное заваривание чая в течение нескольких часов?", "options": ["Айс-ти", "Колд-брю", "Фреш", "Микс"], "correct": 1},
    {"question": "📖 Что Юри принесла в клуб, чтобы читать вместе с Главным Героем?", "options": ["Комикс", "Книгу 'Портрет Маркова'", "Учебник по физике", "Дневник"], "correct": 1}
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

# --- Функция проверки подписки ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return True

# --- КОМАНДЫ (ИДУТ ПЕРВЫМИ!) ---

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 🎀\n\n"
        f"Это официальный бот Клуба **{CHANNEL_ID}**!\n\n"
        "✨ **Предложка (в ЛС):** Отправь мне текст, фото или видео, и я передам администраторам!\n"
        "*(Обрати внимание: отправлять посты могут только подписчики нашего канала!)*\n\n"
        "📅 `/mybd ДД.ММ` — записать свой День Рождения.\n\n"
        "🎭 **Мини-игры и развлечения:**\n"
        "• `/poem` или `!стих слово1, слово2, слово3, слово4` — сочинить стихотворение в стиле DDLC\n"
        "• `/sayori` или `!печенье` — операция с печеньками Сайори\n"
        "• `/cupcake` или `!капкейк` — угостить Нацуки\n"
        "• `/monika` или `!совет` — совет дня от Моники\n"
        "• `/quiz` или `!чай` — викторина с Юри"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(F.text.startswith("!стих") | Command("poem"))
async def generate_poem(message: types.Message):
    raw_text = message.text.replace("!стих", "").replace("/poem", "").strip()
    words = [w.strip().lower() for w in raw_text.replace(",", " ").split() if w.strip()]
    
    if len(words) < 4:
        await message.reply(
            "⚠️ Напиши **ровно 4 слова** через запятую или пробел!\n"
            "Пример: `/poem чай, книга, дождь, уют` или `!стих чай, книга, дождь, уют`",
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

@dp.message(F.text.startswith("!печенье") | Command("sayori"))
async def sayori_cookie_game(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="💙 Помочь Сайори (отвлечь Нацуки)", callback_data="cookie_help")
    kb.button(text="🛡️ Охранять поднос", callback_data="cookie_guard")
    kb.button(text="😋 Съесть печеньку самому", callback_data="cookie_eat")
    kb.adjust(1)
    
    text = (
        f"🍪 **Операция: Свежая выпечка!**\n\n"
        f"Нацуки принесла в клуб свежее печенье с корицей и ушла проверять чайник:\n"
        f"*«{message.from_user.first_name}, присмотри за подносом! И не спускай глаз с Сайори!»*\n\n"
        f"Сайори тут же подбегает к тебе с умоляющими глазками:\n"
        f"*«Ну пожалуйста~ Всего одну печеньку! Нацуки даже не заметит!»*\n\n"
        f"Что ты сделаешь?"
    )
    await message.answer(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(F.data.startswith("cookie_"))
async def cookie_cb(call: types.CallbackQuery):
    action = call.data.split("_")[1]
    user_name = call.from_user.first_name

    if action == "help":
        res = (
            f"🤝 **{user_name} помогает Сайори!**\n\n"
            f"Ты забалтываешь Нацуки разговором про новую главу манги. Сайори ловко сцапывает печеньку и довольная жует за спиной!\n"
            f"💖 **Нацуки:** *«Хм... Одно печенье испарилось? Сайори-и-и!!»*\n"
            f"💙 **Сайори:** *«Оно улетело в рай для печенек! Спасибо, {user_name}~!»* 🍪✨"
        )
    elif action == "guard":
        res = (
            f"🛡️ **{user_name} держит оборону!**\n\n"
            f"Ты встаешь перед подносом. Сайори пытается отвлечь тебя криками 'Смотри, там НЛО!', но ты непреклонен.\n"
            f"💖 **Нацуки возвращается:** *«Ого, ты спас выпечку! За надежность держи первую печеньку!»*\n"
            f"💙 **Сайори:** *«Эх... Но зато тебе досталась самая вкусная!»* 😋"
        )
    else:
        res = (
            f"😋 **{user_name} берет дело в свои руки!**\n\n"
            f"Ты хладнокровно съедаешь печеньку прямо на глазах у шокированной Сайори!\n"
            f"💙 **Сайори:** *«Э-эй! Это же была МОЯ идея украсть печенье!»*\n"
            f"💖 **Нацуки вбегает:** *«Так, почему у вас обоих крошки на щеках?!»* 😾"
        )
    await call.message.edit_text(res, parse_mode=ParseMode.MARKDOWN)
    await call.answer()

@dp.message(F.text.startswith("!капкейк") | Command("cupcake"))
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
            f"🧁 **{user_name}** создает настоящий клубничный шедевр!\n\n"
            "✨ **Идеально!**\n"
            "💖 **Нацуки (глаза светятся):** *«Вау... Это потрясающе! Ладно, ты официально лучший кулинар в этом клубе!»* 🧁💖"
        )
    await message.answer(res, parse_mode=ParseMode.MARKDOWN)

@dp.message(F.text.startswith("!моника") | F.text.startswith("!совет") | Command("monika"))
async def monika_advice(message: types.Message):
    advice = random.choice(MONIKA_ADVICES)
    text = (
        f"💚 **Разговор по душам с Моникой:**\n\n"
        f"*{advice}*\n\n"
        f"— Всегда рядом, твоя Моника. ✨"
    )
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(F.text.startswith("!чай") | F.text.startswith("!викторина") | Command("quiz"))
async def quiz_cmd(message: types.Message):
    q = random.choice(QUIZ_QUESTIONS)
    kb = InlineKeyboardBuilder()
    
    for idx, opt in enumerate(q["options"]):
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

# --- ПРЕДЛОЖКА В ЛС (ИДЕТ В САМОМ КОНЦЕ, ЧТОБЫ НЕ ПЕРЕХВАТЫВАТЬ КОМАНДЫ) ---
@dp.message(F.chat.type == "private")
async def handle_suggest(message: types.Message):
    # Пропускаем, если текст начинается с команды или спец. символа
    if message.text and (message.text.startswith("/") or message.text.startswith("!")):
        return

    user = message.from_user

    # Проверка подписки на канал
    is_subscribed = await check_subscription(user.id)
    if not is_subscribed:
        kb = InlineKeyboardBuilder()
        kb.button(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
        await message.answer(
            f"⚠️ **Чтобы отправлять посты в предложку, необходимо быть подписанным на наш канал {CHANNEL_ID}!**\n\n"
            "Подпишись на канал и отправь сообщение повторно! 💕",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb.as_markup()
        )
        return

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

# --- Регистрация списка команд для кнопки / в Telegram ---
async def setup_bot_commands():
    commands = [
        BotCommand(command="start", description="Перезапустить бота / Справка"),
        BotCommand(command="poem", description="Сочинить стих в стиле DDLC (!стих)"),
        BotCommand(command="sayori", description="Операция с печеньем Сайори (!печенье)"),
        BotCommand(command="cupcake", description="Угостить Нацуки капкейком (!капкейк)"),
        BotCommand(command="monika", description="Совет дня от Моники (!моника)"),
        BotCommand(command="quiz", description="Викторина с Юри (!чай)"),
        BotCommand(command="mybd", description="Записать День Рождения (ДД.ММ)"),
    ]
    await bot.set_my_commands(commands)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    await setup_bot_commands()  # Регистрируем меню команд
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
