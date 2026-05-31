import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks
from flask import Flask
from supabase import create_client
from threading import Thread
import os
import time



# =========================
# TOKEN
# =========================

TOKEN = os.getenv("TOKEN")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("URL =", SUPABASE_URL)
print("KEY EXISTS =", SUPABASE_KEY is not None)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

print("VERSION TEST 988")

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



# =========================
# Supabase DB
# =========================

def load_user(guild_id, user_id):

    res = supabase.table(
        "user_settings"
    ).select("*").eq(
        "guild_id", str(guild_id)
    ).eq(
        "user_id", str(user_id)
    ).execute()

    if res.data:
        return res.data[0]

    default = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "enabled": True,
        "mode": "all",
        "targets": [],
        "listeners": []
    }

    supabase.table(
        "user_settings"
    ).insert(default).execute()

    return default


def save_user(data):

    supabase.table(
        "user_settings"
    ).upsert(data).execute()


def load_channel(guild_id):

    res = supabase.table(
        "guild_settings"
    ).select("*").eq(
        "guild_id", str(guild_id)
    ).execute()

    if not res.data:
        return None

    return res.data[0]["channel_id"]


def save_channel(guild_id, channel_id):

    supabase.table(
        "guild_settings"
    ).upsert({
        "guild_id": str(guild_id),
        "channel_id": channel_id
    }).execute()
    
# =========================
# ユーザーデータ
# =========================

def get_user_data(guild_id, user_id):

    res = (
        supabase
        .table("user_settings")
        .select("*")
        .eq("guild_id", str(guild_id))
        .eq("user_id", str(user_id))
        .execute()
    )

    if res.data:
        return res.data[0]

    default = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "enabled": True,
        "mode": "all"
    }

    supabase.table(
        "user_settings"
    ).insert(default).execute()

    return default

# =========================
# クールダウン
# =========================

last_notify = {}
COOLDOWN = 10

# =========================
# VC通知セッション管理
# =========================

active_sessions = {}
# { guild_id : set(user_id) }

notify_mode = {}
# once = 新規参加者だけ通知
# strict = セッション中は誰も通知しない

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

        guild_id = str(member.guild.id)
    
        remaining = [
            m for m in member.guild.members
            if (
                m.voice
                and m.voice.channel
                and not m.bot
            )
        ]
    
        if not remaining:
    
            print("VC空になったのでセッションリセット")
    
            active_sessions[guild_id] = set()
    
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

    # サーバー初期化

    if guild_id not in active_sessions:
        active_sessions[guild_id] = set()
    
    if guild_id not in notify_mode:
        notify_mode[guild_id] = "strict"

    print(f"guild_id={guild_id}")
    
    res = (
        supabase
        .table("guild_settings")
        .select("*")
        .eq("guild_id", guild_id)
        .execute()
    )
    
    if not res.data:
        print("通知チャンネル未設定")
        return
    
    channel_id = int(
        res.data[0]["channel_id"]
    )
    
    print(f"channel_id={channel_id}")

    send_channel = guild.get_channel(channel_id)

    print(f"send_channel={send_channel}")

    if send_channel is None:
        print("チャンネル取得失敗")
        return

    mention_targets = []

    session = active_sessions[guild_id]
    mode = notify_mode[guild_id]
    
    # 既に通知済みなら処理しない
    
    if member.id in session:
    
        print("既通知ユーザー")
        return
    
    # strictモード
    
    if mode == "strict":
    
        if session:
    
            print("strict: セッション中")
            return
    
    # onceモード
    
    elif mode == "once":
    
        vc_members = [
            m.id
            for m in guild.members
            if (
                m.voice
                and m.voice.channel
                and not m.bot
            )
        ]
    
        already = all(
            uid in session
            for uid in vc_members
        )
    
        if already:
    
            print("once: 全員通知済み")
            return

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
    
        receiver = get_user_data(
            guild.id,
            m.id
        )
    
        if not receiver["enabled"]:
            continue
    
        allow = False
    
        # ---------- sender設定 ----------
        sender_res = (
            supabase.table("user_settings")
            .select("*")
            .eq("guild_id", str(guild.id))
            .eq("user_id", str(member.id))
            .execute()
        )
    
        sender_mode = "all"
    
        if sender_res.data:
            sender_mode = sender_res.data[0]["mode"]
    
        # ---------- notify-add ----------
        notify_res = (
            supabase.table("notify_targets")
            .select("*")
            .eq("guild_id", str(guild.id))
            .eq("owner_id", str(member.id))
            .eq("target_id", str(m.id))
            .execute()
        )
    
        sender_notify = bool(notify_res.data)
    
        # ---------- listener-add ----------
        listener_res = (
            supabase.table("listeners")
            .select("*")
            .eq("guild_id", str(guild.id))
            .eq("owner_id", str(m.id))
            .eq("listener_id", str(member.id))
            .execute()
        )
    
        receiver_listener = bool(listener_res.data)
    
        # ===== receiver = all =====
    
        if receiver["mode"] == "all":
    
            if (
                sender_mode == "all"
                or sender_notify
                or receiver_listener
            ):
                allow = True
    
        # ===== receiver = selected =====
    
        elif receiver["mode"] == "selected":
    
            receiver_ok = receiver_listener
    
            sender_ok = (
                sender_mode == "all"
                or sender_notify
            )
    
            if receiver_ok and sender_ok:
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
    active_sessions[guild_id].add(member.id)
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

        supabase.table(
            "user_settings"
        ).upsert(data).execute()

        users = []

        for target_id in data["targets"]:
        
            target = interaction.guild.get_member(target_id)
        
            if target:
                users.append(target)
        
        embed = discord.Embed(
            title=f"📋 通知対象一覧 ({len(users)}人)"
        )
        
        embed.description = (
            "\n".join(
                f"{i}. {u.display_name}"
                for i, u in enumerate(users, start=1)
            )
            if users
            else "登録されていません"
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=NotifyRemoveView(
                self.owner_id,
                users
            ) if users else None
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

        supabase.table(
            "user_settings"
        ).upsert(data).execute()


        users = []

        for target_id in data["listeners"]:
        
            target = interaction.guild.get_member(target_id)
        
            if target:
                users.append(target)
        
        embed = discord.Embed(
            title=f"📋 通知先一覧 ({len(users)}人)"
        )
        
        embed.description = (
            "\n".join(
                f"{i}. {u.display_name}"
                for i, u in enumerate(users, start=1)
            )
            if users
            else "登録されていません"
        )
        
        await interaction.response.edit_message(
            embed=embed,
            view=ListenerRemoveView(
                self.owner_id,
                users
            ) if users else None
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

    supabase.table(
            "user_settings"
        ).upsert(data).execute()


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

    supabase.table(
            "user_settings"
        ).upsert(data).execute()


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

    if user.id == interaction.user.id:

        await interaction.response.send_message(
            "自分は追加できません",
            ephemeral=True
        )
        return

    res = (
        supabase.table("notify_targets")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("target_id", str(user.id))
        .execute()
    )
    
    if res.data:
    
        await interaction.response.send_message(
            f"{user.mention} は既に登録されています",
            ephemeral=True
        )
        return
    
    supabase.table(
        "notify_targets"
    ).insert({
        "guild_id": str(interaction.guild.id),
        "owner_id": str(interaction.user.id),
        "target_id": str(user.id)
    }).execute()

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

    res = (
        supabase
        .table("notify_targets")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("target_id", str(user.id))
        .execute()
    )

    if not res.data:

        await interaction.response.send_message(
            f"{user.mention} は登録されていません",
            ephemeral=True
        )
        return

    (
        supabase
        .table("notify_targets")
        .delete()
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("target_id", str(user.id))
        .execute()
    )

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

    res = (
        supabase.table("notify_targets")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .execute()
    )
    
    users = []
    users_obj = []
    
    for row in res.data:
    
        uid = int(row["target_id"])
    
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

    if user.id == interaction.user.id:

        await interaction.response.send_message(
            "自分は追加できません",
            ephemeral=True
        )
        return

    res = (
        supabase.table("listeners")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("listener_id", str(user.id))
        .execute()
    )
    
    if res.data:
    
        await interaction.response.send_message(
            f"{user.mention} は既に登録されています",
            ephemeral=True
        )
        return
    
    supabase.table(
        "listeners"
    ).insert({
        "guild_id": str(interaction.guild.id),
        "owner_id": str(interaction.user.id),
        "listener_id": str(user.id)
    }).execute()


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

    res = (
        supabase
        .table("listeners")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("listener_id", str(user.id))
        .execute()
    )

    if not res.data:

        await interaction.response.send_message(
            f"{user.mention} は登録されていません",
            ephemeral=True
        )
        return

    (
        supabase
        .table("listeners")
        .delete()
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .eq("listener_id", str(user.id))
        .execute()
    )

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

    res = (
        supabase.table("listeners")
        .select("*")
        .eq("guild_id", str(interaction.guild.id))
        .eq("owner_id", str(interaction.user.id))
        .execute()
    )
    
    users = []
    users_obj = []
    
    for row in res.data:
    
        uid = int(row["listener_id"])
    
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

        "**通知条件**\n"
        "通知は『受信許可』と『送信許可』の両方が必要\n"
        "受信許可: ALL または /listener-add\n"
        "送信許可: ALL または /notify-add\n\n"

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

    supabase.table(
        "guild_settings"
    ).upsert({
        "guild_id": guild_id,
        "channel_id": str(interaction.channel.id)
    }).execute()

    await interaction.response.send_message(
        f"通知チャンネルを {interaction.channel.mention} に設定しました",
        ephemeral=True
    )

# =========================
# /admin-notifymode
# =========================

@bot.tree.command(
    name="admin-notifymode",
    description="通知モード変更"
)
@checks.has_permissions(administrator=True)

@app_commands.describe(
    mode="once / strict"
)

@app_commands.choices(
    mode=[
        app_commands.Choice(
            name="once (新規参加のみ通知)",
            value="once"
        ),
        app_commands.Choice(
            name="strict (1回だけ通知)",
            value="strict"
        )
    ]
)
async def admin_notifymode(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str]
):

    guild_id = str(interaction.guild.id)

    notify_mode[guild_id] = mode.value

    await interaction.response.send_message(
        f"通知モード: {mode.value}",
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
