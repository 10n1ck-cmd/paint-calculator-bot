import os
import time
import asyncio
import requests
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")
PING_URL = f"{WEBAPP_URL}/ping"

START_COOLDOWN = 10
last_start = {}

async def autoping():
    while True:
        try:
            requests.get(PING_URL, timeout=5)
        except:
            pass
        await asyncio.sleep(300)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    now = time.time()

    if now - last_start.get(uid, 0) < START_COOLDOWN:
        await update.message.reply_text("⏳ Подождите пару секунд…")
        return

    last_start[uid] = now

    kb = [[
        KeyboardButton(
            "🧮 Открыть калькулятор",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    ]]

    await update.message.reply_text(
        "🎨 Калькулятор порошковой краски\n\n"
        "Откройте WebApp для расчёта 👇",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    asyncio.create_task(autoping())
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
