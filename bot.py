#bot.py
import os
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
load_dotenv()


# توکن از متغیر محیطی خوانده می‌شود
TOKEN = os.environ.get("BOT_TOKEN")

# دیکشنری برای بازی
user_games = {}

# --- handler های بازی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    number = random.randint(1, 100)
    user_games[user_id] = number
    await update.message.reply_text(
        "🎮 به بازی حدس عدد خوش آمدی!\n"
        "من یک عدد بین ۱ تا ۱۰۰ انتخاب کرده‌ام. حدس بزن!"
    )

async def guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_games:
        await update.message.reply_text("❌ بازی شروع نشده، /start را بزن.")
        return
    
    try:
        user_guess = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد صحیح وارد کن!")
        return
    
    target = user_games[user_id]
    if user_guess < target:
        await update.message.reply_text("⬆️ برو بالا")
    elif user_guess > target:
        await update.message.reply_text("⬇️ برو پایین")
    else:
        await update.message.reply_text(f"🎉 آفرین! عدد {target} بود.")
        del user_games[user_id]

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, guess))

    # تشخیص حالت اجرا بر اساس متغیر محیطی USE_WEBHOOK
    use_webhook = os.environ.get("USE_WEBHOOK", "false").lower() == "true"

    if use_webhook:
        PORT = int(os.environ.get("PORT", 8443))
        WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # روی Render این را ست می‌کنی
        print(f"Running webhook on port {PORT}, URL: {WEBHOOK_URL}")
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