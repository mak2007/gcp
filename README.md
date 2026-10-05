# 🤖 Telegram Verification, Queue & Announcement Bot

A complete, production-ready Telegram Bot built with Python, `python-telegram-bot`, and async SQLite (`aiosqlite`).

---

## 🌟 Features Overview

### 1. 📥 User Submission Flow
- **Step-by-step submission**: Asks user for:
  1. **Full Legal Name**
  2. **Email Address**
  3. **Unique Website Code**
- **⚡ Instant Duplicate Email Prevention**:
  - Automatically normalizes and checks if the email is already registered in the database (by this user or any other user).
  - If a duplicate email is found, **rejects immediately** with a clear explanation: *"Only 1 query per email is allowed."*
- **🔢 Real-time Queue Tracking**:
  - Automatically calculates the user's position in line (e.g., if 10 people have submitted before them, the user is shown **Position #11** with **10 submissions ahead** waiting for review).
- **📅 Submission Timestamp**:
  - Stores and displays the exact date and UTC time the user submitted their account.

---

### 2. 🔄 Status Pipeline & Notifications
The bot supports all 4 lifecycle statuses with instant Telegram push notifications sent to the user upon admin actions:

| Status | Trigger | User Notification Message |
| :--- | :--- | :--- |
| **Pending** | User submits form | Enters queue with position number & date. |
| **In Review** | Admin marks *"🔍 In Review"* | *"Your submission status has changed to: In Review! Our team is currently verifying your details."* |
| **Accepted** | Admin clicks *"✅ Accept (Pay)"* | *"status changed to accepted your payment will be made soon"* |
| **Disapproved** | Admin marks *"❌ Disapprove"* | Detailed rejection reason + option to submit an appeal. |
| **Can Resubmit**| Admin marks *"🔄 Can Resubmit"* | Unlocks the submission and prompts user to update their info via *"📝 Submit Information"*. |

---

### 3. 📢 Broadcast Announcements to Everyone
Admins can send global announcements to every single user who has ever started or submitted to the bot:
- **Interactive Broadcast with Preview**:
  - Go to **⚙️ Admin Dashboard** ➔ click **📢 Make Announcement**.
  - Type your message (supports bold, italics, links, and emojis).
  - The bot displays an **interactive preview** and target audience count.
  - Click **🚀 Confirm & Send to All** to dispatch.
- **Quick Command**:
  - Use `/broadcast <Your Announcement Here>` or `/announce <message>`.
- **Safe & Throttled Delivery**:
  - Rate-limited to respect Telegram API limits (up to 25 msgs/sec).
  - Automatically handles blocked users, retries on rate limits, and outputs a delivery summary report (`Sent: X`, `Blocked: Y`).

---

### 4. ⚖️ Appeal System
- If a user's submission is disapproved, they can click **⚖️ Submit Appeal** or use `/appeal`.
- The user provides an explanation or proof.
- An alert is automatically dispatched to the admin group/chat with inline action buttons:
  - `✅ Accept & Approve` (changes status directly to Accepted)
  - `🔄 Allow Resubmit` (changes status to Can Resubmit)
  - `❌ Reject Appeal`

---

### 5. 💬 Support & Admin Inquiries
- Users can access support via **💬 Support** or `/support`.
- Provides the official `@SupportHandle`.
- Users can also type a direct message which is routed straight to the admins.

---

### 6. ⚙️ Admin Dashboard & Control Panel
Admins (configured via `ADMIN_IDS` in `.env`) have access to `/admin` or the **⚙️ Admin Dashboard** button:
- **📊 Live Statistics**: Total submissions, pending queue, in review, accepted, disapproved, and appeals count.
- **⏳ Pending Queue Viewer**: Paginated browsing of submissions with 1-click status transitions.
- **📢 Global Announcements**: Broadcast messages to all registered users.
- **🔎 Instant Search**: Search by email, name, or code using `/search <query>`.
- **📥 CSV Export**: Exports all submissions directly into a `.csv` file sent to admin's Telegram chat.

---

## ☁️ How to Run 24/7

You have two simple ways to keep your bot running 24/7:

### 🌟 Option A: Free Cloud Hosting (Recommended — PC can be OFF!)
Deploying to a free cloud hosting platform keeps your bot running 24/7 even when your personal computer is turned off.

#### Deploy on Render (Free 24/7):
1. Create a free account at [Render.com](https://render.com).
2. Create a new **Background Worker** (or **Web Service**).
3. Connect your GitHub repository containing this bot's files.
4. Set:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. In the **Environment Variables** tab, add:
   - `BOT_TOKEN`: Your bot token from @BotFather
   - `ADMIN_IDS`: Your Telegram ID
   - `SUPPORT_HANDLE`: `@YourSupportAdmin`
6. Click **Deploy**. Your bot will run 24/7 with automatic crash recovery!

#### Deploy on Railway / Koyeb:
The repository includes a ready-to-use `Dockerfile` and `Procfile`. Simply import the repository on Railway or Koyeb, add your environment variables in the dashboard, and deploy.

---

### 💻 Option B: Run 24/7 on Windows (If Keeping PC/VPS On)
A pre-configured watchdog script `run_247.bat` is included:

1. Double-click **`run_247.bat`** (or run `.\run_247.bat` in PowerShell).
2. The script runs the bot continuously and will **automatically restart** it within 5 seconds if it ever encounters a network disconnect or error.

---

## 🚀 Local Setup Guide

### 1. Requirements
- Python 3.10+ (tested on Python 3.13)
- Telegram account

### 2. Obtain Your Bot Token & Admin ID
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Send `/newbot`, choose a name, and copy the **API Token**.
3. To find your Telegram user ID: message [@userinfobot](https://t.me/userinfobot) on Telegram and copy your numerical `Id` (e.g. `123456789`).

### 3. Configure `.env`
Open `.env` in the project folder and fill in your values:

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_IDS=123456789
SUPPORT_HANDLE=@YourSupportAdmin
DB_PATH=bot_database.sqlite
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Start the Bot
```bash
python bot.py
```
Or for 24/7 auto-restarting:
```bash
run_247.bat
```

---

## 🧪 Testing & Verification
You can run the built-in automated test suite anytime:
```bash
python test_bot.py
```
This tests:
- Instant duplicate email rejection (case-insensitive & whitespace trimmed)
- Dynamic queue ordering & positions (#11 queue calculation)
- Status transitions (`Pending` ➔ `In Review` ➔ `Accepted` / `Disapproved` / `Can Resubmit`)
- Appeals dispatch and resolution
- User registration & broadcast announcement targeting
- Admin statistics calculation
