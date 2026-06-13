from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "机器人已启动！\n\n"
        "/meal 30 = 吃饭30分钟\n"
        "/toilet 10 = 厕所10分钟\n"
        "/smoke 10 = 抽烟10分钟"
    )

async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = context.job.data
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ {user} 的时间已到，请返回岗位。"
    )

async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 30
    await update.message.reply_text(f"🍚 吃饭 {mins} 分钟")
    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )

async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 10
    await update.message.reply_text(f"🚽 厕所 {mins} 分钟")
    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )

async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mins = int(context.args[0]) if context.args else 10
    await update.message.reply_text(f"🚬 抽烟 {mins} 分钟")
    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=update.effective_user.first_name
    )

app = Application.builder().token("TOKEN").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("meal", meal))
app.add_handler(CommandHandler("toilet", toilet))
app.add_handler(CommandHandler("smoke", smoke))

app.run_polling()
