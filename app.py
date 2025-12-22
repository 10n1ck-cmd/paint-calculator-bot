from flask import Flask, render_template, request, jsonify
import os
from telegram import Bot

app = Flask(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT = os.environ.get("ADMIN_CHAT_ID")

bot = Bot(BOT_TOKEN)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/order", methods=["POST"])
def order():
    data = request.json
    c = data["calc"]
    u = data.get("user")

    text = "🛒 ЗАЯВКА С WEBAPP\n\n"

    if u:
        text += f"👤 {u.get('first_name','')} @{u.get('username','')}\n\n"

    text += (
        f"Тип расчёта: {'Теоретический' if c['mode']=='theory' else 'Практический'}\n\n"
        f"Краска 1:\n"
        f"• Расход: {c['kgm1']:.3f} кг/м²\n"
        f"• Цена: {c['r1']:.2f} ₽/м²\n\n"
        f"Краска 2:\n"
        f"• Расход: {c['kgm2']:.3f} кг/м²\n"
        f"• Цена: {c['r2']:.2f} ₽/м²\n\n"
        f"🏆 Выгоднее: {c['cheaper']}\n"
        f"💰 Экономия: {c['economyRub']:.2f} ₽/м² ({c['economyPct']}%)"
    )

    bot.send_message(ADMIN_CHAT, text)
    return jsonify(ok=True)

if __name__ == "__main__":
    app.run()
