import asyncio
import aiohttp
import re
import os
import time
import json
from datetime import datetime, timedelta, timezone
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
STATS_FILE = "stats.json"
PIN_LOCK = None

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

def load_stats():
    default_stats = {
        "всего_найдено": 0,
        "всего_отправлено": 0,
        "всего_удалено": 0,
        "сейчас_активно": 0,
        "лучший_прокси": {"ip": "Нет", "port": 0, "ping": 99999, "protocol": "Нет"},
        "последний_запуск": ""
    }
    if not os.path.exists(STATS_FILE):
        return default_stats
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
            for k, v in default_stats.items():
                if k not in stats: stats[k] = v
            return stats
    except:
        return default_stats

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

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

async def publish_proxy(bot, proxy_data, state, stats):
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

    async def _send_with_retry(retries=2):
        for _ in range(retries):
            try:
                msg = await bot.send_message(
                    chat_id=GROUP_ID, 
                    text=text, 
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
                print(f"✅ Published: {ip}:{port} (Msg ID: {msg.message_id})")
                stats["всего_отправлено"] += 1
                
                if isinstance(ping, int):
                    best_ping = stats["лучший_прокси"].get("ping", 99999)
                    if ping < best_ping:
                        stats["лучший_прокси"] = {"ip": ip, "port": port, "ping": ping, "protocol": protocol, "secret": secret}

                return msg.message_id
            except TelegramRetryAfter as e:
                print(f"⚠️ Flood control exceeded. Sleeping for {e.retry_after} seconds...")
                await asyncio.sleep(e.retry_after)
            except Exception as e:
                print(f"❌ Failed to publish {ip}:{port}: {e}")
                return None
        return None

    return await _send_with_retry()

async def cleanup_dead_proxies(bot, state, stats):
    print("🧹 Starting Auto-Cleanup...")
    proxies_to_remove = []
    items_to_check = [item for item in list(state.items()) if isinstance(item[1], dict)][:50]
    
    for proxy_id, proxy_info in items_to_check:
        ip, port, protocol, message_id = proxy_info["ip"], int(proxy_info["port"]), proxy_info["protocol"], proxy_info["message_id"]
        
        is_alive = await check_mtproto(ip, port) if protocol == "mtproto" else await check_socks5(ip, port)
            
        if is_alive is False:
            print(f"💀 Dead Proxy Detected: {ip}:{port}.")
            if message_id != 0:
                try:
                    await bot.delete_message(chat_id=GROUP_ID, message_id=message_id)
                except: pass
            proxies_to_remove.append(proxy_id)
            await asyncio.sleep(0.5)
            
    for pid in proxies_to_remove:
        if pid in state: del state[pid]
            
    if proxies_to_remove:
        save_state(state)
        stats["всего_удалено"] += len(proxies_to_remove)

async def scrape_channel(bot, channel, state, stats, mtproto_regex, socks_regex):
    print(f"🔎 Scraping: {channel}...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    sources = [f"https://t.me/s/{channel}", f"https://telemetr.io/en/channels/{channel}/posts", f"https://tgstat.ru/channel/@{channel}"]
    
    for url in sources:
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=10) as response:
                    if response.status != 200: continue
                    text = await response.text()
                    found = False
                    for match in mtproto_regex.finditer(text):
                        ip, port, secret = match.group(1), match.group(2), match.group(3)
                        proxy_id = f"mtproto|{ip}|{port}|{secret}"
                        if proxy_id not in state:
                            stats["всего_найдено"] += 1
                            ping = await check_mtproto(ip, int(port))
                            if ping is not False:
                                message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}, state, stats)
                                if message_id:
                                    state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": message_id}
                                    save_state(state)
                            else:
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                                save_state(state)
                            found = True
                    for match in socks_regex.finditer(text):
                        ip, port = match.group(1), match.group(2)
                        proxy_id = f"socks5|{ip}|{port}"
                        if proxy_id not in state:
                            stats["всего_найдено"] += 1
                            ping = await check_socks5(ip, int(port))
                            if ping is not False:
                                message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "socks5", "ping": ping}, state, stats)
                                if message_id:
                                    state[proxy_id] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": message_id}
                                    save_state(state)
                            else:
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": 0}
                                save_state(state)
                            found = True
                    if found: return
        except: pass

async def scrape_raw_url(bot, url, state, stats, mtproto_regex, socks_regex):
    print(f"🔎 Scraping RAW URL: {url}...")
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200: return
                text = await response.text()
                for match in mtproto_regex.finditer(text):
                    ip, port, secret = match.group(1), match.group(2), match.group(3)
                    proxy_id = f"mtproto|{ip}|{port}|{secret}"
                    if proxy_id not in state:
                        stats["всего_найдено"] += 1
                        ping = await check_mtproto(ip, int(port))
                        if ping is not False:
                            message_id = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}, state, stats)
                            if message_id:
                                state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": message_id}
                                save_state(state)
                        else:
                            state[proxy_id] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                            save_state(state)
    except: pass

async def publish_stats(bot, state, stats):
    # Update timestamp to MSK BEFORE publishing
    msk_time = datetime.now(timezone.utc) + timedelta(hours=3)
    current_time_str = msk_time.strftime("%Y-%m-%d %H:%M:%S МСК")
    stats["последний_запуск"] = current_time_str

    best = stats.get("лучший_прокси", {})
    best_ip, best_port, best_ping, best_secret = best.get("ip", "Нет"), best.get("port", 0), best.get("ping", "Нет"), best.get("secret", "")
    best_protocol = str(best.get("protocol", "Нет")).upper()
    
    text = (
        f"📊 <b>Статистика</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔍 Всего найдено: <code>{stats.get('всего_найдено', 0)}</code>\n"
        f"📥 Отправлено в канал: <code>{stats.get('всего_отправлено', 0)}</code>\n"
        f"🗑 Удалено мёртвых: <code>{stats.get('всего_удалено', 0)}</code>\n"
        f"🟢 Сейчас активно в канале: <code>{stats.get('сейчас_активно', 0)}</code>\n\n"
        f"⏱️ Последнее сканирование:\n"
        f"<code>{current_time_str}</code>\n\n"
        f"🏆 Лучший прокси:\n"
        f"├ Протокол: <code>{best_protocol}</code>\n"
        f"├ IP:Port: <code>{best_ip}:{best_port}</code>\n"
        f"└ Пинг: <code>{best_ping} ms</code> ⚡️\n\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    
    reply_markup = None
    if best_ip != "Нет":
        link = f"https://t.me/proxy?server={best_ip}&port={best_port}&secret={best_secret}" if best_protocol == "MTPROTO" else f"tg://socks?server={best_ip}&port={best_port}"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✅ Подключить к лучшему", url=link))
        reply_markup = builder.as_markup()

    try:
        msg = await bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
        # Handle pinning and unpinning
        old_stats_id = state.get("stats_message_id")
        if old_stats_id:
            try:
                await bot.unpin_chat_message(chat_id=GROUP_ID, message_id=old_stats_id)
                await bot.delete_message(chat_id=GROUP_ID, message_id=old_stats_id)
            except: pass
        await bot.pin_chat_message(chat_id=GROUP_ID, message_id=msg.message_id, disable_notification=True)
        state["stats_message_id"] = msg.message_id
        save_state(state)
    except Exception as e: print(f"❌ Stats error: {e}")

async def main():
    global PIN_LOCK
    PIN_LOCK = asyncio.Lock()
    if not BOT_TOKEN or not GROUP_ID: return

    state, stats = load_state(), load_stats()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    
    await cleanup_dead_proxies(bot, state, stats)
    
    mtproto_regex = re.compile(r"server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)(?:&|&amp;)secret=([a-zA-Z0-9._~%-]+)")
    socks_regex = re.compile(r"socks\?server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)")

    batch_size = 10
    for i in range(0, len(CHANNELS), batch_size):
        await asyncio.gather(*[scrape_channel(bot, ch, state, stats, mtproto_regex, socks_regex) for ch in CHANNELS[i:i + batch_size]])
        await asyncio.sleep(1)

    for url in RAW_URLS: await scrape_raw_url(bot, url, state, stats, mtproto_regex, socks_regex)

    stats["сейчас_активно"] = len([p for p in state.values() if isinstance(p, dict) and p.get("message_id", 0) != 0])
    await publish_stats(bot, state, stats)
    await bot.session.close()
    save_stats(stats)

if __name__ == "__main__":
    asyncio.run(main())
