#!/usr/bin/env python3
"""Единый стандарт оформления документов «Ромашка Стрит Фуд».
Все документы системы собираются ТОЛЬКО через эти функции — тогда вид одинаковый
не по договорённости, а технически.

Правило оформления Азиза: Times New Roman 13, без цветовой заливки, только белый фон.
Жирный и рамки — разрешены (это не цвет).
"""
import os, json
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CRED = '/home/user/My-vault/scripts/credentials/romashka-drive.json'
USER = 'base@azizkhaidarov.com'
DRIVE_ID = '0AA2YI8glLw-eUk9PVA'
SC = ['https://www.googleapis.com/auth/drive',
      'https://www.googleapis.com/auth/spreadsheets',
      'https://www.googleapis.com/auth/documents']

def session():
    return AuthorizedSession(service_account.Credentials
        .from_service_account_file(CRED, scopes=SC).with_subject(USER))

COMPANY = 'РОМАШКА СТРИТ ФУД'

# ── ЕДИНЫЙ СТИЛЬ ─────────────────────────────────────────────────────────────
STYLE = """<style>
@page { size: A4 portrait; margin: 16mm 14mm; }
body { font-family: 'Times New Roman', serif; font-size: 13pt; line-height: 1.15;
       color: #000; background: #fff; }
.rk-top { border-bottom: 2px solid #000; padding-bottom: 5pt; margin-bottom: 11pt; }
.rk-co  { font-size: 10.5pt; letter-spacing: 1.6pt; font-weight: bold; }
.rk-kind{ font-size: 10.5pt; }
h1 { font-size: 17pt; margin: 0 0 3pt 0; }
h2 { font-size: 13.5pt; margin: 14pt 0 4pt 0; }
h3 { font-size: 13pt; font-weight: bold; margin: 12pt 0 3pt 0; }
p  { margin: 0 0 4pt 0; }
ul, ol { margin: 0 0 7pt 0; padding-left: 17pt; }
li { margin-bottom: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 5pt 0 9pt 0;
        font-size: 12pt; }
th, td { border: 1px solid #000; padding: 2.5pt 5pt; vertical-align: top;
         background: #fff; }
th { font-weight: bold; text-align: left; }
.meta td, .meta th { font-size: 11.5pt; padding: 3pt 6pt; }
.meta th { width: 27%; }
.num  { text-align: center; width: 5%; }
.what { width: 38%; }
.norm { width: 15%; font-size: 11pt; }
.cmt  { width: 22%; }
.mark { text-align: center; width: 10%; }
.markw{ text-align: center; width: 10%; }
.small{ font-size: 11pt; }
.note { font-size: 11.5pt; font-style: italic; }
.sign { margin-top: 9pt; font-size: 12pt; }
</style>"""


def header(meta):
    """Единая шапка: компания · тип документа · код · название · мета-таблица."""
    m = meta
    return f"""<div class="rk-top">
  <span class="rk-co">{COMPANY}</span>
  &nbsp;·&nbsp;<span class="rk-kind">{m['kind']}</span>
  &nbsp;·&nbsp;<span class="rk-kind"><b>{m['code']}</b></span>
</div>
<h1>{m['title']}</h1>
<table class="meta">
<tr><th>Версия</th><td>{m.get('version','v1.0')}</td></tr>
<tr><th>Дата ввода</th><td>{m.get('date','')}</td></tr>
<tr><th>Владелец документа</th><td>{m.get('owner','')}</td></tr>
<tr><th>Утвердил</th><td>{m.get('approved','COO')}</td></tr>
<tr><th>Дата пересмотра</th><td>{m.get('review','')}</td></tr>
<tr><th>Область действия</th><td>{m.get('scope','ЗБ · ОВИР')}</td></tr>
<tr><th>Кому обязателен</th><td>{m.get('who','')}</td></tr>
</table>"""


def footer(control, violation, rows=8):
    """Единый подвал: контроль · нарушение · лист ознакомления."""
    ctl = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in control.items())
    vio = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in violation)
    sign = "".join("<tr><td class='num'>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td>"
                   "<td>&nbsp;</td><td>&nbsp;</td></tr>" for _ in range(rows))
    return f"""<h2>Контроль</h2>
<table class="meta">{ctl}</table>
<h2>Нарушение</h2>
<table><tr><th style="width:58%">Что считается нарушением</th>
<th>Мера по дисциплинарной сетке</th></tr>{vio}</table>
<h2>Лист ознакомления</h2>
<p class="note">Сотрудник, не подписавший лист, считается не ознакомленным — спрашивать
с него за нарушение этого документа нельзя.</p>
<table><tr><th class="num">№</th><th>ФИО</th><th style="width:21%">Должность</th>
<th style="width:14%">Дата</th><th style="width:18%">Подпись</th></tr>{sign}</table>"""


def build_html(meta, body, control, violation, sign_rows=8):
    """Собрать полный документ в едином стандарте."""
    return (STYLE + header(meta) + body
            + footer(control, violation, sign_rows))


# ── Drive ────────────────────────────────────────────────────────────────────
def find(s, name, parent):
    r = s.get('https://www.googleapis.com/drive/v3/files', params={
        'q': f"name='{name}' and '{parent}' in parents and trashed=false",
        'fields': 'files(id)', 'driveId': DRIVE_ID, 'corpora': 'drive',
        'includeItemsFromAllDrives': 'true', 'supportsAllDrives': 'true'}, timeout=30)
    f = r.json().get('files', [])
    return f[0]['id'] if f else None


def folder_by_name(s, name, parent):
    return find(s, name, parent)


def put_doc(s, name, parent, html, replace=True):
    """Создать/обновить Google Doc из HTML. Возвращает (id, 'создан'|'обновлён')."""
    data = html.encode('utf-8')
    ex = find(s, name, parent)
    if ex and replace:
        r = s.patch(f'https://www.googleapis.com/upload/drive/v3/files/{ex}',
            params={'uploadType': 'media', 'supportsAllDrives': 'true'},
            headers={'Content-Type': 'text/html'}, data=data, timeout=120)
        r.raise_for_status()
        return ex, 'обновлён'
    if ex:
        return ex, 'уже был'
    meta = {'name': name, 'parents': [parent],
            'mimeType': 'application/vnd.google-apps.document'}
    b = '----rk'
    body = (f'--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'
            + json.dumps(meta) + f'\r\n--{b}\r\nContent-Type: text/html\r\n\r\n').encode() \
           + data + f'\r\n--{b}--'.encode()
    r = s.post('https://www.googleapis.com/upload/drive/v3/files',
        params={'uploadType': 'multipart', 'supportsAllDrives': 'true'},
        headers={'Content-Type': f'multipart/related; boundary={b}'}, data=body, timeout=120)
    r.raise_for_status()
    return r.json()['id'], 'создан'


def enforce_font(s, doc_id, family='Times New Roman'):
    """Проставить Times New Roman по всему документу.

    Тонкость Docs API: weightedFontFamily несёт weight=400 и тем самым снимает
    жирность с заголовков и <th>. Поэтому: запоминаем жирные фрагменты ДО,
    ставим шрифт, возвращаем жирность ПОСЛЕ.
    """
    d = s.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', timeout=30).json()

    bold_ranges = []
    def walk(content):
        for e in content:
            p = e.get('paragraph')
            if p:
                heading = p.get('paragraphStyle', {}).get('namedStyleType', '')
                is_head = heading.startswith('HEADING') or heading == 'TITLE'
                for el in p.get('elements', []):
                    tr = el.get('textRun')
                    if not tr:
                        continue
                    if (tr.get('textStyle', {}).get('bold') or is_head) \
                       and el['endIndex'] - el['startIndex'] > 0:
                        bold_ranges.append((el['startIndex'], el['endIndex']))
            t = e.get('table')
            if t:
                for row in t.get('tableRows', []):
                    for cell in row.get('tableCells', []):
                        walk(cell.get('content', []))
    walk(d['body']['content'])

    end = max(e.get('endIndex', 1) for e in d['body']['content'])
    if end < 3:
        return 0

    reqs = [{'updateTextStyle': {
        'range': {'startIndex': 1, 'endIndex': end - 1},
        'textStyle': {'weightedFontFamily': {'fontFamily': family}},
        'fields': 'weightedFontFamily'}}]
    for a_, b_ in bold_ranges:
        reqs.append({'updateTextStyle': {
            'range': {'startIndex': a_, 'endIndex': b_},
            'textStyle': {'bold': True,
                          'weightedFontFamily': {'fontFamily': family, 'weight': 700}},
            'fields': 'bold,weightedFontFamily'}})
    for i in range(0, len(reqs), 300):
        s.post(f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
               json={'requests': reqs[i:i+300]}, timeout=60).raise_for_status()
    return len(bold_ranges)


def add_footer(s, doc_id, text):
    """Колонтитул внизу каждой страницы: код · название · версия.
    Через HTML не задаётся — только Docs API."""
    d = s.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', timeout=30).json()
    fid = None
    for k, v in (d.get('footers') or {}).items():
        fid = k
        break
    if not fid:
        r = s.post(f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
                   json={'requests': [{'createFooter': {'type': 'DEFAULT'}}]}, timeout=30)
        r.raise_for_status()
        fid = r.json()['replies'][0]['createFooter']['footerId']
    else:
        # очистить старое содержимое колонтитула
        d2 = s.get(f'https://docs.googleapis.com/v1/documents/{doc_id}', timeout=30).json()
        cont = d2['footers'][fid]['content']
        end = max(e.get('endIndex', 1) for e in cont)
        if end > 2:
            s.post(f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
                   json={'requests': [{'deleteContentRange': {'range': {
                       'segmentId': fid, 'startIndex': 1, 'endIndex': end - 1}}}]},
                   timeout=30).raise_for_status()
    reqs = [
      {'insertText': {'location': {'segmentId': fid, 'index': 0}, 'text': text}},
      {'updateTextStyle': {
        'range': {'segmentId': fid, 'startIndex': 0, 'endIndex': len(text)},
        'textStyle': {'weightedFontFamily': {'fontFamily': 'Times New Roman'},
                      'fontSize': {'magnitude': 9, 'unit': 'PT'},
                      'foregroundColor': {'color': {'rgbColor': {'red': .35, 'green': .35, 'blue': .35}}}},
        'fields': 'weightedFontFamily,fontSize,foregroundColor'}},
    ]
    s.post(f'https://docs.googleapis.com/v1/documents/{doc_id}:batchUpdate',
           json={'requests': reqs}, timeout=30).raise_for_status()
    return fid


def footer_text(meta):
    """Единый текст колонтитула."""
    return f"{meta['code']} · {meta['title']} · {meta.get('version','v1.0')}"


def registry_update(s, sheet_id, code, status=None, version=None,
                    date=None, review=None, link=None):
    """Обновить строку документа в реестре по коду."""
    v = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/A1:M200',
              timeout=30).json().get('values', [])
    for i, row in enumerate(v[1:], 2):
        if row and row[0] == code:
            data = []
            if status:  data.append({'range': f'E{i}', 'values': [[status]]})
            if version: data.append({'range': f'H{i}', 'values': [[version]]})
            if date:    data.append({'range': f'I{i}', 'values': [[date]]})
            if review:  data.append({'range': f'J{i}', 'values': [[review]]})
            if link:    data.append({'range': f'K{i}', 'values': [[link]]})
            if data:
                s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchUpdate',
                       json={'valueInputOption': 'USER_ENTERED', 'data': data}, timeout=30
                       ).raise_for_status()
            return True
    return False
