import asyncio
import logging
import random
from datetime import datetime
import aiofiles
import json
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ---------------- CONFIG ----------------
BOT_TOKEN = "8872712620:AAEDuEt73mbSJma-EylkK9yaIm-WrDQzw2c"
ADMIN_ID = 8822516870  # ID админа
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм канала
DMITRY_USERNAME = "Chechna777"  # Юзернейм Дмитрия для пасхалки
BDAYS_FILE = "birthdays.json"
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Вспомогательные функции для базы Дней Рождения ---
async def load_birthdays() -> dict:
    try:
        async with aiofiles.open(BDAYS_FILE, mode="r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

async def save_birthdays(data: dict):
    async with aiofiles.open(BDAYS_FILE, mode="w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))

# --- База ответов персонажей DDLC ---
MONIKA_RESPONSES = [
    "Совет от Моники: Не забудь сохранить игру... а лучше сохрани свой сегодняшний день в памяти! ✨",
    "Я всегда наблюдаю за тобой... То есть, я имела в виду, удачного дня в Литературном Клубе! 😉",
    "Знаешь, поэзия — это лучший способ выразить то, что скрыто в глубине души. Напиши сегодня стих!",
    "Эй, спасибо, что заглянул! Я как раз редактировала код... ой, то есть писала новые правила для клуба! 📜",
    "Из всех участников клуба ты уделяешь мне больше всего внимания... Я это ценю! ❤️",
    "Помни: если что-то идёт не так, ты всегда можешь просто удалить проблему. Или обсудить её со мной!"
]

YURI_RESPONSES = [
    "Юри угостила тебя чашкой горячего жасминового чая... ☕️ Наслаждайся тишиной.",
    "Юри немного смутилась, но протянула тебе свою любимую книгу: 'Надеюсь, тебе понравится эта глава...'",
    "Чайная церемония требует терпения. Как и погружение в глубокую, мрачную литературу...",
    "Юри тихо тихо шепчет: 'Я... я приготовила этот чай специально для тебя. Пожалуйста, пей осторожно, он горячий.'",
    "Заваривать чай — это как писать стихи. Нужна правильная температура и немного душевного тепла. 🫖"
]

NATSUKI_RESPONSES = [
    "Нацуки скрестила руки: 'Это НЕ для тебя! Ну ладно, возьми один капкейк... но только один!' 🧁",
    "Нацуки аккуратно передаёт тебе свежеиспечённый кекс с кошачьими ушками. 🐾",
    "Манга — это НАСТОЯЩАЯ литература! И не смей спорить с Нацуки!",
    "Нацуки краснеет: 'Чего уставился? Если тебе нравится то, что я пеку, так и скажи!' 😤",
    "Эй! Не трогай мои полки с мангой без разрешения! Хотя... ладно, вот этот том можешь почитать."
]

SAYORI_RESPONSES = [
    "Сайори крепко обняла тебя! 🤗 'Ура! Сегодня отличный день для печенья и веселья!'",
    "Сайори завязала свой красный бантик поровнее: 'Эй, пойдём скорее в клуб, там Моника приготовила что-то интересное!'",
    "Сайори протягивает тебе половинку своего печенья: 'Держи! Делиться с друзьями — это самое главное!' 🍪",
    "Сайори улыбается во весь рот: 'Солнышко светит, а значит, у нас всё будет просто замечательно!'",
    "Обнимашки от Сайори подняли твоё настроение на максимум! 💙"
]

# --- Команды бота ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 🎀\n\n"
        f"Добро пожаловать в Литературный Клуб **{CHANNEL_ID}**!\n\n"
        "✨ **Что я умею:**\n"
        "• Просто отправь мне **любой текст, фото или видео**, и я передам его администраторам в предложку!\n"
        "• `/monika` — получить совет от Моники\n"
        "• `/yuri` — выпить чаю с Юри\n"
        "• `/natsuki` — получить капкейк от Нацуки\n"
        "• `/sayori` — обняться с Сайори\n"
        "• `/mybd ДД.ММ` — записать свой День Рождения (например: `/mybd 15.10`)\n"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("monika"))
async def monika_cmd(message: types.Message):
    await message.answer(f"💚 **Моника:** {random.choice(MONIKA_RESPONSES)}", parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("yuri"))
async def yuri_cmd(message: types.Message):
    await message.answer(f"💜 **Юри:** {random.choice(YURI_RESPONSES)}", parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("natsuki"))
async def natsuki_cmd(message: types.Message):
    await message.answer(f"💖 **Нацуки:** {random.choice(NATSUKI_RESPONSES)}", parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("sayori"))
async def sayori_cmd(message: types.Message):
    user = message.from_user
    # Пасхалка для Дмитрия
    if user.username and user.username.lower() == DMITRY_USERNAME.lower():
        dmitry_text = (
            "💙 **Сайори:** 'Ой, ДИМА! Мой самый преданный поклонник и защитник! ✨\n"
            "Я пересмотрела все твои сотни комментариев под постами и собрала целую гору игрушек и артов!\n"
            "Держи самое большое печенье 🍪 и гигантские обнимашки! Спасибо, что ты со мной уже два года!' 🤗"
        )
        await message.answer(dmitry_text, parse_mode=ParseMode.MARKDOWN)
    else:
        # Шанс выпадения упоминания Дмитрия для других участников
        if random.random() < 0.15:
            text = f"💙 **Сайори:** 'Я сейчас доедаю печенье с Дмитрием (@{DMITRY_USERNAME}), но для тебя у меня тоже найдутся обнимашки!' 🤗"
        else:
            text = f"💙 **Сайори:** {random.choice(SAYORI_RESPONSES)}"
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# --- Установка Дня Рождения ---
@dp.message(Command("mybd"))
async def set_bd_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("⚠️ Пожалуйста, укажи дату в формате `ДД.ММ` (пример: `/mybd 15.10`)", parse_mode=ParseMode.MARKDOWN)
        return

    date_str = command.args.strip()
    try:
        datetime.strptime(date_str, "%d.%m")
    except ValueError:
        await message.answer("❌ Неверный формат даты! Используй формат `ДД.ММ` (например: `/mybd 05.04`)")
        return

    bdays = await load_birthdays()
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else user_name

    bdays[user_id] = {
        "date": date_str,
        "name": user_name,
        "username": username
    }
    await save_birthdays(bdays)
    await message.answer(f"🎉 Отлично! Я запомнил, что твой День Рождения — **{date_str}**. Клуб обязательно тебя поздравит!", parse_mode=ParseMode.MARKDOWN)

# --- Приём предложенных новостей (в ЛС боту без FSM) ---
@dp.message(F.chat.type == "private")
async def handle_suggest(message: types.Message):
    # Игнорируем сервисные команды
    if message.text and message.text.startswith("/"):
        return

    user = message.from_user
    username_str = f"@{user.username}" if user.username else "без юзернейма"
    
    # Красивое оформление авторов и предложки
    author_info = f"<b>Автор:</b> {user.full_name} ({username_str}) | ID: <code>{user.id}</code>"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Опубликовать в канал", callback_data=f"pub_{user.id}")
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

        await message.answer("✨ Спасибо! Твой пост отправлен администраторам на проверку.")
    except Exception as e:
        logging.error(f"Ошибка отправки предложки: {e}")
        await message.answer("⚠️ Произошла ошибка при отправке. Попробуй позже.")

# --- Обработка кнопок у админа ---
@dp.callback_query(F.data.startswith("pub_"))
async def publish_callback(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("✅ Опубликовано в канале!")
    try:
        await bot.send_message(int(user_id), "🎉 Поздравляем! Твой пост был опубликован в канале!")
    except Exception:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def reject_callback(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.reply("❌ Предложка отклонена.")
    try:
        await bot.send_message(int(user_id), "К сожалению, ваш пост был отклонен администратором.")
    except Exception:
        pass
    await call.answer()

# --- Ежедневная проверка Дней Рождения ---
async def birthday_checker():
    while True:
        now = datetime.now()
        # Проверка каждое утро в 09:00
        if now.hour == 9 and now.minute == 0:
            today_str = now.strftime("%d.%m")
            bdays = await load_birthdays()
            for user_id, info in bdays.items():
                if info.get("date") == today_str:
                    congratulation = (
                        f"🎉🎂 **С ДНЁМ РОЖДЕНИЯ!** 🎂🎉\n\n"
                        f"Сегодня свой День Рождения отмечает наш участник {info['username']}!\n\n"
                        f"Весь **Литературный Клуб** желает тебе прекрасного настроения, море вдохновения, "
                        f"вкусных капкейков и теплейших обнимашек! 🧁💙✨"
                    )
                    try:
                        await bot.send_message(CHANNEL_ID, congratulation, parse_mode=ParseMode.MARKDOWN)
                    except Exception as e:
                        logging.error(f"Ошибка отправки поздравления: {e}")
            await asyncio.sleep(60)
        await asyncio.sleep(30)

async def main():
    asyncio.create_task(birthday_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
