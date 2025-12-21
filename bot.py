import os
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # https://your-app.onrender.com

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            KeyboardButton(
                text="🧮 Открыть калькулятор",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "👋 Добро пожаловать!\n\n"
        "Нажмите кнопку ниже, чтобы открыть калькулятор краски 👇",
        reply_markup=reply_markup
    )

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("🤖 Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
