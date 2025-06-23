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

# 🎭 Фейковый веб-сервер для Render
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return 'Bot is alive on Render!'

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

# 📘 Текст помощи
HELP_TEXT = (
    "🕵️ Добро пожаловать в викторину по нашей любимой игре — *Мафия*.\n\n"
    "📚 Команды:\n"
    "/start — выбрать режим и начать игру\n"
    "/score — ваш текущий результат\n"
    "/leaders — таблица лидеров (по точности)\n"
    "/stop — прервать викторину\n"
    "/help — справка\n\n"
    "Ответы выбираются кнопками. Думайте быстро — мафия не дремлет...\n\n"
    "📌 *Ведущий должен знать правила и быть беспристрастным.*"
)

# 📥 Загрузка вопросов
def load_all_questions():
    wb = load_workbook("questions.xlsx")
    sheet = wb.active
    headers = [cell.value for cell in sheet[1]]
    return [dict(zip(headers, row)) for row in sheet.iter_rows(min_row=2, values_only=True)]

ALL_QUESTIONS = load_all_questions()

# 🧠 Состояние пользователей
user_progress = {}
user_scores = {}
user_question_sets = {}

# 🚀 Команды Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_progress[user_id] = 0
    user_scores[user_id] = 0

    buttons = [
        [InlineKeyboardButton("5 — Разминка 🔄", callback_data="quiz_5")],
        [InlineKeyboardButton("10 — Проверка на прочность 🧠", callback_data="quiz_10")],
        [InlineKeyboardButton("20 — Я ПРО этой игры 🎩", callback_data="quiz_20")]
    ]
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        "🔍 Сколько вопросов выдержишь?\n"
        "Выбери режим и докажи, что не просто мирный житель под прикрытием:",
        reply_markup=markup
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")

async def stop_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_progress.pop(uid, None)
    user_scores.pop(uid, None)
    user_question_sets.pop(uid, None)
    await update.message.reply_text("⛔ Викторина прервана.\n\n" + HELP_TEXT, parse_mode="Markdown")

async def show_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    correct = user_scores.get(uid, 0)
    total = user_progress.get(uid, 0)
    await update.message.reply_text(f"📊 Ваш счёт: {correct} из {total} пройденных вопросов.")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = []
    for uid in user_scores:
        correct = user_scores[uid]
        total = user_progress.get(uid, 0)
        if total >= 5:
            percent = round(correct / total * 100)
            stats.append((uid, correct, total, percent))

    if not stats:
        await update.message.reply_text("👥 Лидерборд появится, когда хотя бы один игрок ответит на 5+ вопросов.")
        return

    stats.sort(key=lambda x: x[3], reverse=True)
    lines = []
    for rank, (uid, correct, total, percent) in enumerate(stats[:10], 1):
        try:
            user = await context.bot.get_chat(uid)
            name = user.username or user.first_name or f"User{uid}"
        except:
            name = f"User{uid}"
        lines.append(f"{rank}. @{name}: {correct} из {total} — {percent}%")

    await update.message.reply_text("🏆 Лидерборд по точности (от 5 ответов):\n\n" + "\n".join(lines))

# 🧩 Обработка режима
async def handle_start_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    count = int(query.data.replace("quiz_", ""))
    selected = random.sample(ALL_QUESTIONS, k=min(count, len(ALL_QUESTIONS)))
    user_question_sets[uid] = selected
    user_progress[uid] = 0
    user_scores[uid] = 0

    await query.edit_message_text(f"🔥 Отлично! Загружаю {count} вопросов.")
    await send_question(query, context, uid)

# ❓ Отправка вопроса
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
                "👉 /start — начать заново\n"
                "👉 /score — ваш результат\n"
                "👉 /leaders — таблица лидеров\n"
                "👉 /help — список команд"
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

# 🎯 Ответ
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

# ▶️ Запуск
app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", show_help))
app.add_handler(CommandHandler("score", show_score))
app.add_handler(CommandHandler("leaders", show_leaderboard))
app.add_handler(CommandHandler("stop", stop_quiz))
app.add_handler(CallbackQueryHandler(handle_start_mode, pattern="^quiz_"))
app.add_handler(CallbackQueryHandler(handle_answer))

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    app.run_polling()
