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

print("VERSION TEST 989")

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
    command_prefix="!",
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

def get_user_data(guild_id: int, user_id: int):

    gid = str(guild_id)
    uid = str(user_id)

    if gid not in notify_settings:
        notify_settings[gid] = {}

    if uid not in notify_settings[gid]:

        notify_settings[gid][uid] = {
            "enabled": True,
            "mode": "all",
            "targets": [],
            "listeners": []
        }

    return notify_settings[gid][uid]

# =========================
# クールダウン
# =========================

last_notify = {}
COOLDOWN = 10

# =========================
# VC参加監視
# =========================

@bot.event
async def on_voice_state_update(member, before, after):
    print("VOICE EVENT FIRED", flush=True)

    print("======== VC EVENT ========")
    print(member)
    print(before.channel)
    print(after.channel)

    print(f"VCイベント: {member} | {before.channel} -> {after.channel}")

    if member.bot:
        print("Botなので無視")
        return

    if before.channel == after.channel:
        print("同じVCなので無視")
        return

    if after.channel is None:
        print("退出なので無視")
        return

    print("VC参加検知")

    now = time.time()

    last_time = last_notify.get(member.id, 0)

    if now - last_time < COOLDOWN:
        print("クールダウン中")
        return

    last_notify[member.id] = now

    guild = member.guild
    vc = after.channel

    guild_id = str(guild.id)

    print(f"guild_id={guild_id}")

    channel_id = notify_channels.get(guild_id)

    print(f"channel_id={channel_id}")

    if not channel_id:
        print("通知チャンネル未設定")
        return

    send_channel = guild.get_channel(channel_id)

    print(f"send_channel={send_channel}")

    if send_channel is None:
        print("チャンネル取得失敗")
        return

    mention_targets = []

    # =========================
    # 通常通知
    # =========================
    
    for m in guild.members:
    
        if m.bot:
            continue
    
        if m.id == member.id:
            continue
    
        if m.voice and m.voice.channel == vc:
            continue
    
        settings = get_user_data(
            guild.id,
            m.id
        )
    
        if not settings["enabled"]:
            continue
    
        # 全員通知
        if settings["mode"] == "all":
    
            if m.mention not in mention_targets:
                mention_targets.append(m.mention)
    
        # 選択通知
        elif settings["mode"] == "selected":
    
            allow = False
    
            # notify-add
            if member.id in settings["targets"]:
                allow = True
    
            # listener-add
            member_settings = get_user_data(
                guild.id,
                member.id
            )
    
            if m.id in member_settings["listeners"]:
                allow = True
    
            if allow:
    
                if m.mention not in mention_targets:
                    mention_targets.append(m.mention)

    
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
    
    print("送信対象:", mention_targets)
    print(text)
    
    await send_channel.send(text)
# ============================
# list remove
# ============================
class NotifyRemoveSelect(discord.ui.Select):

    def __init__(self, owner_id, users):

        self.owner_id = owner_id

        options = [
            discord.SelectOption(
                label=user.display_name,
                value=str(user.id)
            )
            for user in users
        ]

        super().__init__(
            placeholder="通知対象を削除",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        data = get_user_data(
            interaction.guild.id,
            self.owner_id
        )

        uid = int(self.values[0])

        if uid in data["targets"]:
            data["targets"].remove(uid)

        save_json(SETTINGS_FILE, notify_settings)

        user = interaction.guild.get_member(uid)

        await interaction.response.send_message(
            f"{user.mention} を通知対象から削除しました",
            ephemeral=True
        )


class NotifyRemoveView(discord.ui.View):

    def __init__(self, owner_id, users):

        super().__init__(timeout=300)

        self.add_item(
            NotifyRemoveSelect(owner_id, users)
        )


class ListenerRemoveSelect(discord.ui.Select):

    def __init__(self, owner_id, users):

        self.owner_id = owner_id

        options = [
            discord.SelectOption(
                label=user.display_name,
                value=str(user.id)
            )
            for user in users
        ]

        super().__init__(
            placeholder="通知先を削除",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        data = get_user_data(
            interaction.guild.id,
            self.owner_id
        )

        uid = int(self.values[0])

        if uid in data["listeners"]:
            data["listeners"].remove(uid)

        save_json(SETTINGS_FILE, notify_settings)

        user = interaction.guild.get_member(uid)

        await interaction.response.send_message(
            f"{user.mention} を通知先から削除しました",
            ephemeral=True
        )


class ListenerRemoveView(discord.ui.View):

    def __init__(self, owner_id, users):

        super().__init__(timeout=300)

        self.add_item(
            ListenerRemoveSelect(owner_id, users)
        )

# =========================
# /notify
# =========================

@bot.tree.command(
    name="notify",
    description="通知ON/OFF"
)
@app_commands.describe(
    mode="通知設定"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="ON", value="on"),
        app_commands.Choice(name="OFF", value="off")
    ]
)
async def notify(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str]
):

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    data["enabled"] = (mode.value == "on")

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"通知設定を {mode.value} にしました",
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
    mode="通知モード"
)
@app_commands.choices(
    mode=[
        app_commands.Choice(name="全員通知", value="all"),
        app_commands.Choice(name="選択通知", value="selected")
    ]
)
async def notify_mode(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str]
):

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    data["mode"] = mode.value

    save_json(SETTINGS_FILE, notify_settings)

    await interaction.response.send_message(
        f"通知モードを {mode.name} にしました",
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    if user.id in data["targets"]:

        await interaction.response.send_message(
            f"{user.mention} は既に登録されています",
            ephemeral=True
        )
        return
    
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    if user.id not in data["targets"]:

        await interaction.response.send_message(
            f"{user.mention} は登録されていません",
            ephemeral=True
        )
        return
    
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    targets = data["targets"]

    users = []
    users_obj = []

    for uid in targets:

        user = interaction.guild.get_member(uid)

        if user:
            users.append(user.display_name)
            users_obj.append(user)

    embed = discord.Embed(
        title=f"📋 通知対象一覧 ({len(users)}人)"
    )

    if users:

        embed.description = "\n".join(
            f"{i}. {name}"
            for i, name in enumerate(users, start=1)
        )

        await interaction.response.send_message(
            embed=embed,
            view=NotifyRemoveView(
                interaction.user.id,
                users_obj
            ),
            ephemeral=True
        )

    else:

        embed.description = "登録されていません"

        await interaction.response.send_message(
            embed=embed,
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    if user.id in data["listeners"]:

        await interaction.response.send_message(
            f"{user.mention} は既に登録されています",
            ephemeral=True
        )
        return
    
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    if user.id not in data["listeners"]:

        await interaction.response.send_message(
            f"{user.mention} は登録されていません",
            ephemeral=True
        )
        return
    
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

    data = get_user_data(
        interaction.guild.id,
        interaction.user.id
    )

    listeners = data["listeners"]

    users = []
    users_obj = []

    for uid in listeners:

        user = interaction.guild.get_member(uid)

        if user:
            users.append(user.display_name)
            users_obj.append(user)

    embed = discord.Embed(
        title=f"📋 通知先一覧 ({len(users)}人)"
    )

    if users:

        embed.description = "\n".join(
            f"{i}. {name}"
            for i, name in enumerate(users, start=1)
        )

        await interaction.response.send_message(
            embed=embed,
            view=ListenerRemoveView(
                interaction.user.id,
                users_obj
            ),
            ephemeral=True
        )

    else:

        embed.description = "登録されていません"

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

# =========================
# /help
# =========================

@bot.tree.command(
    name="help",
    description="コマンド一覧"
)
async def help_command(interaction: discord.Interaction):

    embed = discord.Embed(
        title="📖 VC Notify Bot コマンド一覧"
    )

    embed.description = (
        "**通知設定**\n"
        "/notify → 通知ON/OFF\n"
        "/notify-mode → 通知モード変更\n"
        "/notify-add → 自分に通知する相手を追加\n"
        "/notify-remove → 通知対象削除\n"
        "/notify-list → 通知対象一覧\n\n"

        "**通知先設定**\n"
        "/listener-add → 自分が参加した時の通知先追加\n"
        "/listener-remove → 通知先削除\n"
        "/listener-list → 通知先一覧\n\n"

        "**管理者**\n"
        "/admin-setchannel → 通知チャンネル設定"
    )

    await interaction.response.send_message(
        embed=embed,
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
    try:
        print("READY ENTERED", flush=True)

        synced = await bot.tree.sync()

        print(f"SYNCED={len(synced)}", flush=True)
        print(f"USER={bot.user}", flush=True)

    except Exception as e:
        print("ON_READY_ERROR:", repr(e), flush=True)
# =========================
# 起動
# =========================

keep_alive()
print("MAIN START")
bot.run(TOKEN)
