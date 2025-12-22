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

# ================= НАСТРОЙКИ =================

BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
ANTI_SPAM_SECONDS = 60
TG_RETRY_COUNT = 3

# ============================================

app = Flask(__name__)
bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
last_request = {}

# ================= PDF FONT =================

FONT_PATH = "fonts/DejaVuSans.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))
    PDF_FONT = "DejaVu"
else:
    PDF_FONT = "Helvetica"

# ============================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ping")
def ping():
    return "ok"


# ================= РАСЧЁТ =================

def calc_percent(c1, c2):
    if not c1 or not c2:
        return None
    expensive = max(c1, c2)
    cheap = min(c1, c2)
    return round((expensive - cheap) / expensive * 100, 1)


# ================= PDF =================

def generate_pdf(payload, path):
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = PDF_FONT

    doc = SimpleDocTemplate(path)
    story = []

    calc = payload.get("calc", {})
    order = payload.get("order", {})

    story.append(Paragraph("<b>СРАВНЕНИЕ ПОРОШКОВЫХ КРАСОК</b>", styles["Normal"]))
    story.append(Spacer(1, 12))

    for block_name in ("theory", "practice"):
        if block_name in calc:
            b = calc[block_name]
            percent = calc_percent(b["c1"], b["c2"])
            cheaper = "Краска 1" if b["c1"] < b["c2"] else "Краска 2"

            story.append(Paragraph(
                f"<b>{'Теория' if block_name=='theory' else 'Практика'}</b><br/>"
                f"Краска 1: {b['c1']} ₽<br/>"
                f"Краска 2: {b['c2']} ₽<br/>"
                f"Выгоднее: {cheaper}<br/>"
                f"Экономия: {percent if percent else '—'} %",
                styles["Normal"]
            ))
            story.append(Spacer(1, 12))

    story.append(Paragraph("<b>ЗАКАЗ</b>", styles["Normal"]))
    story.append(Paragraph(
        f"Тип поверхности: {order.get('surface','—')}<br/>"
        f"Цвет: {order.get('color','—')}<br/>"
        f"Количество: {order.get('quantity','—')} кг",
        styles["Normal"]
    ))

    story.append(Spacer(1, 12))
    story.append(Paragraph("Тут может быть ваша реклама. Обращайтесь: @A_n1ck", styles["Normal"]))

    doc.build(story)


# ================= API =================

@app.route("/api/order", methods=["POST"])
def api_order():
    payload = request.get_json(force=True)
    print("📩 ORDER RECEIVED:", json.dumps(payload, ensure_ascii=False))

    user = payload.get("telegram") or {}
    user_id = user.get("id", request.remote_addr)

    # ---------- АНТИСПАМ ----------
    now = time.time()
    if user_id in last_request and now - last_request[user_id] < ANTI_SPAM_SECONDS:
        return jsonify({"error": "antispam"}), 429
    last_request[user_id] = now
    # -----------------------------

    calc = payload.get("calc", {})
    order = payload.get("order", {})

    msg = "🛒 *НОВАЯ ЗАЯВКА С WEBAPP*\n\n"

    if user:
        msg += (
            f"👤 Пользователь: {user.get('first_name','')} @{user.get('username','')}\n"
            f"🆔 user_id: `{user.get('id')}`\n\n"
        )

    for block_name in ("theory", "practice"):
        if block_name in calc:
            b = calc[block_name]
            percent = calc_percent(b["c1"], b["c2"])
            cheaper = "Краска 1" if b["c1"] < b["c2"] else "Краска 2"

            msg += (
                f"📊 *{'Теория' if block_name=='theory' else 'Практика'}*\n"
                f"Краска 1: {b['c1']} ₽\n"
                f"Краска 2: {b['c2']} ₽\n"
                f"Выгоднее: *{cheaper}*\n"
                f"Экономия: *{percent if percent else '—'} %*\n\n"
            )

    msg += (
        f"🎨 *Заказ:*\n"
        f"Тип поверхности: {order.get('surface','—')}\n"
        f"Цвет: {order.get('color','—')}\n"
        f"Количество: {order.get('quantity','—')} кг\n"
    )

    pdf_path = f"/tmp/order_{int(time.time())}.pdf"
    generate_pdf(payload, pdf_path)

    # ---------- ОТПРАВКА С RETRY ----------
    if bot and ADMIN_CHAT_ID:
        for attempt in range(TG_RETRY_COUNT):
            try:
                bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
                with open(pdf_path, "rb") as f:
                    bot.send_document(ADMIN_CHAT_ID, f)
                break
            except TelegramError as e:
                print(f"❌ TG ERROR attempt {attempt+1}:", e)
                time.sleep(2)
    # ------------------------------------

    return jsonify({"ok": True})
