import asyncio
import logging
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ---------------- CONFIG ----------------
BOT_TOKEN = "8872712620:AAEDuEt73mbSJma-EylkK9yaIm-WrDQzw2c"
# ВАЖНО: Вставь сюда ЧИСЛОВОЙ TELEGRAM ID знакомой (например: 123456789), НЕ ТОКЕН!
ADMIN_ID = 8822516870  
CHANNEL_ID = "@DOKIDOKIFOREVERLOVE"  # Юзернейм канала
# ----------------------------------------

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Временное хранилище предложек в памяти
suggestions_db = {}

# Советы от Моники
MONIKA_TIPS = [
    "Моника рекомендует: Иногда, когда ты бьёшься головой о стену, лучше сделать перерыв и выпить чаю!",
    "Моника рекомендует: Пиши от сердца! Не волнуйся о том, понравится ли это всем подряд.",
    "Моника рекомендует: Записывай даже самые маленькие идеи в блокнот, они могут стать началом чего-то грандиозного!",
    "Моника рекомендует: Не забудь сохранить свой проект! Ты же не хочешь, чтобы файлы случайно... исчезли? ~"
]

class Suggestion(StatesGroup):
    waiting_for_content = State()

# Клавиатура для админа
def get_admin_keyboard(sugg_id: str):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{sugg_id}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{sugg_id}")
        ]
    ])
    return kb

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer(
        "Привет! Добро пожаловать в Литературный Клуб и нашу предложку! 🌸\n\n"
        "Присылай сюда свой контент по DDLC (арты, стихи, теории, мемы), "
        "и админ обязательно его рассмотрит!\n\n"
        "Команды клуба:\n"
        "🟢 /tip — Совет дня от Моники\n"
        "🍵 /tea — Угоститься чаем у Юри\n"
        "🧁 /cupcake — Получить капкейк от Нацуки"
    )
    await state.set_state(Suggestion.waiting_for_content)

# Команда: Совет от Моники
@dp.message(Command("tip"))
async def cmd_tip(message: types.Message):
    tip = random.choice(MONIKA_TIPS)
    await message.answer(f"🎀 **Совет дня от Моники:**\n\n_{tip}_", parse_mode="Markdown")

# Команда: Чай от Юри
@dp.message(Command("tea"))
async def cmd_tea(message: types.Message):
    await message.answer("🍵 *Юри аккуратно наливает вам чашку горячего чая с ароматом жасмина и вежливо улыбается.*", parse_mode="Markdown")

# Команда: Капкейк от Нацуки
@dp.message(Command("cupcake"))
async def cmd_cupcake(message: types.Message):
    await message.answer("🧁 *Нацуки смущённо скрещивает руки на груди:* «Это... это не для тебя! Хотя ладно, держи один капкейк с мишами... Но не думай ничего такого!»", parse_mode="Markdown")

# Прием предложенного сообщения
@dp.message(Suggestion.waiting_for_content)
async def process_suggestion(message: types.Message, state: FSMContext):
    sugg_id = str(message.message_id)
    
    # Сохраняем информацию в память
    suggestions_db[sugg_id] = {
        "user_id": message.from_user.id,
        "from_user": message.from_user.full_name,
        "username": f"@{message.from_user.username}" if message.from_user.username else "без юзернейма",
        "chat_id": message.chat.id,
        "msg_id": message.message_id
    }

    author_info = f"👤 **От кого:** {message.from_user.full_name} ({suggestions_db[sugg_id]['username']})\n🆔 `ID: {message.from_user.id}`"

    # Формируем текст с цитатой (рамкой) для админа
    raw_text = message.text or message.caption or ""
    quoted_text = "\n".join([f"> {line}" for line in raw_text.split("\n")]) if raw_text else "> _[Медиаконтент без текста]_"

    caption_for_admin = f"📥 **Новая предложка!**\n\n{quoted_text}\n\n{author_info}"

    try:
        if message.photo or message.video or message.document or message.animation:
            await message.copy_to(
                chat_id=ADMIN_ID,
                caption=caption_for_admin,
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard(sugg_id)
            )
        else:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=caption_for_admin,
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard(sugg_id)
            )

        await message.answer("Спасибо! Твоё сообщение отправлено админу. 🎀")
    except Exception as e:
        await message.answer("Произошла ошибка при отправке.")
        logging.error(f"Ошибка: {e}")

# Обработка нажатий на кнопки (Опубликовать / Отклонить)
@dp.callback_query(F.data.startswith("publish_") | F.data.startswith("reject_"))
async def handle_admin_action(callback: CallbackQuery):
    action, sugg_id = callback.data.split("_")
    data = suggestions_db.get(sugg_id)

    if callback.from_user.id != ADMIN_ID:
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    if action == "publish":
        try:
            # Пересылаем исходное сообщение от подписчика прямо в канал
            if data:
                await bot.copy_message(
                    chat_id=CHANNEL_ID,
                    from_chat_id=data["chat_id"],
                    message_id=data["msg_id"]
                )
                try:
                    await bot.send_message(data["user_id"], "🎉 Ура! Твой пост был опубликован в канале!")
                except:
                    pass

            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.reply("✅ **Пост успешно опубликован в канале!**")
            await callback.answer("Опубликовано!")
        except Exception as e:
            await callback.answer(f"Ошибка публикации: {e}", show_alert=True)

    elif action == "reject":
        if data:
            try:
                await bot.send_message(data["user_id"], "Спасибо за предложение! К сожалению, этот пост не подошёл для публикации. 🌸")
            except:
                pass

        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("❌ **Предложка отклонена.**")
        await callback.answer("Отклонено")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
