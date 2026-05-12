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

# متغیرهای محیطی
TOKEN = os.environ.get("BOT_TOKEN")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# سوالات طبقه‌بندی‌شده - می‌توانی بعداً بیشتر اضافه کنی
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

TIMEOUT = 20  # ثانیه

user_quiz = {}

# ... (بقیه کد دقیقاً همان است که در پاسخ قبلی گذاشتم - جهت اختصار اینجا تکرار نمی‌کنم)