import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import redis

TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")

r = None
if REDIS_URL and (REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        r = None


TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL")

r = None
if REDIS_URL and (REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        r = None

QUESTION_BANK = {
    "beginner": [
        # همون ۲۰ سوال قبلی، کپی کنید
        {"question": "خروجی print(2**3) چیست؟",
         "options": ["6", "8", "9", "5"], "correct": 1},
        # ... ۱۹ تای دیگه
    ],
    "intermediate": [
        # همون ۲۰ سوال قبلی
        {"question": "خروجی کد زیر چیست؟\n```python\nx = [1,2,3]\ny = x\ny.append(4)\nprint(x)\n```", "options": [
            "[1,2,3]", "[1,2,3,4]", "[1,2,4]", "Error"], "correct": 1},
        # ... ۱۹ تای دیگه
    ],
    "advanced": [
        # همون ۲۰ سوال قبلی
        {"question": "دکوراتور (decorator) در پایتون چیست؟", "options": [
            "نوعی حلقه", "یک تابع که تابع دیگر را می‌گیرد و توسعه می‌دهد", "ماژول استاندارد", "شیء گرافیکی"], "correct": 1},
        # ... ۱۹ تای دیگه
    ]
}

TIMEOUTS = {"beginner": 8, "intermediate": 20, "advanced": 40}
user_quiz = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدی (۵ سوال، ۸ ثانیه)",
                              callback_data="level:beginner")],
        [InlineKeyboardButton("🟡 متوسط (۷ سوال، ۲۰ ثانیه)",
                              callback_data="level:intermediate")],
        [InlineKeyboardButton("🔴 پیشرفته (۱۰ سوال، ۴۰ ثانیه)",
                              callback_data="level:advanced")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📚 به آزمون پایتون خوش آمدید!\nلطفاً سطح خود را انتخاب کنید:", reply_markup=reply_markup)


async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    level = query.data.split(":")[1]
    first_name = update.effective_user.first_name
    num_questions = {"beginner": 5, "intermediate": 7, "advanced": 10}[level]
    all_questions = QUESTION_BANK[level]
    selected = random.sample(all_questions, min(
        num_questions, len(all_questions)))
    user_quiz[user_id] = {
        "level": level,
        "questions": selected,
        "current_index": 0,
        "score": 0,
        "first_name": first_name,
        "job": None,
        "last_msg_id": None,
        "last_chat_id": None
    }
    await query.edit_message_text(
        f"✅ {first_name} عزیز، سطح {level} انتخاب شد.\n"
        f"تعداد: {num_questions} | زمان هر سوال: {TIMEOUTS[level]} ثانیه"
    )
    await asyncio.sleep(1)
    await send_question(update, context, user_id)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    data = user_quiz.get(user_id)
    if not data or data["current_index"] >= len(data["questions"]):
        return
    q = data["questions"][data["current_index"]]
    keyboard = [[InlineKeyboardButton(
        opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        msg = await update.callback_query.message.reply_text(
            f"❓ سوال {data['current_index']+1}/{len(data['questions'])}:\n{q['question']}",
            reply_markup=reply_markup
        )
    else:
        msg = await update.message.reply_text(
            f"❓ سوال {data['current_index']+1}/{len(data['questions'])}:\n{q['question']}",
            reply_markup=reply_markup
        )
    data["last_msg_id"] = msg.message_id
    data["last_chat_id"] = update.effective_chat.id
    if data["job"]:
        data["job"].schedule_removal()
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUTS[data["level"]],
        chat_id=update.effective_chat.id,
        user_id=user_id,
        data={"question_index": data["current_index"]}
    )
    data["job"] = job


async def send_next_question(context, user_id, chat_id):
    quiz = user_quiz.get(user_id)
    if not quiz:
        return
    q = quiz["questions"][quiz["current_index"]]
    keyboard = [[InlineKeyboardButton(
        opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"❓ سوال {quiz['current_index']+1}/{len(quiz['questions'])}:\n{q['question']}",
        reply_markup=reply_markup
    )
    quiz["last_msg_id"] = msg.message_id
    quiz["last_chat_id"] = chat_id
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUTS[quiz["level"]],
        chat_id=chat_id,
        user_id=user_id,
        data={"question_index": quiz["current_index"]}
    )
    quiz["job"] = job


async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] != job_data["question_index"]:
        return
    # ویرایش پیام به زمان تمام شد
    try:
        await context.bot.edit_message_text(
            chat_id=quiz["last_chat_id"],
            message_id=quiz["last_msg_id"],
            text="⏰ زمان تمام شد! این سوال از دست رفت."
        )
    except Exception:
        pass
    quiz["current_index"] += 1
    quiz["job"] = None
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
    if quiz["job"]:
        quiz["job"].schedule_removal()
        quiz["job"] = None
    ans_index = int(query.data.split(":")[1])
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
    level = quiz["level"]
    first_name = quiz.get("first_name", "کاربر")
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
            print(f"Redis error: {e}")
    text = (
        f"🏁 {first_name} عزیز، آزمون به پایان رسید!\n"
        f"📊 سطح: {level}\n"
        f"✅ پاسخ صحیح: {score} از {total}\n"
        f"📈 درصد: {percentage:.1f}%\n\n"
        "برای آزمون دوباره /start را بزنید."
    )
    await context.bot.send_message(chat_id=chat_id, text=text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not r:
        await update.message.reply_text("📭 سیستم آمار موقتاً در دسترس نیست.")
        return
    try:
        key = f"quizstats:{user_id}"
        data = r.hgetall(key)
        if not data:
            await update.message.reply_text("📭 هنوز هیچ آماری ثبت نشده است.")
            return
        quizzes = data.get("quizzes", 0)
        total_score = data.get("total_score", 0)
        total_q = data.get("total_questions", 0)
        best = data.get("best_percent", "-")
        avg = (int(total_score) / int(total_q) * 100) if int(total_q) else 0
        await update.message.reply_text(
            f"📊 آمار شما:\n"
            f"🔢 تعداد آزمون‌ها: {quizzes}\n"
            f"⭐ میانگین امتیاز: {avg:.1f}%\n"
            f"🏆 بهترین درصد: {best}\n"
            f"📝 کل سوالات پاسخ‌داده‌شده: {total_q}"
        )
    except:
        await update.message.reply_text("خطا در دریافت آمار.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_quiz:
        quiz = user_quiz.pop(user_id)
        if quiz["job"]:
            quiz["job"].schedule_removal()
        await update.message.reply_text("🛑 آزمون لغو شد.")
    else:
        await update.message.reply_text("آزمونی در جریان نیست.")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(level_selection, pattern="^level:"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^ans:"))
    use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
    if use_webhook:
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
        app.run_webhook(listen="0.0.0.0", port=PORT,
                        webhook_url=WEBHOOK_URL, drop_pending_updates=True)
    else:
        print("Running polling...")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
TIMEOUTS = {"beginner": 8, "intermediate": 20, "advanced": 40}
user_quiz = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدی (۵ سوال، ۸ ثانیه)",
                              callback_data="level:beginner")],
        [InlineKeyboardButton("🟡 متوسط (۷ سوال، ۲۰ ثانیه)",
                              callback_data="level:intermediate")],
        [InlineKeyboardButton("🔴 پیشرفته (۱۰ سوال، ۴۰ ثانیه)",
                              callback_data="level:advanced")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📚 به آزمون پایتون خوش آمدید!\nلطفاً سطح خود را انتخاب کنید:", reply_markup=reply_markup)


async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    level = query.data.split(":")[1]
    first_name = update.effective_user.first_name
    num_questions = {"beginner": 5, "intermediate": 7, "advanced": 10}[level]
    all_questions = QUESTION_BANK[level]
    selected = random.sample(all_questions, min(
        num_questions, len(all_questions)))
    user_quiz[user_id] = {
        "level": level,
        "questions": selected,
        "current_index": 0,
        "score": 0,
        "first_name": first_name,
        "job": None,
        "last_msg_id": None,
        "last_chat_id": None
    }
    await query.edit_message_text(
        f"✅ {first_name} عزیز، سطح {level} انتخاب شد.\n"
        f"تعداد: {num_questions} | زمان هر سوال: {TIMEOUTS[level]} ثانیه"
    )
    await asyncio.sleep(1)
    await send_question(update, context, user_id)


async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    data = user_quiz.get(user_id)
    if not data or data["current_index"] >= len(data["questions"]):
        return
    q = data["questions"][data["current_index"]]
    keyboard = [[InlineKeyboardButton(
        opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        msg = await update.callback_query.message.reply_text(
            f"❓ سوال {data['current_index']+1}/{len(data['questions'])}:\n{q['question']}",
            reply_markup=reply_markup
        )
    else:
        msg = await update.message.reply_text(
            f"❓ سوال {data['current_index']+1}/{len(data['questions'])}:\n{q['question']}",
            reply_markup=reply_markup
        )
    data["last_msg_id"] = msg.message_id
    data["last_chat_id"] = update.effective_chat.id
    if data["job"]:
        data["job"].schedule_removal()
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUTS[data["level"]],
        chat_id=update.effective_chat.id,
        user_id=user_id,
        data={"question_index": data["current_index"]}
    )
    data["job"] = job


async def send_next_question(context, user_id, chat_id):
    quiz = user_quiz.get(user_id)
    if not quiz:
        return
    q = quiz["questions"][quiz["current_index"]]
    keyboard = [[InlineKeyboardButton(
        opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"❓ سوال {quiz['current_index']+1}/{len(quiz['questions'])}:\n{q['question']}",
        reply_markup=reply_markup
    )
    quiz["last_msg_id"] = msg.message_id
    quiz["last_chat_id"] = chat_id
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUTS[quiz["level"]],
        chat_id=chat_id,
        user_id=user_id,
        data={"question_index": quiz["current_index"]}
    )
    quiz["job"] = job


async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] != job_data["question_index"]:
        return
    # ویرایش پیام به زمان تمام شد
    try:
        await context.bot.edit_message_text(
            chat_id=quiz["last_chat_id"],
            message_id=quiz["last_msg_id"],
            text="⏰ زمان تمام شد! این سوال از دست رفت."
        )
    except Exception:
        pass
    quiz["current_index"] += 1
    quiz["job"] = None
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
    if quiz["job"]:
        quiz["job"].schedule_removal()
        quiz["job"] = None
    ans_index = int(query.data.split(":")[1])
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
    level = quiz["level"]
    first_name = quiz.get("first_name", "کاربر")
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
            print(f"Redis error: {e}")
    text = (
        f"🏁 {first_name} عزیز، آزمون به پایان رسید!\n"
        f"📊 سطح: {level}\n"
        f"✅ پاسخ صحیح: {score} از {total}\n"
        f"📈 درصد: {percentage:.1f}%\n\n"
        "برای آزمون دوباره /start را بزنید."
    )
    await context.bot.send_message(chat_id=chat_id, text=text)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not r:
        await update.message.reply_text("📭 سیستم آمار موقتاً در دسترس نیست.")
        return
    try:
        key = f"quizstats:{user_id}"
        data = r.hgetall(key)
        if not data:
            await update.message.reply_text("📭 هنوز هیچ آماری ثبت نشده است.")
            return
        quizzes = data.get("quizzes", 0)
        total_score = data.get("total_score", 0)
        total_q = data.get("total_questions", 0)
        best = data.get("best_percent", "-")
        avg = (int(total_score) / int(total_q) * 100) if int(total_q) else 0
        await update.message.reply_text(
            f"📊 آمار شما:\n"
            f"🔢 تعداد آزمون‌ها: {quizzes}\n"
            f"⭐ میانگین امتیاز: {avg:.1f}%\n"
            f"🏆 بهترین درصد: {best}\n"
            f"📝 کل سوالات پاسخ‌داده‌شده: {total_q}"
        )
    except:
        await update.message.reply_text("خطا در دریافت آمار.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_quiz:
        quiz = user_quiz.pop(user_id)
        if quiz["job"]:
            quiz["job"].schedule_removal()
        await update.message.reply_text("🛑 آزمون لغو شد.")
    else:
        await update.message.reply_text("آزمونی در جریان نیست.")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(level_selection, pattern="^level:"))
    app.add_handler(CallbackQueryHandler(answer_handler, pattern="^ans:"))
    use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"
    if use_webhook:
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
        app.run_webhook(listen="0.0.0.0", port=PORT,
                        webhook_url=WEBHOOK_URL, drop_pending_updates=True)
    else:
        print("Running polling...")
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
