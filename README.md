# AI Micro Agent

A smart Telegram bot that acts as your personal assistant. It can set reminders, manage orders between buyers and stores, summarize your emails, and keep track of your notes.

---

## Table of Contents

- [What Does This Bot Do?](#what-does-this-bot-do)
- [Features](#features)
- [How It Works (Architecture)](#how-it-works-architecture)
- [Feature Deep Dive](#feature-deep-dive)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Commands Reference](#commands-reference)
- [Configuration](#configuration)

---

## What Does This Bot Do?

Think of this bot as a smart assistant that lives in your Telegram app. You can:

- **Set reminders** using natural language ("remind me to drink water every 2 hours")
- **Place orders** to registered stores and get notified when they accept or reject
- **Get email summaries** from your Gmail inbox
- **Save quick notes** and export them as PDF

The bot uses AI (Ollama) to understand what you're saying and converts it into scheduled tasks.

---

## Features

### 1. Smart Reminders
- Set reminders using plain English
- Supports: every X seconds/minutes/hours/days/weeks
- Supports: specific times like "every day at 9am"
- Reminders persist even if the bot restarts

### 2. Order Management
- Place orders to registered stores via Telegram
- Stores receive order notifications with Accept/Reject buttons
- Real-time chat between buyer and store
- Order status tracking (pending, accepted, out of stock, skipped)

### 3. Email Summaries
- Link your Gmail account securely
- Get instant email summaries on demand
- Schedule daily or weekly email digests
- AI-powered summarization of email content

### 4. Notes
- Save quick notes with `/note`
- Pin important notes
- View all notes with `/notes`
- Export notes as PDF

### 5. Agenda View
- See your daily overview: reminders + notes in one place

---

## How It Works (Architecture)

Here's a simple explanation of how the different parts work together:

```
                         YOU (Telegram)
                              |
                              v
                    +-------------------+
                    | Telegram Listener |  <-- Listens for your messages
                    +-------------------+
                              |
           +------------------+------------------+
           |                  |                  |
           v                  v                  v
    +-----------+      +------------+     +-----------+
    |  Planner  |      | Scheduler  |     |  Orders   |
    | (AI Brain)|      | (Timer)    |     | (Shop)    |
    +-----------+      +------------+     +-----------+
           |                  |                  |
           +------------------+------------------+
                              |
                              v
                    +-------------------+
                    |   MCP Dispatcher  |  <-- Routes tasks to right tool
                    +-------------------+
                              |
        +----------+----------+----------+----------+
        |          |          |          |          |
        v          v          v          v          v
    +-------+  +-------+  +-------+  +-------+  +------+
    |Message|  |Email  |  |Orders |  | PDF   |  | DB   |
    | Send  |  |Fetch  |  |Handle |  |Export |  |Store |
    +-------+  +-------+  +-------+  +-------+  +------+
```

### Main Components Explained

#### 1. Telegram Listener (`src/telegram_listener.py`)
**What it does:** Constantly checks Telegram for new messages from you.

**How it works:**
- Uses "long polling" - asks Telegram "any new messages?" every few seconds
- When you send a command like `/remind`, it figures out what you want
- Routes your request to the right handler

#### 2. Planner (`src/planner.py`)
**What it does:** The AI brain that understands natural language.

**How it works:**
- Takes your message like "remind me to exercise every morning at 7am"
- Sends it to Ollama (local AI model)
- AI converts it to structured data:
  ```json
  {
    "task_type": "reminder",
    "schedule_rule": "RRULE:FREQ=DAILY;BYHOUR=7;BYMINUTE=0",
    "text": "Exercise"
  }
  ```

#### 3. Scheduler (`src/scheduler.py`)
**What it does:** Runs your reminders at the right time.

**How it works:**
- Uses APScheduler library (like a smart alarm clock)
- Understands two types of schedules:
  - **Interval**: "every 2 hours" → runs repeatedly
  - **Cron**: "at 9am daily" → runs at specific times
- When the time comes, triggers the reminder

#### 4. MCP Dispatcher (`src/mcp.py`)
**What it does:** Routes tasks to the correct tool.

**How it works:**
- Has a map of tool names to functions:
  ```
  "messaging.send_message" → sends a Telegram message
  "email.summary" → fetches and summarizes emails
  "orders.place_order" → places an order to a store
  ```
- When a task runs, MCP looks up the right function and calls it

#### 5. Database (`src/db.py`)
**What it does:** Stores all your data permanently.

**Stores:**
- Users and their chat IDs
- Tasks/reminders with schedules
- Orders and their status
- Notes
- Chat sessions

---

## Feature Deep Dive

### How Reminders Work

```
Step 1: You type "/remind drink water every 2 hours"
            |
Step 2: Bot checks if it can understand the pattern directly
        "every 2 hours" → Yes! Creates RRULE:FREQ=HOURLY;INTERVAL=2
            |
Step 3: If pattern is complex, asks Ollama AI to parse it
            |
Step 4: Creates a task in the database with:
        - What to remind: "drink water"
        - When: every 2 hours
            |
Step 5: Registers with APScheduler
            |
Step 6: Every 2 hours, scheduler triggers:
        → MCP dispatches to messaging tool
        → You get a Telegram message: "drink water"
```

**Schedule Format (RRULE):**
The bot uses iCalendar RRULE format internally:
- `RRULE:FREQ=HOURLY;INTERVAL=2` = every 2 hours
- `RRULE:FREQ=DAILY;BYHOUR=9;BYMINUTE=0` = daily at 9:00 AM
- `RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR` = every Monday, Wednesday, Friday

---

### How Orders Work

```
BUYER                          BOT                           STORE
  |                             |                              |
  |  "/remind order milk        |                              |
  |   from Capital Store"       |                              |
  |-----------------------------→                              |
  |                             |  Looks up store's chat_id   |
  |                             |  from user_registry         |
  |                             |                              |
  |                             |  "New order for milk"        |
  |                             |  [Accept] [Out of Stock]     |
  |                             |-----------------------------→|
  |                             |                              |
  |  "Order sent to store"      |                              |
  |←----------------------------|                              |
  |                             |                              |
  |                             |     Store clicks [Accept]    |
  |                             |←-----------------------------|
  |                             |                              |
  |  "Store accepted your       |  "You accepted the order"   |
  |   order for milk!"          |-----------------------------→|
  |←----------------------------|                              |
```

**Order States:**
1. `pending` - Order placed, waiting for store response
2. `accepted` - Store accepted the order
3. `out_of_stock` - Store marked item unavailable
4. `skipped` - Buyer chose to skip this time

**Chat Feature:**
If store says "out of stock", buyer can start a chat:
- Messages are forwarded between buyer ↔ store
- Use `/endchat` to close the conversation

---

### How Email Summary Works

```
Step 1: You link Gmail once with /link_gmail
        → Opens OAuth flow
        → Saves token to tokens/token_{your_chat_id}.json
            |
Step 2: You request summary with /emailsummary
            |
Step 3: Bot loads your saved OAuth token
            |
Step 4: Fetches last 5 emails from Gmail API
        → Gets: sender, subject, snippet
            |
Step 5: Sends emails to Ollama AI for summarization
        "Summarize these emails briefly..."
            |
Step 6: Sends summary to you on Telegram
```

**Scheduling Email Summaries:**
- `/emailsummary every day at 10am` - Creates a daily scheduled task
- `/emailsummary weekly on Mon at 9am` - Creates a weekly task

---

### How Notes Work

```
/note Buy groceries
    |
    v
Database INSERT:
+----+------------+----------------+---------------------+--------+
| id | user_chat_id| text          | created_at          | pinned |
+----+------------+----------------+---------------------+--------+
| 1  | 123456     | Buy groceries  | 2024-01-15T10:30:00 | 0      |
+----+------------+----------------+---------------------+--------+
    |
    v
"Saved note #1: Buy groceries"
```

**PDF Export:**
- Uses ReportLab library
- Creates A4 PDF with all your notes
- Pinned notes show with a star
- Automatically handles page breaks

---

## Project Structure

```
Ai_Micro_Agent/
│
├── src/
│   ├── config.py              # Environment variables & settings
│   ├── db.py                  # Database operations (SQLite)
│   ├── mcp.py                 # Tool dispatcher (routes tasks to functions)
│   ├── orchestrator.py        # Executes tasks from database
│   ├── planner.py             # AI-powered natural language parsing
│   ├── scheduler.py           # APScheduler for timed tasks
│   ├── telegram_listener.py   # Main bot loop & command handlers
│   ├── utils.py               # Helper functions
│   │
│   └── tools/                 # Individual feature modules
│       ├── messaging.py       # Send Telegram messages
│       ├── orders.py          # Order management logic
│       ├── email_summary.py   # Email summarization with AI
│       ├── gmail_oauth.py     # Gmail authentication & fetching
│       ├── pdf_export.py      # Generate PDF from notes
│       ├── calendar_tool.py   # Calendar events (stub)
│       └── payments.py        # Payment links (stub)
│
├── migrations/
│   └── init_db.sql            # Database schema
│
├── tokens/                    # Gmail OAuth tokens (per user)
│
├── run_service.py             # Start the scheduler service
├── run_planner.py             # Test natural language parsing
├── admin_cli.py               # Admin utilities
├── show_db.py                 # View database contents
├── init_db.py                 # Initialize fresh database
│
├── requirements.txt           # Python dependencies
└── .env                       # Environment variables (create this)
```

---

## Setup & Installation

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd Ai_Micro_Agent
```

### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Create Environment File
Create a `.env` file in the project root:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_default_chat_id

OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

DATABASE_URL=sqlite:///ai_agent.db

TIMEZONE=Asia/Kolkata

# Optional: Gmail (for email features)
# Place credentials.json from Google Cloud Console in project root
```

### 5. Set Up Ollama (for AI features)
```bash
# Install Ollama from https://ollama.ai
ollama pull llama3.2
ollama serve
```

### 6. Initialize Database
```bash
python init_db.py
```

### 7. Run the Bot
```bash
python src/telegram_listener.py
```

---

## Commands Reference

### Reminders
| Command | Description | Example |
|---------|-------------|---------|
| `/remind <text>` | Create a reminder | `/remind drink water every 2 hours` |
| `/list_reminders` | Show all active reminders | `/list_reminders` |
| `/delete_reminder <id>` | Delete a reminder | `/delete_reminder 5` |

### Orders
| Command | Description | Example |
|---------|-------------|---------|
| `/remind order <item> from <store>` | Place immediate order | `/remind order milk from Capital Store` |
| `/remind order <item> in 2 hours from <store>` | Delayed order | `/remind order bread in 2 hours from Bakery` |
| `/remind order <item> every 2 days from <store>` | Recurring order | `/remind order milk every 2 days from Dairy Store` |
| `/endchat` | End buyer-store chat | `/endchat` |

### Notes
| Command | Description | Example |
|---------|-------------|---------|
| `/note <text>` | Save a note | `/note Buy groceries tomorrow` |
| `/notes` | List all notes | `/notes` |
| `/pin_note <id>` | Pin a note | `/pin_note 3` |
| `/unpin_note <id>` | Unpin a note | `/unpin_note 3` |
| `/delete_note <id>` | Delete a note | `/delete_note 2` |
| `/export_notes` | Download notes as PDF | `/export_notes` |

### Email
| Command | Description | Example |
|---------|-------------|---------|
| `/link_gmail` | Connect your Gmail | `/link_gmail` |
| `/emailsummary` | Get email summary now | `/emailsummary` |
| `/emailsummary <n>` | Get last N emails | `/emailsummary 10` |
| `/emailsummary every day at 10am` | Schedule daily digest | `/emailsummary every day at 10am` |
| `/disconnect_gmail` | Unlink Gmail | `/disconnect_gmail` |
| `/check_gmail` | Check if Gmail is linked | `/check_gmail` |

### Utility
| Command | Description |
|---------|-------------|
| `/start` | Welcome message & help |
| `/manual` | Show full user guide |
| `/whoami` | Show your profile info |
| `/status` | System status |
| `/agenda` | Today's reminders + notes |
| `/list_jobs` | Show scheduled jobs |
| `/systemcheck` | Run system diagnostics |

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Get from @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | Yes | Your Telegram user ID |
| `OLLAMA_URL` | Yes | Ollama server URL (default: http://localhost:11434) |
| `OLLAMA_MODEL` | Yes | Model name (e.g., llama3.2, mistral) |
| `DATABASE_URL` | Yes | SQLite path (e.g., sqlite:///ai_agent.db) |
| `TIMEZONE` | No | Your timezone (default: Asia/Kolkata) |

### Gmail Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable Gmail API
4. Create OAuth 2.0 credentials (Desktop App)
5. Download `credentials.json` and place in project root
6. Use `/link_gmail` command to authenticate

---

## Database Schema

```sql
-- Users
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    name TEXT,
    chat_id TEXT UNIQUE,
    timezone TEXT DEFAULT 'Asia/Kolkata'
);

-- Tasks/Reminders
CREATE TABLE task (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    type TEXT,
    params_json TEXT,      -- MCP execution plan
    schedule_rule TEXT,    -- RRULE string
    enabled INTEGER DEFAULT 1
);

-- Orders
CREATE TABLE order_status (
    id INTEGER PRIMARY KEY,
    buyer_chat_id TEXT,
    store_chat_id TEXT,
    store_name TEXT,
    item TEXT,
    status TEXT,           -- pending/accepted/out_of_stock/skipped
    created_at TEXT,
    updated_at TEXT
);

-- Notes
CREATE TABLE note (
    id INTEGER PRIMARY KEY,
    user_chat_id TEXT,
    text TEXT,
    created_at TEXT,
    pinned INTEGER DEFAULT 0
);

-- User Registry (for store lookup)
CREATE TABLE user_registry (
    id INTEGER PRIMARY KEY,
    chat_id TEXT UNIQUE,
    name TEXT,
    username TEXT,
    last_seen TEXT
);
```

---

## Technologies Used

| Component | Technology | Why |
|-----------|------------|-----|
| Bot Platform | Telegram Bot API | Free, reliable, great mobile experience |
| AI/NLP | Ollama (local LLM) | Privacy-focused, no API costs |
| Scheduling | APScheduler | Reliable, supports cron & intervals |
| Database | SQLite | Simple, no setup needed, portable |
| Email | Gmail API + OAuth 2.0 | Secure access to user emails |
| PDF | ReportLab | Simple PDF generation |
| HTTP | aiohttp + requests | Async & sync HTTP support |

---

## Troubleshooting

### Bot not responding?
- Check if `TELEGRAM_BOT_TOKEN` is correct
- Ensure the bot is running: `python src/telegram_listener.py`

### Reminders not working?
- Check if scheduler is running: `/list_jobs`
- Verify task is enabled: `/list_reminders`

### Gmail errors?
- Re-link with `/link_gmail`
- Check if `credentials.json` exists
- Ensure Gmail API is enabled in Google Cloud Console

### Ollama errors?
- Make sure Ollama is running: `ollama serve`
- Check if model is downloaded: `ollama list`

---

## License

MIT License - feel free to use and modify!

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

Built with Python and Telegram Bot API
