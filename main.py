import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
BJ_TZ = ZoneInfo("Asia/Shanghai")
DATA_FILE = "data.json"


def now_time():
    return datetime.now(BJ_TZ)


def today_key():
    return now_time().strftime("%Y-%m-%d")


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_name(update: Update):
    user = update.effective_user
    return user.full_name or user.first_name or "用户"


def init_user(data, day, user_id, name):
    data.setdefault(day, {})
    data[day].setdefault(user_id, {
        "name": name,
        "on": None,
        "off": None,
        "meal": 0,
        "toilet": 0,
        "smoke": 0,
        "back": 0,
        "away": None
    })


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 打卡机器人已启动\n\n"
        "/on = 上班打卡\n"
        "/off = 下班打卡并计算工时\n"
        "/meal 30 = 吃饭30分钟\n"
        "/toilet 10 = 厕所10分钟\n"
        "/smoke 10 = 抽烟10分钟\n"
        "/back = 回座\n"
        "/status = 查看个人状态\n"
        "/report = 今日统计"
    )


async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = context.job.data
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"🔔 {user} 时间到，请回座继续上班。"
    )


async def on_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()
    user_id = str(update.effective_user.id)
    name = get_user_name(update)
    now = now_time()

    init_user(data, day, user_id, name)
    data[day][user_id]["on"] = now.isoformat()
    data[day][user_id]["off"] = None

    save_data(data)

    await update.message.reply_text(
        f"✅ {name} 上班打卡成功\n"
        f"🕘 上班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )


async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()
    user_id = str(update.effective_user.id)
    name = get_user_name(update)
    now = now_time()

    init_user(data, day, user_id, name)

    on_time_str = data[day][user_id].get("on")

    if not on_time_str:
        await update.message.reply_text("❌ 请先使用 /on 上班打卡")
        return

    on_time = datetime.fromisoformat(on_time_str)
    duration = now - on_time

    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    data[day][user_id]["off"] = now.isoformat()
    save_data(data)

    await update.message.reply_text(
        f"✅ {name} 下班打卡成功\n"
        f"🕘 上班时间：{on_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🕕 下班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"🕒 今日工时：{hours}小时{minutes}分钟"
    )


async def set_away(update: Update, context: ContextTypes.DEFAULT_TYPE, kind, emoji, default_mins):
    data = load_data()
    day = today_key()
    user_id = str(update.effective_user.id)
    name = get_user_name(update)
    now = now_time()

    try:
        mins = int(context.args[0]) if context.args else default_mins
    except:
        await update.message.reply_text("❌ 时间格式错误，例如：/meal 30")
        return

    if mins <= 0:
        await update.message.reply_text("❌ 时间必须大于0分钟")
        return

    init_user(data, day, user_id, name)

    names = {
        "meal": "吃饭",
        "toilet": "厕所",
        "smoke": "抽烟"
    }

    data[day][user_id][kind] += mins
    data[day][user_id]["away"] = {
        "kind": kind,
        "name": names[kind],
        "start": now.isoformat()
    }

    save_data(data)

    await update.message.reply_text(
        f"{emoji} {name} {names[kind]} {mins} 分钟，已开始计时。"
    )

    context.job_queue.run_once(
        timer_done,
        mins * 60,
        chat_id=update.effective_chat.id,data=name
    )


async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "meal", "🍚", 30)


async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "toilet", "🚽", 10)


async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_away(update, context, "smoke", "🚬", 10)


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()
    user_id = str(update.effective_user.id)
    name = get_user_name(update)
    now = now_time()

    init_user(data, day, user_id, name)

    away = data[day][user_id].get("away")
    data[day][user_id]["back"] += 1

    if not away:
        save_data(data)
        await update.message.reply_text(f"✅ {name} 已回座。")
        return

    start = datetime.fromisoformat(away["start"])
    total_minutes = int((now - start).total_seconds() // 60)

    data[day][user_id]["away"] = None
    save_data(data)

    await update.message.reply_text(
        f"✅ {name} 已回座\n"
        f"📌 类型：{away['name']}\n"
        f"⏱ 实际离开：{total_minutes}分钟\n"
        f"🕒 回座时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()
    user_id = str(update.effective_user.id)

    if day not in data or user_id not in data[day]:
        await update.message.reply_text("暂无今日记录")
        return

    d = data[day][user_id]

    on_text = "未打卡"
    off_text = "未打卡"

    if d.get("on"):
        on_text = datetime.fromisoformat(d["on"]).strftime("%H:%M:%S")
    if d.get("off"):
        off_text = datetime.fromisoformat(d["off"]).strftime("%H:%M:%S")

    away_text = "无"
    if d.get("away"):
        away_text = d["away"]["name"] + "中"

    await update.message.reply_text(
        f"📌 {d['name']} 今日状态\n\n"
        f"上班：{on_text}\n"
        f"下班：{off_text}\n"
        f"当前离岗：{away_text}\n"
        f"吃饭：{d.get('meal', 0)}分钟\n"
        f"厕所：{d.get('toilet', 0)}分钟\n"
        f"抽烟：{d.get('smoke', 0)}分钟\n"
        f"回座：{d.get('back', 0)}次"
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()

    if day not in data or not data[day]:
        await update.message.reply_text("暂无今日统计")
        return

    msg = f"📊 今日统计 {day}（北京时间）\n\n"

    for d in data[day].values():
        on_text = "未打卡"
        off_text = "未打卡"
        work_text = "未计算"

        if d.get("on"):
            on_dt = datetime.fromisoformat(d["on"])
            on_text = on_dt.strftime("%H:%M:%S")

            if d.get("off"):
                off_dt = datetime.fromisoformat(d["off"])
                off_text = off_dt.strftime("%H:%M:%S")

                mins = int((off_dt - on_dt).total_seconds() // 60)
                work_text = f"{mins // 60}小时{mins % 60}分钟"

        msg += (
            f"👤 {d['name']}\n"
            f"上班：{on_text}\n"
            f"下班：{off_text}\n"
            f"工时：{work_text}\n"
            f"吃饭：{d.get('meal', 0)}分钟｜"
            f"厕所：{d.get('toilet', 0)}分钟｜"
            f"抽烟：{d.get('smoke', 0)}分钟｜"
            f"回座：{d.get('back', 0)}次\n\n"
        )

    await update.message.reply_text(msg)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", start))
app.add_handler(CommandHandler("on", on_work))
app.add_handler(CommandHandler("off", off_work))
app.add_handler(CommandHandler("meal", meal))
app.add_handler(CommandHandler("toilet", toilet))
app.add_handler(CommandHandler("smoke", smoke))
app.add_handler(CommandHandler("back", back))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("report", report))

print("Bot started with Beijing time...")

app.run_polling()
