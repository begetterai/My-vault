#!/usr/bin/env python3
"""
romashka_daily_digest.py — ежедневный дайджест Ромашка в Telegram.
Запускается GitHub Actions каждое утро в 09:00 Душанбе.

Env vars (обязательные):
  TELEGRAM_BOT_TOKEN  — токен бота от @BotFather
  TELEGRAM_CHAT_ID    — chat_id получателя (узнать через /getid у @userinfobot)
  ROMASHKA_SA_JSON    — JSON сервисного аккаунта (или файл credentials/romashka-drive.json)
"""
import os, sys, json, datetime
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

ROMASHKA_SS_ID = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'
DASHBOARD_URL  = 'https://claude.ai/code/artifact/4ae088f2-dadd-4b55-b65c-beeded5193d3'
SCOPES         = ['https://www.googleapis.com/auth/spreadsheets']

MONTHS_RU = {
    '01':'Январь','02':'Февраль','03':'Март','04':'Апрель',
    '05':'Май','06':'Июнь','07':'Июль','08':'Август',
    '09':'Сентябрь','10':'Октябрь','11':'Ноябрь','12':'Декабрь',
}

def load_creds():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    if raw:
        return service_account.Credentials.from_service_account_info(
            json.loads(raw), scopes=SCOPES)
    creds_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'scripts', 'credentials', 'romashka-drive.json')
    return service_account.Credentials.from_service_account_file(creds_file, scopes=SCOPES)

def get_poster_rows():
    import time
    session = AuthorizedSession(load_creds())
    for attempt in range(5):
        r = session.get(
            f'https://sheets.googleapis.com/v4/spreadsheets/{ROMASHKA_SS_ID}/values/'
            'Данные_Poster!A2:G', timeout=30)
        if r.status_code >= 500 and attempt < 4:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json().get('values', [])

def fmt(n):
    return f'{int(round(float(n or 0))):,}'.replace(',', ' ')

def tg_send(token, chat_id, text):
    r = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML',
              'disable_web_page_preview': True},
        timeout=15)
    r.raise_for_status()
    return r.json()

def build_message(rows, target_date, today):
    yday_str  = str(target_date)
    month_str = target_date.strftime('%Y-%m')
    mon_name  = MONTHS_RU.get(target_date.strftime('%m'), '')

    yday  = {}   # {loc: {rev, vis, avck}}
    month = {}   # {loc: {rev, vis, days}}

    for row in rows:
        if len(row) < 3:
            continue
        date, loc = row[0], row[1]
        rev  = float(row[2] or 0)
        vis  = int(row[3] or 0) if len(row) > 3 else 0
        avck = float(row[5] or 0) if len(row) > 5 else 0

        if date == yday_str:
            yday[loc] = {'rev': rev, 'vis': vis, 'avck': avck}

        if date.startswith(month_str):
            if loc not in month:
                month[loc] = {'rev': 0, 'vis': 0, 'days': 0}
            month[loc]['rev']  += rev
            month[loc]['vis']  += vis
            month[loc]['days'] += 1

    lines = [f'🌸 <b>Ромашка — {target_date.strftime("%d.%m.%Y")}</b>\n']

    # Yesterday per location
    total_yday = 0
    for loc in ['ЗБ', 'ОВИР']:
        d = yday.get(loc)
        if d and d['rev']:
            total_yday += d['rev']
            lines.append(f'📍 <b>{loc}</b>: {fmt(d["rev"])} с')
            if d['vis']:
                lines.append(f'   {d["vis"]} гостей · ср.чек {fmt(d["avck"])} с')
        else:
            lines.append(f'📍 <b>{loc}</b>: нет данных за вчера')
        lines.append('')

    if total_yday:
        lines.append(f'💰 Вчера сеть: <b>{fmt(total_yday)} с</b>\n')

    # Month to date
    days_in = max((month.get(l, {}).get('days', 0) for l in ['ЗБ', 'ОВИР']), default=0)
    if days_in:
        lines.append(f'📊 <b>{mon_name} {target_date.year}</b> ({days_in} дн. MTD)')
        net_month = 0
        for loc in ['ЗБ', 'ОВИР']:
            md = month.get(loc, {})
            if md.get('rev'):
                net_month += md['rev']
                lines.append(f'   {loc}: {fmt(md["rev"])} с')
        if net_month:
            lines.append(f'   <b>Сеть: {fmt(net_month)} с</b>')

    lines.append(f'\n<a href="{DASHBOARD_URL}">📈 Открыть полный дашборд</a>')
    return '\n'.join(lines)

def main():
    token   = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat_id:
        print('❌ TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID должны быть заданы в env vars')
        sys.exit(1)

    today     = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    print(f'Загружаем данные из Google Sheet...')
    rows = get_poster_rows()
    print(f'  Строк: {len(rows)}')

    msg = build_message(rows, yesterday, today)
    print('Отправляем в Telegram...')
    tg_send(token, chat_id, msg)
    print(f'✅ Дайджест отправлен за {yesterday}')

if __name__ == '__main__':
    main()
