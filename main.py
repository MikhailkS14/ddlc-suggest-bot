import logging
import os
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Set

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BotCommand, ChatPermissions
from aiohttp import web

# ================= CONFIGURATION =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8872712620:AAHa6LcIJpWtVDElhKt_watIrvWLoTFuU4A")
ADMIN_ID = 8822516870  # ID глав. админа
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм или ID канала
BDAYS_FILE = "birthdays.json"
PORT = int(os.environ.get("PORT", 8080))
# =================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# База данных пользователей бота (для рассылки)
BOT_USERS: Set[int] = set()

# Хранилище заблокированных в предложке пользователей
BANNED_USERS: Set[int] = set()

# Хранилище варнов в чате: {user_id: count}
USER_WARNS: Dict[int, int] = {}

# Исправленное хранилище черновиков с числовым индексом (чтобы не было ошибки "Черновик не найден")
DRAFTS: Dict[int, dict] = {}
DRAFT_COUNTER = 0

# Черный список слов для автомодерации чата
BAD_WORDS = {"спам", "скам", "ругательство"}

# FSM Состояния
class CustomRejectState(StatesGroup):
    waiting_for_custom_reason = State()

# --- РАБОТА С JSON (ДНИ РОЖДЕНИЯ) ---
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

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return True

# --- ПРОВЕРКА АДМИНА В ЧАТЕ ---
async def is_admin(chat_id: int, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR]
    except Exception:
        return False

# --- СЕРВЕР ДЛЯ KEEP-ALIVE ---
async def handle_ping(request):
    return web.Response(text="Bot is running smoothly!")

# --- КОМАНДА /START ---
@dp.message(CommandStart(), F.chat.type == "private")
async def start_cmd_private(message: types.Message):
    BOT_USERS.add(message.from_user.id)

    if message.from_user.id in BANNED_USERS:
        await message.answer("❌ Вы заблокированы в предложке.")
        return

    welcome_text = (
        f"<b>Добро пожаловать в Литературный Клуб, {message.from_user.first_name}! 🎀</b>\n\n"
        f"Это официальный бот предложки для нашего канала <b>{CHANNEL_ID}</b>.\n\n"
        "✨ <b>Как предложить свой пост:</b>\n"
        "1️⃣ Отправь в этот чат <b>текст</b>, <b>фото</b>, <b>видео</b>, <b>гифку</b>, <b>голосовое</b> или <b>кружочек</b>.\n"
        "2️⃣ Выбери режим публикации: <b>Открыто</b> (с указанием автора) или <b>Анонимно</b>.\n"
        "3️⃣ Подтверди отправку, и пост уйдёт администраторам на модерацию!\n\n"
        "📅 <code>/mybd ДД.ММ</code> — записать свой День Рождения."
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Наш канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())

@dp.message(CommandStart(), F.chat.type.in_({"group", "supergroup"}))
async def start_cmd_group(message: types.Message):
    await message.answer("🌸 Привет! Чтобы предложить пост или записать день рождения, напиши мне в личные сообщения: @DokiDokiForever_bot")

# --- КОМАНДА /MYBD (ДЕНЬ РОЖДЕНИЯ) ---
@dp.message(Command("mybd"))
async def set_bd_cmd(message: types.Message, command: CommandObject):
    if not command.args:
        await message.answer("⚠️ Укажи дату в формате `ДД.ММ` (пример: `/mybd 13.10`)", parse_mode=ParseMode.MARKDOWN)
        return

    date_str = command.args.strip()
    try:
        datetime.strptime(date_str, "%d.%m")
    except ValueError:
        await message.answer("❌ Неверный формат! Используй `ДД.ММ` (пример: `13.10` или `04.06`)", parse_mode=ParseMode.MARKDOWN)
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

# ================= РЕКЛАМА И РАССЫЛКА (ДЛЯ АДМИНА) =================

@dp.message(Command("broadcast"), F.chat.type == "private")
@dp.message(Command("реклама"), F.chat.type == "private")
async def broadcast_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    target_msg = message.reply_to_message

    if not target_msg and len(message.text.split()) == 1:
        await message.reply(
            "📢 <b>Как использовать рассылку рекламы:</b>\n\n"
            "1. Напиши рекламный пост.\n"
            "2. Ответь на него командой <code>/broadcast</code> или <code>/реклама</code>.",
            parse_mode=ParseMode.HTML
        )
        return

    confirm_kb = InlineKeyboardBuilder()
    confirm_kb.button(text="🚀 Запустить рассылку", callback_data="confirm_broadcast")
    confirm_kb.button(text="❌ Отмена", callback_data="cancel_broadcast")
    
    await message.reply(
        f"📢 <b>Подтверждение рассылки:</b>\nПолучателей в базе: <b>{len(BOT_USERS)}</b> чел.",
        parse_mode=ParseMode.HTML,
        reply_markup=confirm_kb.as_markup()
    )

@dp.callback_query(F.data == "confirm_broadcast")
async def start_broadcast_callback(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    await call.message.edit_text("⏳ <i>Рассылка запущена...</i>", parse_mode=ParseMode.HTML)
    msg_to_send = call.message.reply_to_message
    success, failed = 0, 0

    for user_id in list(BOT_USERS):
        try:
            if msg_to_send:
                await bot.copy_message(chat_id=user_id, from_chat_id=msg_to_send.chat.id, message_id=msg_to_send.message_id)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await call.message.edit_text(f"🎉 Готово! Успешно: {success}, Ошибок: {failed}")
    await call.answer()

@dp.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast_callback(call: types.CallbackQuery):
    await call.message.edit_text("❌ Рассылка отменена.")
    await call.answer()

# ================= ФИШКИ ДЛЯ ЧАТА =================

@dp.message(Command("rules"), F.chat.type.in_({"group", "supergroup"}))
async def rules_cmd(message: types.Message):
    rules_text = (
        "🌸≈◈☛ⲠⲢⲀⲂΥⲖⲀ☚◈≈🌸\n\n"
        "1~Ⲙⲁⲧⲉⲣυⲧⲥя Ⲙⲟⲯⲏⲟ ⲏⲟ ⲏⲉ ⲕⲁⲕ ⲥⲁⲡⲟⲯⲏυⲕ\n\n"
        "2~Ⲟⲥⲕⲟⲣⳝⲗяⲧь ⲇⲣⲩⲅυⲭ υ υⲭ ⲣⲟⲇⲏю ⲎⲈⲖЬⳄЯ\n\n"
        "3~Ⲏⲉ ⲥⲡⲁⲙυⲧь Ⲙⲁⲕⲥ. 10 ⲥⲧυⲕⲉⲣⲟⲃ υⲗυ ⲯⲉ ⲡⲉⲅⲟ ⲧⲟ ⲧⲁⲕⲟⲅⲟ\n\n"
        "4~Ⲏⲉ ⲩⲅⲣⲟⲯⲁⲧь ⲏυ ⲕⲟⲙⲩ\n\n"
        "5~ⲏⲉ ⲅⲟⲃⲟⲣυⲧь ⲡⲧⲟ ⲧы ⲉⳝ#ⲁⲗ ⲕⲟⲅⲟ-ⲧⲟ υⲗυ υⳅ Ⲣⲟⲇⲏυ ⲡⲉⲗⲟⲃⲉⲕⲁ\n\n"
        "6~ 18+ Ⲙⲟⲯⲏⲟ ⲯⲉⲗⲁⲧⲉⲗьⲏⲟ ⲏⲉ ⲞⳠⲈⲎЬ ⲙⲏⲟⲅⲟ\n\n"
        "1. Ⲡⲣⲁⲃυⲗⲁ Ⲥⲟⳝⲗюⲇⲁⲧь υ ⲏⲉ ⲏⲁⲣⲩⲱⲁⲧь ⲡⲣⲁⲃυⲗⲁ"
    )
    await message.answer(rules_text, parse_mode=ParseMode.HTML)

@dp.message(Command("dice"), F.chat.type.in_({"group", "supergroup"}))
async def dice_cmd(message: types.Message):
    await message.answer_dice(emoji="🎲")

@dp.message(Command("warn"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id) or not message.reply_to_message:
        return

    target_user = message.reply_to_message.from_user
    if target_user.id == (await bot.get_me()).id or await is_admin(message.chat.id, target_user.id):
        return

    warns = USER_WARNS.get(target_user.id, 0) + 1
    USER_WARNS[target_user.id] = warns

    if warns >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, target_user.id)
            await bot.unban_chat_member(message.chat.id, target_user.id)
            USER_WARNS[target_user.id] = 0
            await message.answer(f"🔴 <b>{target_user.full_name}</b> получил 3/3 варнов и исключён!", parse_mode=ParseMode.HTML)
        except Exception:
            pass
    else:
        await message.answer(f"⚠️ <b>{target_user.full_name}</b> получает предупреждение! ({warns}/3)", parse_mode=ParseMode.HTML)

@dp.message(Command("unwarn"), F.chat.type.in_({"group", "supergroup"}))
async def unwarn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id) or not message.reply_to_message:
        return
    target_user = message.reply_to_message.from_user
    warns = USER_WARNS.get(target_user.id, 0)
    if warns > 0:
        USER_WARNS[target_user.id] = warns - 1
        await message.answer(f"✅ У <b>{target_user.full_name}</b> снят варн ({warns - 1}/3)", parse_mode=ParseMode.HTML)

@dp.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id) or not message.reply_to_message:
        return
    target_user = message.reply_to_message.from_user
    args = message.text.split()
    minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
    until_date = datetime.now() + timedelta(minutes=minutes)
    try:
        await bot.restrict_chat_member(message.chat.id, target_user.id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
        await message.answer(f"🤐 <b>{target_user.full_name}</b> в муте на {minutes} минут.", parse_mode=ParseMode.HTML)
    except Exception:
        pass

@dp.message(Command("kick"), F.chat.type.in_({"group", "supergroup"}))
async def kick_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id) or not message.reply_to_message:
        return
    target_user = message.reply_to_message.from_user
    try:
        await bot.ban_chat_member(message.chat.id, target_user.id)
        await bot.unban_chat_member(message.chat.id, target_user.id)
        await message.answer(f"🚪 <b>{target_user.full_name}</b> исключён.", parse_mode=ParseMode.HTML)
    except Exception:
        pass

# --- ПРИВЕТСТВИЕ И ПРОЩАНИЕ ---
@dp.message(F.new_chat_members)
async def welcome_new_members(message: types.Message):
    bot_obj = await bot.get_me()
    for new_member in message.new_chat_members:
        if new_member.id == bot_obj.id:
            continue
        await message.answer(f"🌸 <b>Добро пожаловать в Литературный Клуб, {new_member.full_name}!</b> 🎀", parse_mode=ParseMode.HTML)

@dp.message(F.left_chat_member)
async def farewell_member(message: types.Message):
    bot_obj = await bot.get_me()
    if message.left_chat_member.id == bot_obj.id:
        return
    await message.answer(f"💔 <b>{message.left_chat_member.full_name}</b> покидает Клуб...", parse_mode=ParseMode.HTML)

# --- АВТОМОДЕРАЦИЯ ЧАТА И УДАЛЕНИЕ СООБЩЕНИЙ "0101" ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def chat_moderation(message: types.Message):
    if not message.text:
        return

    if message.text.strip() == "0101":
        try:
            await message.delete()
        except Exception:
            pass
        return

    if await is_admin(message.chat.id, message.from_user.id):
        return

    text_lower = message.text.lower()
    if "t.me/" in text_lower or "telegram.me/" in text_lower:
        if CHANNEL_ID.replace("@", "").lower() not in text_lower:
            await message.delete()
            return

    for word in BAD_WORDS:
        if word in text_lower:
            await message.delete()
            break

# ================= ПРЕДЛОЖКА (В ЛС) =================

@dp.message(F.chat.type == "private")
async def handle_suggestion(message: types.Message, state: FSMContext):
    global DRAFT_COUNTER
    user = message.from_user
    BOT_USERS.add(user.id)

    if user.id in BANNED_USERS or (message.text and message.text.startswith("/")):
        return

    is_sub = await check_subscription(user.id)
    if not is_sub:
        kb = InlineKeyboardBuilder()
        kb.button(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
        await message.answer(f"⚠️ Для предложки нужно подписаться на {CHANNEL_ID}!", reply_markup=kb.as_markup())
        return

    DRAFT_COUNTER += 1
    draft_id = DRAFT_COUNTER
    
    DRAFTS[draft_id] = {
        "user_id": user.id, "user_name": user.full_name, "username": user.username,
        "message_id": message.message_id, "chat_id": message.chat.id,
        "caption": message.caption or message.text or "", "content_type": message.content_type
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Открыто", callback_data=f"send_pub_{draft_id}")
    kb.button(text="🕵️‍♂️ Анонимно", callback_data=f"send_anon_{draft_id}")
    kb.button(text="🗑️ Отмена", callback_data=f"cancel_draft_{draft_id}")
    kb.adjust(1)

    await message.reply("📝 Выберите режим публикации поста:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("send_"))
async def process_send_option(call: types.CallbackQuery):
    parts = call.data.split("_")
    is_anon = (parts[1] == "anon")
    draft_id = int(parts[2])

    draft = DRAFTS.get(draft_id)
    if not draft:
        await call.message.edit_text("⚠️ Ошибка: черновик устарел.")
        await call.answer()
        return

    author_info = f"👤 <b>Автор:</b> {draft['user_name']} (@{draft['username'] or 'нет'})\n🔒 <b>Режим:</b> {'Анонимно' if is_anon else 'Открыто'}"

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Опубликовать", callback_data=f"adm_pub_{draft_id}_{1 if is_anon else 0}")
    kb.button(text="❌ Отклонить", callback_data=f"adm_rej_{draft_id}")
    kb.button(text="🚫 Забанить", callback_data=f"adm_ban_{draft['user_id']}")
    kb.adjust(2, 1)

    try:
        await bot.send_message(ADMIN_ID, f"📥 <b>Новая предложка!</b>\n\n{author_info}", parse_mode=ParseMode.HTML)
        await bot.copy_message(chat_id=ADMIN_ID, from_chat_id=draft["chat_id"], message_id=draft["message_id"], reply_markup=kb.as_markup())
        await call.message.edit_text("✨ Пост отправлен администраторам!")
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")
        await call.message.edit_text("⚠️ Ошибка отправки.")
    await call.answer()

@dp.callback_query(F.data.startswith("cancel_draft_"))
async def cancel_draft(call: types.CallbackQuery):
    draft_id = int(call.data.replace("cancel_draft_", ""))
    DRAFTS.pop(draft_id, None)
    await call.message.edit_text("❌ Отменено.")
    await call.answer()

@dp.callback_query(F.data.startswith("adm_pub_"))
async def admin_publish(call: types.CallbackQuery):
    parts = call.data.split("_")
    is_anon = bool(int(parts[2]))
    draft_id = int(parts[3])
    
    draft = DRAFTS.get(draft_id)
    if not draft:
        await call.answer("Черновик не найден в памяти бота", show_alert=True)
        return

    try:
        caption_extra = f"\n\n✍️ <b>Автор:</b> @{draft['username'] or draft['user_name']}" if not is_anon else ""
        if draft["content_type"] == "text":
            pub_msg = await bot.send_message(CHANNEL_ID, draft["caption"] + caption_extra, parse_mode=ParseMode.HTML)
        else:
            pub_msg = await bot.copy_message(chat_id=CHANNEL_ID, from_chat_id=draft["chat_id"], message_id=draft["message_id"])
            if not is_anon and caption_extra:
                try:
                    await bot.edit_message_caption(chat_id=CHANNEL_ID, message_id=pub_msg.message_id, caption=(draft["caption"] or "") + caption_extra, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

        post_link = f"https://t.me/{CHANNEL_ID.replace('@', '')}/{pub_msg.message_id}"
        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.reply(f"✅ Опубликовано: {post_link}")
        
        # Очищаем черновик после публикации
        DRAFTS.pop(draft_id, None)

        try:
            kb = InlineKeyboardBuilder().button(text="👀 Посмотреть", url=post_link)
            await bot.send_message(draft["user_id"], "🎉 Ваш пост опубликован в канале!", reply_markup=kb.as_markup())
        except Exception:
            pass
    except Exception as e:
        await call.message.reply(f"⚠️ Ошибка публикации: {e}")
    await call.answer()

@dp.callback_query(F.data.startswith("adm_rej_"))
async def admin_reject_menu(call: types.CallbackQuery):
    draft_id = call.data.replace("adm_rej_", "")
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Не по теме", callback_data=f"rejreason_offtopic_{draft_id}")
    kb.button(text="⚠️ Спам", callback_data=f"rejreason_spam_{draft_id}")
    kb.button(text="❌ Без причины", callback_data=f"rejreason_none_{draft_id}")
    kb.adjust(1)
    await call.message.reply("Выберите причину:", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("rejreason_"))
async def process_rejection_reason(call: types.CallbackQuery):
    parts = call.data.split("_")
    draft_id = int(parts[2])
    
    draft = DRAFTS.get(draft_id)
    if draft:
        if draft["user_id"]:
            try:
                await bot.send_message(draft["user_id"], "💔 К сожалению, ваш пост был отклонён модератором.")
            except Exception:
                pass
        DRAFTS.pop(draft_id, None)

    await call.message.edit_text("❌ Пост отклонён.")
    await call.answer()

@dp.callback_query(F.data.startswith("adm_ban_"))
async def admin_ban_user(call: types.CallbackQuery):
    user_id = int(call.data.replace("adm_ban_", ""))
    BANNED_USERS.add(user_id)
    await call.message.reply(f"🚫 Пользователь {user_id} заблокирован.")
    await call.answer()

async def setup_bot_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="Инструкция"),
        BotCommand(command="rules", description="Правила"),
        BotCommand(command="mybd", description="Записать День Рождения (ДД.ММ)")
    ])

async def main():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()

    await setup_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
