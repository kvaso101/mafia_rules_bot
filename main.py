import os
import random
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from openpyxl import load_workbook

# --- Flask для Render ---
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return 'Bot is alive on Render!'

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

# --- Глобальные переменные ---
ALL_QUESTIONS = []
MODULES = []
user_progress = {}
user_scores = {}
user_question_sets = {}

# --- Загрузка вопросов ---
def load_all_questions():
    wb = load_workbook("questions.xlsx")
    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]
    return [dict(zip(headers, row)) for row in sheet.iter_rows(min_row=2, values_only=True)]

def reload_questions():
    global ALL_QUESTIONS, MODULES
    ALL_QUESTIONS = load_all_questions()
    unique_modules = sorted(set(q["Module"] for q in ALL_QUESTIONS if q.get("Module")))
    MODULES = ["Микс"] + unique_modules

reload_questions()

# --- Команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_progress[user_id] = 0
    user_scores[user_id] = 0

    buttons = [
        [InlineKeyboardButton(module, callback_data=f"module_{module}")]
        for module in MODULES
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "📚 Выберите модуль, по которому хотите пройти викторину:",
        reply_markup=markup
    )

async def handle_module_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    selected_module = query.data.replace("module_", "")
    context.user_data["selected_module"] = selected_module

    buttons = [
        [InlineKeyboardButton("5 — Разминка 🔄", callback_data="quiz_5")],
        [InlineKeyboardButton("10 — Проверка на прочность 🧠", callback_data="quiz_10")],
        [InlineKeyboardButton("20 — Я ПРО этой игры 🎩", callback_data="quiz_20")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(
        f"🧠 Вы выбрали модуль: *{selected_module}*\n\nТеперь выберите количество вопросов:",
        parse_mode="Markdown",
        reply_markup=markup
    )

async def handle_start_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    count = int(query.data.replace("quiz_", ""))
    selected_module = context.user_data.get("selected_module")

    if selected_module == "Микс":
        filtered = ALL_QUESTIONS
    else:
        filtered = [q for q in ALL_QUESTIONS if q.get("Module") == selected_module]

    selected = random.sample(filtered, k=min(count, len(filtered)))

    user_question_sets[user_id] = selected
    user_progress[user_id] = 0
    user_scores[user_id] = 0

    await query.edit_message_text(
        f"🔥 Загружаю {len(selected)} вопросов из модуля *{selected_module}*.",
        parse_mode="Markdown"
    )
    await send_question(query, context, user_id)

async def send_question(source, context, uid):
    chat_id = getattr(source.message, "chat_id", uid)
    idx = user_progress.get(uid, 0)
    questions = user_question_sets.get(uid, [])

    if idx >= len(questions):
        score = user_scores.get(uid, 0)
        total = len(questions)
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                f"🎉 Викторина завершена!\nВы набрали {score} из {total}.\n\n"
                "👉 /start — начать заново"
            )
        )
        return

    q = questions[idx]
    buttons = [
        [InlineKeyboardButton(q["Option1"], callback_data=q["Option1"])],
        [InlineKeyboardButton(q["Option2"], callback_data=q["Option2"])],
        [InlineKeyboardButton(q["Option3"], callback_data=q["Option3"])],
        [InlineKeyboardButton(q["Option4"], callback_data=q["Option4"])]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await context.bot.send_message(chat_id=chat_id, text=q["Question"], reply_markup=markup)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    idx = user_progress.get(uid, 0)
    questions = user_question_sets.get(uid, [])

    if idx >= len(questions):
        await query.edit_message_text("❗️Викторина завершена.")
        return

    q = questions[idx]
    selected = query.data
    correct = str(q["CorrectAnswer"]).strip()
    explanation = str(q.get("Explanation", "")).strip()

    if selected == correct:
        result = "✅ Верно!"
        user_scores[uid] += 1
    else:
        result = f"❌ Неверно. Правильный ответ: {correct}"

    if explanation:
        result += f"\n\n📘 Объяснение: {explanation}"

    await query.edit_message_text(result)
    user_progress[uid] += 1
    await send_question(query, context, uid)

# --- Запуск ---
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_module_selection, pattern="^module_"))
app.add_handler(CallbackQueryHandler(handle_start_mode, pattern="^quiz_"))
app.add_handler(CallbackQueryHandler(handle_answer))

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    app.run_polling()