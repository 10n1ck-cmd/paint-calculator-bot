from flask import Flask, request, jsonify, render_template, send_file
import os
import logging
from datetime import datetime
import asyncio
from telegram import Bot
from weasyprint import HTML
from io import BytesIO

app = Flask(__name__)

# --- Настройки ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID')
bot = Bot(token=TELEGRAM_TOKEN)

logging.basicConfig(level=logging.INFO)

# Антиспам
user_last_submit = {}

# --- Главная страница ---
@app.route('/')
def home():
    return render_template('index.html')

# --- Получение заявки и генерация PDF ---
@app.route('/api/order', methods=['POST'])
def api_order():
    data = request.json
    user_id = data.get('user', {}).get('id', 'unknown')
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Антиспам
    last_time = user_last_submit.get(user_id, 0)
    if (datetime.now().timestamp() - last_time) < 60:
        return jsonify({"success": False, "error": "Антиспам: подождите минуту"}), 429
    user_last_submit[user_id] = datetime.now().timestamp()

    calc = data.get('calc', {})
    if not calc:
        return jsonify({"success": False, "error": "Нет данных расчета"}), 400

    # Формируем текст для Telegram
    msg = f"📌 Новый заказ ({now})\n"
    msg += f"👤 Пользователь: {user_id}\n\n"
    msg += "📊 Расчет:\n"
    msg += f"Режим: {calc.get('mode')}\n"
    msg += f"Краска 1: {calc.get('kgm1',0):.3f} кг/м², {calc.get('r1',0):.2f} ₽/м²\n"
    msg += f"Краска 2: {calc.get('kgm2',0):.3f} кг/м², {calc.get('r2',0):.2f} ₽/м²\n"
    msg += f"Выгоднее: {calc.get('cheaper')}\n"
    msg += f"Экономия: {calc.get('economyRub',0):.2f} ₽/м² ({calc.get('economyPct',0)}%)\n\n"
    msg += "🔥 Тут может быть ваша реклама: @A_n1ck"

    try:
        asyncio.run(bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg))
    except Exception as e:
        logging.error(f"Ошибка отправки Telegram: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

    # Генерация PDF
    pdf_html = render_template("pdf_template.html", calc=calc, user_id=user_id, now=now)
    pdf_file = BytesIO()
    HTML(string=pdf_html).write_pdf(pdf_file)
    pdf_file.seek(0)

    return send_file(pdf_file, download_name=f"calc_{user_id}.pdf", as_attachment=True, mimetype='application/pdf')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
