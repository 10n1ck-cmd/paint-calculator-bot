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
LIMIT = 600
last = {}

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ping")
def ping():
    return "ok"

def pdf(data, path):
    s = getSampleStyleSheet()
    s["Normal"].fontName = "DejaVu"
    doc = SimpleDocTemplate(path)
    r = data["result"]
    story = [
        Paragraph("<b>Сравнение порошковых красок</b>", s["Normal"]),
        Paragraph(f"Теория: {r['theory']}", s["Normal"]),
        Paragraph(f"Практика: {r.get('practice','—')}", s["Normal"]),
        Paragraph(f"Выгоднее: {r['summary']['cheaper']}", s["Normal"]),
        Paragraph(f"Экономия: {r['summary']['percent']} %", s["Normal"]),
        Paragraph("<br/>@A_n1ck", s["Normal"])
    ]
    doc.build(story)

@app.route("/api/order", methods=["POST"])
def order():
    data = request.json
    uid = data["telegram"]["id"]
    if time.time() - last.get(uid,0) < LIMIT:
        return jsonify({"err":"spam"}),429
    last[uid]=time.time()

    path = f"/tmp/{uid}.pdf"
    pdf(data, path)

    bot = Bot(BOT_TOKEN)
    bot.send_message(ADMIN_CHAT_ID, str(data))
    bot.send_document(ADMIN_CHAT_ID, open(path,"rb"))

    return jsonify({"ok":True})
