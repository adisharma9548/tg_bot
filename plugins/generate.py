import traceback
import asyncio
from pyrogram.types import Message
from pyrogram import Client, filters
from asyncio.exceptions import TimeoutError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    ListenerTimeout
)
from config import API_ID, API_HASH
from database.db import db

SESSION_STRING_SIZE = 351

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["logout"]))
async def handle_logout_command(client, message):
    user_data = await db.get_session(message.from_user.id)  
    if user_data is None:
        await message.reply("**You are not logged in.**")
        return 
    await db.set_session(message.from_user.id, session=None)  
    await message.reply("**Logged out successfully!**")

@Client.on_message(filters.private & ~filters.forwarded & filters.command(["login"]))
async def handle_login_command(bot: Client, message: Message):
    user_data = await db.get_session(message.from_user.id)
    if user_data is not None:
        await message.reply("**You are already logged in. First use /logout, then login again.**")
        return 
    user_id = int(message.from_user.id)
    api_id = API_ID
    api_hash = API_HASH

    client = None
    try:
        phone_number_msg = await bot.ask(
            chat_id=user_id, 
            text="<b>Please send your phone number with country code.</b>\n<b>Example:</b> <code>+917182818188</code>\n\n(Send /cancel to cancel)", 
            filters=filters.text,
            timeout=300
        )
        if phone_number_msg.text == '/cancel':
            return await phone_number_msg.reply('<b>Process cancelled.</b>')
        
        phone_number = phone_number_msg.text.strip()
        client = Client(f"temp_session_{user_id}", api_id=api_id, api_hash=api_hash, in_memory=True)
        await client.connect()
        await phone_number_msg.reply("Sending OTP code...")

        try:
            code = await client.send_code(phone_number)
        except PhoneNumberInvalid:
            await phone_number_msg.reply('❌ **The phone number is invalid.** Please try /login again.')
            return

        phone_code_msg = await bot.ask(
            chat_id=user_id, 
            text="📩 **Please check Telegram for the official login OTP code.**\n\n"
                 "If your OTP is `12345`, **send it with spaces like:** `1 2 3 4 5`.\n\n"
                 "(You have 10 minutes. Send /cancel to cancel)", 
            filters=filters.text, 
            timeout=600
        )
        if phone_code_msg.text == '/cancel':
            return await phone_code_msg.reply('<b>Process cancelled.</b>')

        try:
            phone_code = phone_code_msg.text.replace(" ", "").strip()
            await client.sign_in(phone_number, code.phone_code_hash, phone_code)
        except PhoneCodeInvalid:
            await phone_code_msg.reply('❌ **OTP is invalid.** Please try /login again.')
            return
        except PhoneCodeExpired:
            await phone_code_msg.reply('❌ **OTP has expired.** Please try /login again.')
            return
        except SessionPasswordNeeded:
            two_step_msg = await bot.ask(
                chat_id=user_id, 
                text='🔐 **Two-step verification is enabled on your account. Please enter your password:**\n\n(Send /cancel to cancel)', 
                filters=filters.text, 
                timeout=300
            )
            if two_step_msg.text == '/cancel':
                return await two_step_msg.reply('<b>Process cancelled.</b>')
            try:
                password = two_step_msg.text.strip()
                await client.check_password(password=password)
            except PasswordHashInvalid:
                await two_step_msg.reply('❌ **Invalid two-step password.** Please try /login again.')
                return

        string_session = await client.export_session_string()
        if len(string_session) < SESSION_STRING_SIZE:
            return await message.reply('❌ **Failed to generate valid session string.** Please try again.')

        uclient = Client(f"check_session_{user_id}", session_string=string_session, api_id=api_id, api_hash=api_hash, in_memory=True)
        await uclient.connect()
        await db.set_session(message.from_user.id, session=string_session)
        await db.set_api_id(message.from_user.id, api_id=api_id)
        await db.set_api_hash(message.from_user.id, api_hash=api_hash)
        try:
            await uclient.disconnect()
        except:
            pass

        await bot.send_message(
            message.from_user.id, 
            "✅ **Account logged in successfully!**\n\nNow you can send any restricted post or channel link to download."
        )

    except (TimeoutError, ListenerTimeout):
        await bot.send_message(user_id, "⏱ **Login timed out.** Please send /login to start again when you are ready.")
    except Exception as e:
        await bot.send_message(user_id, f"❌ **Login error:** `{e}`")
    finally:
        if client and client.is_connected:
            try:
                await client.disconnect()
            except:
                pass
