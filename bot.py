import asyncio
import aiohttp
import re
import os
import time
import json
import sys
import random
import subprocess
import warnings
from datetime import datetime, timedelta, timezone
from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiohttp_socks import ProxyConnector

warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "sent_proxies.json")
STATS_FILE = os.path.join(BASE_DIR, "stats.json")
PROXIES_TXT = os.path.join(BASE_DIR, "proxies.txt")
PID_FILE = os.path.join(BASE_DIR, "bot.pid")

STATE_LOCK = asyncio.Lock()
STATS_LOCK = asyncio.Lock()
PROCESSING_PIDS = set()

CHANNELS = [
    "iMTProto", "ProxyFree_Ru", "ProxyMTProto", "MTProtoProxies", "TelMTProto", "MTP_ro",
    "TelegramProxies", "ProxyMTProto_ORG", "tg_proxies", "vpn_proxy_mtproto", "mtproto_proxies",
    "proxy_mtproto", "proXy", "mtproto_proxy", "proxyme", "proxy_socks5", "proxy_socks",
    "proxy_mtp", "mtproto", "socks5_bot", "socks5list", "socks5_proxy", "mtproto_tg",
    "proxy_tg", "tg_proxy", "proxy_for_telegram", "free_proxy", "proxymtproto_free",
    "proxy_free", "proxy_server", "proxy_list", "TgProxies", "Proxy", "Vpn", "Best_MTProto", 
    "MTProto_Proxy_Server", "Proxy_MTProto_Telegram", "FreeMTProto", "MTProto_Free", "ProxyVIP",
    "MTProto_VIP", "Telegram_Proxy", "Tg_Proxy_Bot", "FastProxy", "SpeedProxy", "BestProxy", 
    "TopProxy", "MTProxy_Hub", "Proxy_Master", "Proxy_King", "Proxy_Empire", "Proxy_World"
]

RAW_URLS = [
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/mtproto.json",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-mtproto.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/mtproto.txt",
    "https://raw.githubusercontent.com/shifure007/Proxy-List/main/mtproto.txt",
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt"
]

UA_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def load_json(path):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
    except: pass

async def sync_github(state):
    try:
        links = []
        for pid, info in state.items():
            if isinstance(info, dict) and info.get("message_id", 0) != 0:
                ip, port, proto, secret = info.get("ip"), info.get("port"), info.get("protocol"), info.get("secret")
                if ip and port:
                    if proto == "mtproto": links.append(f"https://t.me/proxy?server={ip}&port={port}&secret={secret or ''}")
                    else: links.append(f"tg://socks?server={ip}&port={port}")
        links = sorted(list(set(links)))
        if not links: return
        with open(PROXIES_TXT, "w", encoding="utf-8") as f: f.write("\n".join(links))
        subprocess.run(["git", "add", "proxies.txt"], cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Auto-update: {len(links)} proxies"], cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, capture_output=True)
    except: pass

async def check_p(ip, port, protocol):
    if int(port) in [21, 22, 23, 25, 53, 80, 110, 143, 465, 587, 993, 995, 3306, 3389]: return False
    try:
        start = time.time()
        if protocol == "mtproto":
            r, w = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=3)
            try: w.close(); await w.wait_closed()
            except: pass
        else:
            async def _check_socks():
                connector = ProxyConnector.from_url(f"socks5://{ip}:{port}")
                async with aiohttp.ClientSession(connector=connector) as s:
                    async with s.get("https://api.telegram.org/bot/getMe", timeout=5) as r:
                        if r.status not in [200, 401, 404]: return False
                        return True
            res = await asyncio.wait_for(_check_socks(), timeout=7)
            if not res: return False
        
        ping = int((time.time() - start) * 1000)
        return ping if 10 <= ping <= 1000 else False
    except:
        return False

async def send_msg(bot, gid, text, kb):
    try:
        msg = await bot.send_message(chat_id=gid, text=text, reply_markup=kb, disable_web_page_preview=True)
        return msg
    except Exception as e:
        print(f"Error sending message: {e}")
        return None

async def del_msg(bot, gid, mid):
    if not mid: return False
    try:
        await bot.delete_message(chat_id=gid, message_id=mid)
        return True
    except TelegramBadRequest as e:
        if "not found" in str(e).lower(): return True
        return False
    except: 
        return False

async def process_one(bot, gid, c, state, stats, session_stats):
    pid = c["proxy_id"]
    
    async with STATE_LOCK:
        if pid in PROCESSING_PIDS: return
        PROCESSING_PIDS.add(pid)
        
    ping = await check_p(c["ip"], c["port"], c["protocol"])
    if ping is False:
        async with STATE_LOCK: state[pid] = {"message_id": 0, "timestamp": int(time.time())}
        return
    
    if c["protocol"] == "mtproto":
        link = f"https://t.me/proxy?server={c['ip']}&port={c['port']}&secret={c['secret']}"
        text = f"🔐 MTProto Proxy\n━━━━━━━━━━━━━━━━━━━━\n\n🖥  Server :  {c['ip']}\n🔌  Port :  {c['port']}\n🔑  Secret :  {c['secret']}\n⚡️  Ping :  {ping} ms\n\n━━━━━━━━━━━━━━━━━━━━"
        kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ Подключить", url=link)).as_markup()
    else:
        link = f"tg://socks?server={c['ip']}&port={c['port']}"
        text = f"🌐 SOCKS5 Proxy\n━━━━━━━━━━━━━━━━━━━━\n\n🖥  Server :  {c['ip']}\n🔌  Port :  {c['port']}\n⚡️  Ping :  {ping} ms\n\n━━━━━━━━━━━━━━━━━━━━"
        kb = InlineKeyboardBuilder().row(types.InlineKeyboardButton(text="✅ Подключить", url=link)).as_markup()

    msg = await send_msg(bot, gid, text, kb)
    if msg:
        async with STATE_LOCK:
            state[pid] = {"ip":c["ip"],"port":c["port"],"protocol":c["protocol"],"secret":c.get("secret",""),"message_id":msg.message_id,"timestamp":int(time.time())}
        print(f"📡 Отправлено: {c['ip']}:{c['port']} ({ping}ms)")
        async with STATS_LOCK: stats["всего_отправлено"] += 1; session_stats["sent_this_run"] += 1

async def scrape(bot, gid, url, state, stats, session_stats, mt_re, is_chan=True):
    headers = {"User-Agent": random.choice(UA_LIST)}
    try:
        async with aiohttp.ClientSession(headers=headers) as s:
            target = f"https://t.me/s/{url}" if is_chan else url
            async with s.get(target, timeout=12) as r:
                if r.status != 200: return
                t = await r.text(); cand = []
                async with STATE_LOCK:
                    for m in mt_re.finditer(t):
                        pid = f"mtproto|{m.group(1)}|{m.group(2)}|{m.group(3)}"
                        if pid not in state or state[pid].get("message_id") == 0:
                            cand.append({"ip":m.group(1),"port":int(m.group(2)),"protocol":"mtproto","secret":m.group(3),"proxy_id":pid})
                    
                    raw_txt = re.findall(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", t)
                    for ip, port in raw_txt:
                        pid = f"socks5|{ip}|{port}"
                        if pid not in state or state[pid].get("message_id") == 0:
                            cand.append({"ip":ip,"port":int(port),"protocol":"socks5","proxy_id":pid})
                
                if cand:
                    unique = []
                    seen = set()
                    for c in cand:
                        if c["proxy_id"] not in seen:
                            seen.add(c["proxy_id"])
                            unique.append(c)
                    
                    if unique:
                        print(f"✨ {url}: Найдено {len(unique)}. Проверяю...")
                        await asyncio.gather(*[process_one(bot, gid, c, state, stats, session_stats) for c in unique[:30]])
    except: pass

def silence_event_loop_closed(loop):
    orig_handler = loop.get_exception_handler()
    def handler(loop, context):
        if "connection_lost" in str(context.get("message")) or "ConnectionResetError" in str(context.get("exception")): return
        if orig_handler: orig_handler(loop, context)
        else: loop.default_exception_handler(context)
    loop.set_exception_handler(handler)

async def main():
    try:
        loop = asyncio.get_running_loop(); silence_event_loop_closed(loop)
        turbo_mode = "--turbo" in sys.argv
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
        with open(PID_FILE, "w") as f: f.write(str(os.getpid()))
        from dotenv import load_dotenv
        load_dotenv()
        token, gid = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TARGET_GROUP_ID")
        mt_re = re.compile(r"server=([a-zA-Z0-9.-]+)(?:&|&amp;)port=(\d+)(?:&|&amp;)secret=([a-zA-Z0-9._~%-]+)")
        
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=None))
        
        print(f"🚀 Бот запущен! [ОБЛАЧНЫЙ СЕРВЕР | РЕЖИМ: {'ТУРБО' if turbo_mode else 'ОБЫЧНЫЙ'}]")
        loop_count = 0
        while True:
            try:
                loop_count += 1
                PROCESSING_PIDS.clear()
                print(f"\n🕒 [{datetime.now().strftime('%H:%M:%S')}] Круг {loop_count}...")
                
                state, stats = load_json(STATE_FILE), load_json(STATS_FILE)
                default_stats = {"всего_найдено": 0, "всего_отправлено": 0, "всего_удалено": 0}
                for k, v in default_stats.items(): stats.setdefault(k, v)
                session_stats = {"sent_this_run": 0}
                
                if loop_count % 3 == 0:
                    print("🔄 Перетряхиваем базу...")
                    async with STATE_LOCK:
                        state = {k: v for k, v in state.items() if isinstance(v, dict) and v.get("message_id", 0) != 0}
                        save_json(STATE_FILE, state)

                # Process Channels Immediately
                for i in range(0, len(CHANNELS), 10):
                    await asyncio.gather(*[scrape(bot, gid, ch, state, stats, session_stats, mt_re, is_chan=True) for ch in CHANNELS[i:i+10]])
                    await asyncio.sleep(0.5)

                # Process RAW URLS
                await asyncio.gather(*[scrape(bot, gid, url, state, stats, session_stats, mt_re, is_chan=False) for url in RAW_URLS])
                
                # Finalize
                async with STATE_LOCK: save_json(STATE_FILE, state)
                await sync_github(state)
                save_json(STATS_FILE, stats)
                print(f"🏁 Завершено. Отправлено {session_stats['sent_this_run']}.")
                if not turbo_mode: await asyncio.sleep(60)
            except Exception as e:
                print(f"❌ Ошибка в круге: {e}")
                await asyncio.sleep(5)
    except (KeyboardInterrupt, asyncio.CancelledError): print("\n🛑 Бот остановлен.")
    finally:
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
        try: await bot.session.close()
        except: pass

if __name__ == "__main__": asyncio.run(main())
