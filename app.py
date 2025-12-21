import os
import time
from flask import Flask, render_template, request, jsonify
from telegram import Bot
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

ORDER_COOLDOWN = 600
last_orders = {}

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ping")
def ping():
    return "ok", 200

def generate_pdf(calc, path):
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    doc = SimpleDocTemplate(path)
    story = [
        Paragraph("<b>Сравнение двух красок</b>", styles["Normal"]),
        Paragraph(f"Площадь: {calc['area']} м²", styles["Normal"]),
        Paragraph(f"Выгоднее: <b>{calc['cheaper']}</b>", styles["Normal"]),
        Paragraph(f"Экономия: {calc['percent']} %", styles["Normal"]),
        Paragraph("<br/>Тут может быть ваша реклама<br/>@A_n1ck", styles["Normal"]),
    ]
    doc.build(story)

@app.route("/api/order", methods=["POST"])
def order():
    data = request.json
    tg = data.get("telegram")

    if not tg or "id" not in tg:
        return jsonify({"error": "no telegram user"}), 403

    uid = tg["id"]
    now = time.time()

    if now - last_orders.get(uid, 0) < ORDER_COOLDOWN:
        return jsonify({"error": "too frequent"}), 429

    last_orders[uid] = now

    pdf_path = f"/tmp/order_{uid}.pdf"
    generate_pdf(data["calculation"], pdf_path)

    text = (
        "🧾 ЗАЯВКА С WEBAPP\n\n"
        f"👤 {tg.get('first_name','')} @{tg.get('username','')}\n"
        f"🆔 {uid}\n\n"
        f"📐 Площадь: {data['calculation']['area']} м²\n"
        f"🏆 Выгоднее: {data['calculation']['cheaper']}\n"
        f"💰 Экономия: {data['calculation']['percent']} %\n\n"
        f"🎨 Поверхность: {data['order']['surface']}\n"
        f"🌈 Цвет: {data['order']['color']}\n"
        f"⚖️ Кол-во: {data['order']['quantity']} кг"
    )

    bot = Bot(BOT_TOKEN)
    bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
    bot.send_document(chat_id=ADMIN_CHAT_ID, document=open(pdf_path, "rb"))

    return jsonify({"success": True})
