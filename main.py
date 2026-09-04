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
        
        # ব্যাকগ্রাউন্ড থ্রেড চালু করুন
        threading.Thread(target=background_generation, daemon=True).start()
        
    except Exception as e:
        logger.error(f"Error in generate: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        user_data = db.get_user(user_id)
        
        if not user_data:
            if update.message:
                await update.message.reply_text("❌ Use /start first.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Use /start first.")
            return
        
        status_text = {'pending': '⏳ Pending', 'approved': '✅ Approved', 'rejected': '❌ Rejected'}.get(user_data['status'], '❓ Unknown')
        
        message = f"""
👤 **User Status**

🆔 **ID:** `{user_id}`
🔔 **Status:** {status_text}
📧 **Emails Generated:** `{user_data.get('emails_generated', 0)}`
💰 **Balance:** `${user_data['balance']:.2f}`
        """
        
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in status: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        user_data = db.get_user(user_id)
        
        if not user_data:
            if update.message:
                await update.message.reply_text("❌ Use /start first.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Use /start first.")
            return
        
        message = f"""
💰 **Balance Information**

🆔 **ID:** `{user_id}`
💸 **Current Balance:** `${user_data['balance']:.2f}`
💰 **Price per Email:** `${float(db.get_setting('price_per_email') or 5):.2f}`
        """
        
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in balance: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = """
📚 **Help & Commands**

**User Commands:**
📧 `/generate` - Generate .edu email
📊 `/status` - Check status
💰 `/balance` - Check balance
❓ `/help` - Show help

**Admin Commands:**
✅ `/approve <user_id>` - Approve user
💰 `/addbalance <user_id> <amount>` - Add balance
📊 `/stats` - Show statistics

**Tips:**
- Use /start to register
- Get approved by admin
- Add balance to generate emails
- Save email credentials safely
        """
        
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in help: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

# ============ ADMIN COMMANDS ============
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        
        # Check if admin
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("❌ You are not authorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ You are not authorized.")
            return
        
        # Get user ID from args
        if len(context.args) < 1:
            if update.message:
                await update.message.reply_text("❌ Usage: /approve <user_id>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /approve <user_id>")
            return
        
        target_user_id = int(context.args[0])
        db.update_user_status(target_user_id, 'approved')
        
        if update.message:
            await update.message.reply_text(f"✅ User {target_user_id} approved.")
        elif update.callback_query:
            await update.callback_query.message.reply_text(f"✅ User {target_user_id} approved.")
    
    except Exception as e:
        logger.error(f"Error in approve: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        
        # Check if admin
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("❌ You are not authorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ You are not authorized.")
            return
        
        # Get user ID and amount from args
        if len(context.args) < 2:
            if update.message:
                await update.message.reply_text("❌ Usage: /addbalance <user_id> <amount>")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ Usage: /addbalance <user_id> <amount>")
            return
        
        target_user_id = int(context.args[0])
        amount = float(context.args[1])
        db.update_balance(target_user_id, amount)
        
        if update.message:
            await update.message.reply_text(f"✅ Added ${amount:.2f} to user {target_user_id}.")
        elif update.callback_query:
            await update.callback_query.message.reply_text(f"✅ Added ${amount:.2f} to user {target_user_id}.")
    
    except Exception as e:
        logger.error(f"Error in addbalance: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = get_user_id(update)
        
        # Check if admin
        if user_id != ADMIN_ID:
            if update.message:
                await update.message.reply_text("❌ You are not authorized.")
            elif update.callback_query:
                await update.callback_query.message.reply_text("❌ You are not authorized.")
            return
        
        # Get statistics
        total_users = db.get_total_users()
        total_emails = db.get_total_emails()
        total_balance = db.get_total_balance()
        
        message = f"""
📊 **Statistics**

👥 **Total Users:** `{total_users}`
📧 **Total Emails Generated:** `{total_emails}`
💰 **Total Balance:** `${total_balance:.2f}`
        """
        
        if update.message:
            await update.message.reply_text(message, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.message.reply_text(message, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Error in stats: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

# ============ BUTTON CALLBACK ============
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = get_user_id(update)
        data = query.data
        
        if data == "generate":
            await generate(update, context)
        elif data == "status":
            await status(update, context)
        elif data == "balance":
            await balance(update, context)
        elif data == "help":
            await help_command(update, context)
    
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")
        if update.message:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        elif update.callback_query:
            await update.callback_query.message.reply_text("❌ An error occurred. Please try again.")

# ============ MAIN ============
def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("generate", generate))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("addbalance", addbalance))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
