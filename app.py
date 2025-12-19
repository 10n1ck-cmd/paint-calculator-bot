from flask import Flask, request, jsonify, render_template
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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

# КОНФИГУРАЦИЯ - ВАШИ ДАННЫЕ
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN', '8538859591:AAHKXc0k1b53rNVtnx0WAilDXuuYtPqOGs8')
ADMIN_CHAT_ID = os.environ.get('ADMIN_CHAT_ID', '5298304043')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://paint-calculator-bot.onrender.com')
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
    def calculate_theoretical(paint_data, product_area):
        """ТЕОРЕТИЧЕСКИЙ расчет (зная плотность, толщину, цену)"""
        # Площадь покрытия (м²/кг) = 1000 / (плотность * толщина)
        coverage_area = 1000 / (paint_data['density'] * paint_data['thickness'])
        
        # Теоретический расход (кг) = площадь изделия / площадь покрытия
        theoretical_consumption = product_area / coverage_area
        
        # Практический расход с учетом потерь
        practical_consumption = theoretical_consumption * (1 + paint_data.get('loss_factor', 0.15))
        
        # Стоимость на изделие
        product_cost = practical_consumption * paint_data['price']
        
        return {
            'coverage_area': round(coverage_area, 2),
            'theoretical_consumption': round(theoretical_consumption, 3),
            'practical_consumption': round(practical_consumption, 3),
            'product_cost': round(product_cost, 2),
            'cost_per_sqm': round(paint_data['price'] / coverage_area, 2)
        }
    
    @staticmethod
    def calculate_practical(paint_data, product_area):
        """ПРАКТИЧЕСКИЙ расчет (зная расход на изделие и цену)"""
        # Если есть реальный расход, используем его
        if 'real_consumption' in paint_data:
            consumption = paint_data['real_consumption']
            product_cost = consumption * paint_data['price']
            
            # Расчетная площадь покрытия (обратный расчет)
            coverage_area = product_area / consumption if consumption > 0 else 0
            
            return {
                'real_consumption': round(consumption, 3),
                'product_cost': round(product_cost, 2),
                'coverage_area': round(coverage_area, 2),
                'cost_per_sqm': round(product_cost / product_area, 2) if product_area > 0 else 0
            }
        else:
            return None
    
    @staticmethod
    def compare_paints(paint1_data, paint2_data, product_area, calculation_type='theoretical'):
        """Сравнение двух красок (теоретический или практический метод)"""
        if calculation_type == 'theoretical':
            results1 = PaintCalculator.calculate_theoretical(paint1_data, product_area)
            results2 = PaintCalculator.calculate_theoretical(paint2_data, product_area)
        else:
            results1 = PaintCalculator.calculate_practical(paint1_data, product_area)
            results2 = PaintCalculator.calculate_practical(paint2_data, product_area)
        
        if not results1 or not results2:
            return None
        
        cost_diff = results2['product_cost'] - results1['product_cost']
        cost_diff_percent = (cost_diff / results1['product_cost']) * 100 if results1['product_cost'] > 0 else 0
        
        return {
            'paint1': {
                **results1,
                'name': paint1_data.get('name', 'Краска 1'),
                'price_per_kg': paint1_data['price']
            },
            'paint2': {
                **results2,
                'name': paint2_data.get('name', 'Краска 2'),
                'price_per_kg': paint2_data['price']
            },
            'comparison': {
                'cost_difference': round(cost_diff, 2),
                'cost_difference_percent': round(cost_diff_percent, 1),
                'cheaper_paint': 'paint1' if cost_diff > 0 else 'paint2',
                'cheaper_paint_name': paint1_data.get('name', 'Краска 1') if cost_diff > 0 else paint2_data.get('name', 'Краска 2'),
                'cheaper_paint_cost': results1['product_cost'] if cost_diff > 0 else results2['product_cost'],
                'calculation_type': calculation_type
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
        self.application.add_handler(CommandHandler("practical", self.practical_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Старт с выбором типа расчета"""
        keyboard = [
            [InlineKeyboardButton("🎓 Теоретический расчет", callback_data='calc_theoretical')],
            [InlineKeyboardButton("🔧 Практический расчет", callback_data='calc_practical')],
            [InlineKeyboardButton("🌐 Открыть веб-версию", web_app=WebAppInfo(url=f"{WEBHOOK_URL}"))],
            [InlineKeyboardButton("💼 Заказать краску", callback_data='get_offer')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_text = """
🎨 *Добро пожаловать в калькулятор порошковых красок!*

*Выберите тип расчета:*

🎓 *ТЕОРЕТИЧЕСКИЙ* - если знаете:
• Плотность краски (г/см³)
• Толщину покрытия (мкм)
• Цену за кг

🔧 *ПРАКТИЧЕСКИЙ* - если знаете:
• Фактический расход на изделие (кг)
• Цену за кг

*Или воспользуйтесь веб-версией для удобного расчета!*
        """
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def calculate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Теоретический расчет"""
        user_id = update.effective_user.id
        user_data[user_id] = {
            'step': 'theory_area',
            'paint1': {},
            'paint2': {},
            'calc_type': 'theoretical'
        }
        await update.message.reply_text(
            "🎓 *ТЕОРЕТИЧЕСКИЙ РАСЧЕТ*\n\n"
            "📏 *ШАГ 1: Введите площадь изделия в м²*\n"
            "Пример: 2.5",
            parse_mode='Markdown'
        )
    
    async def practical_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Практический расчет"""
        user_id = update.effective_user.id
        user_data[user_id] = {
            'step': 'practice_area',
            'paint1': {},
            'paint2': {},
            'calc_type': 'practical'
        }
        await update.message.reply_text(
            "🔧 *ПРАКТИЧЕСКИЙ РАСЧЕТ*\n\n"
            "📏 *ШАГ 1: Введите площадь изделия в м²*\n"
            "Пример: 2.5",
            parse_mode='Markdown'
        )
    
    async def offer_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /offer для заказа краски"""
        user_id = update.effective_user.id
        user_data[user_id] = {'step': 'offer_1'}
        
        keyboard = [
            [InlineKeyboardButton("Глянцевая", callback_data='gloss')],
            [InlineKeyboardButton("Матовая", callback_data='matte')],
            [InlineKeyboardButton("Шагрень", callback_data='shagreen')],
            [InlineKeyboardButton("Муар", callback_data='moire')],
            [InlineKeyboardButton("Антик", callback_data='antique')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💼 *ЗАКАЗ КРАСКИ*\n\n"
            "Выберите тип поверхности:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id not in user_data:
            await update.message.reply_text("Введите /start для начала работы")
            return
        
        step = user_data[user_id]['step']
        text = update.message.text
        calc_type = user_data[user_id].get('calc_type', 'theoretical')
        
        try:
            # ОБЩИЕ ШАГИ: площадь изделия
            if step in ['theory_area', 'practice_area']:
                area = float(text)
                user_data[user_id]['product_area'] = area
                user_data[user_id]['step'] = f'{calc_type}_paint1'
                
                if calc_type == 'theoretical':
                    await update.message.reply_text(
                        "🎨 *ШАГ 2: Параметры ПЕРВОЙ краски*\n"
                        "Формат: `Название; Плотность; Толщина; Цена`\n"
                        "Пример: `Полиэстер; 1.5; 60; 450`",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "🎨 *ШАГ 2: Параметры ПЕРВОЙ краски*\n"
                        "Формат: `Название; Расход на изделие; Цена`\n"
                        "Пример: `Полиэстер; 0.85; 450`",
                        parse_mode='Markdown'
                    )
            
            # ТЕОРЕТИЧЕСКИЙ: параметры первой краски
            elif step == 'theoretical_paint1':
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint1'] = {
                    'name': parts[0],
                    'density': float(parts[1]),
                    'thickness': float(parts[2]),
                    'price': float(parts[3]),
                    'loss_factor': 0.15
                }
                user_data[user_id]['step'] = 'theoretical_paint2'
                await update.message.reply_text(
                    "🎨 *ШАГ 3: Параметры ВТОРОЙ краски*\n"
                    "Формат: `Название; Плотность; Толщина; Цена`\n"
                    "Пример: `Эпоксидная; 1.8; 80; 520`",
                    parse_mode='Markdown'
                )
            
            # ТЕОРЕТИЧЕСКИЙ: параметры второй краски
            elif step == 'theoretical_paint2':
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint2'] = {
                    'name': parts[0],
                    'density': float(parts[1]),
                    'thickness': float(parts[2]),
                    'price': float(parts[3]),
                    'loss_factor': 0.15
                }
                await self.perform_calculation(update, user_id)
            
            # ПРАКТИЧЕСКИЙ: параметры первой краски
            elif step == 'practical_paint1':
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint1'] = {
                    'name': parts[0],
                    'real_consumption': float(parts[1]),
                    'price': float(parts[2])
                }
                user_data[user_id]['step'] = 'practical_paint2'
                await update.message.reply_text(
                    "🎨 *ШАГ 3: Параметры ВТОРОЙ краски*\n"
                    "Формат: `Название; Расход на изделие; Цена`\n"
                    "Пример: `Эпоксидная; 1.2; 520`",
                    parse_mode='Markdown'
                )
            
            # ПРАКТИЧЕСКИЙ: параметры второй краски
            elif step == 'practical_paint2':
                parts = [p.strip() for p in text.split(';')]
                user_data[user_id]['paint2'] = {
                    'name': parts[0],
                    'real_consumption': float(parts[1]),
                    'price': float(parts[2])
                }
                await self.perform_calculation(update, user_id)
            
            # ЗАКАЗ: цвет краски
            elif step == 'offer_color':
                user_data[user_id]['color'] = text
                user_data[user_id]['step'] = 'offer_quantity_kg'
                await update.message.reply_text(
                    "⚖️ *ШАГ 2: Введите необходимое количество краски (кг)*\n"
                    "Пример: 25.5",
                    parse_mode='Markdown'
                )
            
            # ЗАКАЗ: количество краски в кг
            elif step == 'offer_quantity_kg':
                quantity_kg = float(text)
                if quantity_kg <= 0:
                    raise ValueError
                user_data[user_id]['quantity_kg'] = quantity_kg
                
                # Отправляем заказ
                await self.send_offer_request(update, user_id)
                
        except Exception as e:
            await update.message.reply_text(
                f"❌ Ошибка ввода. Проверьте формат.\n\n"
                f"Для теоретического расчета: `Название; Плотность; Толщина; Цена`\n"
                f"Для практического расчета: `Название; Расход; Цена`\n"
                f"Для заказа краски: введите число (кг)",
                parse_mode='Markdown'
            )
    
    async def perform_calculation(self, update: Update, user_id: int):
        data = user_data[user_id]
        calculator = PaintCalculator()
        
        result = calculator.compare_paints(
            data['paint1'],
            data['paint2'],
            data['product_area'],
            data['calc_type']
        )
        
        if not result:
            await update.message.reply_text("❌ Ошибка расчета. Проверьте данные.")
            return
        
        user_data[user_id]['calculation_result'] = result
        
        # Формируем отчет
        if data['calc_type'] == 'theoretical':
            report = self._format_theoretical_report(result)
        else:
            report = self._format_practical_report(result)
        
        keyboard = [
            [InlineKeyboardButton("💼 Заказать краску", callback_data='get_offer')],
            [InlineKeyboardButton("🌐 Открыть веб-версию", web_app=WebAppInfo(url=f"{WEBHOOK_URL}"))],
            [InlineKeyboardButton("🔄 Новый расчет", callback_data='new_calc')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(report, parse_mode='Markdown', reply_markup=reply_markup)
    
    def _format_theoretical_report(self, result):
        return f"""
🎓 *ТЕОРЕТИЧЕСКИЙ РАСЧЕТ*

📐 Площадь: {result['product_area']} м²

🎨 *{result['paint1']['name']}:*
• Цена: {result['paint1']['price_per_kg']} руб/кг
• Плотность: {result['paint1'].get('density', 'N/A')} г/см³
• Толщина: {result['paint1'].get('thickness', 'N/A')} мкм
• Покрытие: {result['paint1']['coverage_area']} м²/кг
• Расход: {result['paint1']['practical_consumption']} кг
• 💰 Стоимость: {result['paint1']['product_cost']} руб
• Цена м²: {result['paint1']['cost_per_sqm']} руб/м²

🎨 *{result['paint2']['name']}:*
• Цена: {result['paint2']['price_per_kg']} руб/кг
• Плотность: {result['paint2'].get('density', 'N/A')} г/см³
• Толщина: {result['paint2'].get('thickness', 'N/A')} мкм
• Покрытие: {result['paint2']['coverage_area']} м²/кг
• Расход: {result['paint2']['practical_consumption']} кг
• 💰 Стоимость: {result['paint2']['product_cost']} руб
• Цена м²: {result['paint2']['cost_per_sqm']} руб/м²

📈 *СРАВНЕНИЕ:*
• Разница: {abs(result['comparison']['cost_difference'])} руб
• 📉 Процент: {abs(result['comparison']['cost_difference_percent'])}%

🏆 *Экономия:* {result['comparison']['cheaper_paint_name']}
        """
    
    def _format_practical_report(self, result):
        return f"""
🔧 *ПРАКТИЧЕСКИЙ РАСЧЕТ*

📐 Площадь: {result['product_area']} м²

🎨 *{result['paint1']['name']}:*
• Цена: {result['paint1']['price_per_kg']} руб/кг
• Факт. расход: {result['paint1']['real_consumption']} кг
• 💰 Стоимость: {result['paint1']['product_cost']} руб
• Цена м²: {result['paint1']['cost_per_sqm']} руб/м²
• Покрытие: {result['paint1']['coverage_area']} м²/кг

🎨 *{result['paint2']['name']}:*
• Цена: {result['paint2']['price_per_kg']} руб/кг
• Факт. расход: {result['paint2']['real_consumption']} кг
• 💰 Стоимость: {result['paint2']['product_cost']} руб
• Цена м²: {result['paint2']['cost_per_sqm']} руб/м²
• Покрытие: {result['paint2']['coverage_area']} м²/кг

📈 *СРАВНЕНИЕ:*
• Разница: {abs(result['comparison']['cost_difference'])} руб
• 📉 Процент: {abs(result['comparison']['cost_difference_percent'])}%

🏆 *Экономия:* {result['comparison']['cheaper_paint_name']}
        """
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == 'calc_theoretical':
            await self.calculate_command(query)
        
        elif query.data == 'calc_practical':
            await self.practical_command(query)
        
        elif query.data in SURFACE_TYPES:
            user_data[user_id]['surface_type'] = SURFACE_TYPES[query.data]
            user_data[user_id]['step'] = 'offer_color'
            await query.edit_message_text(
                f"✅ Выбрано: *{SURFACE_TYPES[query.data]}*\n\n"
                "🎨 *ШАГ 1: Введите цвет краски*\n"
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
        
        elif query.data == 'new_calc':
            await self.start_command(query)
    
    async def send_offer_request(self, update: Update, user_id: int):
        data = user_data[user_id]
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        username = update.effective_user.username or 'N/A'
        
        if ADMIN_CHAT_ID:
            # Формируем детали заказа
            details = f"""🎨 *ДЕТАЛИ ЗАКАЗА:*
• Тип поверхности: {data['surface_type']}
• Цвет: {data['color']}
• Количество краски: {data['quantity_kg']} кг"""
            
            # Добавляем данные расчета если есть
            if 'calculation_result' in data:
                result = data['calculation_result']
                details += f"""
📊 *РАСЧЕТ:*
• Тип: {'Теоретический' if result['comparison']['calculation_type'] == 'theoretical' else 'Практический'}
• Площадь: {result['product_area']} м²
• Выгодная краска: {result['comparison']['cheaper_paint_name']}
• Экономия: {abs(result['comparison']['cost_difference'])} руб"""
            
            admin_msg = f"""
🚀 *НОВЫЙ ЗАКАЗ КРАСКИ!*

📅 Дата: {timestamp}
👤 Клиент: @{username}
📞 ID: {user_id}

{details}
            """
            
            try:
                await self.application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_msg,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logging.error(f"Ошибка отправки заказа: {e}")
        
        # Формируем подтверждение для пользователя
        confirmation = f"""
✅ *Заказ оформлен!*

📋 *Детали вашего заказа:*
• Тип поверхности: {data['surface_type']}
• Цвет: {data['color']}
• Количество краски: {data['quantity_kg']} кг

📞 *Наш менеджер свяжется с вами в течение часа* для уточнения деталей и согласования доставки.

💬 *Есть Telegram?* Добавляйте нашего бота для быстрых расчетов!
👉 https://t.me/{username or 'ваш_бот'}
        """
        
        await update.message.reply_text(confirmation, parse_mode='Markdown')
        
        # Сохраняем заказ
        offer_id = f"{user_id}_{int(datetime.now().timestamp())}"
        offer_requests[offer_id] = {
            'user_id': user_id,
            'username': username,
            'data': data,
            'timestamp': timestamp,
            'status': 'new'
        }
        
        # Очищаем данные пользователя
        if user_id in user_data:
            del user_data[user_id]
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
🆘 *ПОМОЩЬ*

*Выберите тип расчета:*

🎓 *ТЕОРЕТИЧЕСКИЙ* (/calculate)
Формат: `Название; Плотность; Толщина; Цена`
Пример: `Полиэстер; 1.5; 60; 450`

🔧 *ПРАКТИЧЕСКИЙ* (/practical)
Формат: `Название; Расход на изделие; Цена`
Пример: `Полиэстер; 0.85; 450`

💼 *ЗАКАЗ КРАСКИ* (/offer)
Выберите тип поверхности → цвет → количество краски (кг)

🌐 *ВЕБ-ВЕРСИЯ*
Полный функционал в браузере
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
        
        if data.get('calc_type') == 'practical':
            # Практический расчет
            paint1 = {
                'name': data['paint1']['name'],
                'real_consumption': data['paint1']['real_consumption'],
                'price': data['paint1']['price']
            }
            paint2 = {
                'name': data['paint2']['name'],
                'real_consumption': data['paint2']['real_consumption'],
                'price': data['paint2']['price']
            }
            result = calculator.compare_paints(
                paint1, paint2, 
                data['product_area'],
                'practical'
            )
        else:
            # Теоретический расчет
            paint1 = {
                'name': data['paint1']['name'],
                'density': data['paint1']['density'],
                'thickness': data['paint1']['thickness'],
                'price': data['paint1']['price'],
                'loss_factor': 0.15
            }
            paint2 = {
                'name': data['paint2']['name'],
                'density': data['paint2']['density'],
                'thickness': data['paint2']['thickness'],
                'price': data['paint2']['price'],
                'loss_factor': 0.15
            }
            result = calculator.compare_paints(
                paint1, paint2, 
                data['product_area'],
                'theoretical'
            )
        
        if result:
            return jsonify({'success': True, 'result': result})
        else:
            return jsonify({'success': False, 'error': 'Ошибка расчета'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/offer', methods=['POST'])
def api_offer():
    try:
        data = request.json
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        if TELEGRAM_TOKEN and ADMIN_CHAT_ID:
            # Формируем детали заказа
            order_details = f"""🎨 *ДЕТАЛИ ЗАКАЗА С САЙТА:*
• Тип: {SURFACE_TYPES.get(data.get('surface_type'), data.get('surface_type', 'N/A'))}
• Цвет: {data.get('color', 'N/A')}
• Количество краски: {data.get('quantity_kg', 'N/A')} кг"""
            
            admin_msg = f"""
🚀 *НОВЫЙ ЗАКАЗ КРАСКИ С САЙТА!*

📅 {timestamp}
👤 {data.get('name', 'N/A')}
📧 {data.get('email', 'N/A')}
📞 {data.get('phone', 'N/A')}

{order_details}

💬 Комментарий: {data.get('comment', 'Без комментария')}
            """
            
            try:
                asyncio.run(bot.application.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=admin_msg,
                    parse_mode='Markdown'
                ))
            except Exception as e:
                logging.error(f"Ошибка отправки в Telegram: {e}")
        
        # Сохраняем заказ
        offer_id = f"web_{int(datetime.now().timestamp())}"
        offer_requests[offer_id] = {
            'source': 'web',
            'data': data,
            'timestamp': timestamp,
            'status': 'new'
        }
        
        return jsonify({
            'success': True, 
            'message': 'Заказ оформлен! Мы свяжемся с вами в течение часа.',
            'offer_id': offer_id
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), bot.application.bot)
    asyncio.run(bot.application.process_update(update))
    return 'OK'

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
