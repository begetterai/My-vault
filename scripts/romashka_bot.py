#!/usr/bin/env python3
"""
romashka_bot.py — интерактивный Telegram-бот для аналитики Ромашка.
Запускается на Railway (или любом сервере) и отвечает на команды 24/7.

Команды:
  /start   /помощь  — справка
  /отчет           — данные за вчера
  /месяц           — текущий месяц MTD
  /январь … /июнь  — конкретный месяц 2026
  /неделя          — последние 7 дней

Env vars:
  TELEGRAM_BOT_TOKEN — токен от @BotFather
  TELEGRAM_CHAT_ID   — только этот chat_id может управлять ботом
  ROMASHKA_SA_JSON   — JSON сервисного аккаунта Google
"""
import os, sys, json, time, datetime, logging
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s  %(message)s')
log = logging.getLogger(__name__)

TOKEN          = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
ALLOWED_CHAT   = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
SS_ID          = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'
DASHBOARD_URL  = 'https://claude.ai/code/artifact/4ae088f2-dadd-4b55-b65c-beeded5193d3'
SCOPES         = ['https://www.googleapis.com/auth/spreadsheets']

MONTHS_RU  = {'01':'январь','02':'февраль','03':'март','04':'апрель',
               '05':'май','06':'июнь','07':'июль','08':'август',
               '09':'сентябрь','10':'октябрь','11':'ноябрь','12':'декабрь'}
MONTHS_CAP = {v: k for k, v in MONTHS_RU.items()}

# ── Google Sheets ─────────────────────────────────────────────────────────────

def load_creds():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    if raw:
        info = json.loads(raw)
    else:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'scripts', 'credentials', 'romashka-drive.json')
        with open(path) as f:
            info = json.load(f)
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

_sheet_cache = {'rows': None, 'ts': 0}

def get_rows(ttl=300):
    now = time.time()
    if _sheet_cache['rows'] and now - _sheet_cache['ts'] < ttl:
        return _sheet_cache['rows']
    session = AuthorizedSession(load_creds())
    r = session.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}'
                    '/values/Данные_Poster!A2:G', timeout=30)
    r.raise_for_status()
    rows = r.json().get('values', [])
    _sheet_cache.update({'rows': rows, 'ts': now})
    return rows

# ── Telegram API ─────────────────────────────────────────────────────────────

def tg(method, **kw):
    r = requests.post(f'https://api.telegram.org/bot{TOKEN}/{method}', json=kw, timeout=20)
    return r.json()

def send(chat_id, text):
    return tg('sendMessage', chat_id=chat_id, text=text, parse_mode='HTML',
              disable_web_page_preview=True)

def typing(chat_id):
    tg('sendChatAction', chat_id=chat_id, action='typing')

# ── Report builder ───────────────────────────────────────────────────────────

def fmt(n):
    return f'{int(round(float(n or 0))):,}'.replace(',', ' ')

def report(filter_fn, title):
    rows = get_rows()
    data = {}
    for row in rows:
        if len(row) < 3:
            continue
        date, loc = row[0], row[1]
        if not filter_fn(date):
            continue
        rev  = float(row[2] or 0)
        vis  = int(row[3] or 0)  if len(row) > 3 else 0
        avck = float(row[5] or 0) if len(row) > 5 else 0
        if loc not in data:
            data[loc] = {'rev': 0, 'vis': 0, 'days': 0, 'avck': avck}
        data[loc]['rev']  += rev
        data[loc]['vis']  += vis
        data[loc]['days'] += 1
        if avck:
            data[loc]['avck'] = avck

    lines = [f'<b>{title}</b>\n']
    total = 0
    for loc in ['ЗБ', 'ОВИР']:
        d = data.get(loc)
        if d and d['rev']:
            total += d['rev']
            lines.append(f'📍 <b>{loc}</b>: {fmt(d["rev"])} с')
            if d['days'] == 1:
                if d['vis']:
                    lines.append(f'   {d["vis"]} гостей · ср.чек {fmt(d["avck"])} с')
            else:
                gpd = d['vis'] / d['days'] if d['days'] else 0
                avck_avg = d['rev'] / d['vis'] if d['vis'] else 0
                lines.append(f'   {d["days"]} дн · {d["vis"]} гостей · ср.чек {fmt(avck_avg)} с')
        else:
            lines.append(f'📍 <b>{loc}</b>: нет данных')
        lines.append('')

    if total:
        lines.append(f'💰 <b>Сеть: {fmt(total)} с</b>')

    lines.append(f'\n<a href="{DASHBOARD_URL}">📈 Полный дашборд</a>')
    return '\n'.join(lines)

# ── Command handlers ──────────────────────────────────────────────────────────

HELP_TEXT = (
    '🌸 <b>Ромашка — Аналитика</b>\n\n'
    '/отчет — данные за вчера\n'
    '/месяц — текущий месяц MTD\n'
    '/неделя — последние 7 дней\n'
    '/январь … /декабрь — месяц 2026\n'
    '/помощь — эта справка\n\n'
    f'<a href="{DASHBOARD_URL}">📈 Открыть дашборд</a>'
)

def handle_message(msg):
    chat_id = str(msg['chat']['id'])

    # Security gate
    if ALLOWED_CHAT and chat_id != ALLOWED_CHAT:
        send(chat_id, '⛔ Нет доступа.')
        return

    text = msg.get('text', '').strip().lower()
    # Strip bot username from command
    cmd = text.split()[0].split('@')[0] if text else ''

    today     = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    typing(chat_id)

    if cmd in ('/start', '/помощь', '/help'):
        send(chat_id, HELP_TEXT)

    elif cmd in ('/отчет', '/вчера', '/report', '/today'):
        yday = str(yesterday)
        mon  = MONTHS_RU.get(yesterday.strftime('%m'), '')
        send(chat_id, report(lambda d: d == yday,
            f'🌸 {yesterday.strftime("%d.%m.%Y")} · {mon.capitalize()}'))

    elif cmd in ('/месяц', '/month', '/mtd'):
        pref = today.strftime('%Y-%m')
        mon  = MONTHS_RU.get(today.strftime('%m'), '')
        send(chat_id, report(lambda d: d.startswith(pref),
            f'📊 {mon.capitalize()} {today.year} (MTD, {today.day} дн.)'))

    elif cmd in ('/неделя', '/week'):
        week_ago = today - datetime.timedelta(days=7)
        dates = {str(week_ago + datetime.timedelta(days=i)) for i in range(7)}
        send(chat_id, report(lambda d: d in dates,
            f'📅 Последние 7 дней ({week_ago.strftime("%d.%m")}–{yesterday.strftime("%d.%m")})'))

    else:
        # Month name command: /январь, /февраль, etc.
        word = cmd.lstrip('/')
        if word in MONTHS_CAP:
            mnum = MONTHS_CAP[word]
            year = today.year
            pref = f'{year}-{mnum}'
            mon  = MONTHS_RU[mnum]
            send(chat_id, report(lambda d: d.startswith(pref),
                f'📊 {mon.capitalize()} {year}'))
        else:
            send(chat_id, '❓ Неизвестная команда. /помощь — список команд.')

# ── Long-polling loop ─────────────────────────────────────────────────────────

def run():
    if not TOKEN:
        log.error('TELEGRAM_BOT_TOKEN не задан')
        sys.exit(1)

    log.info('🌸 Ромашка-бот запущен (long-polling)...')

    # Send startup notification
    if ALLOWED_CHAT:
        try:
            send(ALLOWED_CHAT, '🌸 Ромашка-бот запущен. /помощь — команды.')
        except Exception:
            pass

    offset = 0
    while True:
        try:
            res = tg('getUpdates', offset=offset, timeout=25,
                     allowed_updates=['message'])
            for upd in (res.get('result') or []):
                offset = upd['update_id'] + 1
                if 'message' in upd:
                    try:
                        handle_message(upd['message'])
                    except Exception as e:
                        log.error(f'handle_message error: {e}')
        except requests.RequestException as e:
            log.warning(f'Network error: {e}')
            time.sleep(5)
        except Exception as e:
            log.error(f'Unexpected error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    run()
