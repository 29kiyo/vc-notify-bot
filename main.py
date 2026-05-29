import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import json
import os
import time

# =========================
# TOKEN
# =========================

TOKEN = os.getenv("TOKEN")

# =========================
# Flask (Render用)
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# =========================
# Discord Intents
# =========================

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.guilds = True

# =========================
# Bot
# =========================

bot = commands.Bot(
    command_prefix=None,
    intents=intents
)

# =========================
# 設定ファイル
# =========================

SETTINGS_FILE = "notify_settings.json"

# =========================
# 設定読み込み
# =========================

def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return {}

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# =========================
# 設定保存
# =========================

def save_settings(data):

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

notify_settings = load_settings()

# =========================
# 通知設定取得
# =========================

def is_notify_enabled(user_id: int):
    return notify_settings.get(str(user_id), True)

# =========================
# 連続通知防止
# =========================

last_notify = {}

# 秒
COOLDOWN = 300

# =========================
# VC参加監視
# =========================

@bot.event
async def on_voice_state_update(member, before, after):

    # Bot除外
    if member.bot:
        return

    # VC変更なし
    if before.channel == after.channel:
        return

    # VC退出は無視
    if after.channel is None:
        return

    # =========================
    # クールダウン
    # =========================

    now = time.time()

    last_time = last_notify.get(member.id, 0)

    if now - last_time < COOLDOWN:
        return

    last_notify[member.id] = now

    vc = after.channel
    guild = member.guild

    mention_targets = []

    # =========================
    # メンション対象検索
    # =========================

    for m in guild.members:

        # Bot除外
        if m.bot:
            continue

        # 同じVC参加者除外
        if m.voice and m.voice.channel == vc:
            continue

        # 通知OFF除外
        if not is_notify_enabled(m.id):
            continue

        mention_targets.append(m.mention)

    # 対象なし
    if not mention_targets:
        return

    text = (
        f"{member.display_name} が "
        f"🎤 {vc.name} に参加しました！\n"
        + " ".join(mention_targets)
    )

    # =========================
    # 送信チャンネル検索
    # =========================

    send_channel = None

    for channel in guild.text_channels:

        permissions = channel.permissions_for(guild.me)

        if permissions.send_messages:
            send_channel = channel
            break

    # =========================
    # メッセージ送信
    # =========================

    if send_channel:
        await send_channel.send(text)

# =========================
# /notify
# =========================

@bot.tree.command(
    name="notify",
    description="通知設定を変更"
)
@app_commands.describe(
    mode="on または off"
)
async def notify(
    interaction: discord.Interaction,
    mode: str
):

    mode = mode.lower()

    if mode not in ["on", "off"]:

        await interaction.response.send_message(
            "on または off を指定してください",
            ephemeral=True
        )
        return

    notify_settings[str(interaction.user.id)] = (mode == "on")

    save_settings(notify_settings)

    await interaction.response.send_message(
        f"通知設定を {mode} にしました",
        ephemeral=True
    )

# =========================
# 起動時
# =========================

@bot.event
async def on_ready():

    await bot.tree.sync()

    print("------------------")
    print(f"ログイン: {bot.user}")
    print("Bot起動完了")
    print("------------------")

# =========================
# 起動
# =========================

keep_alive()
bot.run(TOKEN)
