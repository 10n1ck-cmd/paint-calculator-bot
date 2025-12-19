from flask import Flask, request, jsonify, render_template
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import asyncio
from threading import Thread
import json
from datetime import datetime

app = Flask(__name__)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID', '')  # ID администратора для заявок
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://your-app.onrender.com')
PORT = int(os.environ.get('PORT', 5000))

# Типы поверхностей
SURFACE_TYPES = {
    'gloss': 'Глянцевая',
    'matte': 'Матовая',
    'shagreen': 'Шагрень',
    'moire': 'Муар',
    'antique': 'Антик'
}

class PaintCalculator:
    @staticmethod
    def calculate_theoretical(paint_data):
        coverage_area = 1000 / (paint_data['density'] * paint_data['thickness'])
        cost_per_sqm = paint_data['price'] / coverage_area
        return {
            'coverage_area': round(coverage_area, 2),
            'cost_per_sqm': round(cost_per_sqm, 2)
        }
    
    @staticmethod
    def calculate_practical(paint_data, product_area):
        theoretical_coverage = PaintCalculator.calculate_theoretical(paint_data)['coverage_area']
        theoretical_consumption = product_area / theoretical_coverage
        practical_consumption = theoretical_consumption * (1 + paint_data.get('loss_factor', 0.15))
        product_cost = practical_consumption * paint_data['price']
        return {
            'theoretical_consumption': round(theoretical_consumption, 3),
            'practical_consumption': round(practical_consumption, 3),
            'product_cost': round(product_cost, 2)
        }
    
    @staticmethod
    def compare_paints(paint1, paint2, product_area):
        results1 = PaintCalculator.calculate_practical(paint1, product_area)
        results2 = PaintCalculator.calculate_practical(paint2, product_area)
        
        cost_diff = results2['product_cost'] - results1['product_cost']
        cost_diff_percent = (cost_diff / results1['product_cost']) * 100 if results1['product_cost'] > 0 else 0
        
        return {
            'paint1': {
                **results1,
                'name': paint1.get('name', 'Краска 1'),
                'price_per_kg': paint1['price'],
                'density': paint1['density'],
                'thickness': paint1['thickness']
            },
            'paint2': {
                **results2,
                'name': paint2.get('name', 'Краска 2'),
                'price_per_kg': paint2['price'],
                'density': paint2['density'],
                'thickness': paint2['thickness']
            },
            'comparison': {
                'cost_difference': round(cost_diff, 2),
                'cost_difference_percent': round(cost_diff_percent, 1),
                'cheaper_paint_name': paint1.get('name', 'Краска 1') if cost_diff > 0 else paint2.get('name', 'Краска 2'),
            },
            'product_area': product_area
        }

user_data = {}
offer_requests = {}

class TelegramBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("calculate", self.calculate_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("offer", self.offer_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """
🎨 *Добро пожаловать в калькулятор порошковых красок!*

📋 *Доступные команды:*
/calculate - сравнить две краски
/offer - запросить предложение
/help - помощь

Начнем? Введите /calculate
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data[user_id] = {'step': 1, 'paint1': {}, 'paint2': {}}
        await update.message.reply_text("📏 *ШАГ 1: Введите площадь изделия в м²*\nПример: 2.5", parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in user_data:
            await update.message.reply_text("Введите /start для начала работы")
            return
        
        step = user_data[user_id]['step']
        text = update.message.text
        
        try:
            if step == 1:
                area = float(text)
                user_data[user_id]['product_area'] = area
                user_data[user_id]['step'] = 2
                await update.message.reply_text(
                    "🎨 *ШАГ 2: Параметры ПЕРВОЙ краски*\n"
                    "Формат: `Название; Плотность; Толщина; Цена`\n"
                    "Пример: `Полиэстер; 1.5; 60; 450`",
                    parse_mode='Markdown'
                )
            
            elif step == 2:
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint1'] = {
                    'name': parts[0],
                    'density': float(parts[1]),
                    'thickness': float(parts[2]),
                    'price': float(parts[3]),
                    'loss_factor': 0.15
                }
                user_data[user_id]['step'] = 3
                await update.message.reply_text(
                    "🎨 *ШАГ 3: Параметры ВТОРОЙ краски*\n"
                    "Формат: `Название; Плотность; Толщина; Цена`\n"
                    "Пример: `Эпоксидная; 1.8; 80; 520`",
                    parse_mode='Markdown'
                )
            
            elif step == 3:
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint2'] = {
                    'name': parts[0],
                    'density': float(parts[1]),
                    'thickness': float(parts[2]),
                    'price': float(parts[3]),
                    'loss_factor': 0.15
                }
                await self.perform_calculation(update, user_id)
            
            elif step == 'offer_color':
                user_data[user_id]['color'] = text
                user_data[user_id]['step'] = 'offer_quantity'
                await update.message.reply_text("🔢 *ШАГ 3: Введите количество изделий (шт)*\nПример: 100", parse_mode='Markdown')
            
            elif step == 'offer_quantity':
                quantity = int(text)
                user_data[user_id]['quantity'] = quantity
                await self.send_offer_request(update, user_id)
                
        except Exception:
            await update.message.reply_text("❌ Ошибка ввода. Проверьте формат.")
    
    async def perform_calculation(self, update: Update, user_id: int):
        data = user_data[user_id]
        calculator = PaintCalculator()
        result = calculator.compare_paints(data['paint1'], data['paint2'], data['product_area'])
        user_data[user_id]['calculation_result'] = result
        
        report = f"""
📊 *РЕЗУЛЬТАТЫ СРАВНЕНИЯ*

📐 Площадь: {data['product_area']} м²

🎨 *{result['paint1']['name']}:*
• Цена: {result['paint1']['price_per_kg']} руб/кг
• Расход: {result['paint1']['practical_consumption']} кг
• 💰 Стоимость: {result['paint1']['product_cost']} руб

🎨 *{result['paint2']['name']}:*
• Цена: {result['paint2']['price_per_kg']} руб/кг
• Расход: {result['paint2']['practical_consumption']} кг
• 💰 Стоимость: {result['paint2']['product_cost']} руб

📈 *СРАВНЕНИЕ:*
• Разница: {abs(result['comparison']['cost_difference'])} руб
• 📉 Процент: {abs(result['comparison']['cost_difference_percent'])}%

🏆 *Экономия:* {result['comparison']['cheaper_paint_name']}
        """
        
        keyboard = [
            [InlineKeyboardButton("💼 Получить выгодное предложение", callback_data='get_offer')],
            [InlineKeyboardButton("🔄 Новый расчет", callback_data='new')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(report, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data in SURFACE_TYPES:
            user_data[user_id]['surface_type'] = SURFACE_TYPES[query.data]
            user_data[user_id]['step'] = 'offer_color'
            await query.edit_message_text(
                f"✅ Выбрано: *{SURFACE_TYPES[query.data]}*\n\n"
                "🎨 *ШАГ 2: Введите цвет краски*\n"
                "Пример: RAL 9010",
                parse_mode='Markdown'
            )
        
        elif query.data == 'get_offer':
            keyboard = [[InlineKeyboardButton(text, callback_data=key)] for key, text in SURFACE_TYPES.items()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "💼 *ВЫБЕРИТЕ ТИП ПОВЕРХНОСТИ:*",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        
        elif query.data == 'new':
            await query.edit_message_text("Введите /calculate для нового расчета")
    
    async def send_offer_request(self, update: Update, user_id: int):
        data = user_data[user_id]
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        if ADMIN_CHAT_ID:
            admin_msg = f"""
🚀 *НОВАЯ ЗАЯВКА!*

📅 Дата: {timestamp}
👤 Пользователь: @{update.effective_user.username or 'N/A'}
📞 ID: {user_id}

🎨 *ДЕТАЛИ:*
• Тип: {data['surface_type']}
• Цвет: {data['color']}
• Количество: {data['quantity']} шт
            """
            
            if 'calculation_result' in data:
                result = data['calculation_result']
                admin_msg += f"""
📊 *РАСЧЕТ:*
• Площадь: {result['product_area']} м²
• Выгодная краска: {result['comparison']['cheaper_paint_name']}
                """
            
            try:
                await self.application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_msg,
                    parse_mode='Markdown'
                )
            except:
                pass
        
        confirmation = f"""
✅ *Заявка отправлена!*

📋 *Ваша заявка:*
• Тип: {data['surface_type']}
• Цвет: {data['color']}
• Количество: {data['quantity']} шт

📞 *Свяжемся в течение часа!*
        """
        
        await update.message.reply_text(confirmation, parse_mode='Markdown')
        if user_id in user_data:
            del user_data[user_id]
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🆘 *ПОМОЩЬ*

/start - начало работы
/calculate - сравнить краски
/offer - запросить предложение

*Формат ввода данных:*
`Название; Плотность; Толщина; Цена`
Пример: `Полиэстер; 1.5; 60; 450`
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

bot = TelegramBot()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    try:
        data = request.json
        calculator = PaintCalculator()
        result = calculator.compare_paints(data['paint1'], data['paint2'], data['product_area'])
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/offer', methods=['POST'])
def api_offer():
    try:
        data = request.json
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        if TELEGRAM_TOKEN and ADMIN_CHAT_ID:
            admin_msg = f"""
🚀 *ЗАЯВКА С САЙТА!*

📅 {timestamp}
👤 {data.get('name', 'N/A')}
📧 {data.get('email', 'N/A')}
📞 {data.get('phone', 'N/A')}

🎨 {data.get('surface_type', 'N/A')}
🌈 {data.get('color', 'N/A')}
📦 {data.get('quantity', 'N/A')} шт
            """
            
            try:
                asyncio.run(bot.application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_msg,
                    parse_mode='Markdown'
                ))
            except:
                pass
        
        return jsonify({'success': True, 'message': 'Заявка отправлена'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

def run_bot():
    bot.application.run_polling()

if __name__ == '__main__':
    if os.environ.get('RENDER'):
        bot.application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        )
    else:
        bot_thread = Thread(target=run_bot)
        bot_thread.start()
        app.run(host='0.0.0.0', port=PORT, debug=False)
