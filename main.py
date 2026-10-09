import asyncio
import logging
import os
from datetime import datetime
from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# === НАСТРОЙКИ ===
BOT_TOKEN = "8649830901:AAE7ab4e_Ga1zWOw8MSsgNvxgVWt4u60ETE" 
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbyhzZz5ffSVQot30yECv_1e4A5JhNxrPIDyZKUqQmUa-UrRJIO87cnxz5ISNqscoXhQ/exec"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
users_db = {}

class Registration(StatesGroup):
    waiting_for_name = State()

# === КОНСТАНТЫ КНОПОК ===
BTN_IN = "🟢 Зашел на смену"
BTN_OUT = "🔴 Вышел"
BTN_LUNCH = "🍱 Обед"
BTN_BACK_LUNCH = "🔙 Вернулся с обеда"
BTN_BREAK = "☕️ Перерыв"
BTN_BACK_BREAK = "🔙 Вернулся с перерыва"
BTN_CALLS = "📞 Звонки"
BTN_QUEUE = "📅 Мои брони / Очередь"

# === КЛАВИАТУРЫ ===
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_IN), KeyboardButton(text=BTN_OUT)],
            [KeyboardButton(text=BTN_LUNCH), KeyboardButton(text=BTN_BREAK)],
            [KeyboardButton(text=BTN_CALLS), KeyboardButton(text=BTN_QUEUE)]
        ], resize_keyboard=True
    )

def get_lunch_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_BACK_LUNCH)]], resize_keyboard=True)

def get_break_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_BACK_BREAK)]], resize_keyboard=True)

def get_lunch_time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="30 минут", callback_data="lunch_30"),
         InlineKeyboardButton(text="60 минут", callback_data="lunch_60")]
    ])

def get_break_time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 минут", callback_data="break_15"),
         InlineKeyboardButton(text="30 минут", callback_data="break_30")]
    ])

# === ОТПРАВКА В ТАБЛИЦУ ===
async def send_to_google_sheets(name: str, action: str):
    now = datetime.now()
    payload = {"date": now.strftime("%Y-%m-%d"), "name": name, "action": action, "time": now.strftime("%H:%M:%S")}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(WEBAPP_URL, json=payload) as response:
                return await response.text()
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            return None

async def reminder_timer(user_id: int, minutes: int, text: str):
    await asyncio.sleep(minutes * 60)
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception:
        pass

# === РЕГИСТРАЦИЯ ===
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("Привет! Для начала работы, пожалуйста, напиши свои ФИО (например, Иванов Иван):")
    await state.set_state(Registration.waiting_for_name)

@dp.message(Registration.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    users_db[message.from_user.id] = message.text
    await state.clear()
    await message.answer(f"Приятно познакомиться, {message.text}! Твое имя сохранено.\nТеперь выбери действие:", reply_markup=get_main_keyboard())

async def check_user_registered(message_or_call) -> str:
    user_id = message_or_call.from_user.id
    if user_id not in users_db:
        if isinstance(message_or_call, Message):
            await message_or_call.answer("Я забыл твое имя 😅 Пожалуйста, нажми /start, чтобы ввести ФИО заново.")
        return None
    return users_db[user_id]

# === ОБРАБОТЧИКИ ===
@dp.message(F.text == BTN_IN)
async def start_shift(message: Message):
    name = await check_user_registered(message)
    if name:
        await send_to_google_sheets(name, "🟢 Вход на смену")
        await message.answer(f"✅ {name}, ты успешно зашел на смену!")

@dp.message(F.text == BTN_OUT)
async def end_shift(message: Message):
    name = await check_user_registered(message)
    if name:
        await send_to_google_sheets(name, "🔴 Выход со смены")
        await message.answer("✅ Смена завершена. Хорошего отдыха!", reply_markup=get_main_keyboard())

@dp.message(F.text == BTN_LUNCH)
async def btn_lunch(message: Message):
    if await check_user_registered(message):
        await message.answer("На сколько минут уходишь на обед?", reply_markup=get_lunch_time_kb())

@dp.callback_query(F.data.startswith("lunch_"))
async def process_lunch_time(callback: CallbackQuery):
    name = await check_user_registered(callback)
    if not name: return await callback.answer()
    minutes = int(callback.data.split("_")[1])
    await send_to_google_sheets(name, f"🍱 Ушел на обед ({minutes} мин)")
    await callback.message.edit_text(f"🍱 Приятного аппетита! Таймер запущен на {minutes} минут.")
    await callback.message.answer("Как вернешься, нажми кнопку ниже 👇", reply_markup=get_lunch_keyboard())
    await callback.answer()
    asyncio.create_task(reminder_timer(callback.from_user.id, minutes, f"🔔 Твой обед закончился! Нажми '{BTN_BACK_LUNCH}'."))

@dp.message(F.text == BTN_BACK_LUNCH)
async def return_from_lunch(message: Message):
    name = await check_user_registered(message)
    if name:
        await send_to_google_sheets(name, "🔙 Вернулся с обеда")
        await message.answer("✅ С возвращением!", reply_markup=get_main_keyboard())

@dp.message(F.text == BTN_BREAK)
async def btn_break(message: Message):
    if await check_user_registered(message):
        await message.answer("На сколько минут уходишь на перерыв?", reply_markup=get_break_time_kb())

@dp.callback_query(F.data.startswith("break_"))
async def process_break_time(callback: CallbackQuery):
    name = await check_user_registered(callback)
    if not name: return await callback.answer()
    minutes = int(callback.data.split("_")[1])
    await send_to_google_sheets(name, f"☕️ Ушел на перерыв ({minutes} мин)")
    await callback.message.edit_text(f"☕️ Хорошего отдыха! Таймер запущен на {minutes} минут.")
    await callback.message.answer("Как вернешься, нажми кнопку ниже 👇", reply_markup=get_break_keyboard())
    await callback.answer()
    asyncio.create_task(reminder_timer(callback.from_user.id, minutes, f"🔔 Твой перерыв закончился! Нажми '{BTN_BACK_BREAK}'."))

@dp.message(F.text == BTN_BACK_BREAK)
async def return_from_break(message: Message):
    name = await check_user_registered(message)
    if name:
        await send_to_google_sheets(name, "🔙 Вернулся с перерыва")
        await message.answer("✅ С возвращением!", reply_markup=get_main_keyboard())

@dp.message(F.text == BTN_CALLS)
async def btn_calls(message: Message):
    name = await check_user_registered(message)
    if name:
        await send_to_google_sheets(name, "📞 Сел на звонки")
        await message.answer("📞 Статус изменен на 'Звонки'.")

@dp.message(F.text == BTN_QUEUE)
async def btn_queue(message: Message):
    await message.answer("🚧 Этот раздел в разработке!")

# === DUMMY WEB SERVER ДЛЯ RENDER ===
async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Dummy web server started on port {port}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
