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

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f: json.dump(state, f, indent=2)

def load_stats():
    default_stats = {
        "всего_найдено": 0,
        "всего_отправлено": 0,
        "всего_удалено": 0,
        "лучший_прокси": {"ip": "Нет", "port": 0, "ping": 99999, "protocol": "Нет"}
    }
    if not os.path.exists(STATS_FILE): return default_stats
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            stats = json.load(f)
            for k, v in default_stats.items():
                if k not in stats: stats[k] = v
            return stats
    except: return default_stats

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f: json.dump(stats, f, indent=2, ensure_ascii=False)

async def check_mtproto(ip, port):
    start_time = time.time()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=3)
        writer.close()
        await writer.wait_closed()
        return int((time.time() - start_time) * 1000)
    except: return False

async def check_socks5(ip, port):
    start_time = time.time()
    try:
        connector = ProxyConnector.from_url(f"socks5://{ip}:{port}")
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get("https://api.telegram.org/bot/getMe", timeout=5) as resp:
                if resp.status in [200, 401, 404]: return int((time.time() - start_time) * 1000)
    except: pass
    return False

async def publish_proxy(bot, proxy_data, state, stats, session_stats):
    ip, port, protocol, secret, ping = proxy_data["ip"], proxy_data["port"], proxy_data["protocol"], proxy_data.get("secret", ""), proxy_data.get("ping", "Unknown")
    
    if protocol == "mtproto":
        link = f"https://t.me/proxy?server={ip}&port={port}&secret={secret}"
        text = f"🔐 MTProto Proxy\n━━━━━━━━━━━━━━━━━━━━\n\n🖥  Server :  {ip}\n🔌  Port :  {port}\n🔑  Secret :  {secret}\n⚡️  Ping :  {ping} ms\n\n━━━━━━━━━━━━━━━━━━━━"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✅ Подключить", url=link))
        builder.row(types.InlineKeyboardButton(text="🚀 Поделиться", url=f"https://t.me/share/url?url={link}"))
        reply_markup = builder.as_markup()
    else:
        text = f"🌐 SOCKS5 Proxy\n{ip}:{port}\nPing: {ping}ms"
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="✅ Connect", url=f"tg://socks?server={ip}&port={port}"))
        reply_markup = builder.as_markup()

    try:
        await bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=reply_markup, disable_web_page_preview=True, parse_mode=None)
        print(f"✅ Published: {ip}:{port}")
        stats["всего_отправлено"] += 1
        session_stats["sent_this_run"] += 1
        
        if isinstance(ping, int) and ping < stats["лучший_прокси"].get("ping", 99999):
            stats["лучший_прокси"] = {"ip": ip, "port": port, "ping": ping, "protocol": protocol, "secret": secret}
        return True
    except TelegramRetryAfter as e:
        print(f"⚠️ Flood control! Sleeping {e.retry_after}s")
        await asyncio.sleep(e.retry_after)
        return await publish_proxy(bot, proxy_data, state, stats, session_stats)
    except Exception as e:
        print(f"❌ Publish error: {e}")
        return False

async def cleanup_dead_proxies(bot, state, stats):
    print("🧹 Starting Auto-Cleanup...")
    to_remove = []
    items = [it for it in list(state.items()) if isinstance(it[1], dict) and it[1].get("message_id", 0) != 0][:50]
    for pid, info in items:
        alive = await check_mtproto(info["ip"], int(info["port"])) if info["protocol"] == "mtproto" else await check_socks5(info["ip"], int(info["port"]))
        if alive is False:
            print(f"💀 Deleting dead: {info['ip']}:{info['port']}")
            try: await bot.delete_message(chat_id=GROUP_ID, message_id=info["message_id"])
            except: pass
            to_remove.append(pid)
            await asyncio.sleep(0.5)
    for pid in to_remove:
        if pid in state: del state[pid]
    stats["всего_удалено"] += len(to_remove)
    save_state(state)

async def scrape_channel(bot, channel, state, stats, session_stats, mt_re, sk_re):
    print(f"🔎 Scraping: {channel}")
    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [f"https://t.me/s/{channel}", f"https://telemetr.io/en/channels/{channel}/posts"]
    for url in urls:
        try:
            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.get(url, timeout=10) as r:
                    if r.status != 200: continue
                    text = await r.text()
                    found = False
                    for m in mt_re.finditer(text):
                        ip, port, secret = m.group(1), m.group(2), m.group(3)
                        pid = f"mtproto|{ip}|{port}|{secret}"
                        if pid not in state:
                            stats["всего_найдено"] += 1
                            ping = await check_mtproto(ip, int(port))
                            if ping is not False:
                                success = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}, state, stats, session_stats)
                                if success: state[pid] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 1} # Temporary ID until next run
                            else: state[pid] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                            save_state(state)
                            found = True
                    for m in sk_re.finditer(text):
                        ip, port = m.group(1), m.group(2)
                        pid = f"socks5|{ip}|{port}"
                        if pid not in state:
                            stats["всего_найдено"] += 1
                            ping = await check_socks5(ip, int(port))
                            if ping is not False:
                                success = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "socks5", "ping": ping}, state, stats, session_stats)
                                if success: state[pid] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": 1}
                            else: state[pid] = {"ip": ip, "port": port, "protocol": "socks5", "message_id": 0}
                            save_state(state)
                            found = True
                    if found: return
        except: pass

async def scrape_raw_url(bot, url, state, stats, session_stats, mt_re, sk_re):
    print(f"🔎 Scrape RAW: {url}")
    try:
        async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
            async with session.get(url, timeout=15) as response:
                if response.status != 200: return
                text = await response.text()
                for m in mt_re.finditer(text):
                    ip, port, secret = m.group(1), m.group(2), m.group(3)
                    pid = f"mtproto|{ip}|{port}|{secret}"
                    if pid not in state:
                        stats["всего_найдено"] += 1
                        ping = await check_mtproto(ip, int(port))
                        if ping is not False:
                            success = await publish_proxy(bot, {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "ping": ping}, state, stats, session_stats)
                            if success: state[pid] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 1}
                        else: state[pid] = {"ip": ip, "port": port, "protocol": "mtproto", "secret": secret, "message_id": 0}
                        save_state(state)
    except: pass

async def publish_stats(bot, state, stats, session_stats):
    now = (datetime.now(timezone.utc) + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S МСК")
    best = stats.get("лучший_прокси", {})
    text = f"📊 Статистика\n━━━━━━━━━━━━━━━━━━━━\n\n🔍 Всего найдено: {stats['всего_найдено']}\n📥 Отправлено в канал: {session_stats['sent_this_run']}\n🗑 Удалено мёртвых: {stats['всего_удалено']}\n🟢 Сейчас активно в канале: {len([p for p in state.values() if isinstance(p, dict) and p.get('message_id', 0) != 0])}\n\n⏱️ Последнее сканирование:\n{now}\n\n🏆 Лучший прокси:\n├ Протокол: {str(best.get('protocol','Нет')).upper()}\n├ IP:Port: {best.get('ip','Нет')}:{best.get('port',0)}\n└ Пинг: {best.get('ping','Нет')} ms ⚡️\n\n━━━━━━━━━━━━━━━━━━━━"
    
    kb = InlineKeyboardBuilder()
    if best.get("ip") != "Нет":
        link = f"https://t.me/proxy?server={best['ip']}&port={best['port']}&secret={best['secret']}" if best['protocol'] == "mtproto" else f"tg://socks?server={best['ip']}&port={best['port']}"
        kb.row(types.InlineKeyboardButton(text="✅ Подключить", url=link))
    
    try:
        msg = await bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=kb.as_markup(), parse_mode=None)
        if state.get("stats_message_id"):
            try:
                await bot.unpin_chat_message(chat_id=GROUP_ID, message_id=state["stats_message_id"])
                await bot.delete_message(chat_id=GROUP_ID, message_id=state["stats_message_id"])
            except: pass
        await bot.pin_chat_message(chat_id=GROUP_ID, message_id=msg.message_id, disable_notification=True)
        state["stats_message_id"] = msg.message_id
        save_state(state)
    except: pass

async def main():
    if not BOT_TOKEN or not GROUP_ID: return
    state, stats = load_state(), load_stats()
    session_stats = {"sent_this_run": 0}
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    
    await cleanup_dead_proxies(bot, state, stats)
    
    mt_re = re.compile(r"server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)(?:&|&amp;)secret=([a-zA-Z0-9._~%-]+)")
    sk_re = re.compile(r"socks\?server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)")

    batch_size = 10
    for i in range(0, len(CHANNELS), batch_size):
        await asyncio.gather(*[scrape_channel(bot, ch, state, stats, session_stats, mt_re, sk_re) for ch in CHANNELS[i:i + batch_size]])
        await asyncio.sleep(1)

    for url in RAW_URLS: await scrape_raw_url(bot, url, state, stats, session_stats, mt_re, sk_re)

    await publish_stats(bot, state, stats, session_stats)
    await bot.session.close()
    save_stats(stats)

if __name__ == "__main__": asyncio.run(main())
