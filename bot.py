import os
import time
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

# антиспам лимиты
START_COOLDOWN = 10  # секунд между /start
user_last_start = {}  # user_id -> timestamp

# ================== /start ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time.time()

    last_time = user_last_start.get(user_id, 0)
    if now - last_time < START_COOLDOWN:
        wait = int(START_COOLDOWN - (now - last_time))
        await update.message.reply_text(
            f"⏳ Подождите {wait} сек перед повторным запуском калькулятора."
        )
        return

    user_last_start[user_id] = now

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
        "🎨 *Калькулятор порошковой краски*\n\n"
        "Нажмите кнопку ниже, чтобы рассчитать расход и стоимость 👇",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# ================== MAIN ==================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("🤖 Bot with anti-spam started")
    app.run_polling()

if __name__ == "__main__":
    main()
