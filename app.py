import os, time
from flask import Flask, request, jsonify, render_template
from telegram import Bot
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

ORDER_LIMIT = 600
last_order = {}

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ping")
def ping():
    return "ok"

def make_pdf(calc, path):
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    doc = SimpleDocTemplate(path)
    story = [
        Paragraph("<b>Сравнение порошковых красок</b>", styles["Normal"]),
        Paragraph(f"Площадь: {calc['area']} м²", styles["Normal"]),
        Paragraph(f"Расход: {calc['consumption']} кг", styles["Normal"]),
        Paragraph(f"Выгоднее: <b>{calc['cheaper']}</b>", styles["Normal"]),
        Paragraph(f"Экономия: {calc['percent']} %", styles["Normal"]),
        Paragraph("<br/>Тут может быть ваша реклама<br/>@A_n1ck", styles["Normal"])
    ]
    doc.build(story)

@app.route("/api/order", methods=["POST"])
def order():
    data = request.json
    user = data["telegram"]
    uid = user["id"]
    now = time.time()

    if now - last_order.get(uid, 0) < ORDER_LIMIT:
        return jsonify({"error":"too fast"}), 429

    last_order[uid] = now

    calc = data["calculation"]
    ord = data["order"]

    pdf_path = f"/tmp/{uid}.pdf"
    make_pdf(calc, pdf_path)

    text = (
        "🧾 ЗАЯВКА С WEBAPP\n\n"
        f"👤 {user.get('first_name','')} @{user.get('username','')}\n"
        f"🆔 {uid}\n\n"
        f"📐 Площадь: {calc['area']} м²\n"
        f"⚖️ Расход: {calc['consumption']} кг\n"
        f"🏆 Выгоднее: {calc['cheaper']}\n"
        f"💰 Экономия: {calc['percent']} %\n\n"
        f"🎨 Поверхность: {ord['surface']}\n"
        f"🌈 Цвет: {ord['color']}\n"
        f"📦 Кол-во: {ord['quantity']} кг"
    )

    bot = Bot(BOT_TOKEN)
    bot.send_message(ADMIN_CHAT_ID, text)
    bot.send_document(ADMIN_CHAT_ID, open(pdf_path, "rb"))

    return jsonify({"ok":True})
