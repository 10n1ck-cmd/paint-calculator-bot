import os
import time
import json
from flask import Flask, request, jsonify, render_template
from telegram import Bot
from telegram.error import TelegramError

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ===================== НАСТРОЙКИ =====================

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")  # ID пользователя или группы
ANTI_SPAM_SECONDS = 60

# ====================================================

app = Flask(__name__)
bot = Bot(BOT_TOKEN) if BOT_TOKEN else None

last_request = {}

# ---------- PDF FONT ----------
FONT_PATH = "fonts/DejaVuSans.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
    PDF_FONT = "DejaVu"
else:
    PDF_FONT = "Helvetica"

# ====================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ping")
def ping():
    return "ok"


# ===================== PDF =====================

def generate_pdf(payload, path):
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = PDF_FONT

    doc = SimpleDocTemplate(path)
    story = []

    calc = payload.get("calc", {})
    order = payload.get("order", {})
    user = payload.get("telegram", {})

    story.append(Paragraph("<b>СРАВНЕНИЕ ПОРОШКОВЫХ КРАСОК</b>", styles["Normal"]))
    story.append(Spacer(1, 12))

    if "theory" in calc:
        t = calc["theory"]
        story.append(Paragraph(
            f"Теория:<br/>"
            f"Краска 1: {t['c1']:.2f} ₽<br/>"
            f"Краска 2: {t['c2']:.2f} ₽",
            styles["Normal"]
        ))
        story.append(Spacer(1, 10))

    if "practice" in calc:
        p = calc["practice"]
        story.append(Paragraph(
            f"Практика:<br/>"
            f"Краска 1: {p['c1']:.2f} ₽<br/>"
            f"Краска 2: {p['c2']:.2f} ₽",
            styles["Normal"]
        ))
        story.append(Spacer(1, 10))

    if "summary" in calc:
        s = calc["summary"]
        story.append(Paragraph(
            f"<b>Выгоднее:</b> {s['cheaper']}<br/>"
            f"<b>Экономия:</b> {s['percent']} %",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

    story.append(Paragraph("<b>ЗАКАЗ</b>", styles["Normal"]))
    story.append(Paragraph(
        f"Тип поверхности: {order.get('surface')}<br/>"
        f"Цвет: {order.get('color')}<br/>"
        f"Количество: {order.get('quantity')} кг",
        styles["Normal"]
    ))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Контакт: @A_n1ck", styles["Normal"]))

    doc.build(story)


# ===================== API =====================

@app.route("/api/order", methods=["POST"])
def api_order():
    payload = request.get_json(force=True)

    print("📩 ORDER RECEIVED:", json.dumps(payload, ensure_ascii=False))

    user = payload.get("telegram") or {}
    user_id = user.get("id", request.remote_addr)

    # --------- АНТИСПАМ ---------
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < ANTI_SPAM_SECONDS:
        return jsonify({"error": "antispam"}), 429
    last_request[user_id] = now
    # ----------------------------

    # --------- ФОРМИРУЕМ ТЕКСТ ---------
    calc = payload.get("calc", {})
    order = payload.get("order", {})

    msg = "🛒 *НОВАЯ ЗАЯВКА С WEBAPP*\n\n"

    if user:
        msg += f"👤 Пользователь: {user.get('first_name','')} @{user.get('username','')}\n"
        msg += f"🆔 user_id: `{user.get('id')}`\n\n"

    if "summary" in calc:
        msg += (
            f"📊 *Результат:*\n"
            f"Выгоднее: *{calc['summary']['cheaper']}*\n"
            f"Экономия: *{calc['summary']['percent']} %*\n\n"
        )

    msg += (
        f"🎨 *Заказ:*\n"
        f"Тип поверхности: {order.get('surface')}\n"
        f"Цвет: {order.get('color')}\n"
        f"Количество: {order.get('quantity')} кг\n"
    )

    # --------- PDF ---------
    pdf_path = f"/tmp/order_{int(time.time())}.pdf"
    generate_pdf(payload, pdf_path)

    # --------- ОТПРАВКА В TG ---------
    if bot and ADMIN_CHAT_ID:
        try:
            bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg,
                parse_mode="Markdown"
            )
            with open(pdf_path, "rb") as f:
                bot.send_document(ADMIN_CHAT_ID, f)
        except TelegramError as e:
            print("❌ TELEGRAM ERROR:", e)
    else:
        print("⚠️ BOT TOKEN или ADMIN_CHAT_ID не заданы")

    return jsonify({"ok": True})
