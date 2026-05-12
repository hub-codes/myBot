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

# تلاش برای اتصال به Redis؛ در صورت شکست، r = None
r = None
if REDIS_URL and (REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        # تست اتصال
        r.ping()
        print("✅ Connected to Redis successfully.")
    except Exception as e:
        print(f"⚠️ Could not connect to Redis: {e}")
        r = None
else:
    print("ℹ️ No valid REDIS_URL provided. Statistics will not be saved.")

QUESTION_BANK = {
    "beginner": [
        {
            "question": "خروجی print(2**3) چیست؟",
            "options": ["6", "8", "9", "5"],
            "correct": 1
        },
        {
            "question": "کدام نوع داده برای اعداد صحیح استفاده می‌شود؟",
            "options": ["float", "int", "str", "list"],
            "correct": 1
        },
        {
            "question": "برای ایجاد لیست خالی از کدام دستور استفاده می‌شود؟",
            "options": ["[]", "{}", "()", "<>"],
            "correct": 0
        },
        {
            "question": "تابع len() چه کاری انجام می‌دهد؟",
            "options": ["طول رشته/لیست را برمی‌گرداند", "بزرگترین عدد را می‌دهد", "عدد را گرد می‌کند", "نوع متغیر را چک می‌کند"],
            "correct": 0
        },
        {
            "question": "کدام گزینه یک کامنت در پایتون است؟",
            "options": ["// این یک کامنت است", "# این یک کامنت است", "/* این یک کامنت است */", "<!-- این یک کامنت است -->"],
            "correct": 1
        },
    ],
    "intermediate": [
        {
            "question": "خروجی کد زیر چیست؟\n```python\nx = [1,2,3]\ny = x\ny.append(4)\nprint(x)\n```",
            "options": ["[1,2,3]", "[1,2,3,4]", "[1,2,4]", "Error"],
            "correct": 1
        },
        {
            "question": "کلیدواژه def برای چه کاری استفاده می‌شود؟",
            "options": ["تعریف متغیر", "تعریف تابع", "تعریف کلاس", "ایجاد حلقه"],
            "correct": 1
        },
        {
            "question": "برای خواندن فایل متنی از کدام تابع استفاده می‌شود؟",
            "options": ["read()", "write()", "open()", "input()"],
            "correct": 2
        },
        {
            "question": "کدام متد برای اضافه کردن آیتم به انتهای لیست استفاده می‌شود؟",
            "options": [".add()", ".insert()", ".extend()", ".append()"],
            "correct": 3
        },
        {
            "question": "خروجی type(3.14) چیست؟",
            "options": ["<class 'int'>", "<class 'float'>", "<class 'str'>", "<class 'complex'>"],
            "correct": 1
        },
        {
            "question": "کدام یک tuple می‌سازد؟",
            "options": ["(1,2,3)", "[1,2,3]", "{1,2,3}", "<1,2,3>"],
            "correct": 0
        },
        {
            "question": "حلقه for در پایتون چگونه کار می‌کند؟",
            "options": ["شمارشی", "بر اساس اندیس", "روی عناصر یک iterable", "تا بی‌نهایت"],
            "correct": 2
        },
    ],
    "advanced": [
        {
            "question": "دکوراتور (decorator) در پایتون چیست؟",
            "options": ["نوعی حلقه", "یک تابع که تابع دیگر را می‌گیرد و توسعه می‌دهد", "ماژول استاندارد", "شیء گرافیکی"],
            "correct": 1
        },
        {
            "question": "کلیدواژه yield چه کاری انجام می‌دهد؟",
            "options": ["مقدار را برمی‌گرداند و تابع را پایان می‌دهد", "generator می‌سازد", "حلقه را می‌شکند", "لیست برمی‌گرداند"],
            "correct": 1
        },
        {
            "question": "مفهوم GIL در پایتون چیست؟",
            "options": ["Global Interpreter Lock", "Great Integrated Language", "General Input Library", "Garbage Interpreter Lock"],
            "correct": 0
        },
        {
            "question": "کدام یک یک context manager است؟",
            "options": ["تابع lambda", "کلاسی با متدهای __enter__ و __exit__", "دستور with", "ماژول os"],
            "correct": 1
        },
        {
            "question": "خروجی کد زیر چیست؟\n```python\nprint(list(map(lambda x: x*2, [1,2,3])))\n```",
            "options": ["[2,4,6]", "[1,4,9]", "[3,6,9]", "Error"],
            "correct": 0
        },
        {
            "question": "کدام یک برای ارث‌بری چندگانه استفاده می‌شود؟",
            "options": ["class Child(Base1):", "class Child(Base1, Base2):", "class Child(Base1(Base2)):", "class Child(Base1, Base2, Base3)"],
            "correct": 1
        },
        {
            "question": "متد __str__ در یک کلاس چه وظیفه‌ای دارد؟",
            "options": ["تبدیل شیء به رشته", "مقایسه دو شیء", "ایجاد شیء جدید", "حذف شیء"],
            "correct": 0
        },
        {
            "question": "کتابخانه asyncio برای چه منظوری استفاده می‌شود؟",
            "options": ["محاسبات ریاضی", "برنامه‌نویسی ناهمگام", "رابط گرافیکی", "کار با فایل"],
            "correct": 1
        },
        {
            "question": "تفاوت list و tuple چیست؟",
            "options": ["list تغییرپذیر است و tuple تغییرناپذیر", "list مرتب نیست", "tuple سرعت کمتری دارد", "list از حافظه بیشتری استفاده می‌کند"],
            "correct": 0
        },
        {
            "question": "کدام ماژول برای کار با عبارات با قاعده (regex) استفاده می‌شود؟",
            "options": ["regex", "re", "reg", "pyre"],
            "correct": 1
        },
    ]
}

TIMEOUT = 20
user_quiz = {}

# --- تابع start (بدون تغییر) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدی (۵ سوال)", callback_data="level:beginner")],
        [InlineKeyboardButton("🟡 متوسط (۷ سوال)", callback_data="level:intermediate")],
        [InlineKeyboardButton("🔴 پیشرفته (۱۰ سوال)", callback_data="level:advanced")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 به آزمون پایتون خوش آمدید!\nلطفاً سطح خود را انتخاب کنید:",
        reply_markup=reply_markup
    )

# --- تابع level_selection (بدون تغییر) ---
async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    level = query.data.split(":")[1]
    await query.edit_message_text(f"✅ سطح {level} انتخاب شد. آزمون شروع می‌شود...")
    num_questions = {"beginner": 5, "intermediate": 7, "advanced": 10}[level]
    all_questions = QUESTION_BANK[level]
    selected = random.sample(all_questions, min(num_questions, len(all_questions)))
    user_quiz[user_id] = {
        "level": level,
        "questions": selected,
        "current_index": 0,
        "score": 0,
        "job": None
    }
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    data = user_quiz.get(user_id)
    if not data or data["current_index"] >= len(data["questions"]):
        return
    q = data["questions"][data["current_index"]]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
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
    # تایمر قبلی را لغو کن
    if data["job"]:
        data["job"].schedule_removal()
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUT,
        chat_id=update.effective_chat.id,
        user_id=user_id,
        data={"question_index": data["current_index"]}
    )
    data["job"] = job

async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] != job_data["question_index"]:
        return
    await context.bot.send_message(chat_id=chat_id, text="⏰ زمان تمام شد! این سوال اشتباه محسوب می‌شود.")
    quiz["current_index"] += 1
    quiz["job"] = None
    if quiz["current_index"] < len(quiz["questions"]):
        await send_next_question(context, user_id, chat_id)
    else:
        await finish_quiz(context, user_id, chat_id)

async def send_next_question(context, user_id, chat_id):
    quiz = user_quiz.get(user_id)
    if not quiz:
        return
    q = quiz["questions"][quiz["current_index"]]
    keyboard = [[InlineKeyboardButton(opt, callback_data=f"ans:{i}")] for i, opt in enumerate(q["options"])]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"❓ سوال {quiz['current_index']+1}/{len(quiz['questions'])}:\n{q['question']}",
        reply_markup=reply_markup
    )
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUT,
        chat_id=chat_id,
        user_id=user_id,
        data={"question_index": quiz["current_index"]}
    )
    quiz["job"] = job

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    quiz = user_quiz.get(user_id)
    if not quiz:
        await query.edit_message_text("آزمونی در جریان نیست. /start را بزنید.")
        return
    if quiz["job"]:
        quiz["job"].schedule_removal()
        quiz["job"] = None
    ans_index = int(query.data.split(":")[1])
    q = quiz["questions"][quiz["current_index"]]
    correct = q["correct"]
    if ans_index == correct:
        quiz["score"] += 1
        await query.edit_message_text(f"✅ درست بود! (+1 امتیاز)\nسوال: {q['question']}")
    else:
        await query.edit_message_text(f"❌ اشتباه بود! گزینه صحیح: {q['options'][correct]}\nسوال: {q['question']}")
    quiz["current_index"] += 1
    await asyncio.sleep(1.5)
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
    percentage = (score / total) * 100

    # ذخیره در Redis فقط در صورت در دسترس بودن
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
            print(f"Redis error in finish_quiz: {e}")

    text = (
        f"🏁 آزمون به پایان رسید!\n"
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
    except Exception as e:
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
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True
        )
    else:
        print("Running polling... (Local test)")
        app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()