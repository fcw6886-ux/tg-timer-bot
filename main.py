import os
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

work_times = {}
away_status = {}
records = {}


def now_time():
    return datetime.now()


def today_key():
    return now_time().strftime("%Y-%m-%d")


def get_user_name(update: Update):
    user = update.effective_user
    return user.full_name or user.first_name or "用户"


def init_user_record(day, user_id, user):
    records.setdefault(day, {})
    records[day].setdefault(
        user_id,
        {
            "name": user,
            "on": None,
            "off": None,
            "meal": 0,
            "toilet": 0,
            "smoke": 0,
            "back": 0,
        },
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 打卡机器人已启动\n\n"
        "/on = 上班打卡\n"
        "/off = 下班打卡\n"
        "/meal 30 = 吃饭30分钟\n"
        "/toilet 10 = 厕所10分钟\n"
        "/smoke 10 = 抽烟10分钟\n"
        "/back = 回座\n"
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
        text=f"🔔 {user} 时间到，请回座继续上班。"
    )


async def set_away(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str, emoji: str, default_mins: int):
    user_id = update.effective_user.id
    user = get_user_name(update)
    day = today_key()

    try:
        mins = int(context.args[0]) if context.args else default_mins
    except ValueError:
        await update.message.reply_text("❌ 时间格式错误，例如：/meal 30")
        return

    if mins <= 0:
        await update.message.reply_text("❌ 时间必须大于0分钟")
        return

    names = {
        "meal": "吃饭",
        "toilet": "厕所",
        "smoke": "抽烟",
    }

    init_user_record(day, user_id, user)

    records[day][user_id][kind] += mins
    away_status[user_id] = {
        "kind": kind,
        "name": names[kind],
        "start": now_time(),
        "mins": mins,
    }

    await update.message.reply_text(
        f"{emoji} {user} {names[kind]} {mins} 分钟，已开始计时。"
    )

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=user,
    )


async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "meal", "🍚", 30)


async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "toilet", "🚽", 10)


async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "smoke", "🚬", 10)


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    day = today_key()

    init_user_record(day, user_id, user)
    records[day][user_id]["back"] += 1

    if user_id not in away_status:
        await update.message.reply_text(f"✅ {user} 已回座。")
        return

    info = away_status[user_id]
    duration = now_time() - info["start"]
    total_minutes = int(duration.total_seconds() // 60)

    await update.message.reply_text(
        f"✅ {user} 已回座\n"
        f"📌 类型：{info['name']}\n"
        f"⏱ 实际离开：{total_minutes}分钟"
    )

    del away_status[user_id]


async def on_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    now = now_time()
    day = today_key()

    work_times[user_id] = now
    init_user_record(day, user_id, user)
    records[day][user_id]["on"] = now.strftime("%H:%M")

    await update.message.reply_text(
        f"✅ {user} 上班打卡成功\n"
        f"🕘 时间：{now.strftime('%H:%M')}"
    )


async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.iduser = get_user_name(update)
    now = now_time()
    day = today_key()

    if user_id not in work_times:
        await update.message.reply_text("❌ 请先使用 /on 上班打卡")
        return

    start_time = work_times[user_id]
    duration = now - start_time

    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    init_user_record(day, user_id, user)
    records[day][user_id]["off"] = now.strftime("%H:%M")

    await update.message.reply_text(
        f"✅ {user} 下班打卡成功\n"
        f"🕕 时间：{now.strftime('%H:%M')}\n"
        f"🕒 今日工时：{hours}小时{minutes}分钟"
    )

    del work_times[user_id]


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_name(update)
    day = today_key()

    data = records.get(day, {}).get(user_id)

    if not data:
        await update.message.reply_text("暂无今日记录")
        return

    away = away_status.get(user_id)

    away_text = "无"
    if away:
        away_text = f"{away['name']}中"

    await update.message.reply_text(
        f"📌 {user} 今日状态\n\n"
        f"上班：{data.get('on') or '未打卡'}\n"
        f"下班：{data.get('off') or '未打卡'}\n"
        f"当前离岗：{away_text}\n"
        f"吃饭：{data.get('meal', 0)} 分钟\n"
        f"厕所：{data.get('toilet', 0)} 分钟\n"
        f"抽烟：{data.get('smoke', 0)} 分钟\n"
        f"回座次数：{data.get('back', 0)} 次"
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = today_key()
    day_records = records.get(day, {})

    if not day_records:
        await update.message.reply_text("暂无今日统计")
        return

    msg = f"📊 今日统计 {day}\n\n"

    for data in day_records.values():
        msg += (
            f"👤 {data['name']}\n"
            f"上班：{data.get('on') or '未打卡'}\n"
            f"下班：{data.get('off') or '未打卡'}\n"
            f"吃饭：{data.get('meal', 0)}分钟｜"
            f"厕所：{data.get('toilet', 0)}分钟｜"
            f"抽烟：{data.get('smoke', 0)}分钟｜"
            f"回座：{data.get('back', 0)}次\n\n"
        )

    await update.message.reply_text(msg)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("on", on_work))
app.add_handler(CommandHandler("off", off_work))
app.add_handler(CommandHandler("meal", meal))
app.add_handler(CommandHandler("toilet", toilet))
app.add_handler(CommandHandler("smoke", smoke))
app.add_handler(CommandHandler("back", back))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("report", report))

print("Bot started...")

app.run_polling()
