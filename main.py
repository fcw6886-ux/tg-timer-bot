import os
import shelve
from datetime import datetime

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")

# 使用 shelve 进行本地持久化存储，Bot 重启数据不丢失
DB_FILE = "bot_data.db"


def get_user_name(update: Update):
    user = update.effective_user
    return user.full_name or user.first_name or "用户"


def today_key():
    return datetime.now().strftime("%Y-%m-%d")


def get_db_data(file_path, key, default):
    """安全读取 shelve 数据"""
    with shelve.open(file_path) as db:
        return db.get(key, default)


def update_db_data(file_path, key, update_func):
    """安全更新 shelve 数据"""
    with shelve.open(file_path, writeback=True) as db:
        data = db.get(key, {})
        update_func(data)
        db[key] = data


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 考勤打卡机器人已启动\n\n"
        "/on - 上班打卡\n"
        "/off - 下班打卡\n"
        "/meal [分钟] - 吃饭（默认30分钟）\n"
        "/toilet [分钟] - 厕所（默认10分钟）\n"
        "/smoke [分钟] - 抽烟（默认10分钟）\n"
        "/status - 查看个人今日状态\n"
        "/report - 查看今日团队统计\n"
        "/help - 查看命令"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def timer_done(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    user = context.job.data
    await context.bot.send_message(
        chat_id=chat_id, text=f"🔔 {user} 时间到！请回座继续搬砖。"
    )


async def set_timer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    name: str,
    emoji: str,
    default_mins: int,
):
    user = get_user_name(update)
    user_id = str(update.effective_user.id)  # shelve 的 key 必须是字符串
    day = today_key()

    try:
        mins = int(context.args[0]) if context.args else default_mins
    except ValueError:
        await update.message.reply_text("❌ 时间格式错误，例如：/meal 30")
        return

    if mins <= 0:
        await update.message.reply_text("❌ 时间必须大于 0 分钟")
        return

    text_names = {"meal": "吃饭", "toilet": "厕所", "smoke": "抽烟"}
    text_name = text_names.get(name, "休息")

    def mutate_records(records):
        day_data = records.setdefault(day, {})
        user_data = day_data.setdefault(
            user_id,
            {
                "name": user,
                "meal": 0,
                "toilet": 0,
                "smoke": 0,
                "on": None,
                "off": None,
            },
        )
        user_data[name] += mins
        user_data["name"] = user  # 顺便更新可能变更的用户名

    update_db_data(DB_FILE, "records", mutate_records)

    await update.message.reply_text(
        f"{emoji} {user} 登记【{text_name}】{mins} 分钟，已开始倒计时。"
    )

    context.job_queue.run_once(
        timer_done, mins * 60, chat_id=update.effective_chat.id, data=user
    )


async def meal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "meal", "🍚", 30)


async def toilet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "toilet", "🚽", 10)


async def smoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_timer(update, context, "smoke", "🚬", 10)


async def on_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = get_user_name(update)
    now = datetime.now()
    day = today_key()

    # 记录上班时间（支持持久化）
    def update_work_times(wt):
        wt[user_id] = now

    update_db_data(DB_FILE, "work_times", update_work_times)

    def update_records(records):
        day_data = records.setdefault(day, {})
        user_data = day_data.setdefault(
            user_id,
            {
                "name": user,
                "meal": 0,
                "toilet": 0,
                "smoke": 0,
                "on": None,
                "off": None,
            },
        )
        user_data["on"] = now.strftime("%H:%M")
        user_data["name"] = user

    update_db_data(DB_FILE, "records", update_records)

    await update.message.reply_text(
        f"✅ {user} 上班打卡成功\n🕘 时间：{now.strftime('%H:%M')}"
    )


async def off_work(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = get_user_name(update)
    now = datetime.now()

    work_times = get_db_data(DB_FILE, "work_times", {})

    if user_id not in work_times:
        await update.message.reply_text("❌ 找不到您的上班打卡记录，请先使用 /on")
        return

    start_time = work_times[user_id]
    duration = now - start_time

    total_minutes = int(duration.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    # 关键修复：下班卡应当记录在【上班打卡】的那天，防止跨天（过午夜）导致数据分裂
    on_day = start_time.strftime("%Y-%m-%d")

    def update_records(records):
        day_data = records.setdefault(on_day, {})
        user_data = day_data.setdefault(
            user_id,
            {
                "name": user,
                "meal": 0,
                "toilet": 0,
                "smoke": 0,
                "on": start_time.strftime("%H:%M"),
                "off": None,
            },
        )
        user_data["off"] = now.strftime("%H:%M")
        user_data["name"] = user

    update_db_data(DB_FILE, "records", update_records)

    # 清除当前上班状态
    def del_work_time(wt):
        if user_id in wt:
            del wt[user_id]

    update_db_data(DB_FILE, "work_times", del_work_time)

    await update.message.reply_text(
        f"✅ {user} 下班打卡成功\n"
        f"🕕 时间：{now.strftime('%H:%M')} (包含跨天)\n"
        f"🕒 本班工时：{hours}小时{minutes}分钟"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = get_user_name(update)
    day = today_key()

    records = get_db_data(DB_FILE, "records", {})
    data = records.get(day, {}).get(user_id)

    if not data:
        await update.message.reply_text(" 暂无今日打卡及摸鱼记录")
        return

    await update.message.reply_text(
        f"📌 {user} 今日状态 ({day})\n\n"
        f" 上班：{data.get('on') or '未打卡'}\n"
        f" 下班：{data.get('off') or '未打卡'}\n"
        f" 吃饭：{data.get('meal', 0)} 分钟\n"
        f" 厕所：{data.get('toilet', 0)} 分钟\n"
        f" 抽烟：{data.get('smoke', 0)} 分钟"
    )


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day = today_key()
    records = get_db_data(DB_FILE, "records", {})
    day_records = records.get(day, {})

    if not day_records:
        await update.message.reply_text(f" 暂无今日团队统计 ({day})")
        return

    msg = f"📊 今日团队考勤统计 {day}\n"
    msg += "—" * 15 + "\n"

    for data in day_records.values():
        msg += (
            f"👤 *{data['name']}*\n"
            f"  └ 上班：`{data.get('on') or '未打卡'}`\n"
            f"  └ 下班：`{data.get('off') or '未打卡'}`\n"
            f"  └ 摸鱼：饭 {data.get('meal', 0)}m | 厕 {data.get('toilet', 0)}m | 烟 {data.get('smoke', 0)}m\n\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


# 初始化 Bot
app = Application.builder().token(TOKEN).build()

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
    if not TOKEN:
        print("❌ 错误: 请先在环境变量中设置 BOT_TOKEN")
    else:
        print("🤖 打卡机器人已在后台平稳运行...")
        app.run_polling()
