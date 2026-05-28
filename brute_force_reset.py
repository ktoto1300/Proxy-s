import asyncio
import os
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.environ.get("TARGET_GROUP_ID")

async def force_clean_channel():
    if not BOT_TOKEN or not GROUP_ID:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN or TARGET_GROUP_ID is missing!")
        return

    print("🧨 STARTING BRUTE-FORCE CLEANUP OF THE CHANNEL...")
    print("⚠️ This will attempt to delete the last 500 messages sent by the bot.")
    
    bot = Bot(token=BOT_TOKEN)
    
    # We don't have the exact IDs, so we'll guess them.
    # First, let's send a dummy message to get the current highest message ID
    try:
        dummy = await bot.send_message(chat_id=GROUP_ID, text="[System] Starting wipe...", disable_notification=True)
        highest_id = dummy.message_id
        await bot.delete_message(chat_id=GROUP_ID, message_id=highest_id)
        print(f"📌 Highest detected message ID is {highest_id}")
    except Exception as e:
        print(f"❌ Failed to get current message ID: {e}")
        await bot.session.close()
        return

    # Now, count backward from the highest ID and try to delete
    # the last 500 messages
    deleted_count = 0
    start_id = highest_id - 1
    end_id = max(0, highest_id - 500)
    
    print(f"🧹 Sweeping IDs from {start_id} down to {end_id}...")

    for msg_id in range(start_id, end_id, -1):
        try:
            await bot.delete_message(chat_id=GROUP_ID, message_id=msg_id)
            print(f"  🗑️ Deleted orphaned message {msg_id}")
            deleted_count += 1
            await asyncio.sleep(0.05) # Rate limiting
        except TelegramBadRequest as e:
            # Message doesn't exist, ignore
            pass
        except TelegramRetryAfter as e:
            print(f"  ⚠️ Flood control. Sleeping for {e.retry_after}s")
            await asyncio.sleep(e.retry_after)
        except Exception as e:
            pass # Ignore other errors

    await bot.session.close()
    print(f"\n✅ BRUTE-FORCE CLEANUP FINISHED. Deleted {deleted_count} orphaned messages.")

if __name__ == "__main__":
    asyncio.run(force_clean_channel())
