# VC Notify Bot

Discord VC参加通知Bot

## 使用技術

### Backend

* Python 3.14
* discord.py
* Flask (Render keepalive用)

### Database

* Supabase

  * PostgreSQL
  * user_settings
  * guild_settings
  * listeners
  * notify_targets

### Hosting

* Render

  * Discord Bot本体ホスティング

### Keep Alive / Anti Sleep

* Supabase Edge Functions
* UptimeRobot (5分監視)

7日間アクセス無し停止対策。

---

## 主な機能

### ユーザー設定

* `/notify`
  通知 ON / OFF

* `/notify-mode`
  all / selected

* `/notify-add`
  通知対象追加

* `/notify-remove`
  通知対象削除

* `/listener-add`
  通知先追加

* `/listener-remove`
  通知先削除

---

### 管理者設定

* `/admin-setchannel`
  通知チャンネル設定

* `/admin-notifymode`
  strict / once

* `/admin-defaultnotify` (予定)
  新規ユーザー通知初期値設定

---

## 通知仕様

### strict (デフォルト)

一度通知されたユーザーは、

**VC参加者が全員退出するまで再通知されない。**

### once

通知済みユーザーのみ除外。

新規対象ユーザーは途中参加でも通知される。

---

## 環境変数

```env
TOKEN=
SUPABASE_URL=
SUPABASE_KEY=
```

---

## Deploy

### Render

Start Command

```bash
python main.py
```

### Supabase

必要機能:

* Database
* Edge Functions

### UptimeRobot

監視URL:

```txt
/functions/v1/ping
```
