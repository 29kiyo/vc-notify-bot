import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import time

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.voice_states = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

SETTINGS_FILE = "notify_settings.json"

# =========================
# 設定読み込み
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
# 通知設定
# =========================

def is_notify_enabled(user_id: int):
    return notify_settings.get(str(user_id), True)

# =========================
# 連続通知防止
# =========================

last_notify = {}

COOLDOWN = 300

# =========================
# VC監視
# =========================

@bot.event
async def on_voice_state_update(member, before, after):

    if member.bot:
        return

    if before.channel == after.channel:
        return

    if after.channel is None:
        return

    now = time.time()

    last_time = last_notify.get(member.id, 0)

    if now - last_time < COOLDOWN:
        return

    last_notify[member.id] = now

    vc = after.channel
    guild = member.guild

    mention_targets = []

    for m in guild.members:

        if m.bot:
            continue

        if m.voice and m.voice.channel == vc:
            continue

        if not is_notify_enabled(m.id):
            continue

        mention_targets.append(m.mention)

    if not mention_targets:
        return

    text = (
        f"{member.display_name} が "
        f"🎤 {vc.name} に参加しました！\n"
        + " ".join(mention_targets)
    )

    send_channel = None

    for channel in guild.text_channels:

        permissions = channel.permissions_for(guild.me)

        if permissions.send_messages:
            send_channel = channel
            break

    if send_channel:
        await send_channel.send(text)

# =========================
# /notify
# =========================

@bot.tree.command(
    name="notify",
    description="通知設定変更"
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
            "on または off を指定",
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
# 起動
# =========================

@bot.event
async def on_ready():

    await bot.tree.sync()

    print("------------------")
    print(f"ログイン: {bot.user}")
    print("Bot起動完了")
    print("------------------")

bot.run(TOKEN)
