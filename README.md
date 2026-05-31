# VC Notify Bot

Discord VC参加通知Bot

VC参加時に条件に応じてメンション通知を送信します。

---

## 使用技術

* **Python 3.14**
* **discord.py** (Slash Commands / VCイベント監視)
* **Flask** (Render health check)
* **Supabase**

  * PostgreSQL
  * RLS
  * Edge Functions
* **Render** (Botホスティング)
* **UptimeRobot** (定期Ping / スリープ対策)

---

## システム構成

```txt
Discord
 ↓
Render (Python Bot)
 ├─ discord.py
 ├─ VC参加監視
 └─ 通知判定
 ↓
Supabase
 ├─ user_settings
 ├─ guild_settings
 ├─ notify_targets
 └─ listeners
 ↓
Edge Function (/ping)
 ↓
UptimeRobot
```

---

## 通知仕様

通知には **受信許可 + 送信許可** の両方が必要。

### 受信許可

* notify mode = `all`
* または `/listener-add`

### 送信許可

* notify mode = `all`
* または `/notify-add`

### 通知セッションモード

**strict (デフォルト)**

一度通知されたユーザーは、
VC参加者が全員退出するまで再通知されません。

**once**

通知済みユーザーのみ再通知を防止。
未通知ユーザーは途中参加時でも通知対象になります。

---

## コマンド一覧

### ユーザー設定

| コマンド               | 説明        |
| ------------------ | --------- |
| `/notify`          | 通知 ON/OFF |
| `/notify-mode`     | 通知モード変更   |
| `/notify-add`      | 通知対象追加    |
| `/notify-remove`   | 通知対象削除    |
| `/notify-list`     | 通知対象一覧    |
| `/listener-add`    | 通知先追加     |
| `/listener-remove` | 通知先削除     |
| `/listener-list`   | 通知先一覧     |
| `/help`            | コマンド一覧表示  |

### 管理者設定

| コマンド                   | 説明               |
| ---------------------- | ---------------- |
| `/admin-setchannel`    | 通知チャンネル設定        |
| `/admin-notifymode`    | strict / once 切替 |
| `/admin-defaultnotify` | 新規ユーザー通知初期値変更    |

---

## 環境変数

```env
TOKEN=
SUPABASE_URL=
SUPABASE_KEY=
```
