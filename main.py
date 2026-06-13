import os
from datetime import datetime
import pytz  # 记得先 pip install pytz

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
# 显式指定时区，防止服务器在海外导致时间混乱
TIMEZONE = pytz.timezone("Asia/Shanghai")

# 全局内存存储（建议后续升级为数据库）
work_times = {}
records = {}

def get_user_name(update: Update):
    user = update.effective_user
    return user.full_name or user.first_name or "用户"

def get_now():
    return datetime.now(TIMEZONE)

def today_key():
    return get_now().strftime("%Y-%m-%d")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 规范打卡机器人已启动\n\n"
        "/on = 上班打卡\n"
        "/off = 下班打卡\n"
        "/meal 30 = 吃饭30分钟\n"
        "/toilet 10 = 厕所10分钟\n"
        "/smoke 10 = 抽烟10分钟\n"
        "/status = 查看个人状态\n"
        "/report = 查看今日统计\n"
        "/help = 查看命令"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = context.job.data
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔔 {user} 时间到！请回座继续努力工作工作工作~"
    )

async def set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str, emoji: str, default_mins: int):
    user = get_user_name(update)
    user_id = update.effective_user.id
    day = today_key()

    try:
        mins = int(context.args[0]) if context.args else default_mins
    except ValueError:
        await update.message.reply_text("❌ 时间格式错误，例如：/meal 30")
        return

    if mins <= 0:
        await update.message.reply_text("❌ 时间必须大于0分钟")
        return

    records.setdefault(day, {})
    records[day].setdefault(user_id, {"name": user, "meal": 0, "toilet": 0, "smoke": 0, "on": None, "off": None})

    records[day][user_id][name] += mins
    text_names = {"meal": "吃饭", "toilet": "厕所", "smoke": "抽烟"}
    text_name = text_names.get(name, "活动")

    await update.message.reply_text(f"{emoji} {user} 开始 {text_name} {mins} 分钟，冲水/灭烟后请及时回座。")

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=user
    )

async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "meal", "🍚", 30)

async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "toilet", "🚽", 10)

async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "smoke", "🚬", 10)

async def on_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    now = get_now()
    day = today_key()

    # 修复漏洞：防止重复打卡覆盖
    if user_id in work_times:
        recorded_day = work_times[user_id].strftime("%Y-%m-%d")
        if recorded_day == day:
            await update.message.reply_text(f"⚠️ 您今天在 {work_times[user_id].strftime('%H:%M')} 已经打过上班卡了，请勿重复打卡。")
            return
        else:
            # 如果是昨天的卡没下班，先清除昨天的残留
            del work_times[user_id]

    work_times[user_id] = now

    records.setdefault(day, {})
    records[day].setdefault(user_id, {"name": user, "meal": 0, "toilet": 0, "smoke": 0, "on": None, "off": None})
    records[day][user_id]["on"] = now.strftime("%H:%M")

    await update.message.reply_text(f"✅ {user} 上班打卡成功\n🕘 时间：{now.strftime('%H:%M')}")

async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    now = get_now()
    day = today_key()

    if user_id not in work_times:
        await update.message.reply_text("❌ 找不到您的上班打卡记录，请先使用 /on 上班打卡")
        return

    start_time = work_times[user_id]
    
    # 修复漏洞：防止跨天错误计算
    if start_time.strftime("%Y-%m-%d") != day:
        await update.message.reply_text("⚠️ 监测到您昨日未打下班卡。系统已重置状态，请重新使用 /on 开始今日工作。")
        del work_times[user_id]
        return

    duration = now - start_time
    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    records.setdefault(day, {})
    records[day].setdefault(user_id, {"name": user, "meal": 0, "toilet": 0, "smoke": 0, "on": None, "off": None})
    records[day][user_id]["off"] = now.strftime("%H:%M")

    await update.message.reply_text(
        f"✅ {user} 下班打卡成功\n"
        f"🕕 时间：{now.strftime('%H:%M')}\n"
        f"🕒 今日工时：{hours} 小时 {minutes} 分钟"
    )

    del work_times[user_id]

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    day = today_key()

    data = records.get(day, {}).get(user_id)

    if not data:
        await update.message.reply_text("🔍 暂无您今日的打卡及活动记录")
        return

    await update.message.reply_text(
        f"📌 {user} 今日状态 ({day})\n\n"
        f"🛫 上班：{data.get('on') or '未打卡'}\n"
        f"🛬 下班：{data.get('off') or '未打卡'}\n"
        f"🍵 吃饭：{data.get('meal', 0)} 分钟\n"
        f"🧻 厕所：{data.get('toilet', 0)} 分钟\n"
        f"🚬 抽烟：{data.get('smoke', 0)} 分钟"
    )

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = today_key()
    day_records = records.get(day, {})

    if not day_records:
        await update.message.reply_text("📊 暂无今日团队统计数据")
        return

    msg = f"📊 今日团队统计 ({day})\n"
    msg += "—" * 15 + "\n"

    for data in day_records.values():
        msg += (
            f"👤 **{data['name']}**\n"
            f"└ ⏱️ 考勤：{data.get('on') or '未到'} → {data.get('off') or '在摆摊'}\n"
            f"└ 📊 离座：吃饭 {data.get('meal', 0)}m | 厕所 {data.get('toilet', 0)}m | 抽烟 {data.get('smoke', 0)}m\n\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


# 初始化 Bot
app = Application.builder().token(TOKEN).build()

# 注册命令
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("on", on_work))
app.add_handler(CommandHandler("off", off_work))
app.add_handler(CommandHandler("meal", meal))
app.add_handler(CommandHandler("toilet", toilet))
app.add_handler(CommandHandler("smoke", smoke))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("report", report))

if __name__ == "__main__":
    print("🤖 Bot is running with timezone: Asia/Shanghai...")
    app.run_polling()
