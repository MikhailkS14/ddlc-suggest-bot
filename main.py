import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BotCommand
from aiohttp import web

# ---------------- CONFIG ----------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8872712620:AAHa6LcIJpWtVDElhKt_watIrvWLoTFuU4A")
ADMIN_ID = 8822516870  # ID глав. админа
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм канала
PORT = int(os.environ.get("PORT", 8080))
# ----------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return True

# --- КОМАНДА /START (В ЛИЧНЫХ СООБЩЕНИЯХ) ---
@dp.message(CommandStart(), F.chat.type == "private")
async def start_cmd(message: types.Message):
    welcome_text = (
        f"Привет, {message.from_user.first_name}! 🎀\n\n"
        f"Это официальный бот предложки для канала **{CHANNEL_ID}**!\n\n"
        "📥 **Как отправить пост:**\n"
        "Просто отправь мне в этот чат **текст**, **фото** или **видео**, и я передам его администраторам на модерацию.\n\n"
        "⚠️ *Предложка доступна только для подписчиков нашего канала!*"
    )
    await message.answer(welcome_text, parse_mode=ParseMode.MARKDOWN)

# --- ПРИВЕТСТВИЕ И ПРОЩАНИЕ В ГРУППАХ ---
@dp.message(F.new_chat_members)
async def welcome_new_members(message: types.Message):
    for new_member in message.new_chat_members:
        # Не приветствуем самого бота
        if new_member.id == (await bot.get_me()).id:
            continue
        
        name = new_member.full_name
        welcome_msg = (
            f"Добро пожаловать в Литературный Клуб, {name}! 🎀\n"
            f"Мы очень рады видеть тебя среди нас! Проходи, присаживайся и чувствуй себя как дома. ✨"
        )
        await message.answer(welcome_msg)

@dp.message(F.left_chat_member)
async def farewell_member(message: types.Message):
    left_member = message.left_chat_member
    # Не прощаемся с самим ботом
    if left_member.id == (await bot.get_me()).id:
        return

    name = left_member.full_name
    farewell_msg = (
        f"{name} покидает Литературный Клуб... 💔\n"
        f"Спасибо за время, проведённое с нами! Двери нашего клуба всегда открыты для тебя."
    )
    await message.answer(farewell_msg)

# --- ПРЕДЛОЖКА (СТРОГО В ЛС) ---
@dp.message(F.chat.type == "private")
async def handle_suggest(message: types.Message):
    # Игнорируем стартовую команду
    if message.text and message.text.startswith("/start"):
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

# --- КНОПКИ МОДЕРАЦИИ (ДЛЯ АДМИНА) ---
@dp.callback_query(F.data.startswith("pub_"))
async def publish_callback(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]
    
    try:
        if call.message.photo:
            caption = call.message.caption or ""
            clean_text = caption.split("<blockquote>")[1].split("</blockquote>")[0] if "<blockquote>" in caption else ""
            await bot.send_photo(CHANNEL_ID, call.message.photo[-1].file_id, caption=clean_text)
        elif call.message.video:
            caption = call.message.caption or ""
            clean_text = caption.split("<blockquote>")[1].split("</blockquote>")[0] if "<blockquote>" in caption else ""
            await bot.send_video(CHANNEL_ID, call.message.video.file_id, caption=clean_text)
        elif call.message.text:
            text = call.message.text
            clean_text = text.split("<blockquote>")[1].split("</blockquote>")[0] if "<blockquote>" in text else text
            await bot.send_message(CHANNEL_ID, clean_text)

        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.reply("✅ Опубликовано в канал!")
        
        try:
            await bot.send_message(int(user_id), "🎉 Твой пост опубликован в канале!")
        except Exception:
            pass
            
    except Exception as e:
        logging.error(f"Ошибка публикации в канал: {e}")
        await call.message.reply(f"⚠️ Ошибка при публикации в канал: {e}")
        
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

# --- СЕРВЕР И ЗАПУСК ---
async def handle_ping(request):
    return web.Response(text="OK")

async def setup_bot_commands():
    commands = [
        BotCommand(command="start", description="Инструкция по предложке"),
    ]
    await bot.set_my_commands(commands)

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()

    await setup_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
