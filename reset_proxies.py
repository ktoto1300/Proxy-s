import asyncio
import json
import os
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.environ.get("TARGET_GROUP_ID")
STATE_FILE = "sent_proxies.json"
STATS_FILE = "stats.json"

async def main():
    if not BOT_TOKEN or not GROUP_ID:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN or TARGET_GROUP_ID is missing!")
        return

    print("🧨 Starting FULL RESET of all proxy messages...")
    bot = Bot(token=BOT_TOKEN)
    
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
    except:
        state = {}

    deleted_count = 0
    # Collect all valid message IDs
    items_to_delete = []
    for proxy_id, info in list(state.items()):
        if isinstance(info, dict) and "message_id" in info and info["message_id"] != 0:
            items_to_delete.append(info["message_id"])

    print(f"🔎 Found {len(items_to_delete)} messages to delete.")

    for msg_id in items_to_delete:
        try:
            await bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
            print(f"  🗑️ Deleted message {msg_id}")
            deleted_count += 1
            await asyncio.sleep(0.1) # Small delay to avoid flooding Telegram API
        except TelegramRetryAfter as e:
            print(f"  ⚠️ Flood control. Sleeping for {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
            try:
                await bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
                deleted_count += 1
            except: pass
        except TelegramBadRequest:
            print(f"  ℹ️ Message {msg_id} already deleted.")
        except Exception as e:
            print(f"  ⚠️ Error deleting {msg_id}: {e}")

    # Try to delete the pinned stats message too
    stats_msg_id = state.get("stats_message_id")
    if stats_msg_id:
        try:
            await bot.delete_message(chat_id=GROUP_ID, message_id=stats_msg_id)
            print(f"  🗑️ Deleted pinned stats message {stats_msg_id}")
        except: pass

    await bot.session.close()

    # 1. Clear the state file completely
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, indent=2)
        
    # 2. Update stats file to reflect 0 active proxies
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
        stats["сейчас_активно"] = 0
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
    except: pass

    print(f"✅ Reset complete. Successfully deleted {deleted_count} messages. Database is wiped clean.")

if __name__ == "__main__":
    asyncio.run(main())
