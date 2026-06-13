import os
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

TOKEN = os.getenv("BOT_TOKEN")

work_times = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 打卡机器人已启动\n\n"
        "/on = 上班打卡\n"
        "/off = 下班打卡\n"
        "/meal 30 = 吃饭30分钟\n"
        "/toilet 10 = 厕所10分钟\n"
        "/smoke 10 = 抽烟10分钟"
    )


async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = context.job.data

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔔 {user} 时间到，请回座继续上班。"
    )


async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 30

    await update.message.reply_text(
        f"🍚 吃饭 {mins} 分钟"
    )

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )


async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 10

    await update.message.reply_text(
        f"🚽 厕所 {mins} 分钟"
    )

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )


async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 10

    await update.message.reply_text(
        f"🚬 抽烟 {mins} 分钟"
    )

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )


async def on_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    work_times[user_id] = datetime.now()

    await update.message.reply_text(
        "✅ 上班打卡成功"
    )


async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in work_times:
        await update.message.reply_text(
            "❌ 请先使用 /on 上班打卡"
        )
        return

    start_time = work_times[user_id]
    end_time = datetime.now()

    duration = end_time - start_time

    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    await update.message.reply_text(
        f"✅ 下班打卡成功\n"
        f"🕒 今日工时：{hours}小时{minutes}分钟"
    )

    del work_times[user_id]


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("meal", meal))
app.add_handler(CommandHandler("toilet", toilet))
app.add_handler(CommandHandler("smoke", smoke))
app.add_handler(CommandHandler("on", on_work))
app.add_handler(CommandHandler("off", off_work))

print("Bot started...")

app.run_polling()
