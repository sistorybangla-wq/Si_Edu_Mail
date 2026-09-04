"""
config.py - All configuration variables
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
OWNER_ID = int(os.getenv("OWNER_ID", "123456789"))

# Database
DATABASE_FILE = "users.db"

# Liberty University
LIBERTY_APPLY_URL = "https://apply.liberty.edu"
LIBERTY_CLAIM_URL = "https://apply.liberty.edu/claim-account"
LIBERTY_LOGIN_URL = "https://mylu.liberty.edu"

# Pricing (in USD)
PRICE_PER_EMAIL = 5

# Messages
WELCOME_MESSAGE = """
🎓 **Welcome to EduMail Generator Bot!**

I can generate a real **@liberty.edu** email address for you.
**100% anonymous** - No user data is used or stored.

📌 **How to use:**
1. Send `/generate` to start the process
2. Wait 2-5 minutes for automation
3. Receive your **real .edu email** + password

💰 **Price:** $5 per email
💳 **Payment:** Contact owner

👤 **Your Status:** {status}
📧 **Emails Generated:** {count}

🔒 **Privacy:** No user data is stored or leaked
"""

HELP_MESSAGE = """
📖 **Help Menu**

🔹 `/start` - Start the bot
🔹 `/generate` - Generate .edu email
🔹 `/status` - Check your status
🔹 `/balance` - Check your balance
🔹 `/myemails` - View your emails
🔹 `/help` - Show this menu

👑 **Admin Commands:**
🔹 `/approve <user_id>` - Approve user
🔹 `/reject <user_id>` - Reject user
🔹 `/addbalance <user_id> <amount>` - Add balance
🔹 `/setprice <amount>` - Set price
🔹 `/stats` - Bot statistics
🔹 `/broadcast <message>` - Broadcast
"""

# User Status
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_BANNED = "banned"

# Contact
CONTACT = {
    "owner": "@your_username",
    "upi": "your_upi@upi"
}