import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8285439649

# Твои реальные реквизиты
MY_IBAN = "ES50 1563 2626 3232 6996 2745"
MY_PAYPAL_EMAIL = "vadim.escritor@gmail.com"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

class EscrowDeal(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment = State()
    completed = State()

SERVICES = {
    "videocall": "📹 Video Call",
    "photos": "📸 Photos",
    "video": "🎬 Video",
    "voice": "🎙️ Voice Messages",
    "sign": "✍️ Sign / Custom Request"
}

def get_services_keyboard(selected=None):
    if selected is None:
        selected = []
    
    keyboard = []
    for code, name in SERVICES.items():
        is_sel = code in selected
        btn_text = f"✅ {name}" if is_sel else f"➕ {name}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"toggle_{code}")])
    
    if selected:
        keyboard.append([InlineKeyboardButton(text="➡️ Confirm Selection & Set Budget", callback_data="finish_selection")])
        
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.set_data({"selected_services": []})
    await message.answer(
        "🛡️ **Secure Deal Coordinator**\n\n"
        "Welcome! This system coordinates custom orders securely. "
        "Please select one or multiple formats you are interested in (click to add/remove), then confirm your choice:",
        reply_markup=get_services_keyboard([]),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("toggle_"))
async def process_toggle_service(callback: types.CallbackQuery, state: FSMContext):
    service_code = callback.data.split("_")[1]
    data = await state.get_data()
    selected = data.get("selected_services", [])
    
    if service_code in selected:
        selected.remove(service_code)
    else:
        selected.append(service_code)
        
    await state.update_data(selected_services=selected)
    
    try:
        await callback.message.edit_reply_markup(reply_markup=get_services_keyboard(selected))
    except Exception:
        pass
    await callback.answer()

@dp.callback_query(F.data == "finish_selection")
async def process_finish_selection(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_services", [])
    
    if not selected:
        await callback.answer("Please select at least one service first!", show_alert=True)
        return
        
    await state.set_state(EscrowDeal.waiting_for_amount)
    
    selected_names = [SERVICES[code] for code in selected]
    
    await callback.message.edit_text(
        f"✅ **Selected formats:**\n" + "\n".join([f"• {name}" for name in selected_names]) + "\n\n"
        "💶 Now, please **type your custom budget/amount** in EUR (from **5€** to **100€**):\n"
        "*(Just send the number as a message, e.g., `30`)*",
        parse_mode="Markdown"
    )

@dp.message(EscrowDeal.waiting_for_amount)
async def process_amount_input(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Please enter a valid number between 5 and 100 (e.g., `25`):")
        return

    if amount < 5 or amount > 100:
        await message.answer("⚠️ Amount must be between **5€** and **100€**. Please try again:", parse_mode="Markdown")
        return

    await state.update_data(amount=amount)
    await state.set_state(EscrowDeal.waiting_for_payment)
    
    data = await state.get_data()
    selected = data.get("selected_services", [])
    selected_names = [SERVICES[code] for code in selected]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🏦 Pay {amount}€ via IBAN", callback_data="show_iban")],
        [InlineKeyboardButton(text=f"🅿️ Pay {amount}€ via PayPal", callback_data="show_paypal")],
        [InlineKeyboardButton(text="✅ I Have Paid (Verify)", callback_data="check_payment")]
    ])

    await message.answer(
        f"🔒 **Secure Deal Created & Locked**\n\n"
        f"📌 **Order Details:**\n" + "\n".join([f"• {name}" for name in selected_names]) + "\n"
        f"💵 **Total Budget:** `{amount:.2f} EUR`\n"
        f"Status: `Awaiting Payment Verification`\n\n"
        "Choose your preferred payment method below. Once transferred, click 'I Have Paid' to notify the creator.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "show_iban")
async def process_show_iban(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 20)
    await callback.message.answer(
        f"🏦 **Bank Transfer Details (IBAN)**\n\n"
        f"Amount to send: **{amount:.2f} EUR**\n"
        f"IBAN: `{MY_IBAN}`\n\n"
        f"⚠️ *Please make sure to send the exact amount.* Once transferred, click **'I Have Paid'** in the main menu.",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "show_paypal")
async def process_paypal(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 20)
    await callback.message.answer(
        f"🅿️ **PayPal Transfer Details**\n\n"
        f"Amount to send: **{amount:.2f} EUR**\n"
        f"PayPal Account: `{MY_PAYPAL_EMAIL}`\n"
        f"*(Please send as Friends & Family to avoid transaction fees)*\n\n"
        f"⚠️ Once transferred, click **'I Have Paid'** in the main menu.",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "check_payment")
async def process_check_payment(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(EscrowDeal.funds_held)
    data = await state.get_data()
    selected = data.get("selected_services", [])
    selected_names = [SERVICES[code] for code in selected]
    amount = data.get("amount", 20)

    await callback.message.edit_text(
        "⏳ **Payment Verification in Progress**\n\n"
        "Your payment notification has been sent to the creator. "
        "As soon as the transfer is verified on the account, creation of your custom content will begin.",
        parse_mode="Markdown"
    )
    
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎉 Content Ready & Complete ({amount}€)", callback_data="release_funds")]
    ])
    
    try:
        await bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **NEW SECURE ORDER SUBMITTED!**\n\n"
                 f"👤 Buyer: @{callback.from_user.username or callback.from_user.id} (ID: `{callback.from_user.id}`)\n"
                 f"📌 Formats:\n" + "\n".join([f"• {name}" for name in selected_names]) + "\n"
                 f"💰 Budget: **{amount:.2f} EUR**\n\n"
                 f"🔍 *Action required:* Check your N26 / PayPal for the incoming transfer. Once confirmed, prepare the custom content and click below to finish the deal.",
            reply_markup=kb_admin,
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error notifying admin: {e}")

@dp.callback_query(F.data == "release_funds")
async def process_release_funds(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount", 20)
    await state.set_state(EscrowDeal.completed)
    
    await callback.message.edit_text(
        f"✅ **Deal Successfully Completed!**\n\n"
        f"Thank you for using the secure service. Order closed.",
        parse_mode="Markdown"
    )

async def handle(request):
    return web.Response(text="Bot is running!")

async def main():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
@dp.callback_query(F.data == "paid_clicked")
async def process_paid_payment(callback: types.CallbackQuery):
    # Отправляем подтверждение покупателю
    await callback.message.answer(
        "✅ Thank you! Your payment verification request has been sent to the creator."
    )
    
    # Отправляем уведомление тебе (админу) в личку
    await callback.bot.send_message(
        ADMIN_ID, 
        f"🔔 User @{callback.from_user.username} (ID: {callback.from_user.id}) clicked 'I Have Paid'!"
    )
    
    # Убираем часики с кнопки
    await callback.answer()
    
