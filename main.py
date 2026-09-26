import asyncio
import logging
import random
import re
import json
import os
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# ---------------- CONFIG ----------------
BOT_TOKEN = "8872712620:AAEDuEt73mbSJma-EylkK9yaIm-WrDQzw2c"
ADMIN_ID = 8822516870  # ID глав. админа
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм канала
DMITRY_USERNAME = "Chechna777"  # Юзернейм Дмитрия
BDAYS_FILE = "birthdays.json"
WARNS_FILE = "warns.json"
PORT = int(os.environ.get("PORT", 8080))  # Порт для Render
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Работа с JSON файлами ---
def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка чтения {filepath}: {e}")
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка записи {filepath}: {e}")

# --- Проверка прав админа ---
async def is_admin(message: types.Message) -> bool:
    if message.from_user.id == ADMIN_ID:
        return True
    if message.chat.type in ["group", "supergroup"]:
        member = await message.chat.get_member(message.from_user.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    return False

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
    "Юри тихо шепчет: 'Я... я приготовила этот чай специально для тебя. Пожалуйста, пей осторожно, он горячий.'",
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
    kb = InlineKeyboardBuilder()
    kb.button(text="📜 Правила клуба", callback_data="show_rules")
    
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 🎀\n\n"
        f"Добро пожаловать в Литературный Клуб **{CHANNEL_ID}**!\n\n"
        "✨ **Что я умею:**\n"
        "• Просто отправь мне **любой текст, фото или видео**, и я передам его администраторам в предложку!\n"
        "• `/monika` — совет от Моники\n"
        "• `/yuri` — выпить чаю с Юри\n"
        "• `/natsuki` — капкейк от Нацуки\n"
        "• `/sayori` — обняться с Сайори\n"
        "• `/mybd ДД.ММ` — записать свой День Рождения (например: `/mybd 13.10` или `/mybd 13. 10`)\n"
        "• `/rules` — правила Клуба\n"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb.as_markup())

@dp.message(Command("rules"))
async def rules_cmd(message: types.Message):
    rules_text = (
        "📜 **Правила Литературного Клуба:**\n\n"
        "1. Будьте вежливы к другим участникам клуба.\n"
        "2. Спам, реклама и неконструктивизм запрещены.\n"
        "3. Уважайте вкусы друг друга в литературе и манге!\n\n"
        "*(Раздел правил находится в процессе дополнения)*"
    )
    await message.answer(rules_text, parse_mode=ParseMode.MARKDOWN)

@dp.callback_query(F.data == "show_rules")
async def rules_callback(call: types.CallbackQuery):
    rules_text = (
        "📜 **Правила Литературного Клуба:**\n\n"
        "1. Будьте вежливы к другим участникам клуба.\n"
        "2. Спам, реклама и оскорбления запрещены.\n"
        "3. Уважайте вкусы друг друга в литературе и манге!\n\n"
        "*(Раздел правил находится в процессе дополнения)*"
    )
    await call.message.answer(rules_text, parse_mode=ParseMode.MARKDOWN)
    await call.answer()

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
    if user.username and user.username.lower() == DMITRY_USERNAME.lower():
        dmitry_text = (
            "💙 **Сайори:** 'Ой, ДИМА! Мой самый преданный поклонник и защитник! ✨\n"
            "Я пересмотрела все твои сотни комментариев под постами и собрала целую гору игрушек и артов!\n"
            "Держи самое большое печенье 🍪 и гигантские обнимашки! Спасибо, что ты со мной с рождения!' 🤗"
        )
        await message.answer(dmitry_text, parse_mode=ParseMode.MARKDOWN)
    else:
        if random.random() < 0.15:
            text = f"💙 **Сайори:** 'Я сейчас доедаю печенье с Дмитрием (@{DMITRY_USERNAME}), но для тебя у меня тоже найдутся обнимашки!' 🤗"
        else:
            text = f"💙 **Сайори:** {random.choice(SAYORI_RESPONSES)}"
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("mybd"))
async def set_bd_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("⚠️ Укажи дату в формате `ДД.ММ` (пример: `/mybd 13.10` или `/mybd 13. 10`)", parse_mode=ParseMode.MARKDOWN)
        return

    clean_args = re.sub(r'[\s/]+', '.', command.args.strip())
    clean_args = re.sub(r'\.+', '.', clean_args)

    try:
        datetime.strptime(clean_args, "%d.%m")
    except ValueError:
        await message.answer("❌ Неверный формат даты! Используй число и месяц (например: `13.10` или `05.04`)", parse_mode=ParseMode.MARKDOWN)
        return

    bdays = load_json(BDAYS_FILE)
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else user_name

    bdays[user_id] = {
        "date": clean_args,
        "name": user_name,
        "username": username
    }
    save_json(BDAYS_FILE, bdays)
    await message.answer(f"🎉 Запомнил! Твой День Рождения — **{clean_args}**. Клуб обязательно тебя поздравит!", parse_mode=ParseMode.MARKDOWN)

# ----------------- КОМАНДЫ МОДЕРАЦИИ -----------------

@dp.message(Command("warn"))
async def warn_user(message: types.Message):
    if not await is_admin(message):
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте этой командой на сообщение нарушителя!")
        return

    target_user = message.reply_to_message.from_user
    warns = load_json(WARNS_FILE)
    user_id = str(target_user.id)

    count = warns.get(user_id, 0) + 1
    warns[user_id] = count
    save_json(WARNS_FILE, warns)

    if count >= 3:
        warns[user_id] = 0
        save_json(WARNS_FILE, warns)
        until = datetime.now() + timedelta(days=1)
        await message.chat.restrict(
            user_id=target_user.id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=until
        )
        await message.answer(f"🚨 Пользователь {target_user.full_name} получил 3/3 предупреждений и замучен на 24 часа!")
    else:
        await message.answer(f"⚠️ Пользователю {target_user.full_name} выдано предупреждение! ({count}/3)")

@dp.message(Command("unwarn"))
async def unwarn_user(message: types.Message):
    if not await is_admin(message):
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте этой командой на сообщение пользователя!")
        return

    target_user = message.reply_to_message.from_user
    warns = load_json(WARNS_FILE)
    user_id = str(target_user.id)

    if warns.get(user_id, 0) > 0:
        warns[user_id] -= 1
        save_json(WARNS_FILE, warns)
        await message.answer(f"✅ С пользователя {target_user.full_name} снято предупреждение. Осталось: {warns[user_id]}/3")
    else:
        await message.answer("У этого пользователя нет активных предупреждений.")

@dp.message(Command("mute"))
async def mute_user(message: types.Message, command: CommandObject):
    if not await is_admin(message):
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответьте этой командой на сообщение пользователя!")
        return

    target_user = message.reply_to_message.from_user
    minutes = 60

    if command.args:
        arg = command.args.lower()
        if arg.endswith("m"): minutes = int(arg[:-1])
        elif arg.endswith("h"): minutes = int(arg[:-1]) * 60
        elif arg.endswith("d"): minutes = int(arg[:-1]) * 1440

    until = datetime.now() + timedelta(minutes=minutes)
    await message.chat.restrict(
        user_id=target_user.id,
        permissions=types.ChatPermissions(can_send_messages=False),
        until_date=until
    )
    await message.answer(f"🔇 Пользователь {target_user.full_name} замучен на {minutes} мин.")

@dp.message(Command("unmute"))
async def unmute_user(message: types.Message):
    if not await is_admin(message):
        return
    if not message.reply_to_message:
        return

    target_user = message.reply_to_message.from_user
    await message.chat.restrict(
        user_id=target_user.id,
        permissions=types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True
        )
    )
    await message.answer(f"🔊 Пользователь {target_user.full_name} размучен.")

@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    if not await is_admin(message):
        return
    if not message.reply_to_message:
        return

    target_user = message.reply_to_message.from_user
    await message.chat.ban(user_id=target_user.id)
    await message.answer(f"🚫 Пользователь {target_user.full_name} забанен.")

@dp.message(Command("kick"))
async def kick_user(message: types.Message):
    if not await is_admin(message):
        return
    if not message.reply_to_message:
        return

    target_user = message.reply_to_message.from_user
    await message.chat.ban(user_id=target_user.id)
    await message.chat.unban(user_id=target_user.id)
    await message.answer(f"👞 Пользователь {target_user.full_name} кикнут из чата.")

# --- Приём предложенных новостей (в ЛС боту) ---
@dp.message(F.chat.type == "private")
async def handle_suggest(message: types.Message):
    if message.text and message.text.startswith("/"):
        return

    user = message.from_user
    username_str = f"@{user.username}" if user.username else "без юзернейма"
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
        if now.hour == 9 and now.minute == 0:
            today_str = now.strftime("%d.%m")
            bdays = load_json(BDAYS_FILE)
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

# --- Веб-сервер для поддержания активности на Render ---
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

async def main():
    await start_web_server()
    asyncio.create_task(birthday_checker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
