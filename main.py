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
# JSON
# =========================

def load_json(path):

    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

notify_settings = load_json(SETTINGS_FILE)
notify_channels = load_json(CHANNELS_FILE)

# =========================
# ユーザーデータ
# =========================

def get_user_data(user_id: int):

    uid = str(user_id)

    if uid not in notify_settings:

        notify_settings[uid] = {
            "enabled": True,
            "mode": "all",
            "targets": [],
            "listeners": []
        }

    return notify_settings[uid]

# =========================
# クールダウン
# =========================

last_notify = {}
COOLDOWN = 300

# =========================
# VC参加監視
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

    guild = member.guild
    vc = after.channel

    guild_id = str(guild.id)

    channel_id = notify_channels.get(guild_id)

    if not channel_id:
        return

    send_channel = guild.get_channel(channel_id)

    if send_channel is None:
        return

    mention_targets = []

    # =========================
    # 通常通知
    # =========================

    for m in guild.members:

        if m.bot:
            continue

        if m.voice and m.voice.channel == vc:
            continue

        settings = get_user_data(m.id)

        if not settings["enabled"]:
            continue

        # 全体通知
        if settings["mode"] == "all":

            if m.mention not in mention_targets:
                mention_targets.append(m.mention)

        # 選択通知
        elif settings["mode"] == "selected":

            if member.id in settings["targets"]:

                if m.mention not in mention_targets:
                    mention_targets.append(m.mention)

    # =========================
    # listener通知
    # =========================

    member_settings = get_user_data(member.id)

    for uid in member_settings["listeners"]:

        target = guild.get_member(uid)

        if not target:
            continue

        if target.bot:
            continue

        if target.voice and target.voice.channel == vc:
            continue

        if target.mention not in mention_targets:
            mention_targets.append(target.mention)

    # =========================
    # 対象なし
    # =========================

    if not mention_targets:
        return

    text = (
        f"{member.display_name} が "
        f"🎤 {vc.name} に参加しました！\n"
        + " ".join(mention_targets)
    )

    await send_channel.send(text)

# =========================
# /notify
# =========================

@bot.tree.command(
    name="notify",
    description="通知ON/OFF"
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

    data = get_user_data(interaction.user.id)

    data["enabled"] = (mode == "on")

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"通知設定を {mode} にしました",
        ephemeral=True
    )

# =========================
# /notify-mode
# =========================

@bot.tree.command(
    name="notify-mode",
    description="通知モード変更"
)
@app_commands.describe(
    mode="all または selected"
)
async def notifymode(
    interaction: discord.Interaction,
    mode: str
):

    mode = mode.lower()

    if mode not in ["all", "selected"]:

        await interaction.response.send_message(
            "all または selected を指定してください",
            ephemeral=True
        )
        return

    data = get_user_data(interaction.user.id)

    data["mode"] = mode

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"通知モードを {mode} にしました",
        ephemeral=True
    )

# =========================
# /notify-add
# =========================

@bot.tree.command(
    name="notify-add",
    description="自分に通知する相手を追加"
)
@app_commands.describe(
    user="通知したいユーザー"
)
async def addnotify(
    interaction: discord.Interaction,
    user: discord.Member
):

    if user.bot:

        await interaction.response.send_message(
            "Botは追加できません",
            ephemeral=True
        )
        return

    data = get_user_data(interaction.user.id)

    if user.id not in data["targets"]:
        data["targets"].append(user.id)

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"{user.mention} を通知対象へ追加しました",
        ephemeral=True
    )

# =========================
# /notify-remove
# =========================

@bot.tree.command(
    name="notify-remove",
    description="通知対象削除"
)
@app_commands.describe(
    user="削除するユーザー"
)
async def removenotify(
    interaction: discord.Interaction,
    user: discord.Member
):

    data = get_user_data(interaction.user.id)

    if user.id in data["targets"]:
        data["targets"].remove(user.id)

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"{user.mention} を通知対象から削除しました",
        ephemeral=True
    )

# =========================
# /notify-list
# =========================

@bot.tree.command(
    name="notify-list",
    description="通知対象一覧"
)
async def notifylist(interaction: discord.Interaction):

    data = get_user_data(interaction.user.id)

    targets = data["targets"]

    if not targets:

        await interaction.response.send_message(
            "通知対象はありません",
            ephemeral=True
        )
        return

    text = []

    for uid in targets:

        user = interaction.guild.get_member(uid)

        if user:
            text.append(user.mention)

    await interaction.response.send_message(
        "通知対象一覧:\n" + "\n".join(text),
        ephemeral=True
    )

# =========================
# /listener-add
# =========================

@bot.tree.command(
    name="listener-add",
    description="自分が参加したとき通知する相手を追加"
)
@app_commands.describe(
    user="通知する相手"
)
async def addlistener(
    interaction: discord.Interaction,
    user: discord.Member
):

    if user.bot:

        await interaction.response.send_message(
            "Botは追加できません",
            ephemeral=True
        )
        return

    data = get_user_data(interaction.user.id)

    if user.id not in data["listeners"]:
        data["listeners"].append(user.id)

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"{user.mention} を通知先へ追加しました",
        ephemeral=True
    )

# =========================
# /listener-remove
# =========================

@bot.tree.command(
    name="listener-remove",
    description="通知先削除"
)
@app_commands.describe(
    user="削除する相手"
)
async def removelistener(
    interaction: discord.Interaction,
    user: discord.Member
):

    data = get_user_data(interaction.user.id)

    if user.id in data["listeners"]:
        data["listeners"].remove(user.id)

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"{user.mention} を通知先から削除しました",
        ephemeral=True
    )

# =========================
# /listener-list
# =========================

@bot.tree.command(
    name="listener-list",
    description="通知先一覧"
)
async def listenerlist(interaction: discord.Interaction):

    data = get_user_data(interaction.user.id)

    listeners = data["listeners"]

    if not listeners:

        await interaction.response.send_message(
            "通知先はありません",
            ephemeral=True
        )
        return

    text = []

    for uid in listeners:

        user = interaction.guild.get_member(uid)

        if user:
            text.append(user.mention)

    await interaction.response.send_message(
        "通知先一覧:\n" + "\n".join(text),
        ephemeral=True
    )

# =========================
# /admin-setchannel
# =========================

@bot.tree.command(
    name="admin-setchannel",
    description="通知チャンネル設定"
)
@checks.has_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction):

    guild_id = str(interaction.guild.id)

    notify_channels[guild_id] = interaction.channel.id

    save_json(CHANNELS_FILE, notify_channels)

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
