import logging
import os
import asyncio
import re
from typing import Dict, Set
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
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
PORT = int(os.environ.get("PORT", 8080))
# =================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Хранилище заблокированных в предложке пользователей
BANNED_USERS: Set[int] = set()

# Хранилище варнов в чате: {user_id: count}
USER_WARNS: Dict[int, int] = {}

# Хранилище временных данных предложек: {draft_id: {...}}
DRAFTS: Dict[str, dict] = {}

# Черный список слов для автомодерации чата
BAD_WORDS = {"спам", "скам", "ругательство"}  # Можно дополнить своими словами

# FSM Состояния
class CustomRejectState(StatesGroup):
    waiting_for_custom_reason = State()

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
async def start_cmd(message: types.Message):
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
        "⚠️ <i>Обратите внимание: предложка доступна только для участников нашего канала.</i>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Наш канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())

# ================= ФИШКИ ДЛЯ ЧАТА =================

# 1. Правила чата
@dp.message(Command("rules"), F.chat.type.in_({"group", "supergroup"}))
async def rules_cmd(message: types.Message):
    rules_text = (
        "📜 <b>Правила Литературного Клуба:</b>\n\n"
        "1. Будьте вежливы и уважайте остальных участников. 🌸\n"
        "2. Запрещён спам, реклама и несанкционированные ссылки. 🚫\n"
        "3. Избегайте оскорблений и конфликтов. 🤝\n"
        "4. Соблюдайте тематику нашего клуба!\n\n"
        "✨ <i>За нарушение правил администраторы могут выдать варн или мут.</i>"
    )
    await message.answer(rules_text, parse_mode=ParseMode.HTML)

# 2. Интерактивная игра /dice (кубик / монетка)
@dp.message(Command("dice"), F.chat.type.in_({"group", "supergroup"}))
async def dice_cmd(message: types.Message):
    await message.answer_dice(emoji="🎲")

# 3. Выдача предупреждения (/warn)
@dp.message(Command("warn"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте этой командой на сообщение нарушителя.")
        return

    target_user = message.reply_to_message.from_user
    if target_user.id == (await bot.get_me()).id or await is_admin(message.chat.id, target_user.id):
        await message.reply("❌ Нельзя выдать варн администратору или боту.")
        return

    warns = USER_WARNS.get(target_user.id, 0) + 1
    USER_WARNS[target_user.id] = warns

    if warns >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, target_user.id)
            await bot.unban_chat_member(message.chat.id, target_user.id)  # Исключаем (кик)
            USER_WARNS[target_user.id] = 0
            await message.answer(f"🔴 <b>{target_user.full_name}</b> получил 3/3 варнов и исключён из чата!", parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.reply(f"⚠️ Ошибка при исключении: {e}")
    else:
        await message.answer(f"⚠️ <b>{target_user.full_name}</b> получает предупреждение! ({warns}/3)", parse_mode=ParseMode.HTML)

# 4. Снятие предупреждения (/unwarn)
@dp.message(Command("unwarn"), F.chat.type.in_({"group", "supergroup"}))
async def unwarn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте этой командой на сообщение пользователя.")
        return

    target_user = message.reply_to_message.from_user
    warns = USER_WARNS.get(target_user.id, 0)

    if warns > 0:
        USER_WARNS[target_user.id] = warns - 1
        await message.answer(f"✅ Предупреждение снято! У <b>{target_user.full_name}</b> осталось ({warns - 1}/3)", parse_mode=ParseMode.HTML)
    else:
        await message.reply("У пользователя нет активных варнов.")

# 5. Мут (/mute <минуты>)
@dp.message(Command("mute"), F.chat.type.in_({"group", "supergroup"}))
async def mute_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте этой командой на сообщение нарушителя.")
        return

    target_user = message.reply_to_message.from_user
    args = message.text.split()
    minutes = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10

    until_date = datetime.now() + timedelta(minutes=minutes)
    permissions = ChatPermissions(can_send_messages=False)

    try:
        await bot.restrict_chat_member(message.chat.id, target_user.id, permissions=permissions, until_date=until_date)
        await message.answer(f"🤐 <b>{target_user.full_name}</b> переведён в режим чтения на {minutes} минут.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при муте: {e}")

# 6. Кик (/kick)
@dp.message(Command("kick"), F.chat.type.in_({"group", "supergroup"}))
async def kick_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте этой командой на сообщение пользователя.")
        return

    target_user = message.reply_to_message.from_user
    try:
        await bot.ban_chat_member(message.chat.id, target_user.id)
        await bot.unban_chat_member(message.chat.id, target_user.id)
        await message.answer(f"🚪 <b>{target_user.full_name}</b> был исключён из чата.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {e}")

# --- ПРИВЕТСТВИЕ И ПРОЩАНИЕ В ГРУППАХ ---
@dp.message(F.new_chat_members)
async def welcome_new_members(message: types.Message):
    bot_obj = await bot.get_me()
    for new_member in message.new_chat_members:
        if new_member.id == bot_obj.id:
            continue
        
        name = new_member.full_name
        welcome_msg = (
            f"🌸 <b>Добро пожаловать в Литературный Клуб, {name}!</b> 🎀\n\n"
            f"Мы очень рады видеть тебя с нами! Проходи, присаживайся, налей чашечку чая ☕ и чувствуй себя как дома. ✨\n"
            f"Ознакомься с правилами чата с помощью команды /rules !"
        )
        await message.answer(welcome_msg, parse_mode=ParseMode.HTML)

@dp.message(F.left_chat_member)
async def farewell_member(message: types.Message):
    bot_obj = await bot.get_me()
    left_member = message.left_chat_member
    if left_member.id == bot_obj.id:
        return

    name = left_member.full_name
    farewell_msg = (
        f"💔 <b>{name}</b> покидает Литературный Клуб...\n"
        f"Спасибо за время, проведённое с нами! Двери нашего клуба всегда открыты для тебя. 🚪✨"
    )
    await message.answer(farewell_msg, parse_mode=ParseMode.HTML)

# --- АВТОМОДЕРАЦИЯ ЧАТА (ФИЛЬТР СПАМА И ССЫЛОК) ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def chat_moderation(message: types.Message):
    if not message.text:
        return

    # Игнорируем администраторов
    if await is_admin(message.chat.id, message.from_user.id):
        return

    text_lower = message.text.lower()

    # Удаление несанкционированных ссылок на сторонние каналы/чаты
    if "t.me/" in text_lower or "telegram.me/" in text_lower:
        if CHANNEL_ID.replace("@", "").lower() not in text_lower:
            await message.delete()
            await message.answer(f"⚠️ {message.from_user.first_name}, ссылки на сторонние ресурсы запрещены!", show_alert=True)
            return

    # Проверка на запрещённые слова
    for word in BAD_WORDS:
        if word in text_lower:
            await message.delete()
            await message.answer(f"⚠️ Сообщение от {message.from_user.first_name} удалено из-за ненормативной лексики.")
            break

# ================= ПРЕДЛОЖКА (В ЛС) =================

@dp.message(F.chat.type == "private")
async def handle_suggestion(message: types.Message, state: FSMContext):
    user = message.from_user

    if user.id in BANNED_USERS:
        await message.answer("❌ Вы заблокированы и не можете отправлять посты.")
        return

    if message.text and message.text.startswith("/"):
        return

    is_sub = await check_subscription(user.id)
    if not is_sub:
        kb = InlineKeyboardBuilder()
        kb.button(text="📢 Подписаться на канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
        await message.answer(
            f"⚠️ <b>Чтобы отправлять посты в предложку, необходимо подписаться на наш канал {CHANNEL_ID}!</b>\n\n"
            "Подпишитесь и отправьте ваш пост снова! 💕",
            parse_mode=ParseMode.HTML,
            reply_markup=kb.as_markup()
        )
        return

    draft_id = f"{user.id}_{message.message_id}"
    
    DRAFTS[draft_id] = {
        "user_id": user.id,
        "user_name": user.full_name,
        "username": user.username,
        "message_id": message.message_id,
        "chat_id": message.chat.id,
        "caption": message.caption or message.text or "",
        "content_type": message.content_type
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Открыто (показать имя)", callback_data=f"send_pub_{draft_id}")
    kb.button(text="🕵️‍♂️ Анонимно", callback_data=f"send_anon_{draft_id}")
    kb.button(text="🗑️ Отмена", callback_data=f"cancel_draft_{draft_id}")
    kb.adjust(1)

    await message.reply(
        "📝 <b>Ваш пост готов к отправке!</b>\n\n"
        "Как бы вы хотели его опубликовать?",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data.startswith("send_"))
async def process_send_option(call: types.CallbackQuery):
    parts = call.data.split("_")
    is_anon = (parts[1] == "anon")
    draft_id = "_".join(parts[2:])

    draft = DRAFTS.get(draft_id)
    if not draft:
        await call.message.edit_text("⚠️ Ошибка: черновик устарел или был удалён.")
        await call.answer()
        return

    user_id = draft["user_id"]
    username_str = f"@{draft['username']}" if draft['username'] else "без юзернейма"
    
    author_info = (
        f"👤 <b>Автор:</b> {draft['user_name']} ({username_str}) | ID: <code>{user_id}</code>\n"
        f"🔒 <b>Режим:</b> {'🕵️‍♂️ Анонимно' if is_anon else '🙋‍♂️ Открыто'}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Опубликовать", callback_data=f"adm_pub_{draft_id}_{1 if is_anon else 0}")
    kb.button(text="❌ Отклонить", callback_data=f"adm_rej_{draft_id}")
    kb.button(text="🚫 Забанить автора", callback_data=f"adm_ban_{user_id}")
    kb.adjust(2, 1)

    try:
        await bot.send_message(ADMIN_ID, f"📥 <b>Новая предложка!</b>\n\n{author_info}", parse_mode=ParseMode.HTML)
        await bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=draft["chat_id"],
            message_id=draft["message_id"],
            reply_markup=kb.as_markup()
        )

        await call.message.edit_text(
            "✨ <b>Спасибо! Твой пост успешно отправлен администраторам на модерацию.</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logging.error(f"Ошибка пересылки предложки: {e}")
        await call.message.edit_text("⚠️ Произошла ошибка при отправке поста администраторам.")

    await call.answer()

@dp.callback_query(F.data.startswith("cancel_draft_"))
async def cancel_draft(call: types.CallbackQuery):
    draft_id = call.data.replace("cancel_draft_", "")
    DRAFTS.pop(draft_id, None)
    await call.message.edit_text("❌ Отправка отменена.")
    await call.answer()

# --- КНОПКИ МОДЕРАЦИИ ДЛЯ АДМИНА ---

@dp.callback_query(F.data.startswith("adm_pub_"))
async def admin_publish(call: types.CallbackQuery):
    parts = call.data.split("_")
    is_anon = bool(int(parts[3]))
    draft_id = "_".join(parts[4:])

    draft = DRAFTS.get(draft_id)
    if not draft:
        await call.answer("⚠️ Черновик не найден в памяти бота.", show_alert=True)
        return

    try:
        caption_extra = ""
        if not is_anon:
            if draft["username"]:
                caption_extra = f"\n\n✍️ <b>Автор:</b> @{draft['username']}"
            else:
                caption_extra = f"\n\n✍️ <b>Автор:</b> {draft['user_name']}"

        if draft["content_type"] == "text":
            text_to_send = draft["caption"] + caption_extra
            published_msg = await bot.send_message(CHANNEL_ID, text_to_send, parse_mode=ParseMode.HTML)
        else:
            published_msg = await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=draft["chat_id"],
                message_id=draft["message_id"]
            )
            if not is_anon and caption_extra:
                new_caption = (draft["caption"] or "") + caption_extra
                try:
                    await bot.edit_message_caption(
                        chat_id=CHANNEL_ID,
                        message_id=published_msg.message_id,
                        caption=new_caption,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    pass

        channel_username = CHANNEL_ID.replace("@", "")
        post_link = f"https://t.me/{channel_username}/{published_msg.message_id}"

        await call.message.edit_reply_markup(reply_markup=None)
        await call.message.reply(f"✅ <b>Опубликовано!</b>\n🔗 <a href='{post_link}'>Ссылка на пост</a>", parse_mode=ParseMode.HTML)

        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="👀 Посмотреть пост", url=post_link)
            await bot.send_message(
                draft["user_id"],
                "🎉 <b>Ура! Твой пост был опубликован в канале!</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=kb.as_markup()
            )
        except Exception:
            pass

    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")
        await call.message.reply(f"⚠️ Ошибка публикации: {e}")

    await call.answer()

@dp.callback_query(F.data.startswith("adm_rej_"))
async def admin_reject_menu(call: types.CallbackQuery):
    draft_id = call.data.replace("adm_rej_", "")
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Не соответствует теме", callback_data=f"rejreason_offtopic_{draft_id}")
    kb.button(text="⚠️ Спам / Реклама", callback_data=f"rejreason_spam_{draft_id}")
    kb.button(text="🖼️ Низкое качество", callback_data=f"rejreason_lowquality_{draft_id}")
    kb.button(text="✍️ Своя причина", callback_data=f"rejreason_custom_{draft_id}")
    kb.button(text="❌ Без причины", callback_data=f"rejreason_none_{draft_id}")
    kb.adjust(1)

    await call.message.reply("Выберите причину отклонения:", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(F.data.startswith("rejreason_"))
async def process_rejection_reason(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    reason_type = parts[1]
    draft_id = "_".join(parts[2:])

    draft = DRAFTS.get(draft_id)
    user_id = draft["user_id"] if draft else None

    reasons_map = {
        "offtopic": "Предложенный контент не соответствует тематике нашего канала.",
        "spam": "Сообщение расценено как спам или несогласованная реклама.",
        "lowquality": "К сожалению, изображение или видео ненадлежащего качества.",
        "none": None
    }

    if reason_type == "custom":
        await state.set_state(CustomRejectState.waiting_for_custom_reason)
        await state.update_data(user_id=user_id, draft_id=draft_id)
        await call.message.edit_text("✏️ Напишите причину отклонения в ответном сообщении:")
        await call.answer()
        return

    reason_text = reasons_map.get(reason_type)
    
    if user_id:
        try:
            msg = "💔 <b>К сожалению, твой пост был отклонён модератором.</b>"
            if reason_text:
                msg += f"\n\n<b>Причина:</b> {reason_text}"
            await bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await call.message.edit_text(f"❌ <b>Пост отклонён.</b>\nПричина: {reason_text or 'Без причины'}", parse_mode=ParseMode.HTML)
    await call.answer()

@dp.message(CustomRejectState.waiting_for_custom_reason)
async def custom_rejection_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    custom_reason = message.text

    if user_id:
        try:
            msg = f"💔 <b>К сожалению, твой пост был отклонён модератором.</b>\n\n<b>Причина:</b> {custom_reason}"
            await bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    await message.reply(f"❌ <b>Пост отклонён с вашей причиной:</b>\n<i>{custom_reason}</i>", parse_mode=ParseMode.HTML)
    await state.clear()

@dp.callback_query(F.data.startswith("adm_ban_"))
async def admin_ban_user(call: types.CallbackQuery):
    user_id = int(call.data.replace("adm_ban_", ""))
    BANNED_USERS.add(user_id)
    
    await call.message.reply(f"🚫 <b>Пользователь ID <code>{user_id}</code> заблокирован!</b>", parse_mode=ParseMode.HTML)
    try:
        await bot.send_message(user_id, "❌ Вы были заблокированы администратором бота.")
    except Exception:
        pass
    await call.answer()

# --- КОМАНДЫ ДЛЯ МЕНЮ ---
async def setup_bot_commands():
    commands = [
        BotCommand(command="start", description="Инструкция по предложке"),
        BotCommand(command="rules", description="Правила Литературного Клуба"),
        BotCommand(command="dice", description="Бросить кубик в чате"),
    ]
    await bot.set_my_commands(commands)

# --- ЗАПУСК БОТА ---
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
    asyncio.run(main())
