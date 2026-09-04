import logging
import asyncio
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from config import *
from database import Database
from generator import EduEmailGenerator

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
generator = EduEmailGenerator()

# ============ HELPER FUNCTION ============

def get_user_id(update: Update) -> int:
    """Safely get user ID from update"""
    if update.effective_user:
        return update.effective_user.id
    elif update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user.id
    raise ValueError("No user found in update")

# ============ USER COMMANDS ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        
        # Get user info from update
        if update.effective_user:
            user = update.effective_user
        elif update.callback_query and update.callback_query.from_user:
            user = update.callback_query.from_user
        else:
            return
        
        db.add_user(user.id, user.username, user.first_name, user.last_name)

        user_data = db.get_user(user_id)
        status = user_data['status'] if user_data else 'pending'

        status_text = {'pending': '⏳ Pending', 'approved': '✅ Approved', 'rejected': '❌ Rejected'}.get(status, '❓ Unknown')

        keyboard = [
            [InlineKeyboardButton("📧 Generate Email", callback_data="generate")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("💰 Balance", callback_data="balance")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]

        message = WELCOME_MESSAGE.format(
            status=status_text,
            count=user_data.get('emails_generated', 0) if user_data else 0
        )

        # ✅ FIX: Check if update.message exists
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in start: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        user_data = db.get_user(user_id)

        # ✅ FIX: Check if update.message exists
        if not user_data:
            if update.message:
                await update.message.reply_text("❌ Use /start first.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Use /start first.")
            return

        if user_data['status'] != 'approved':
            if update.message:
                await update.message.reply_text("⏳ Your account is pending approval.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("⏳ Your account is pending approval.")
            return

        balance = user_data['balance']
        price = float(db.get_setting('price_per_email') or 5)

        if balance < price:
            if update.message:
                await update.message.reply_text(f"❌ Insufficient balance! Need ${price:.2f}, you have ${balance:.2f}")
            elif update.callback_query:
                await update.callback_query.message.reply_text(f"❌ Insufficient balance! Need ${price:.2f}, you have ${balance:.2f}")
            return

        # ✅ FIX: আগে রেসপন্স পাঠান
        if update.message:
            await update.message.reply_text("⏳ Generating .edu email... Please wait 2-5 minutes.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("⏳ Generating .edu email... Please wait 2-5 minutes.")

        # ✅ FIX: ব্যাকগ্রাউন্ড থ্রেডিং
        def background_generation():
            try:
                result = generator.generate()
                if result['status'] == 'success':
                    db.update_balance(user_id, -price)
                    db.add_email(user_id, result['email'], result['password'], result['student_id'])
                    
                    # ✅ FIX: ব্যবহারকারীকে রেসপন্স পাঠান
                    success_message = f"""
✅ **Email Generated Successfully!**

📧 **Email:** `{result['email']}`
🔑 **Password:** `{result['password']}`
🆔 **Student ID:** `{result['student_id']}`

💰 **Price:** ${price:.2f}
💸 **Remaining Balance:** ${balance - price:.2f}

⚠️ **Important:**
- এই ইমেইল এবং পাসওয়ার্ড সংরক্ষণ করুন
- যত তাড়াতাড়ি সম্ভব লগইন করুন
- পাসওয়ার্ড পরিবর্তন করুন
"""
                    
                    # ✅ FIX: context.bot ব্যবহার করুন
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            context.bot.send_message(
                                chat_id=user_id,
                                text=success_message,
                                parse_mode='Markdown'
                            )
                        )
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error sending message to user: {e}")
                else:
                    # ✅ FIX: এরর রেসপন্স পাঠান
                    error_message = f"""
❌ **Email Generation Failed**

❌ **Error:** {result.get('error', 'Unknown error')}

⚠️ **দয়া করে আবার চেষ্টা করুন**
"""
                    
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(
                            context.bot.send_message(
                                chat_id=user_id,
                                text=error_message,
                                parse_mode='Markdown'
                            )
                        )
                        loop.close()
                    except Exception as e:
                        logger.error(f"Error sending error message to user: {e}")
            except Exception as e:
                logger.error(f"Error in background generation: {e}")

        # ✅ FIX: ব্যাকগ্রাউন্ড থ্রেড চালু করুন
        threading.Thread(target=background_generation, daemon=True).start()
        return
    except Exception as e:
        logger.error(f"Error in generate: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        user_data = db.get_user(user_id)
        
        # ✅ FIX: Check if update.message exists
        if not user_data:
            if update.message:
                await update.message.reply_text("❌ Use /start first.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Use /start first.")
            return

        emails = db.get_user_emails(user_id)
        email_list = "\n".join([f"  • `{e['email']}`" for e in emails[:3]])

        message = f"""
📊 **Your Status**
👤 ID: `{user_id}`
🔔 Status: {user_data['status']}
💰 Balance: ${user_data['balance']:.2f}
📧 Emails: {user_data['emails_generated']}

📁 Recent:
{email_list if emails else 'No emails yet'}
"""
        
        # ✅ FIX: Check if update.message exists
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in status_cmd: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        user_data = db.get_user(user_id)
        
        # ✅ FIX: Check if update.message exists
        if not user_data:
            if update.message:
                await update.message.reply_text("❌ Use /start first.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Use /start first.")
            return

        price = float(db.get_setting('price_per_email') or 5)
        
        message = f"""
💰 **Balance**
💵 Balance: ${user_data['balance']:.2f}
💸 Price/Email: ${price:.2f}
📧 Can generate: {int(user_data['balance'] // price)}

📞 Contact @{CONTACT['owner']} to add balance
"""
        
        # ✅ FIX: Check if update.message exists
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in balance_cmd: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

# ============ ADMIN COMMANDS ============

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if get_user_id(update) != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Unauthorized.")
            return
        if not context.args:
            if update.message:
                await update.message.reply_text("❌ Usage: /approve <user_id>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /approve <user_id>")
            return

        target = int(context.args[0])
        if db.update_user_status(target, 'approved'):
            if update.message:
                await update.message.reply_text(f"✅ User {target} approved.")
            elif update.callback_query:
                await update.callback_query.message.reply_text(f"✅ User {target} approved.")
        else:
            if update.message:
                await update.message.reply_text("❌ Failed.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Failed.")
    except Exception as e:
        logger.error(f"Error in approve: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if get_user_id(update) != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Unauthorized.")
            return
        if not context.args:
            if update.message:
                await update.message.reply_text("❌ Usage: /reject <user_id>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /reject <user_id>")
            return

        target = int(context.args[0])
        if db.update_user_status(target, 'rejected'):
            if update.message:
                await update.message.reply_text(f"✅ User {target} rejected.")
            elif update.callback_query:
                await update.callback_query.message.reply_text(f"✅ User {target} rejected.")
        else:
            if update.message:
                await update.message.reply_text("❌ Failed.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Failed.")
    except Exception as e:
        logger.error(f"Error in reject: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if get_user_id(update) != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Unauthorized.")
            return
        if len(context.args) < 2:
            if update.message:
                await update.message.reply_text("❌ Usage: /addbalance <user_id> <amount>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /addbalance <user_id> <amount>")
            return

        target = int(context.args[0])
        amount = float(context.args[1])
        if db.update_balance(target, amount):
            if update.message:
                await update.message.reply_text(f"✅ Added ${amount:.2f} to user {target}.")
            elif update.callback_query:
                await update.callback_query.message.reply_text(f"✅ Added ${amount:.2f} to user {target}.")
        else:
            if update.message:
                await update.message.reply_text("❌ Failed.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Failed.")
    except Exception as e:
        logger.error(f"Error in addbalance: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if get_user_id(update) != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Unauthorized.")
            return

        stats = db.get_statistics()
        
        message = f"""
📊 **Bot Stats**
👥 Total Users: {stats['total_users']}
✅ Approved: {stats['approved_users']}
⏳ Pending: {stats['pending_users']}
📧 Emails Generated: {stats['total_emails']}
💸 Price/Email: ${stats['price_per_email']:.2f}
"""
        
        if update.message:
            await update.message.reply_text(message)
        elif update.callback_query:
            await update.callback_query.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in stats_cmd: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if get_user_id(update) != OWNER_ID:
            if update.message:
                await update.message.reply_text("❌ Unauthorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Unauthorized.")
            return
        if not context.args:
            if update.message:
                await update.message.reply_text("❌ Usage: /broadcast <message>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /broadcast <message>")
            return

        message = " ".join(context.args)
        users = db.get_all_users(status='approved')
        sent = 0
        for user in users:
            try:
                await context.bot.send_message(user['user_id'], f"📢 {message}")
                sent += 1
                await asyncio.sleep(0.5)
            except:
                pass
        if update.message:
            await update.message.reply_text(f"✅ Sent to {sent} users.")
        elif update.callback_query:
            await update.callback_query.message.reply_text(f"✅ Sent to {sent} users.")
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

# ============ CALLBACKS ============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        
        # ✅ FIX: টাইমআউট কমানো
        try:
            await query.answer()
        except Exception as e:
            logger.warning(f"Failed to answer callback query: {e}")
            # উপেক্ষা করুন, চালিয়ে যান

        # ✅ FIX: user_id সংরক্ষণ করুন
        user_id = None
        if query.from_user:
            user_id = query.from_user.id
        
        if query.data == "generate":
            # ✅ FIX: user_id প্যারামিটার হিসেবে পাস করুন
            await generate_with_user_id(update, context, user_id)
        elif query.data == "status":
            await status_cmd(update, context)
        elif query.data == "balance":
            await balance_cmd(update, context)
        elif query.data == "help":
            await query.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")
        # উপেক্ষা করুন, চালিয়ে যান


# ============ MAIN ============

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("generate", generate))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("balance", balance_cmd))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(HELP_MESSAGE, parse_mode='Markdown') if u.message else u.callback_query.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')))

    # Admin commands
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Callback
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot is running...")

    # ==========================================
    # 🚀 FLASK SERVER (WEB SERVICE FIX)
    # ==========================================
    from flask import Flask
    import os

    flask_app = Flask(__name__)

    @flask_app.route('/')
    def home():
        return "Bot is running!"

    def run_flask():
        port = int(os.environ.get('PORT', 8080))
        flask_app.run(host='0.0.0.0', port=port)

    # Flask ko background thread mein chalao
    t = threading.Thread(target=run_flask)
    t.start()
    # ==========================================
    # 🚀 FLASK SERVER (WEB SERVICE FIX) END
    # ==========================================

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
