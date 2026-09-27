import logging
import os
import asyncio
from typing import Dict, Set
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.filters.callback_data import CallbackData
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import BotCommand, ChatPermissions
from aiohttp import web

# ================= CONFIGURATION =================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8872712620:AAHa6LcIJpWtVDElhKt_watIrvWLoTFuU4A")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 8822516870))
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@DOKIDOKIFOREVERLOVE")
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
BAD_WORDS = {"скам", "ругательство"}

# Фабрики для Callback-кнопок (избавляет от ошибок разделения строк)
class DraftCallback(CallbackData, prefix="draft"):
    action: str  # pub, anon, cancel
    draft_id: str

class AdminCallback(CallbackData, prefix="adm"):
    action: str  # pub, rej, ban
    draft_id: str
    is_anon: bool = False
    user_id: int = 0

class RejectCallback(CallbackData, prefix="rej"):
    reason: str
    draft_id: str

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
    return web.Response(text="Monika is keeping this bot alive! ☕")

# --- КОМАНДА /START ---
@dp.message(CommandStart(), F.chat.type == "private")
async def start_cmd(message: types.Message):
    if message.from_user.id in BANNED_USERS:
        await message.answer("❌ Вы заблокированы в предложке.")
        return

    welcome_text = (
        f"<b>Добро пожаловать в Литературный Клуб, {message.from_user.first_name}! 🎀☕</b>\n\n"
        f"Это официальный бот предложки для нашего канала <b>{CHANNEL_ID}</b>.\n\n"
        "✨ <b>Как предложить свой пост / арт / стих:</b>\n"
        "1️⃣ Отправь сюда <b>текст</b>, <b>фото</b>, <b>видео</b>, <b>гифку</b>, <b>голосовое</b> или <b>кружочек</b>.\n"
        "2️⃣ Выбери режим публикации: <b>Открыто</b> (с указанием автора) или <b>Анонимно</b>.\n"
        "3️⃣ Подтверди отправку, и Моника передаст твой пост администраторам!\n\n"
        "⚠️ <i>Обратите внимание: предложка доступна только подписикам нашего канала.</i>"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Наш канал", url=f"https://t.me/{CHANNEL_ID.replace('@', '')}")
    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=kb.as_markup())

# ================= ФИШКИ И МОДЕРАЦИЯ ЧАТА =================

# 1. Правила чата
@dp.message(Command("rules"), F.chat.type.in_({"group", "supergroup"}))
async def rules_cmd(message: types.Message):
    rules_text = (
        "≈◈☛<b>ⲠⲢⲀⲂΥⲖⲀ</b>☚◈≈\n\n"
        "1~ Ⲙⲁⲧⲉⲣυⲧⲥя Ⲙⲟⲯⲏⲟ ⲏⲟ ⲏⲉ ⲕⲁⲕ ⲥⲁⲡⲟⲯⲏυⲕ\n"
        "2~ Ⲟⲥⲕⲟⲣⳝⲗяⲧь ⲇⲣⲩⲅυⲭ υ υⲭ ⲣⲟⲇⲏю ⲎⲈⲖЬⳄЯ\n"
        "3~ Ⲏⲉ ⲥⲡⲁⲙυⲧь. Ⲙⲁⲕⲥ. 10 ⲥⲧυⲕⲉⲣⲟⲃ υⲗυ ⲯⲉ ⳡⲉⲅⲟ-ⲧⲟ ⲧⲁⲕⲟⲅⲟ\n"
        "4~ Ⲏⲉ ⲩⲅⲣⲟⲯⲁⲧь ⲏυ ⲕⲟⲙⲩ\n"
        "5~ Ⲏⲉ ⲅⲟⲃⲟⲣυⲧь ⳡⲧⲟ ⲧы ⲉⳝ#ⲁⲗ ⲕⲟⲅⲟ-ⲧⲟ υⲗυ υⳅ Ⲣⲟⲇⲏυ ⳡⲉⲗⲟⲃⲉⲕⲁ\n"
        "6~ 18+ Ⲙⲟⲯⲏⲟ, ⲯⲉⲗⲁⲧⲉⲗьⲏⲟ ⲏⲉ ⲞⳠⲈⲎⲎЬ ⲙⲏⲟⲅⲟ\n\n"
        "✨ <i>Ⲡⲣⲁⲃυⲗⲁ Ⲥⲟⳝⲗюⲇⲁⲧь υ ⲏⲉ ⲏⲁⲣⲩⲱⲁⲧь!</i>"
    )
    await message.answer(rules_text, parse_mode=ParseMode.HTML)

# 2. Интерактивная игра /dice
@dp.message(Command("dice"), F.chat.type.in_({"group", "supergroup"}))
async def dice_cmd(message: types.Message):
    await message.answer_dice(emoji="🎲")

# 3. Статистика предложки (только для админа)
@dp.message(Command("stats"), F.chat.type == "private")
async def stats_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    text = (
        "📊 <b>Статистика бота:</b>\n\n"
        f"• Черновиков в памяти: <code>{len(DRAFTS)}</code>\n"
        f"• Забанено в предложке: <code>{len(BANNED_USERS)}</code>\n"
        f"• Пользователей с варнами: <code>{len(USER_WARNS)}</code>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

# 4. Выдача варна (/warn)
@dp.message(Command("warn"), F.chat.type.in_({"group", "supergroup"}))
async def warn_cmd(message: types.Message):
    if not await is_admin(message.chat.id, message.from_user.id):
        return

    if not message.reply_to_message:
        await message.reply("⚠️ Ответьте этой командой на сообщение нарушителя.")
        return

    target_user = message.reply_to_message.from_user
    bot_obj = await bot.get_me()

    if target_user.id == bot_obj.id or await is_admin(message.chat.id, target_user.id):
        await message.reply("❌ Нельзя выдать варн администратору или боту.")
        return

    warns = USER_WARNS.get(target_user.id, 0) + 1
    USER_WARNS[target_user.id] = warns

    if warns >= 3:
        try:
            await bot.ban_chat_member(message.chat.id, target_user.id)
            await bot.unban_chat_member(message.chat.id, target_user.id)  # Кик
            USER_WARNS[target_user.id] = 0
            await message.answer(f"🔴 <b>{target_user.full_name}</b> получил 3/3 варнов и исключён из чата!", parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.reply(f"⚠️ Ошибка при исключении: {e}")
    else:
        await message.answer(f"⚠️ <b>{target_user.full_name}</b> получает предупреждение! ({warns}/3)", parse_mode=ParseMode.HTML)

# 5. Снятие варна (/unwarn)
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

# 6. Мут (/mute <минуты>)
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

# 7. Кик (/kick)
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
            f"Проходи, налей чашечку чая ☕ и чувствуй себя как дома! ✨\n"
            f"Ознакомься с правилами клуба командой /rules!"
        )
        msg = await message.answer(welcome_msg, parse_mode=ParseMode.HTML)
        
        # Авто-удаление через 60 секунд, чтобы не забивать чат
        await asyncio.sleep(60)
        try:
            await msg.delete()
        except Exception:
            pass

@dp.message(F.left_chat_member)
async def farewell_member(message: types.Message):
    bot_obj = await bot.get_me()
    left_member = message.left_chat_member
    if left_member.id == bot_obj.id:
        return

    farewell_msg = f"💔 <b>{left_member.full_name}</b> покидает Литературный Клуб..."
    msg = await message.answer(farewell_msg, parse_mode=ParseMode.HTML)
    
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except Exception:
        pass

# --- АВТОМОДЕРАЦИЯ ЧАТА (ФИЛЬТР СПАМА И ССЫЛОК) ---
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def chat_moderation(message: types.Message):
    if not message.text or await is_admin(message.chat.id, message.from_user.id):
        return

    text_lower = message.text.lower()

    # Фильтр сторонних ссылок
    if "t.me/" in text_lower or "telegram.me/" in text_lower:
        if CHANNEL_ID.replace("@", "").lower() not in text_lower:
            try:
                await message.delete()
                warning = await message.answer(f"⚠️ {message.from_user.first_name}, ссылки на сторонние ресурсы запрещены!")
                await asyncio.sleep(10)
                await warning.delete()
            except Exception:
                pass
            return

    # Проверка на запрещённые слова
    for word in BAD_WORDS:
        if word in text_lower:
            try:
                await message.delete()
                warning = await message.answer(f"⚠️ Сообщение от {message.from_user.first_name} удалено фильтром.")
                await asyncio.sleep(10)
                await warning.delete()
            except Exception:
                pass
            break

# ================= ПРЕДЛОЖКА (В ЛС) =================

# Обработка ввода кастомной причины отклонения (должна быть выше обычных ЛС)
@dp.message(CustomRejectState.waiting_for_custom_reason, F.chat.type == "private")
async def custom_rejection_received(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    draft_id = data.get("draft_id")
    custom_reason = message.text

    if user_id:
        try:
            msg = f"💔 <b>К сожалению, твой пост был отклонён модератором.</b>\n\n<b>Причина:</b> {custom_reason}"
            await bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # Очищаем черновик из памяти
    DRAFTS.pop(draft_id, None)

    await message.reply(f"❌ <b>Пост отклонён с вашей причиной:</b>\n<i>{custom_reason}</i>", parse_mode=ParseMode.HTML)
    await state.clear()

# Получение поста в предложку
@dp.message(F.chat.type == "private")
async def handle_suggestion(message: types.Message):
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
    kb.button(text="👤 Открыто (показать имя)", callback_data=DraftCallback(action="pub", draft_id=draft_id).pack())
    kb.button(text="🕵️‍♂️ Анонимно", callback_data=DraftCallback(action="anon", draft_id=draft_id).pack())
    kb.button(text="🗑️ Отмена", callback_data=DraftCallback(action="cancel", draft_id=draft_id).pack())
    kb.adjust(1)

    await message.reply(
        "📝 <b>Ваш пост готов к отправке!</b>\n\nКак бы вы хотели его опубликовать?",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.as_markup()
    )

@dp.callback_query(DraftCallback.filter())
async def process_draft_option(call: types.CallbackQuery, callback_data: DraftCallback):
    draft_id = callback_data.draft_id
    action = callback_data.action

    if action == "cancel":
        DRAFTS.pop(draft_id, None)
        await call.message.edit_text("❌ Отправка отменена.")
        await call.answer()
        return

    draft = DRAFTS.get(draft_id)
    if not draft:
        await call.message.edit_text("⚠️ Ошибка: черновик устарел или был удалён.")
        await call.answer()
        return

    is_anon = (action == "anon")
    user_id = draft["user_id"]
    username_str = f"@{draft['username']}" if draft['username'] else "без юзернейма"
    
    author_info = (
        f"👤 <b>Автор:</b> {draft['user_name']} ({username_str}) | ID: <code>{user_id}</code>\n"
        f"🔒 <b>Режим:</b> {'🕵️‍♂️ Анонимно' if is_anon else '🙋‍♂️ Открыто'}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Опубликовать", callback_data=AdminCallback(action="pub", draft_id=draft_id, is_anon=is_anon, user_id=user_id).pack())
    kb.button(text="❌ Отклонить", callback_data=AdminCallback(action="rej", draft_id=draft_id, user_id=user_id).pack())
    kb.button(text="🚫 Забанить автора", callback_data=AdminCallback(action="ban", draft_id=draft_id, user_id=user_id).pack())
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

# --- КНОПКИ МОДЕРАЦИИ ДЛЯ АДМИНА ---

@dp.callback_query(AdminCallback.filter(F.action == "pub"))
async def admin_publish(call: types.CallbackQuery, callback_data: AdminCallback):
    draft_id = callback_data.draft_id
    is_anon = callback_data.is_anon

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

        # Очищаем черновик из памяти после успешной публикации
        DRAFTS.pop(draft_id, None)

    except Exception as e:
        logging.error(f"Ошибка при публикации: {e}")
        await call.message.reply(f"⚠️ Ошибка публикации: {e}")

    await call.answer()

@dp.callback_query(AdminCallback.filter(F.action == "rej"))
async def admin_reject_menu(call: types.CallbackQuery, callback_data: AdminCallback):
    draft_id = callback_data.draft_id
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🚫 Не соответствует теме", callback_data=RejectCallback(reason="offtopic", draft_id=draft_id).pack())
    kb.button(text="⚠️ Спам / Реклама", callback_data=RejectCallback(reason="spam", draft_id=draft_id).pack())
    kb.button(text="🖼️ Низкое качество", callback_data=RejectCallback(reason="lowquality", draft_id=draft_id).pack())
    kb.button(text="✍️ Своя причина", callback_data=RejectCallback(reason="custom", draft_id=draft_id).pack())
    kb.button(text="❌ Без причины", callback_data=RejectCallback(reason="none", draft_id=draft_id).pack())
    kb.adjust(1)

    await call.message.reply("Выберите причину отклонения:", reply_markup=kb.as_markup())
    await call.answer()

@dp.callback_query(RejectCallback.filter())
async def process_rejection_reason(call: types.CallbackQuery, callback_data: RejectCallback, state: FSMContext):
    reason_type = callback_data.reason
    draft_id = callback_data.draft_id

    draft = DRAFTS.get(draft_id)
    user_id = draft["user_id"] if draft else None

    reasons_map = {
        "offtopic": "Предложенный контент не соответствует тематике нашего клуба.",
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

    # Очищаем память
    DRAFTS.pop(draft_id, None)

    await call.message.edit_text(f"❌ <b>Пост отклонён.</b>\nПричина: {reason_text or 'Без причины'}", parse_mode=ParseMode.HTML)
    await call.answer()

@dp.callback_query(AdminCallback.filter(F.action == "ban"))
async def admin_ban_user(call: types.CallbackQuery, callback_data: AdminCallback):
    user_id = callback_data.user_id
    BANNED_USERS.add(user_id)
    
    await call.message.reply(f"🚫 <b>Пользователь ID <code>{user_id}</code> заблокирован в предложке!</b>", parse_mode=ParseMode.HTML)
    try:
        await bot.send_message(user_id, "❌ Вы были заблокированы администратором бота.")
    except Exception:
        pass
    await call.answer()

# --- КОМАНДЫ ДЛЯ МЕНЮ ---
async def setup_bot_commands():
    commands = [
        BotCommand(command="start", description="Предложить пост в канал"),
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
