import asyncio
import aiohttp
import re
import os
import time
from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter
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

SENT_FILE = "sent_proxies.txt"

def load_sent_proxies():
    if not os.path.exists(SENT_FILE):
        return set()
    with open(SENT_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_sent_proxy(proxy_id):
    with open(SENT_FILE, "a", encoding="utf-8") as f:
        f.write(f"{proxy_id}\n")

async def check_mtproto(ip, port):
    """Attempt to check MTProto by pinging a known host through it."""
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
        await bot.send_message(
            chat_id=GROUP_ID, 
            text=text, 
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        print(f"✅ Published: {ip}:{port} ({protocol})")
        return True
    except TelegramRetryAfter as e:
        print(f"⚠️ Flood control exceeded. Sleeping for {e.retry_after} seconds...")
        await asyncio.sleep(e.retry_after)
        # Try one more time after sleeping
        try:
            await bot.send_message(
                chat_id=GROUP_ID, 
                text=text, 
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            print(f"✅ Published after sleep: {ip}:{port} ({protocol})")
            return True
        except Exception as retry_e:
             print(f"❌ Failed to publish after sleep {ip}:{port}: {retry_e}")
             return False
    except Exception as e:
        print(f"❌ Failed to publish {ip}:{port}: {e}")
        return False

async def scrape_channel(bot, channel, sent_proxies, mtproto_regex, socks_regex):
    print(f"🔎 Scraping: {channel}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    
    # We are on GitHub Actions, no local blocks, so we can try direct mirrors
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
                        
                        if proxy_id not in sent_proxies:
                            print(f"🧪 Testing MTProto: {ip}:{port}...")
                            ping = await check_mtproto(ip, int(port))
                            if ping is not False:
                                if await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}):
                                    save_sent_proxy(proxy_id)
                                    sent_proxies.add(proxy_id)
                            else:
                                print(f"  🗑️ Dead MTProto: {ip}:{port}")
                            # Add to sent anyway to avoid re-checking dead ones constantly in the same run
                            sent_proxies.add(proxy_id)
                            save_sent_proxy(proxy_id)
                            found = True

                    for match in socks_regex.finditer(text):
                        ip, port = match.group(1), match.group(2)
                        proxy_id = f"socks5|{ip}|{port}"
                        
                        if proxy_id not in sent_proxies:
                            print(f"🧪 Testing SOCKS5: {ip}:{port}...")
                            ping = await check_socks5(ip, int(port))
                            if ping is not False:
                                if await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "socks5", "ping": ping}):
                                    save_sent_proxy(proxy_id)
                                    sent_proxies.add(proxy_id)
                            else:
                                print(f"  🗑️ Dead SOCKS5: {ip}:{port}")
                            sent_proxies.add(proxy_id)
                            save_sent_proxy(proxy_id)
                            found = True
                    
                    if found:
                        return # Success, move to next channel
        except Exception as e:
            print(f"⚠️ Error scraping {url}: {e}")

RAW_URLS = [
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/mtproto.json",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-mtproto.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/mtproto.txt"
]

async def scrape_raw_url(bot, url, sent_proxies, mtproto_regex, socks_regex):
    print(f"🔎 Scraping RAW URL: {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return
                text = await response.text()
                
                # Match direct proxy strings or full links
                for match in mtproto_regex.finditer(text):
                    ip, port, secret = match.group(1), match.group(2), match.group(3)
                    proxy_id = f"mtproto|{ip}|{port}|{secret}"
                    
                    if proxy_id not in sent_proxies:
                        ping = await check_mtproto(ip, int(port))
                        if ping is not False:
                            if await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}):
                                save_sent_proxy(proxy_id)
                                sent_proxies.add(proxy_id)
                        sent_proxies.add(proxy_id)
                        save_sent_proxy(proxy_id)
    except Exception as e:
        print(f"⚠️ Error scraping raw {url}: {e}")

async def main():
    if not BOT_TOKEN or not GROUP_ID:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN or TARGET_GROUP_ID is missing!")
        return

    print("🚀 GitHub Actions Proxy Bot Started!")
    sent_proxies = load_sent_proxies()
    print(f"📦 Loaded {len(sent_proxies)} previously checked proxies.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    mtproto_regex = re.compile(r"server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)(?:&|&amp;)secret=([a-zA-Z0-9._~%-]+)")
    socks_regex = re.compile(r"socks\?server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)")

    # Scrape channels
    for channel in CHANNELS:
        await scrape_channel(bot, channel, sent_proxies, mtproto_regex, socks_regex)
        await asyncio.sleep(1)

    # Scrape raw URLs
    for url in RAW_URLS:
        await scrape_raw_url(bot, url, sent_proxies, mtproto_regex, socks_regex)
        await asyncio.sleep(1)

    await bot.session.close()
    print("🏁 Finished scraping all channels and URLs.")

if __name__ == "__main__":
    asyncio.run(main())
