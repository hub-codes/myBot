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

# اتصال به Redis (در صورت وجود)
r = None
if REDIS_URL and (REDIS_URL.startswith("redis://") or REDIS_URL.startswith("rediss://")):
    try:
        r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        print("✅ Connected to Redis")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        r = None
else:
    print("ℹ️ No Redis URL provided, statistics disabled.")

# بانک ۲۰ سوال برای هر سطح
QUESTION_BANK = {
    "beginner": [
        {"question": "خروجی print(2**3) چیست؟", "options": ["6", "8", "9", "5"], "correct": 1},
        {"question": "کدام نوع داده برای اعداد صحیح استفاده می‌شود؟", "options": ["float", "int", "str", "list"], "correct": 1},
        {"question": "برای ایجاد لیست خالی از کدام دستور استفاده می‌شود؟", "options": ["[]", "{}", "()", "<>"], "correct": 0},
        {"question": "تابع len() چه کاری انجام می‌دهد؟", "options": ["طول رشته/لیست را برمی‌گرداند", "بزرگترین عدد را می‌دهد", "عدد را گرد می‌کند", "نوع متغیر را چک می‌کند"], "correct": 0},
        {"question": "کدام گزینه یک کامنت در پایتون است؟", "options": ["// این یک کامنت است", "# این یک کامنت است", "/* این یک کامنت است */", "<!-- این یک کامنت است -->"], "correct": 1},
        {"question": "خروجی print(\"Hello\"[0]) چیست؟", "options": ["H", "e", "l", "o"], "correct": 0},
        {"question": "کدام عملگر برای جمع استفاده می‌شود؟", "options": ["+", "-", "*", "/"], "correct": 0},
        {"question": "تابع print(type(5)) چه چیزی چاپ می‌کند؟", "options": ["<class 'int'>", "<class 'str'>", "<class 'float'>", "5"], "correct": 0},
        {"question": "حلقه for در پایتون روی چه چیزی تکرار می‌کند؟", "options": ["اعداد", "رشته‌ها", "عناصر یک iterable", "اندیس‌ها"], "correct": 2},
        {"question": "علامت مساوی (=) در پایتون چه معنایی دارد؟", "options": ["مقایسه برابری", "تخصیص مقدار", "بررسی نوع", "هیچکدام"], "correct": 1},
        {"question": "خروجی 3 + 2 * 2 چیست؟", "options": ["10", "7", "8", "5"], "correct": 1},
        {"question": "دستور input() چه نوع داده‌ای برمی‌گرداند؟", "options": ["int", "float", "str", "bool"], "correct": 2},
        {"question": "برای حذف فاصله‌های ابتدا و انتهای یک رشته از کدام متد استفاده می‌شود؟", "options": [".strip()", ".trim()", ".clean()", ".remove()"], "correct": 0},
        {"question": "لیست‌ها با چه نمادی تعریف می‌شوند؟", "options": ["()", "[]", "{}", "<>"], "correct": 1},
        {"question": "مقدار True در پایتون چه نوع داده‌ای است؟", "options": ["int", "bool", "str", "NoneType"], "correct": 1},
        {"question": "کدام یک حلقه بی‌نهایت می‌سازد؟", "options": ["while True:", "for i in range(10):", "while False:", "if True:"], "correct": 0},
        {"question": "تابع str(5) چه خروجی دارد؟", "options": ["5", "'5'", "int", "float"], "correct": 1},
        {"question": "برای اضافه کردن آیتم به انتهای لیست از کدام متد استفاده می‌شود؟", "options": [".add()", ".insert()", ".append()", ".extend()"], "correct": 2},
        {"question": "کدام گزینه یک عدد اعشاری (float) است؟", "options": ["5", "5.0", "'5'", "True"], "correct": 1},
        {"question": "خروجی bool([]) چیست؟", "options": ["True", "False", "Error", "None"], "correct": 1},
    ],
    "intermediate": [
        {"question": "خروجی کد زیر چیست؟\n```python\nx = [1,2,3]\ny = x\ny.append(4)\nprint(x)\n```", "options": ["[1,2,3]", "[1,2,3,4]", "[1,2,4]", "Error"], "correct": 1},
        {"question": "کلیدواژه def برای چه کاری استفاده می‌شود؟", "options": ["تعریف متغیر", "تعریف تابع", "تعریف کلاس", "ایجاد حلقه"], "correct": 1},
        {"question": "برای خواندن فایل متنی از کدام تابع استفاده می‌شود؟", "options": ["read()", "write()", "open()", "input()"], "correct": 2},
        {"question": "کدام متد برای اضافه کردن آیتم به انتهای لیست استفاده می‌شود؟", "options": [".add()", ".insert()", ".extend()", ".append()"], "correct": 3},
        {"question": "خروجی type(3.14) چیست؟", "options": ["<class 'int'>", "<class 'float'>", "<class 'str'>", "<class 'complex'>"], "correct": 1},
        {"question": "کدام یک tuple می‌سازد؟", "options": ["(1,2,3)", "[1,2,3]", "{1,2,3}", "<1,2,3>"], "correct": 0},
        {"question": "حلقه for در پایتون چگونه کار می‌کند؟", "options": ["شمارشی", "بر اساس اندیس", "روی عناصر یک iterable", "تا بی‌نهایت"], "correct": 2},
        {"question": "برای ایجاد دیکشنری خالی از چه علامتی استفاده می‌شود؟", "options": ["{}", "[]", "()", "<>"], "correct": 0},
        {"question": "خروجی len([1,2,3,4]) چیست؟", "options": ["3", "4", "5", "1"], "correct": 1},
        {"question": "تابع len در دیکشنری چه چیزی را برمی‌گرداند؟", "options": ["تعداد کلیدها", "تعداد مقادیر", "مجموع کلید و مقدار", "اندیس آخرین عنصر"], "correct": 0},
        {"question": "برای حذف یک کلید از دیکشنری از چه دستوری استفاده می‌شود؟", "options": ["del dict[key]", "dict.remove(key)", "dict.pop(key)", "هر دو گزینه ۱ و ۳"], "correct": 3},
        {"question": "خروجی bool([]) چیست؟", "options": ["True", "False", "Error", "None"], "correct": 1},
        {"question": "متد .split() روی رشته چه کاری انجام می‌دهد؟", "options": ["رشته را به لیست تبدیل می‌کند", "لیست را به رشته تبدیل می‌کند", "فاصله‌ها را حذف می‌کند", "رشته را معکوس می‌کند"], "correct": 0},
        {"question": "برای ایجاد یک کپی از لیست از کدام روش استفاده می‌شود؟", "options": ["list2 = list1", "list2 = list1.copy()", "list2 = copy(list1)", "هر دو گزینه ۲ و ۳"], "correct": 3},
        {"question": "کدام یک برای باز کردن فایل و بستن خودکار آن استفاده می‌شود؟", "options": ["open()", "with open() as f:", "file()", "read()"], "correct": 1},
        {"question": "تابع lambda در پایتون چیست؟", "options": ["یک تابع ناشناس کوچک", "یک ماژول", "یک نوع حلقه", "یک دکوراتور"], "correct": 0},
        {"question": "خروجی list(range(3)) چیست؟", "options": ["[0,1,2]", "[1,2,3]", "[0,1,2,3]", "[3]"], "correct": 0},
        {"question": "کدام عملگر برای مقایسه برابری استفاده می‌شود؟", "options": ["=", "==", "===", "!="], "correct": 1},
        {"question": "برای تبدیل یک عدد به رشته از کدام تابع استفاده می‌شود؟", "options": ["int()", "str()", "float()", "bool()"], "correct": 1},
        {"question": "خروجی 'hello'.upper() چیست؟", "options": ["HELLO", "hello", "Hello", "hELLO"], "correct": 0},
    ],
    "advanced": [
        {"question": "دکوراتور (decorator) در پایتون چیست؟", "options": ["نوعی حلقه", "یک تابع که تابع دیگر را می‌گیرد و توسعه می‌دهد", "ماژول استاندارد", "شیء گرافیکی"], "correct": 1},
        {"question": "کلیدواژه yield چه کاری انجام می‌دهد؟", "options": ["مقدار را برمی‌گرداند و تابع را پایان می‌دهد", "generator می‌سازد", "حلقه را می‌شکند", "لیست برمی‌گرداند"], "correct": 1},
        {"question": "مفهوم GIL در پایتون چیست؟", "options": ["Global Interpreter Lock", "Great Integrated Language", "General Input Library", "Garbage Interpreter Lock"], "correct": 0},
        {"question": "کدام یک یک context manager است؟", "options": ["تابع lambda", "کلاسی با متدهای __enter__ و __exit__", "دستور with", "ماژول os"], "correct": 1},
        {"question": "خروجی کد زیر چیست؟\n```python\nprint(list(map(lambda x: x*2, [1,2,3])))\n```", "options": ["[2,4,6]", "[1,4,9]", "[3,6,9]", "Error"], "correct": 0},
        {"question": "کدام یک برای ارث‌بری چندگانه استفاده می‌شود؟", "options": ["class Child(Base1):", "class Child(Base1, Base2):", "class Child(Base1(Base2)):", "class Child(Base1, Base2, Base3)"], "correct": 1},
        {"question": "متد __str__ در یک کلاس چه وظیفه‌ای دارد؟", "options": ["تبدیل شیء به رشته", "مقایسه دو شیء", "ایجاد شیء جدید", "حذف شیء"], "correct": 0},
        {"question": "کتابخانه asyncio برای چه منظوری استفاده می‌شود؟", "options": ["محاسبات ریاضی", "برنامه‌نویسی ناهمگام", "رابط گرافیکی", "کار با فایل"], "correct": 1},
        {"question": "تفاوت list و tuple چیست؟", "options": ["list تغییرپذیر است و tuple تغییرناپذیر", "list مرتب نیست", "tuple سرعت کمتری دارد", "list از حافظه بیشتری استفاده می‌کند"], "correct": 0},
        {"question": "کدام ماژول برای کار با عبارات با قاعده (regex) استفاده می‌شود؟", "options": ["regex", "re", "reg", "pyre"], "correct": 1},
        {"question": "برای نصب یک کتابخانه خارجی از کدام دستور استفاده می‌شود؟", "options": ["install", "pip install", "add", "library"], "correct": 1},
        {"question": "کدام یک برای ایجاد یک virtual environment استفاده می‌شود؟", "options": ["venv", "virtual", "env", "python -m venv"], "correct": 3},
        {"question": "در مدیریت استثناها، کدام بلاک همیشه اجرا می‌شود؟", "options": ["try", "except", "finally", "else"], "correct": 2},
        {"question": "تابع zip چه کاری انجام می‌دهد؟", "options": ["دو لیست را ادغام می‌کند", "عناصر چند iterable را جفت می‌کند", "فایل‌ها را فشرده می‌کند", "رشته‌ها را ترکیب می‌کند"], "correct": 1},
        {"question": "مفهوم *args در تعریف تابع چیست؟", "options": ["آرگومان‌های کلیدواژه", "تعداد متغیری از آرگومان‌های غیرکلیدواژه", "آرگومان پیش‌فرض", "دکوراتور"], "correct": 1},
        {"question": "کدام یک یک immutable است؟", "options": ["list", "dict", "tuple", "set"], "correct": 2},
        {"question": "برای ایجاد یک set خالی از چه دستوری استفاده می‌شود؟", "options": ["{}", "set()", "[]", "()"], "correct": 1},
        {"question": "متد .get() در دیکشنری چه مزیتی دارد؟", "options": ["سرعت بالاتر", "اگر کلید نباشد، خطا نمی‌دهد", "مقدار را حذف می‌کند", "کلید جدید اضافه می‌کند"], "correct": 1},
        {"question": "کدام یک برای مرتب‌سازی لیست استفاده می‌شود؟", "options": [".sort()", ".order()", ".arrange()", ".sorted()"], "correct": 0},
        {"question": "خروجی bool(0) چیست؟", "options": ["True", "False", "Error", "0"], "correct": 1},
    ]
}

# زمان‌های پاسخگویی بر اساس سطح (ثانیه)
TIMEOUTS = {"beginner": 8, "intermediate": 20, "advanced": 40}

# وضعیت کاربران در حال آزمون
user_quiz = {}

# --- توابع بازی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی انتخاب سطح"""
    keyboard = [
        [InlineKeyboardButton("🟢 مبتدی (۵ سوال، ۸ ثانیه)", callback_data="level:beginner")],
        [InlineKeyboardButton("🟡 متوسط (۷ سوال، ۲۰ ثانیه)", callback_data="level:intermediate")],
        [InlineKeyboardButton("🔴 پیشرفته (۱۰ سوال، ۴۰ ثانیه)", callback_data="level:advanced")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📚 به آزمون پایتون خوش آمدید!\nلطفاً سطح خود را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع آزمون با انتخاب سطح"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    level = query.data.split(":")[1]
    first_name = update.effective_user.first_name

    num_questions = {"beginner": 5, "intermediate": 7, "advanced": 10}[level]
    all_questions = QUESTION_BANK[level]
    selected = random.sample(all_questions, min(num_questions, len(all_questions)))

    user_quiz[user_id] = {
        "level": level,
        "questions": selected,
        "current_index": 0,
        "score": 0,
        "first_name": first_name,
        "job": None
    }

    await query.edit_message_text(
        f"✅ {first_name} عزیز، سطح {level} انتخاب شد.\n"
        f"تعداد سوالات: {num_questions}\n"
        f"زمان هر سوال: {TIMEOUTS[level]} ثانیه\n\n"
        "آزمون شروع شد..."
    )
    await asyncio.sleep(1)
    await send_question(update, context, user_id)

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """ارسال سوال جاری با تایمر"""
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

    # تنظیم تایمر متناسب با سطح
    timeout_seconds = TIMEOUTS[data["level"]]
    job = context.job_queue.run_once(
        timeout_handler,
        timeout_seconds,
        chat_id=update.effective_chat.id,
        user_id=user_id,
        data={"question_index": data["current_index"]}
    )
    data["job"] = job

async def timeout_handler(context: ContextTypes.DEFAULT_TYPE):
    """اگر زمان تمام شود"""
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    quiz = user_quiz.get(user_id)
    if not quiz or quiz["current_index"] != job_data["question_index"]:
        return
    # بدون نمایش پیام، مستقیماً به سوال بعد برو
    quiz["current_index"] += 1
    quiz["job"] = None
    if quiz["current_index"] < len(quiz["questions"]):
        await send_next_question(context, user_id, chat_id)
    else:
        await finish_quiz(context, user_id, chat_id)

async def send_next_question(context, user_id, chat_id):
    """ارسال سوال بعدی (برای timeout یا بعد از پاسخ)"""
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

    # تایمر جدید
    job = context.job_queue.run_once(
        timeout_handler,
        TIMEOUTS[quiz["level"]],
        chat_id=chat_id,
        user_id=user_id,
        data={"question_index": quiz["current_index"]}
    )
    quiz["job"] = job

async def answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پاسخ کاربر (بدون نمایش نتیجه)"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    quiz = user_quiz.get(user_id)
    if not quiz:
        await query.edit_message_text("آزمونی در جریان نیست. /start را بزنید.")
        return

    # لغو تایمر
    if quiz["job"]:
        quiz["job"].schedule_removal()
        quiz["job"] = None

    ans_index = int(query.data.split(":")[1])
    q = quiz["questions"][quiz["current_index"]]
    if ans_index == q["correct"]:
        quiz["score"] += 1

    # حذف پیام قبلی و رفتن به سوال بعدی (بدون اعلام درستی)
    await query.message.delete()
    quiz["current_index"] += 1

    if quiz["current_index"] < len(quiz["questions"]):
        await send_next_question(context, user_id, update.effective_chat.id)
    else:
        await finish_quiz(context, user_id, update.effective_chat.id)

async def finish_quiz(context, user_id, chat_id):
    """پایان آزمون و نمایش نتیجه نهایی"""
    quiz = user_quiz.pop(user_id, None)
    if not quiz:
        return

    total = len(quiz["questions"])
    score = quiz["score"]
    level = quiz["level"]
    first_name = quiz.get("first_name", "کاربر")
    percentage = (score / total) * 100

    # ذخیره در Redis (در صورت وجود)
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
    """نمایش آمار کاربر"""
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
    """لغو آزمون"""
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