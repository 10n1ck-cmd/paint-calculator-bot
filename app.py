import os
import time
from flask import Flask, request, jsonify, render_template
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from telegram import Bot

# ================== CONFIG ==================
app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
bot = Bot(token=BOT_TOKEN)

# антиспам: 1 заявка / 10 минут
ORDER_COOLDOWN = 600
last_orders = {}  # user_id -> timestamp

# PDF font
pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

# ================== ROUTES ==================
@app.route("/")
def index():
    return render_template("index.html")

# ================== PDF ==================
def generate_pdf(data, filename):
    doc = SimpleDocTemplate(filename)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    story = [
        Paragraph("<b>Сравнение двух красок</b>", styles["Normal"]),
        Paragraph(f"Площадь: {data['area']} м²", styles["Normal"]),
        Paragraph(f"Выгоднее: <b>{data['cheaper']}</b>", styles["Normal"]),
        Paragraph(f"Экономия: {data['economy_percent']} %", styles["Normal"]),
        Paragraph("<br/>Тут может быть ваша реклама<br/>@A_n1ck", styles["Normal"]),
    ]

    doc.build(story)

# ================== ORDER ==================
@app.route("/api/order", methods=["POST"])
def order():
    payload = request.json

    tg = payload.get("telegram")
    if not tg or "id" not in tg:
        return jsonify({"error": "telegram user_id required"}), 403

    user_id = tg["id"]
    now = time.time()

    # антиспам
    last = last_orders.get(user_id, 0)
    if now - last < ORDER_COOLDOWN:
        wait = int((ORDER_COOLDOWN - (now - last)) / 60)
        return jsonify({
            "error": f"Слишком часто. Попробуйте через {wait} мин."
        }), 429

    last_orders[user_id] = now

    # PDF
    pdf_path = f"/tmp/order_{user_id}.pdf"
    generate_pdf(payload["calculation"], pdf_path)

    # сообщение админу
    text = (
        "🧾 НОВАЯ ЗАЯВКА С WEBAPP\n\n"
        f"👤 {tg.get('first_name','')} @{tg.get('username','')}\n"
        f"🆔 {user_id}\n\n"
        f"📐 Площадь: {payload['calculation']['area']} м²\n"
        f"🏆 Выгоднее: {payload['calculation']['cheaper']}\n"
        f"💰 Экономия: {payload['calculation']['economy_percent']} %\n\n"
        f"🎨 Тип поверхности: {payload['order']['surface']}\n"
        f"🌈 Цвет: {payload['order']['color']}\n"
        f"⚖️ Количество: {payload['order']['quantity']} кг"
    )

    bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    bot.send_document(chat_id=ADMIN_CHAT_ID, document=open(pdf_path, "rb"))

    return jsonify({"success": True})
