import asyncio
import aiohttp
import re
import os
import time
import json
from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp_socks import ProxyConnector

# Environment variables from GitHub Secrets
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GROUP_ID = os.environ.get("TARGET_GROUP_ID")

CHANNELS = [
    "iMTProto", "ProxyFree_Ru", "ProxyMTProto", 
    "MTProtoProxies", "TelMTProto", "MTP_ro",
    "TelegramProxies", "ProxyMTProto_ORG",
    "tg_proxies", "vpn_proxy_mtproto", "mtproto_proxies",
    "proxy_mtproto", "proXy", "mtproto_proxy", "proxyme",
    "proxy_socks5", "proxy_socks", "proxy_mtp", "mtproto",
    "socks5_bot", "socks5list", "socks5_proxy", "mtproto_tg",
    "proxy_tg", "tg_proxy", "proxy_for_telegram", "free_proxy",
    "proxymtproto_free", "proxy_free", "proxy_server", "proxy_list",
    "TgProxies", "Proxy", "Vpn", "Best_MTProto", "MTProto_Proxy_Server",
    "Proxy_MTProto_Telegram", "FreeMTProto", "MTProto_Free", "ProxyVIP",
    "MTProto_VIP", "Telegram_Proxy", "Tg_Proxy_Bot", "FastProxy",
    "SpeedProxy", "BestProxy", "TopProxy", "MTProtoProxy", "socks5",
    "socks5_proxies", "Socks5_Proxy_List", "MTProto_Proxies_List"
]

RAW_URLS = [
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/mtproto.json",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-mtproto.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/mtproto.txt"
]

STATE_FILE = "sent_proxies.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

async def check_mtproto(ip, port):
    start_time = time.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=3)
        writer.close()
        await writer.wait_closed()
        return int((time.time() - start_time) * 1000)
    except:
        return False

async def check_socks5(ip, port):
    start_time = time.time()
    proxy_url = f"socks5://{ip}:{port}"
    try:
        connector = ProxyConnector.from_url(proxy_url)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("https://api.telegram.org/bot/getMe", timeout=5) as resp:
                if resp.status in [200, 401, 404]:
                    return int((time.time() - start_time) * 1000)
    except:
        pass
    return False

async def get_country(ip):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{ip}", timeout=3) as resp:
                data = await resp.json()
                return data.get("country", "Unknown"), data.get("countryCode", "🌐")
    except:
        return "Unknown", "🌐"

async def publish_proxy(bot, proxy_data):
    ip = proxy_data["ip"]
    port = proxy_data["port"]
    protocol = proxy_data["protocol"]
    secret = proxy_data.get("secret", "")
    ping = proxy_data.get("ping", "Unknown")
    
    country, country_code = await get_country(ip)
    
    if protocol == "mtproto":
        link = f"https://t.me/proxy?server={ip}&port={port}&secret={secret}"
        share_link = f"https://t.me/share/url?url={link}"
        text = (
            f"🔐 <b>MTProto Proxy</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🖥  <b>Server</b> :  <code>{ip}</code>\n"
            f"🔌  <b>Port</b> :  <code>{port}</code>\n"
            f"🔑  <b>Secret</b> :  <code>{secret}</code>\n"
            f"⚡️  <b>Ping</b> :  <code>{ping} ms</code>\n"
            f"📍  <b>Country</b> :  {country} {country_code}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✅ Подключить", url=link))
        builder.row(types.InlineKeyboardButton(text="🚀 Поделиться", url=share_link))
        reply_markup = builder.as_markup()
    else:
        link = f"tg://socks?server={ip}&port={port}"
        text = (
            f"🌐 <b>SOCKS5 Proxy</b>\n"
            f"<code>{ip}:{port}</code>\n"
            f"⚡️ <b>Ping:</b> {ping}ms | 📍 {country} {country_code}"
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✅ Connect", url=link))
        reply_markup = builder.as_markup()

    try:
        msg = await bot.send_message(
            chat_id=GROUP_ID, 
            text=text, 
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        print(f"✅ Published: {ip}:{port} (Msg ID: {msg.message_id})")
        return msg.message_id
    except TelegramRetryAfter as e:
        print(f"⚠️ Flood control exceeded. Sleeping for {e.retry_after} seconds...")
        await asyncio.sleep(e.retry_after)
        try:
            msg = await bot.send_message(
                chat_id=GROUP_ID, 
                text=text, 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            print(f"✅ Published after sleep: {ip}:{port} (Msg ID: {msg.message_id})")
            return msg.message_id
        except Exception as retry_e:
             print(f"❌ Failed to publish after sleep {ip}:{port}: {retry_e}")
             return None
    except Exception as e:
        print(f"❌ Failed to publish {ip}:{port}: {e}")
        return None

async def cleanup_dead_proxies(bot, state):
    print("🧹 Starting Auto-Cleanup: Checking previously published proxies...")
    proxies_to_remove = []
    
    # We only check up to 50 proxies per run to avoid timeout on GitHub Actions
    items_to_check = list(state.items())[:50]
    
    for proxy_id, proxy_info in items_to_check:
        ip = proxy_info["ip"]
        port = int(proxy_info["port"])
        protocol = proxy_info["protocol"]
        message_id = proxy_info["message_id"]
        
        is_alive = False
        if protocol == "mtproto":
            is_alive = await check_mtproto(ip, port)
        elif protocol == "socks5":
            is_alive = await check_socks5(ip, port)
            
        if is_alive is False:
            print(f"💀 Dead Proxy Detected: {ip}:{port}. Deleting message {message_id}...")
            try:
                await bot.delete_message(chat_id=GROUP_ID, message_id=message_id)
                print(f"  🗑️ Message {message_id} deleted successfully.")
            except TelegramBadRequest as e:
                if "message to delete not found" in str(e).lower():
                    print(f"  ℹ️ Message {message_id} already deleted or missing.")
                else:
                    print(f"  ⚠️ Could not delete {message_id}: {e}")
            except Exception as e:
                print(f"  ⚠️ Could not delete {message_id}: {e}")
            
            proxies_to_remove.append(proxy_id)
            await asyncio.sleep(0.5) # Prevent flood control during mass deletion
        else:
            print(f"  🟢 Still alive: {ip}:{port} ({is_alive}ms)")
            
    # Remove dead proxies from state so we don't check them again
    for pid in proxies_to_remove:
        if pid in state:
            del state[pid]
            
    if proxies_to_remove:
        save_state(state)
        print(f"✅ Cleanup finished. Removed {len(proxies_to_remove)} dead proxies.")
    else:
        print("✅ Cleanup finished. All checked proxies are still alive.")

async def scrape_channel(bot, channel, state, mtproto_regex, socks_regex):
    print(f"🔎 Scraping: {channel}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    
    sources = [
        f"https://t.me/s/{channel}",
        f"https://telemetr.io/en/channels/{channel}/posts",
        f"https://tgstat.ru/channel/@{channel}"
    ]
    
    for url in sources:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200:
                        continue
                    text = await response.text()
                    
                    found = False
                    for match in mtproto_regex.finditer(text):
                        ip, port, secret = match.group(1), match.group(2), match.group(3)
                        proxy_id = f"mtproto|{ip}|{port}|{secret}"
                        
                        if proxy_id not in state:
                            print(f"🧪 Testing MTProto: {ip}:{port}...")
                            ping = await check_mtproto(ip, int(port))
                            if ping is not False:
                                message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping})
                                if message_id:
                                    state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": message_id}
                                    save_state(state)
                            else:
                                print(f"  🗑️ Dead MTProto: {ip}:{port}")
                            
                            if ping is False:
                                # Mark as dead but without message_id so we don't try to send it again immediately
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                                save_state(state)
                            found = True

                    for match in socks_regex.finditer(text):
                        ip, port = match.group(1), match.group(2)
                        proxy_id = f"socks5|{ip}|{port}"
                        
                        if proxy_id not in state:
                            print(f"🧪 Testing SOCKS5: {ip}:{port}...")
                            ping = await check_socks5(ip, int(port))
                            if ping is not False:
                                message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "socks5", "ping": ping})
                                if message_id:
                                    state[proxy_id] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": message_id}
                                    save_state(state)
                            else:
                                print(f"  🗑️ Dead SOCKS5: {ip}:{port}")
                            
                            if ping is False:
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": 0}
                                save_state(state)
                            found = True
                    
                    if found:
                        return # Success, move to next channel
        except Exception as e:
            print(f"⚠️ Error scraping {url}: {e}")

async def scrape_raw_url(bot, url, state, mtproto_regex, socks_regex):
    print(f"🔎 Scraping RAW URL: {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return
                text = await response.text()
                
                for match in mtproto_regex.finditer(text):
                    ip, port, secret = match.group(1), match.group(2), match.group(3)
                    proxy_id = f"mtproto|{ip}|{port}|{secret}"
                    
                    if proxy_id not in state:
                        ping = await check_mtproto(ip, int(port))
                        if ping is not False:
                            message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping})
                            if message_id:
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": message_id}
                                save_state(state)
                        if ping is False:
                            state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                            save_state(state)
    except Exception as e:
        print(f"⚠️ Error scraping raw {url}: {e}")

async def main():
    if not BOT_TOKEN or not GROUP_ID:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN or TARGET_GROUP_ID is missing!")
        return

    print("🚀 GitHub Actions Proxy Bot Started!")
    state = load_state()
    print(f"📦 Loaded {len(state)} previously checked proxies.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    # 1. Run the Auto-Cleaner First
    await cleanup_dead_proxies(bot, state)
    
    mtproto_regex = re.compile(r"server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)(?:&|&amp;)secret=([a-zA-Z0-9._~%-]+)")
    socks_regex = re.compile(r"socks\?server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)")

    # 2. Scrape new proxies (Concurrently in batches to speed up)
    batch_size = 10
    
    for i in range(0, len(CHANNELS), batch_size):
        batch = CHANNELS[i:i + batch_size]
        tasks = [scrape_channel(bot, channel, state, mtproto_regex, socks_regex) for channel in batch]
        await asyncio.gather(*tasks)
        await asyncio.sleep(1) # Small pause between batches

    for url in RAW_URLS:
        await scrape_raw_url(bot, url, state, mtproto_regex, socks_regex)

    await bot.session.close()
    print("🏁 Finished all tasks.")

if __name__ == "__main__":
    asyncio.run(main())
