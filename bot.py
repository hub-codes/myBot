import os
import random
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import redis

# ایمپورت بانک سوالات
from questions import QUESTION_BANK, TIMEOUTS, QUESTIONS_COUNT

# لاگ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# توکن و Redis
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")

r = None
if REDIS_URL and (REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")

# وضعیت کاربران (مالتی‌استپ)
user_state = {}      # step: awaiting_name, awaiting_language, awaiting_level, in_quiz
user_data = {}       # ذخیره نام، زبان، سطح برای هر کاربر
user_quiz = {}       # وضعیت آزمون جاری

# ---------- helper: شمارنده تایمر ----------
async def run_timer(context: ContextTypes.DEFAULT_TYPE):
    """هر ثانیه یکبار صدا زده می‌شود تا تایمر را به‌روز کند."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz.get("timer_job") is not job_data:
        return
    remaining = job_data["remaining"] - 1
    if remaining <= 0:
        # زمان تمام شده، کار به timeout_handler واگذار می‌شود
        return
    # به‌روزرسانی عدد تایمر در پیام
    try:
        await context.bot.edit_message_text(
            chat_id=job_data["chat_id"],
            message_id=job_data["msg_id"],
            text=job_data["base_text"] + f"\n⏱ {remaining} ثانیه",
            reply_markup=job_data["reply_markup"]
        )
    except Exception:
        pass
    # کاهش زمان و ادامه تایمر
    job_data["remaining"] = remaining

async def start_timer(context, user_id, chat_id, msg_id, base_text, reply_markup, total_seconds):
    """راه‌اندازی یک شمارنده تایمر که هر ثانیه پیام را به‌روز می‌کند."""
    # تایمر اصلی (یک‌بار پس از total_seconds اجرا می‌شود)
    main_job = context.job_queue.run_once(
        timeout_handler,
        total_seconds,
        chat_id=chat_id,
        user_id=user_id,
        data={"question_index": user_quiz[user_id]["current_index"]}
    )
    # تایمر شمارنده هر ۱ ثانیه
    timer_job = context.job_queue.run_repeating(
        run_timer,
        interval=1,
        first=1,
        chat_id=chat_id,
        user_id=user_id,
        data={
            "user_id": user_id,
            "chat_id": chat_id,
            "msg_id": msg_id,
            "base_text": base_text,
            "reply_markup": reply_markup,
            "remaining": total_seconds,
            "main_job": main_job,
            "question_index": user_quiz[user_id]["current_index"]
        }
    )
    quiz = user_quiz[user_id]
    quiz["main_job"] = main_job
    quiz["timer_job"] = timer_job
    return main_job, timer_job

# ---------- هندلرهای مراحل ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع: درخواست نام"""
    user_id = update.effective_user.id
    user_state[user_id] = "awaiting_name"
    await update.message.reply_text("👋 سلام! لطفاً اسم خودتان را به فارسی وارد کنید:")

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت نام و رفتن به выбор زبان"""
    user_id = update.effective_user.id
    if user_state.get(user_id) != "awaiting_name":
        return
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("لطفاً یک اسم معتبر وارد کنید.")
        return
    user_data[user_id] = {"name": name}
    user_state[user_id] = "awaiting_language"
    # اینلاین کیبورد برای زبان‌ها
    languages = list(QUESTION_BANK.keys())
    keyboard = [[InlineKeyboardButton(lang, callback_data=f"lang:{lang}")] for lang in languages]
    keyboard.append([InlineKeyboardButton("لغو", callback_data="cancel")])
    await update.message.reply_text(
        f"{name} عزیز، کدام زبان را می‌خواهید آزمون بدهید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب زبان و رفتن به انتخاب سطح"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "cancel":
        await cancel_process(update, context)
        return
    lang = query.data.split(":")[1]
    if lang not in QUESTION_BANK:
        await query.edit_message_text("زبان انتخاب‌شده معتبر نیست.")
        return
    user_data[user_id]["language"] = lang
    user_state[user_id] = "awaiting_level"
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدی", callback_data="level:beginner")],
        [InlineKeyboardButton("🟡 متوسط", callback_data="level:intermediate")],
        [InlineKeyboardButton("🔴 پیشرفته", callback_data="level:advanced")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back_lang")]
    ]
    await query.edit_message_text(
        f"زبان {lang} انتخاب شد.\nحالا سطح خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """انتخاب سطح و شروع آزمون"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if query.data == "back_lang":
        # برگشت به انتخاب زبان
        languages = list(QUESTION_BANK.keys())
        keyboard = [[InlineKeyboardButton(lang, callback_data=f"lang:{lang}")] for lang in languages]
        keyboard.append([InlineKeyboardButton("لغو", callback_data="cancel")])
        await query.edit_message_text("یک زبان را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
        user_state[user_id] = "awaiting_language"
        return
    level = query.data.split(":")[1]
    lang = user_data[user_id]["language"]
    if level not in QUESTION_BANK[lang]:
        await query.edit_message_text("سطح نامعتبر است.")
        return
    user_data[user_id]["level"] = level
    # شروع آزمون
    await start_quiz(update, context, user_id, lang, level)

async def start_quiz(update, context, user_id, lang, level):
    """آماده‌سازی و شروع آزمون"""
    all_questions = QUESTION_BANK[lang][level]
    num_q = QUESTIONS_COUNT[level]
    selected = random.sample(all_questions, min(num_q, len(all_questions)))
    user_quiz[user_id] = {
        "language": lang,
        "level": level,
        "questions": selected,
        "current_index": 0,
        "score": 0,
        "first_name": user_data[user_id]["name"],
        "main_job": None,
        "timer_job": None,
        "last_msg_id": None,
        "last_chat_id": update.effective_chat.id
    }
    user_state[user_id] = "in_quiz"
    await update.callback_query.edit_message_text("آزمون شروع شد...")
    await asyncio.sleep(0.5)
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] >= len(quiz["questions"]):
        return
    q = quiz["questions"][quiz["current_index"]]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans:{quiz['current_index']}:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    total_seconds = TIMEOUTS[quiz["level"]]
    base_text = f"❓ سوال {quiz['current_index']+1}/{len(quiz['questions'])} ({quiz['language']}):\n{q['question']}\n⏱ {total_seconds} ثانیه"

    if update.callback_query:
        msg = await update.callback_query.message.reply_text(base_text, reply_markup=reply_markup)
    else:
        msg = await update.message.reply_text(base_text, reply_markup=reply_markup)

    quiz["last_msg_id"] = msg.message_id
    quiz["last_chat_id"] = update.effective_chat.id

    # حذف جاب‌های قبلی
    if quiz["main_job"]:
        quiz["main_job"].schedule_removal()
    if quiz["timer_job"]:
        quiz["timer_job"].schedule_removal()

    main_job, timer_job = await start_timer(
        context, user_id, update.effective_chat.id, msg.message_id,
        base_text, reply_markup, total_seconds
    )
    quiz["main_job"] = main_job
    quiz["timer_job"] = timer_job

async def send_next_question(context, user_id, chat_id):
    """ارسال سوال بعدی (پس از پاسخ یا تایم‌اوت)"""
    quiz = user_quiz.get(user_id)
    if not quiz:
        return
    q = quiz["questions"][quiz["current_index"]]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans:{quiz['current_index']}:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    total_seconds = TIMEOUTS[quiz["level"]]
    base_text = f"❓ سوال {quiz['current_index']+1}/{len(quiz['questions'])} ({quiz['language']}):\n{q['question']}\n⏱ {total_seconds} ثانیه"

    msg = await context.bot.send_message(chat_id=chat_id, text=base_text, reply_markup=reply_markup)
    quiz["last_msg_id"] = msg.message_id
    quiz["last_chat_id"] = chat_id

    # حذف جاب‌های قبلی
    if quiz["main_job"]:
        quiz["main_job"].schedule_removal()
    if quiz["timer_job"]:
        quiz["timer_job"].schedule_removal()

    main_job, timer_job = await start_timer(
        context, user_id, chat_id, msg.message_id, base_text, reply_markup, total_seconds
    )
    quiz["main_job"] = main_job
    quiz["timer_job"] = timer_job

async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    """زمان تمام شود: غیرفعال کردن پیام و رفتن به بعد"""
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] != job_data["question_index"]:
        return
    # حذف دکمه‌ها و نمایش پیام
    try:
        await context.bot.edit_message_reply_markup(
            chat_id=quiz["last_chat_id"],
            message_id=quiz["last_msg_id"],
            reply_markup=None
        )
        await context.bot.edit_message_text(
            chat_id=quiz["last_chat_id"],
            message_id=quiz["last_msg_id"],
            text="⏰ زمان تمام شد! این سوال از دست رفت."
        )
    except Exception:
        pass
    quiz["current_index"] += 1
    # توقف تایمر شمارنده
    if quiz["timer_job"]:
        quiz["timer_job"].schedule_removal()
        quiz["timer_job"] = None
    quiz["main_job"] = None

    if quiz["current_index"] < len(quiz["questions"]):
        await send_next_question(context, user_id, chat_id)
    else:
        await finish_quiz(context, user_id, chat_id)

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    quiz = user_quiz.get(user_id)
    if not quiz:
        await query.edit_message_text("آزمونی در جریان نیست.")
        return
    # استخراج داده
    parts = query.data.split(":")
    if len(parts) != 3:
        return
    q_index = int(parts[1])
    ans_index = int(parts[2])
    if q_index != quiz["current_index"]:
        await query.answer("این سوال منقضی شده است.")
        return
    # توقف تایمرها
    if quiz["main_job"]:
        quiz["main_job"].schedule_removal()
    if quiz["timer_job"]:
        quiz["timer_job"].schedule_removal()
    quiz["main_job"] = None
    quiz["timer_job"] = None

    # بررسی پاسخ
    q = quiz["questions"][quiz["current_index"]]
    if ans_index == q["correct"]:
        quiz["score"] += 1
    await query.message.delete()
    quiz["current_index"] += 1

    if quiz["current_index"] < len(quiz["questions"]):
        await send_next_question(context, user_id, update.effective_chat.id)
    else:
        await finish_quiz(context, user_id, update.effective_chat.id)

async def finish_quiz(context, user_id, chat_id):
    quiz = user_quiz.pop(user_id, None)
    if not quiz:
        return
    total = len(quiz["questions"])
    score = quiz["score"]
    language = quiz["language"]
    level = quiz["level"]
    name = quiz.get("first_name", "کاربر")
    percentage = (score / total) * 100

    if r:
        try:
            key = f"quizstats:{user_id}"
            r.hincrby(key, "quizzes", 1)
            r.hincrby(key, "total_score", score)
            r.hincrby(key, "total_questions", total)
            prev_best = r.hget(key, "best_percent")
            if prev_best is None or percentage > float(prev_best):
                r.hset(key, "best_percent", str(percentage))
        except Exception as e:
            logger.error(f"Redis error: {e}")

    text = (
        f"🏁 {name} عزیز، آزمون {language} تمام شد!\n"
        f"سطح: {level}\n"
        f"✅ پاسخ صحیح: {score} از {total}\n"
        f"📈 درصد: {percentage:.1f}%\n\n"
        "برای آزمون دوباره /start را بزنید."
    )
    await context.bot.send_message(chat_id=chat_id, text=text)
    # پاک کردن وضعیت
    user_state.pop(user_id, None)
    user_data.pop(user_id, None)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not r:
        await update.message.reply_text("سیستم آمار غیرفعال است.")
        return
    try:
        key = f"quizstats:{user_id}"
        data = r.hgetall(key)
        if not data:
            await update.message.reply_text("آماری ثبت نشده.")
            return
        quizzes = data.get("quizzes", 0)
        total_score = data.get("total_score", 0)
        total_q = data.get("total_questions", 0)
        best = data.get("best_percent", "-")
        avg = (int(total_score)/int(total_q)*100) if int(total_q) else 0
        await update.message.reply_text(
            f"📊 آمار شما:\n"
            f"🔢 آزمون‌ها: {quizzes}\n"
            f"⭐ میانگین: {avg:.1f}%\n"
            f"🏆 بهترین درصد: {best}\n"
            f"📝 کل سوالات: {total_q}"
        )
    except Exception:
        await update.message.reply_text("خطا در دریافت آمار.")

async def cancel_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state.pop(user_id, None)
    user_data.pop(user_id, None)
    if user_id in user_quiz:
        quiz = user_quiz.pop(user_id)
        if quiz["main_job"]:
            quiz["main_job"].schedule_removal()
        if quiz["timer_job"]:
            quiz["timer_job"].schedule_removal()
    await update.effective_message.reply_text("عملیات لغو شد.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید.")

def main():
    app = Application.builder().token(TOKEN).build()  # بدون JobQueue دستی
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cancel", cancel_process))
    # مراحل مکالمه
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name))
    # دکمه‌های اینلاین
    app.add_handler(CallbackQueryHandler(language_selection, pattern="^lang:"))
    app.add_handler(CallbackQueryHandler(level_selection, pattern="^level:"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^ans:"))
    app.add_handler(CallbackQueryHandler(cancel_process, pattern="^cancel$"))
    app.add_error_handler(error_handler)

    use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
    if use_webhook:
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
        app.run_webhook(listen="0.0.0.0", port=PORT, webhook_url=WEBHOOK_URL, drop_pending_updates=True)
    else:
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()