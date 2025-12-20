from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import requests
import os

TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:5000/api/calculate")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🎓 Теория", "🔧 Практика"]]
    await update.message.reply_text(
        "Калькулятор порошковой краски\nВыберите тип расчёта:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def theory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "ПЛОЩАДЬ;ПЛОТНОСТЬ;ТОЛЩИНА;ЦЕНА\n\n"
        "Пример:\n"
        "12;1.4;80;450"
    )
    context.user_data["mode"] = "theoretical"

async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Формат:\n"
        "ПЛОЩАДЬ;РАСХОД;ЦЕНА\n\n"
        "Пример:\n"
        "12;0.85;450"
    )
    context.user_data["mode"] = "practical"

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(",", ".")
    if "mode" not in context.user_data:
        return

    try:
        parts = list(map(float, text.split(";")))
        if context.user_data["mode"] == "theoretical":
            area, density, thickness, price = parts
            payload = {
                "mode": "theoretical",
                "area": area,
                "paint1": {"name": "Краска", "density": density, "thickness": thickness, "price": price},
                "paint2": {"name": "Краска", "density": density, "thickness": thickness, "price": price}
            }
        else:
            area, cons, price = parts
            payload = {
                "mode": "practical",
                "area": area,
                "paint1": {"name": "Краска", "consumption": cons, "price": price},
                "paint2": {"name": "Краска", "consumption": cons, "price": price}
            }

        r = requests.post(API_URL, json=payload).json()
        p = r["paint1"]

        await update.message.reply_text(
            f"Результат:\n"
            f"Расход: {p['consumption']} кг\n"
            f"Покрытие: {p['coverage']} м²/кг\n"
            f"Стоимость: {p['cost']} ₽\n"
            f"Цена м²: {p['cost_per_sqm']} ₽"
        )

    except Exception:
        await update.message.reply_text("Ошибка формата. Попробуйте ещё раз.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("theory", theory))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("t", theory))
    app.add_handler(CommandHandler("p", practice))
    app.add_handler(CommandHandler("calc", handle))
    app.add_handler(CommandHandler("go", handle))
    app.run_polling()

if __name__ == "__main__":
    main()
