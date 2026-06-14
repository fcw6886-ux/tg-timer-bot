import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")
BJ_TZ = ZoneInfo("Asia/Shanghai")
DATA_FILE = "data.json"

keyboard = ReplyKeyboardMarkup(
    [
        ["上班/on", "下班/off", "吃饭/mael"],
        ["上厕所/wc", "抽烟/smoke", "其他"],
        ["回坐"]
    ],
    resize_keyboard=True
)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 打卡机器人已启动\n请点击下面按钮操作",
        reply_markup=keyboard
    )


async def timeout_notice(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    name = context.job.data
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⚠️ {name} 已超时，请尽快回坐。"
    )


async def go_away(update, context, kind, label, mins):
    data = load_data()
    day = today_key()
    uid = str(update.effective_user.id)
    name = get_name(update)
    now = now_time()

    init_user(data, day, uid, name)

    data[day][uid][kind] += mins
    data[day][uid]["away"] = {
        "kind": kind,
        "label": label,
        "start": now.isoformat(),
        "mins": mins
    }

    save_data(data)

    for job in context.job_queue.get_jobs_by_name(uid):
        job.schedule_removal()

    context.job_queue.run_once(
        timeout_notice,
        mins * 60,
        chat_id=update.effective_chat.id,
        data=name,
        name=uid
    )

    await update.message.reply_text(
        f"✅ {label}已记录\n"
        f"⏱ 规定时间：{mins}分钟\n"
        f"🕒 开始时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        reply_markup=keyboard
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    data = load_data()
    day = today_key()
    uid = str(update.effective_user.id)
    name = get_name(update)
    now = now_time()

    init_user(data, day, uid, name)

    if text == "上班":
        data[day][uid]["on"] = now.isoformat()
        data[day][uid]["off"] = None
        save_data(data)

        await update.message.reply_text(
            f"✅ 上班打卡成功\n"
            f"🕘 上班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=keyboard
        )

    elif text == "下班":
        on_time_str = data[day][uid].get("on")

        if not on_time_str:
            await update.message.reply_text("❌ 请先上班打卡", reply_markup=keyboard)
            return

        on_time = datetime.fromisoformat(on_time_str)
        diff = now - on_time
        total_minutes = int(diff.total_seconds() // 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60

        data[day][uid]["off"] = now.isoformat()
        save_data(data)

        await update.message.reply_text(
            f"✅ 下班打卡成功\n"
            f"🕘 上班时间：{on_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🕕 下班时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🕒 今日工时：{hours}小时{minutes}分钟",
            reply_markup=keyboard
        )

    elif text == "吃饭":
        await go_away(update, context, "meal", "吃饭", 30)

    elif text == "上厕所":
        await go_away(update, context, "toilet", "上厕所", 10)

    elif text == "抽烟":await go_away(update, context, "smoke", "抽烟", 10)

    elif text == "其他":
        await go_away(update, context, "other", "其他", 10)

    elif text == "回坐":
        away = data[day][uid].get("away")
        data[day][uid]["back"] += 1

        for job in context.job_queue.get_jobs_by_name(uid):
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

        data[day][uid]["away"] = None
        save_data(data)

        if actual_minutes <= allowed:
            result = "✅ 准时回坐"
        else:
            result = f"⚠️ 超时 {actual_minutes - allowed} 分钟"

        await update.message.reply_text(
            f"{result}\n"
            f"📌 类型：{away['label']}\n"
            f"⏱ 实际离开：{actual_minutes}分钟\n"
            f"🕒 回坐时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=keyboard
        )

    else:
        await update.message.reply_text("请点击下面按钮操作", reply_markup=keyboard)


app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("Bot started with button menu and Beijing time")

app.run_polling()
