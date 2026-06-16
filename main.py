import os
import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

BJ_TZ = ZoneInfo("Asia/Shanghai")
DATA_FILE = "data.json"

GROUP_IDS = [
    -1002261583659,
    -1002212346327
]

keyboard = ReplyKeyboardMarkup(
    [
        ["上班/on", "下班/off", "吃饭/meal"],
        ["上厕所/wc", "抽烟/smoke", "其他"],
        ["回坐/back", "统计/report"]
    ],
    resize_keyboard=True
)


def now_time():
    return datetime.now(BJ_TZ)


def date_key(dt):
    return dt.strftime("%Y-%m-%d")


def today_key():
    return date_key(now_time())


def yesterday_key():
    return date_key(now_time() - timedelta(days=1))


def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_name(update):
    user = update.effective_user
    return user.full_name or user.first_name or "用户"


def init_user(data, day, uid, name):
    data.setdefault(day, {})
    data[day].setdefault(uid, {
        "name": name,
        "on": None,
        "off": None,
        "meal": 0,
        "toilet": 0,
        "smoke": 0,
        "other": 0,
        "back": 0,
        "away": None
    })


def find_open_work_day(data, uid):
    """
    找到用户还没下班的上班记录：
    先找今天，再找昨天。
    解决：1号上班，2号下班不能计算的问题。
    """
    for day in [today_key(), yesterday_key()]:
        if day in data and uid in data[day]:
            user_data = data[day][uid]
            if user_data.get("on") and not user_data.get("off"):
                return day
    return None


def fmt_minutes(minutes):
    if minutes < 0:
        minutes = 0
    return f"{minutes // 60}小时{minutes % 60}分钟"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 打卡机器人已启动\n请点击下面按钮操作\n\n发送 /id 获取群ID",
        reply_markup=keyboard
    )


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Chat ID: {update.effective_chat.id}")


async def timeout_notice(context: ContextTypes.DEFAULT_TYPE):
    info = context.job.data
    uid = info["uid"]
    name = info["name"]
    day = info["day"]

    data = load_data()
    away = data.get(day, {}).get(uid, {}).get("away")

    if not away:
        return

    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=f"⚠️ {name} 已超时，请尽快回坐。"
    )


async def go_away(update, context, kind, label, mins):
    data = load_data()
    day = today_key()
    uid = str(update.effective_user.id)
    name = get_name(update)
    now = now_time()

    init_user(data, day, uid, name)

    if data[day][uid].get("away"):
        await update.message.reply_text(
            "❌ 你已经离开中，请先点击 回坐/back",
            reply_markup=keyboard
        )
        return

    data[day][uid]["away"] = {
        "kind": kind,
        "label": label,
        "start": now.isoformat(),
        "mins": mins
    }

    save_data(data)

    for job in context.job_queue.get_jobs_by_name(f"timeout_{uid}"):
        job.schedule_removal()

    context.job_queue.run_once(
        timeout_notice,
        mins * 60,
        chat_id=update.effective_chat.id,
        data={
            "uid": uid,
            "name": name,
            "day": day
        },
        name=f"timeout_{uid}"
    )

    await update.message.reply_text(
        f"✅ {label}已记录\n"
        f"⏱ 规定时间：{mins}分钟\n"
        f"🕒 开始时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=keyboard
    )


async def daily_report(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    day = today_key()

    if day not in data or not data[day]:
        msg = f"📊 每日考勤统计 {day}\n\n暂无数据"
    else:
    msg = f"📊 每日考勤统计 {day}（北京时间）\n\n"

    for user_data in data[day].values():
        on_text = "未打卡"
        off_text = "未打卡"
        work_text = "未计算"
    
        if user_data.get("on"):
            on_dt = datetime.fromisoformat(user_data["on"])
            on_text = on_dt.strftime("%Y-%m-%d %H:%M:%S")
    
            if user_data.get("off"):
                off_dt = datetime.fromisoformat(user_data["off"])
                off_text = off_dt.strftime("%Y-%m-%d %H:%M:%S")
                work_minutes = int((off_dt - on_dt).total_seconds() // 60)
                work_text = fmt_minutes(work_minutes)
    
        msg += (
            f"👤 {user_data.get('name', '用户')}\n"
            f"🕘 上班：{on_text}\n"
            f"🕕 下班：{off_text}\n"
            f"🕒 工时：{work_text}\n"
            f"🍚 吃饭：{user_data.get('meal', 0)}分钟\n"
            f"🚽 厕所：{user_data.get('toilet', 0)}分钟\n"
            f"🚬 抽烟：{user_data.get('smoke', 0)}分钟\n"
            f"📌 其他：{user_data.get('other', 0)}分钟\n"
            f"🔄 回坐：{user_data.get('back', 0)}次\n\n"
        )

    for group_id in GROUP_IDS:
        await context.bot.send_message(chat_id=group_id, text=msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = load_data()
    day = today_key()
    uid = str(update.effective_user.id)
    name = get_name(update)
    now = now_time()

    init_user(data, day, uid, name)

    if text == "上班/on":
        data[day][uid]["name"] = name
        data[day][uid]["on"] = now.isoformat()
        data[day][uid]["off"] = None
        data[day][uid]["away"] = None

        save_data(data)

        await update.message.reply_text(
            f"✅ 上班打卡成功\n"
            f"🕘 上班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=keyboard
        )

    elif text == "下班/off":
        work_day = find_open_work_day(data, uid)

        if not work_day:
            await update.message.reply_text("❌ 请先上班打卡", reply_markup=keyboard)
            return

        user_data = data[work_day][uid]
        on_time = datetime.fromisoformat(user_data["on"])
        total_minutes = int((now - on_time).total_seconds() // 60)

        data[work_day][uid]["off"] = now.isoformat()
        data[work_day][uid]["away"] = None

        for job in context.job_queue.get_jobs_by_name(f"timeout_{uid}"):
            job.schedule_removal()

        save_data(data)

        await update.message.reply_text(
            f"✅ 下班打卡成功\n"
            f"🕘 上班时间：{on_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🕕 下班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🕒 本次工时：{fmt_minutes(total_minutes)}",
            reply_markup=keyboard
        )

    elif text == "吃饭/meal":
        await go_away(update, context, "meal", "吃饭", 30)

    elif text == "上厕所/wc":
        await go_away(update, context, "toilet", "上厕所", 10)

    elif text == "抽烟/smoke":
        await go_away(update, context, "smoke", "抽烟", 10)

    elif text == "其他":
        await go_away(update, context, "other", "其他", 10)

    elif text == "回坐/back":
        away_day = today_key()

        if day in data and uid in data[day] and data[day][uid].get("away"):
            away_day = day
        elif yesterday_key() in data and uid in data[yesterday_key()] and data[yesterday_key()][uid].get("away"):
            away_day = yesterday_key()

        init_user(data, away_day, uid, name)

        away = data[away_day][uid].get("away")
        data[away_day][uid]["back"] += 1

        for job in context.job_queue.get_jobs_by_name(f"timeout_{uid}"):
            job.schedule_removal()

        if not away:
            save_data(data)
            await update.message.reply_text(
                f"✅ 回坐成功\n"
                f"🕒 回坐时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=keyboard
            )
            return

        start = datetime.fromisoformat(away["start"])
        actual_minutes = int((now - start).total_seconds() // 60)
        allowed = away.get("mins", 0)
        kind = away.get("kind")if kind in ["meal", "toilet", "smoke", "other"]:
            data[away_day][uid][kind] += actual_minutes

        data[away_day][uid]["away"] = None
        save_data(data)

        result = "✅ 准时回坐" if actual_minutes <= allowed else f"⚠️ 超时 {actual_minutes - allowed} 分钟"

        await update.message.reply_text(
            f"{result}\n"
            f"📌 类型：{away['label']}\n"
            f"⏱ 规定时间：{allowed}分钟\n"
            f"🕒 实际离开：{actual_minutes}分钟\n"
            f"🕒 回坐时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=keyboard
        )

    elif text == "统计/report":
        report_day = find_open_work_day(data, uid) or today_key()

        if report_day not in data or uid not in data[report_day]:
            init_user(data, report_day, uid, name)

        user_data = data[report_day][uid]

        on_text = "未打卡"
        off_text = "未打卡"
        work_text = "未计算"

        if user_data.get("on"):
            on_dt = datetime.fromisoformat(user_data["on"])
            on_text = on_dt.strftime("%Y-%m-%d %H:%M:%S")

            if user_data.get("off"):
                off_dt = datetime.fromisoformat(user_data["off"])
                off_text = off_dt.strftime("%Y-%m-%d %H:%M:%S")
                work_minutes = int((off_dt - on_dt).total_seconds() // 60)
                work_text = fmt_minutes(work_minutes)
            else:
                work_minutes = int((now - on_dt).total_seconds() // 60)
                work_text = f"进行中，已上班 {fmt_minutes(work_minutes)}"

        await update.message.reply_text(
            f"📊 统计 {report_day}\n\n"
            f"👤 姓名：{user_data.get('name', name)}\n"
            f"🕘 上班：{on_text}\n"
            f"🕕 下班：{off_text}\n"
            f"🕒 工时：{work_text}\n\n"
            f"🍚 吃饭：{user_data.get('meal', 0)}分钟\n"
            f"🚽 厕所：{user_data.get('toilet', 0)}分钟\n"
            f"🚬 抽烟：{user_data.get('smoke', 0)}分钟\n"
            f"📌 其他：{user_data.get('other', 0)}分钟\n"
            f"🔄 回坐：{user_data.get('back', 0)}次",
            reply_markup=keyboard
        )


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("id", get_id))

app.add_handler(
    MessageHandler(
        filters.Regex(
            r"^(上班/on|下班/off|吃饭/meal|上厕所/wc|抽烟/smoke|其他|回坐/back|统计/report)$"
        ),
        handle_message
    )
)

app.job_queue.run_daily(
    daily_report,
    time=time(23, 55, tzinfo=BJ_TZ),
    name="daily_report"
)

print("Bot started OK")

app.run_polling()
