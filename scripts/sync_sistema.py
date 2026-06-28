#!/usr/bin/env python3
"""
Синхронизация: Google Sheet «Система — Подписки» → 1-Projects/sistema/подписки.md
Данные (суммы, даты) — источник истины в Drive. В Obsidian подтягивается только снимок;
статусы/решения/задачи остаются ручными и не затрагиваются.
"""
import os, datetime, subprocess
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

VAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS = os.path.join(VAULT_ROOT, 'scripts', 'credentials', 'romashka-drive.json')
SS_ID = '1tP1xPKU6BO3w9zbhru7dhAsk5nijDl_9Ii9tyF9SAYo'
NOTE_PATH = os.path.join(VAULT_ROOT, '1-Projects', 'sistema', 'подписки.md')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

SYNC_START = '<!-- DRIVE-SYNC:START -->'
SYNC_END = '<!-- DRIVE-SYNC:END -->'


def get_values(session, rng):
    r = session.get(
        f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/{rng}',
        timeout=30)
    r.raise_for_status()
    return r.json().get('values', [])


def fmt_amount(v):
    try:
        return f'{float(v):.2f}'
    except (TypeError, ValueError):
        return v


def build_table(headers, rows):
    lines = ['| ' + ' | '.join(headers) + ' |', '|' + '|'.join(['---'] * len(headers)) + '|']
    for row in rows:
        row = row + [''] * (len(headers) - len(row))
        lines.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(lines)


def totals_by_currency(rows, amount_idx, currency_idx):
    totals = {}
    for row in rows:
        amt = float(row[amount_idx])
        cur = row[currency_idx]
        totals[cur] = totals.get(cur, 0) + amt
    return totals


def main():
    creds = service_account.Credentials.from_service_account_file(CREDS, scopes=SCOPES)
    session = AuthorizedSession(creds)

    active_raw = get_values(session, "'Подписки'!A1:F50")
    cancelled_raw = get_values(session, "'Отменённые'!A1:C50")

    active_headers, active_rows = active_raw[0], active_raw[1:]
    cancelled_headers, cancelled_rows = cancelled_raw[0], cancelled_raw[1:]

    display_active = [[r[0], f'${fmt_amount(r[1])}' if r[2] == 'USD' else f'{fmt_amount(r[1])} {r[2]}', r[3], r[4], r[5]]
                       for r in active_rows]
    display_headers = ['Сервис', 'Сумма', 'Периодичность', 'Дата списания', 'Способ оплаты']

    totals = totals_by_currency(active_rows, 1, 2)
    totals_str = ' + '.join(f'${v:.2f}' if cur == 'USD' else f'{v:.2f} {cur}' for cur, v in totals.items())

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    block = (
        f'{SYNC_START}\n'
        f'## Активные подписки\n\n'
        f'*Снимок из Google Sheet, обновлено: {now}*\n\n'
        f'{build_table(display_headers, display_active)}\n\n'
        f'**Итого известно: {totals_str}/мес**\n\n'
        f'## Отменённые\n\n'
        f'{build_table(cancelled_headers, cancelled_rows)}\n'
        f'{SYNC_END}'
    )

    with open(NOTE_PATH, encoding='utf-8') as f:
        content = f.read()

    start = content.index(SYNC_START)
    end = content.index(SYNC_END) + len(SYNC_END)
    new_content = content[:start] + block + content[end:]

    if new_content == content:
        print('Без изменений — пропускаю commit.')
        return

    with open(NOTE_PATH, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f'✅ Обновлён {NOTE_PATH}')

    subprocess.run(['./cli.sh', 'sync'], cwd=VAULT_ROOT, check=True)


if __name__ == '__main__':
    main()
