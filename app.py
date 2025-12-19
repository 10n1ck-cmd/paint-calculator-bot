from flask import Flask, request, jsonify, render_template
import os
import logging
import asyncio
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ------------------------------------------------------------------
# БАЗОВАЯ НАСТРОЙКА
# ------------------------------------------------------------------

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ❗❗❗ ТОЛЬКО из ENV — НИКАКИХ токенов в коде
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")   # https://xxx.onrender.com
PORT = int(os.environ.get("PORT", 5000))

# ------------------------------------------------------------------
# БИЗНЕС-ЛОГИКА РАСЧЁТА
# ------------------------------------------------------------------

class PaintCalculator:

    @staticmethod
    def calculate_theoretical(paint, area):
        coverage = 1000 / (paint["density"] * paint["thickness"])
        theo = area / coverage
        practical = theo * (1 + paint.get("loss_factor", 0.15))
        cost = practical * paint["price"]

        return {
            "coverage_area": round(coverage, 2),
            "theoretical_consumption": round(theo, 3),
            "practical_consumption": round(practical, 3),
            "product_cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }

    @staticmethod
    def calculate_practical(paint, area):
        cons = paint["real_consumption"]
        cost = cons * paint["price"]
        coverage = area / cons if cons > 0 else 0

        return {
            "real_consumption": round(cons, 3),
            "product_cost": round(cost, 2),
            "coverage_area": round(coverage, 2),
            "cost_per_sqm": round(cost / area, 2) if area > 0 else 0
        }

    @staticmethod
    def compare(p1, p2, area, calc_type):
        if area <= 0:
            return None

        if calc_type == "practical":
            r1 = PaintCalculator.calculate_practical(p1, area)
            r2 = PaintCalculator.calculate_practical(p2, area)
        else:
            r1 = PaintCalculator.calculate_theoretical(p1, area)
            r2 = PaintCalculator.calculate_theoretical(p2, area)

        diff = r2["product_cost"] - r1["product_cost"]
        base = min(r1["product_cost"], r2["product_cost"])
        diff_pct = (abs(diff) / base * 100) if base > 0 else 0

        return {
            "paint1": {**r1, "name": p1["name"], "price_per_kg": p1["price"]},
            "paint2": {**r2, "name": p2["name"], "price_per_kg": p2["price"]},
            "comparison": {
                "difference": round(diff, 2),
                "difference_percent": round(diff_pct, 1),
                "cheaper": "paint1" if diff > 0 else "paint2",
                "cheaper_name": p1["name"] if diff > 0 else p2["name"]
            },
            "product_area": area
        }

# ------------------------------------------------------------------
# API ДЛЯ FRONTEND (index.html)
# ------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def api_calculate():
    try:
        data = request.json
        calc_type = data.get("calc_type", "theoretical")
        area = float(data.get("product_area", 0))

        if calc_type == "practical":
            p1 = {
                "name": data["paint1"]["name"],
                "real_consumption": float(data["paint1"]["real_consumption"]),
                "price": float(data["paint1"]["price"])
            }
            p2 = {
                "name": data["paint2"]["name"],
                "real_consumption": float(data["paint2"]["real_consumption"]),
                "price": float(data["paint2"]["price"])
            }
        else:
            p1 = {
                "name": data["paint1"]["name"],
                "density": float(data["paint1"]["density"]),
                "thickness": float(data["paint1"]["thickness"]),
                "price": float(data["paint1"]["price"]),
                "loss_factor": float(data.get("loss_factor", 0.15))
            }
            p2 = {
                "name": data["paint2"]["name"],
                "density": float(data["paint2"]["density"]),
                "thickness": float(data["paint2"]["thickness"]),
                "price": float(data["paint2"]["price"]),
                "loss_factor": float(data.get("loss_factor", 0.15))
            }

        result = PaintCalculator.compare(p1, p2, area, calc_type)

        if not result:
            return jsonify({"success": False, "error": "Ошибка расчёта"}), 400

        return jsonify({"success": True, "result": result})

    except Exception as e:
        logging.exception("API calculate error")
        return jsonify({"success": False, "error": str(e)}), 500

# ------------------------------------------------------------------
# TELEGRAM BOT (НЕ МЕШАЕТ САЙТУ)
# ------------------------------------------------------------------

def run_bot():
    if not TELEGRAM_TOKEN:
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        kb = [[
            InlineKeyboardButton(
                "🌐 Открыть калькулятор",
                web_app=WebAppInfo(url=WEBHOOK_URL)
            )
        ]]
        await update.message.reply_text(
            "🎨 Калькулятор порошковых красок",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    application.add_handler(CommandHandler("start", start))
    application.run_polling()

# ------------------------------------------------------------------
# ЗАПУСК
# ------------------------------------------------------------------

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        import threading
        threading.Thread(target=run_bot, daemon=True).start()

    app.run(host="0.0.0.0", port=PORT)
