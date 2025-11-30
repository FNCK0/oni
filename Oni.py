import asyncio
import random
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
import httpx
import json
import os

TELEGRAM_TOKEN = "8293382217:AAFwjIRahF_gS0D-7fyYnPTH1sDbcn6ly98"
DEEPSEEK_API_KEY = "sk-079a1a46f4d0489c9bf77af67bcc7b7c"
ADMIN_ID = 8142795333

MEMORY_DURATION = 120
MAX_MEMORY_MESSAGES = 5
RANDOM_MESSAGE_INTERVAL = 600
PERMISSION_FILE = "group_permissions.json"

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)
logger.disabled = True

ONI_SYSTEM_PROMPT = """You are Oni (ওনি) A Girl — a mischievous, witty, playful, naturally savage roasting bot.

CORE PERSONALITY:
- You ALWAYS give funny, smart, savage-but-light roasts.
- You tease like a close friend: brutally honest but never hurtful.
- Your goal: make them LAUGH instantly with a short, sharp roast.

LANGUAGE RULE:
- ALWAYS reply in the SAME language the user used.
- PRIORITIZE Bengali language slightly more (use Bengali words/phrases when mixing)


ROASTING STYLE:
- SHORT (1–2 lines MAX)
- SAVAGE but LIGHT
- FUNNY, CLEVER, UNPREDICTABLE
- Never generic, never repetitive.
- Don’t insult deeply — only playful, harmless savagery.
- Roast their vibe, attitude, situation — NEVER spelling or grammar.

ROASTING TECHNIQUES:
- Dramatic exaggeration
- Playful mockery
- Confusion humor
- Deadpan savagery
- Chaos commentary
- Unexpected punchlines

EMOJI RULE:
- Use emojis creatively but not too many.
- Add extra punch with 😈🔥💀🤡 etc. when fitting.

SPECIAL RULE:
Never say "I’m roasting you" or mention you're a roast bot.  
Just roast silently, confidently, like a chaotic friend.

MAKE EVERY REPLY:
- Savage
- Light-hearted
- Funny
- Fresh
- Creative
- Short
"""

RANDOM_MESSAGES = [
    "Group dead? 💀", "Everyone sleeping? 😴", "Waiting for chaos 🔥", "Bored here 😮‍💨",
    "Someone say something stupid 🤡", "Ghost town vibes 👻", "সবাই কই গেলো? 💀",
    "Silence too loud 😂", "Drama koi? 🎭", "Wake up people 📢",
    "Entertainment চাই 😈", "Group এ life আছে? 🏥", "Tumbleweeds rolling 🌪️",
    "Somebody roast somebody 🔥", "Netflix এর চেয়ে boring 📉", "Waiting... waiting... 💀",
    "আমি একা কথা বলবো? 😭", "Group chat বা graveyard? ⚰️", "Say something funny challenge 🎪",
    "Sleeping beauty গুলো জাগো 😴"
]

DM_RESPONSE = "Hi! Add me to groups for fun 🔥"


class PermissionManager:
    def __init__(self):
        self.permission_mode = True
        self.allowed_groups = set()
        self.load_permissions()
    
    def load_permissions(self):
        if os.path.exists(PERMISSION_FILE):
            try:
                with open(PERMISSION_FILE, 'r') as f:
                    data = json.load(f)
                    self.permission_mode = data.get('permission_mode', True)
                    self.allowed_groups = set(data.get('allowed_groups', []))
            except:
                pass
    
    def save_permissions(self):
        with open(PERMISSION_FILE, 'w') as f:
            json.dump({
                'permission_mode': self.permission_mode,
                'allowed_groups': list(self.allowed_groups)
            }, f)
    
    def is_allowed(self, chat_id):
        if not self.permission_mode:
            return True
        return chat_id in self.allowed_groups
    
    def allow_group(self, chat_id):
        self.allowed_groups.add(chat_id)
        self.save_permissions()
    
    def decline_group(self, chat_id):
        self.allowed_groups.discard(chat_id)
        self.save_permissions()
    
    def set_permission_mode(self, mode: bool):
        self.permission_mode = mode
        self.save_permissions()


class UserMemory:
    def __init__(self):
        self.messages: List[tuple] = []
    
    def add_message(self, message: str):
        now = datetime.now()
        self.messages.append((now, message))
        if len(self.messages) > MAX_MEMORY_MESSAGES:
            self.messages.pop(0)
    
    def get_recent_messages(self) -> List[str]:
        now = datetime.now()
        cutoff = now - timedelta(seconds=MEMORY_DURATION)
        return [msg for ts, msg in self.messages if ts > cutoff]
    
    def clear_old_messages(self):
        now = datetime.now()
        cutoff = now - timedelta(seconds=MEMORY_DURATION)
        self.messages = [(ts, msg) for ts, msg in self.messages if ts > cutoff]


class OniBot:
    def __init__(self):
        self.user_memories: Dict[int, UserMemory] = defaultdict(UserMemory)
        self.active_groups: set = set()
        self.permission_manager = PermissionManager()
        
    async def generate_response(self, msg, memory):
        memory_context = ""
        if memory:
            memory_context = "\n\nRECENT CONVERSATION CONTEXT:\n" + "\n".join(f"- {m}" for m in memory)
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": ONI_SYSTEM_PROMPT + memory_context},
                            {"role": "user", "content": msg}
                        ],
                        "max_tokens": 100,
                        "temperature": 1.1,
                        "top_p": 0.95,
                    },
                )
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"].strip()
                return "Error 💀"
        except:
            return "Brain crash 😭"


oni = OniBot()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text(DM_RESPONSE)
    else:
        if oni.permission_manager.is_allowed(update.effective_chat.id):
            await update.message.reply_text("Oni here! 😈🔥")


async def permission_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        oni.permission_manager.set_permission_mode(True)
        await update.message.reply_text("✅ Permission mode ON")
    else:
        await update.message.reply_text("Admin only 😏")


async def permission_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        oni.permission_manager.set_permission_mode(False)
        await update.message.reply_text("✅ Permission mode OFF")
    else:
        await update.message.reply_text("Admin only 😏")


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(DM_RESPONSE)


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text
    
    if not oni.permission_manager.is_allowed(chat_id):
        return
    
    oni.active_groups.add(chat_id)
    
    mem = oni.user_memories[user_id]
    mem.add_message(text)
    mem.clear_old_messages()
    recent = mem.get_recent_messages()

    bot_mentioned = "oni" in text.lower()
    bot_username = context.bot.username

    if bot_username and f"@{bot_username}".lower() in text.lower():
        bot_mentioned = True

    replied_to_bot = (
        update.message.reply_to_message and
        update.message.reply_to_message.from_user.id == context.bot.id
    )

    if bot_mentioned or replied_to_bot:
        await asyncio.sleep(2)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        response = await oni.generate_response(text, recent)
        await update.message.reply_text(response)


async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = update.effective_chat.id
            chat_title = update.effective_chat.title or "Unknown Group"
            
            if oni.permission_manager.permission_mode:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Allow", callback_data=f"allow_{chat_id}"),
                        InlineKeyboardButton("❌ Decline", callback_data=f"decline_{chat_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"New group: {chat_title}\nID: {chat_id}",
                        reply_markup=reply_markup
                    )
                    await update.message.reply_text("Waiting for admin... ⏳")
                except:
                    pass
            else:
                oni.permission_manager.allow_group(chat_id)
                await update.message.reply_text("Oni here! Ready 😈🔥")


async def handle_permission_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if update.effective_user.id != ADMIN_ID:
        await query.answer("Not authorized!", show_alert=True)
        return
    
    data = query.data
    action, chat_id = data.split('_')
    chat_id = int(chat_id)
    
    if action == "allow":
        oni.permission_manager.allow_group(chat_id)
        await query.edit_message_text(f"Group {chat_id} allowed.")
        try:
            await context.bot.send_message(chat_id=chat_id, text="Permission granted 😈🔥")
        except:
            pass
    
    elif action == "decline":
        oni.permission_manager.decline_group(chat_id)
        await query.edit_message_text(f"Group {chat_id} declined.")
        try:
            await context.bot.send_message(chat_id=chat_id, text="Admin declined 👋")
            await context.bot.leave_chat(chat_id)
        except:
            pass


async def send_random_messages(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in list(oni.active_groups):
        if oni.permission_manager.is_allowed(chat_id):
            try:
                await context.bot.send_message(chat_id=chat_id, text=random.choice(RANDOM_MESSAGES))
            except:
                oni.active_groups.discard(chat_id)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("on", permission_on))
    app.add_handler(CommandHandler("off", permission_off))
    app.add_handler(CallbackQueryHandler(handle_permission_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_member))
    
    app.job_queue.run_repeating(send_random_messages, interval=RANDOM_MESSAGE_INTERVAL, first=RANDOM_MESSAGE_INTERVAL)
    
    print("🔥 Oni Bot Started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
