import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks
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
# ファイル
# =========================

SETTINGS_FILE = "notify_settings.json"
CHANNELS_FILE = "channels.json"

# =========================
# 通知設定
# =========================

def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return {}

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_settings(data):

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

notify_settings = load_settings()

# =========================
# 通知チャンネル設定
# =========================

def load_channels():

    if not os.path.exists(CHANNELS_FILE):
        return {}

    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_channels(data):

    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

notify_channels = load_channels()

# =========================
# 通知ON/OFF取得
# =========================

def is_notify_enabled(user_id: int):
    return notify_settings.get(str(user_id), True)

# =========================
# 連続通知防止
# =========================

last_notify = {}

COOLDOWN = 300  # 5分

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

    # VC退出無視
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

    # =========================
    # 通知チャンネル取得
    # =========================

    guild_id = str(guild.id)

    channel_id = notify_channels.get(guild_id)

    if not channel_id:
        return

    send_channel = guild.get_channel(channel_id)

    if send_channel is None:
        return

    # =========================
    # メンション対象検索
    # =========================

    mention_targets = []

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

    # =========================
    # 通知文
    # =========================

    text = (
        f"{member.display_name} が "
        f"🎤 {vc.name} に参加しました！\n"
        + " ".join(mention_targets)
    )

    # =========================
    # 送信
    # =========================

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
# /setchannel
# =========================

@bot.tree.command(
    name="setchannel",
    description="通知チャンネルを設定"
)
@checks.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction):

    guild_id = str(interaction.guild.id)

    notify_channels[guild_id] = interaction.channel.id

    save_channels(notify_channels)

    await interaction.response.send_message(
        f"通知チャンネルを {interaction.channel.mention} に設定しました",
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
