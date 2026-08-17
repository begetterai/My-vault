#!/usr/bin/env python3
"""
romashka_agent.py — Telegram-агент Ромашки.
Азиз шлёт голос/текст → агент понимает → делает (Notion/Sheet/Poster) → отвечает.

Провайдер мозга и расшифровки: Groq (бесплатно, OpenAI-совместимый) по умолчанию,
Anthropic — если задан ANTHROPIC_API_KEY (умнее, платно).

ENV:
  TELEGRAM_BOT_TOKEN   — токен бота
  TELEGRAM_CHAT_ID     — единственный разрешённый chat_id
  GROQ_API_KEY         — ключ Groq (мозг + Whisper)
  ANTHROPIC_API_KEY    — опционально, мозг на Claude
  ROMASHKA_SA_JSON     — сервисный аккаунт Google (или файл)
  NOTION_TOKEN         — токен Notion (или файл credentials/notion.token)
  NOTION_IDS_JSON      — {tdb,sdb,vdb} (или файл credentials/notion_ids.json)
Запуск: python3 scripts/romashka_agent.py
"""
import os, sys, re, json, time, logging, datetime, urllib.parse
os.environ.setdefault('REQUESTS_CA_BUNDLE', '/etc/ssl/certs/ca-certificates.crt')
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('agent')

# ── Config ────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRED = os.path.join(ROOT, 'scripts', 'credentials')
def _read(name):
    p = os.path.join(CRED, name)
    return open(p).read().strip() if os.path.exists(p) else ''

TG_TOKEN   = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip() or _read('telegram.token')
ALLOWED    = os.environ.get('TELEGRAM_CHAT_ID', '').strip() or _read('telegram_chat_id.txt')
GROQ_KEY   = os.environ.get('GROQ_API_KEY', '').strip() or _read('groq.token')
ANTHRO_KEY = os.environ.get('ANTHROPIC_API_KEY', '').strip() or _read('anthropic.token')

SS_ID = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'
AUDIT_TAB = 'Аудит_агента'
TZ_OFFSET = datetime.timedelta(hours=5)  # Душанбе UTC+5 (сервер в UTC)
def now_local():  return datetime.datetime.utcnow() + TZ_OFFSET
def today_local(): return now_local().date()
POSTER = {'ЗБ':'398711:8746917c4a23ea897774040e039dfb76',
          'ОВИР':'935215:79675564e3d086d7e03d5fd56b50c8df'}

NOTION_TOKEN = os.environ.get('NOTION_TOKEN','').strip() or _read('notion.token')
try:
    NIDS = json.loads(os.environ.get('NOTION_IDS_JSON','') or open(os.path.join(CRED,'notion_ids.json')).read())
except Exception:
    NIDS = {}
NH = {'Authorization': f'Bearer {NOTION_TOKEN}', 'Notion-Version':'2022-06-28', 'Content-Type':'application/json'}

def load_sa():
    raw = os.environ.get('ROMASHKA_SA_JSON')
    info = json.loads(raw) if raw else json.load(open(os.path.join(CRED,'romashka-drive.json')))
    return service_account.Credentials.from_service_account_info(
        info, scopes=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive'])
SHEETS = AuthorizedSession(load_sa())

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg(method, **kw):
    return requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/{method}', json=kw, timeout=25).json()
def send(text):
    tg('sendMessage', chat_id=ALLOWED, text=text, parse_mode='HTML', disable_web_page_preview=True)
def typing():
    tg('sendChatAction', chat_id=ALLOWED, action='typing')

# ── Файлы: Telegram → Google Drive + обратная связь ───────────────────────────
def _tg_download(file_id):
    info = tg('getFile', file_id=file_id)
    path = info['result']['file_path']
    return requests.get(f'https://api.telegram.org/file/bot{TG_TOKEN}/{path}', timeout=120).content, path

def drive_upload(name, content, mime):
    folder = NIDS.get('drive_files')
    meta = {'name': name, 'parents': [folder]} if folder else {'name': name}
    files = {'data':('m', json.dumps(meta), 'application/json'), 'file':(name, content, mime)}
    r = SHEETS.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,webViewLink',
                    files=files, timeout=120)
    r.raise_for_status(); return r.json()

TEXT_EXT = ('.txt','.csv','.md','.log','.json')
def extract_text(name, content, mime):
    import io
    n = name.lower()
    try:
        if n.endswith(TEXT_EXT) or (mime or '').startswith('text/'):
            return content.decode('utf-8', errors='replace')[:8000]
        if n.endswith('.pdf'):
            from pypdf import PdfReader
            rd = PdfReader(io.BytesIO(content))
            return '\n'.join((p.extract_text() or '') for p in rd.pages)[:8000]
        if n.endswith('.docx'):
            import docx
            d = docx.Document(io.BytesIO(content))
            return '\n'.join(p.text for p in d.paragraphs)[:8000]
        if n.endswith(('.xlsx','.xlsm')):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
            out=[]
            for ws in wb.worksheets[:3]:
                out.append(f'[Лист {ws.title}]')
                for i,row in enumerate(ws.iter_rows(values_only=True)):
                    if i>=40: break
                    out.append(' | '.join('' if c is None else str(c) for c in row))
            return '\n'.join(out)[:8000]
    except Exception as e:
        return f'(не смог прочитать содержимое: {e})'
    return ''

def plain_llm(prompt):
    """Чистый ответ LLM без инструментов — для анализа и обратной связи."""
    r=requests.post('https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization':f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
        json={'model':'llama-3.3-70b-versatile','temperature':0.3,
              'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}]},timeout=60)
    r.raise_for_status()
    return r.json()['choices'][0]['message'].get('content','').strip()

def analyze_receipt(content):
    """Читает фото чека через Claude vision → {total, merchant, category, summary}. Нужен ANTHROPIC_API_KEY."""
    import base64
    b64 = base64.b64encode(content).decode()
    cats = "Дом,Машина,Гаджеты,Подписки,Кафе,Продукты,Лечение / Медикаменты,Спортивное питание,Абонемент в зал,БАДы,Массаж / Сауна,Курение,Одежда/Обувь,Развлечение,Обучение,Семья,Подарки,Путешествие,Прочее"
    q = ('Это фото чека/квитанции. Верни СТРОГО JSON без пояснений: '
         '{"total": число_итого, "merchant": "магазин/место", '
         f'"category": "одна из: {cats}", "summary": "кратко что куплено"}}. '
         'Если сумма не видна — total:0.')
    r = requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key':ANTHRO_KEY,'anthropic-version':'2023-06-01','content-type':'application/json'},
        json={'model':'claude-3-5-sonnet-20241022','max_tokens':400,
              'messages':[{'role':'user','content':[
                {'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':b64}},
                {'type':'text','text':q}]}]}, timeout=60)
    r.raise_for_status()
    txt=''.join(b.get('text','') for b in r.json().get('content',[]) if b.get('type')=='text')
    import re
    m=re.search(r'\{.*\}', txt, re.S)
    return json.loads(m.group(0)) if m else {}

def analyze_image(content, caption=''):
    """Анализ фото через Claude vision (нужен ANTHROPIC_API_KEY)."""
    import base64
    b64 = base64.b64encode(content).decode()
    q = caption or ('Ты контролируешь кафе «Ромашка». Опиши, что на фото, и отметь нарушения: '
                    'чистота, перчатки, порядок, поведение персонала. Кратко, по делу.')
    r = requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key':ANTHRO_KEY,'anthropic-version':'2023-06-01','content-type':'application/json'},
        json={'model':'claude-3-5-sonnet-20241022','max_tokens':500,
              'messages':[{'role':'user','content':[
                {'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':b64}},
                {'type':'text','text':q}]}]}, timeout=60)
    r.raise_for_status()
    return ''.join(b.get('text','') for b in r.json().get('content',[]) if b.get('type')=='text').strip()

def handle_file(name, content, mime, caption=''):
    up = drive_upload(name, content, mime)
    link = up.get('webViewLink','')
    reply = f'📎 Сохранил на Drive: <a href="{link}">{name}</a>'
    text = extract_text(name, content, mime)
    if text:
        prompt = (caption+'\n\n' if caption else 'Дай короткую деловую обратную связь: что важное, что настораживает.\n\n')+f'Файл «{name}»:\n{text}'
        try: reply += '\n\n'+plain_llm(prompt)
        except Exception as e: reply += f'\n(не смог разобрать содержимое: {e})'
    return reply

# ── Расшифровка голоса (Groq Whisper) ─────────────────────────────────────────
# Словарь-подсказка Whisper — термины Ромашки, чтобы узнавал имена и жаргон
WHISPER_PROMPT = ('Ромашка, ЗБ, ОВИР, Лохути, Турсунзода, Владимир, Дилчу, Азиз, Махмуд, '
 'касса, инкассация, поставка, шаурма, бариста, повар, кассир, смена, нарушение, '
 'выручка, план, факт, Beeyor, Алиф, Душанбе, food cost, перчатки, техкарта.')

def transcribe(file_id):
    info = tg('getFile', file_id=file_id)
    path = info['result']['file_path']
    audio = requests.get(f'https://api.telegram.org/file/bot{TG_TOKEN}/{path}', timeout=60).content
    r = requests.post('https://api.groq.com/openai/v1/audio/transcriptions',
        headers={'Authorization': f'Bearer {GROQ_KEY}'},
        files={'file': ('audio.ogg', audio, 'audio/ogg')},
        data={'model':'whisper-large-v3','language':'ru','prompt':WHISPER_PROMPT,'temperature':'0'}, timeout=90)
    r.raise_for_status()
    return r.json().get('text','').strip()

# ── Инструменты агента ────────────────────────────────────────────────────────
def _notion_post(path, payload):
    r = requests.post(f'https://api.notion.com/v1/{path}', headers=NH, json=payload, timeout=30)
    r.raise_for_status(); return r.json()

def tool_add_task(title, kind='тактическая', assignee=None, due=None, **_):
    db = NIDS.get('sdb') if kind.startswith('страт') else NIDS.get('tdb')
    props = {'Задача':{'title':[{'text':{'content':title}}]}}
    if kind.startswith('страт'):
        props['Статус']={'select':{'name':'Не начато'}}
    else:
        props['Статус']={'select':{'name':'Не начато'}}
        if assignee: props['Кто']={'select':{'name':assignee}}
        if due: props['Срок']={'date':{'start':due}}
    _notion_post('pages', {'parent':{'database_id':db},'properties':props})
    return f'✅ Задача добавлена ({kind}): {title}'

def tool_add_violation(point, description, employee=None, category='Прочее', **_):
    props = {'Нарушение':{'title':[{'text':{'content':description}}]},
             'Дата':{'date':{'start':str(today_local())}},
             'Точка':{'select':{'name':point}},
             'Категория':{'select':{'name':category}},
             'Статус':{'select':{'name':'Новое'}}}
    if employee: props['Сотрудник']={'rich_text':[{'text':{'content':employee}}]}
    _notion_post('pages', {'parent':{'database_id':NIDS.get('vdb')},'properties':props})
    who = f' ({employee})' if employee else ''
    return f'🚨 Нарушение записано — {point}{who}: {description}'

def _sheet_rows():
    r = SHEETS.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Данные_Poster!A2:K', timeout=30)
    r.raise_for_status(); return r.json().get('values',[])

def tool_revenue_channels(period='месяц', **_):
    """Разбивка выручки по каналам (В заведении/Навынос/Доставка) + СНБЖ за период."""
    rows=_sheet_rows(); today=today_local(); yday=today-datetime.timedelta(days=1)
    if period.startswith('нед'):
        keys={str(yday-datetime.timedelta(days=i)) for i in range(7)}; sel=lambda d:d in keys; lab='за 7 дней'
    elif period.startswith('год'):
        sel=lambda d:d.startswith(str(today.year)); lab='за год'
    elif period.startswith('дн') or period.startswith('вчер'):
        sel=lambda d:d==str(yday); lab=f'за вчера ({yday.strftime("%d.%m")})'
    else:
        sel=lambda d:d.startswith(today.strftime('%Y-%m')); lab='за месяц'
    acc={'зал':0.0,'навынос':0.0,'доставка':0.0,'снбж':0.0}
    for r in rows:
        if len(r)<11 or not sel(r[0]): continue
        for i,n in [(7,'зал'),(8,'навынос'),(9,'доставка'),(10,'снбж')]:
            try: acc[n]+=float(r[i] or 0)
            except: pass
    f=lambda n: f'{int(round(n)):,}'.replace(',',' ')
    retail=acc['зал']+acc['навынос']+acc['доставка']
    return (f'📊 Каналы {lab}:\n🍽 В заведении: {f(acc["зал"])} с\n🥡 Навынос: {f(acc["навынос"])} с\n'
            f'🛵 Доставка: {f(acc["доставка"])} с\n— Розница: {f(retail)} с\n🔄 СНБЖ (не в выручке): {f(acc["снбж"])} с')

def tool_get_revenue(period='день', **_):
    rows = _sheet_rows()
    today = today_local(); yday = today - datetime.timedelta(days=1)
    acc = {'ЗБ':0.0,'ОВИР':0.0}
    if period.startswith('нед'):
        keys = {str(yday-datetime.timedelta(days=i)) for i in range(7)}
        sel = lambda d: d in keys; label='за 7 дней'
    elif period.startswith('мес'):
        sel = lambda d: d.startswith(today.strftime('%Y-%m')); label='за месяц (MTD)'
    elif period.startswith('год'):
        sel = lambda d: d.startswith(str(today.year)); label='за год (YTD)'
    else:
        sel = lambda d: d==str(yday); label=f'за вчера ({yday.strftime("%d.%m")})'
    for r in rows:
        if len(r)<3: continue
        if r[1] in acc and sel(r[0]):
            try: acc[r[1]]+=float(r[2] or 0)
            except: pass
    f=lambda n: f'{int(round(n)):,}'.replace(',',' ')
    return (f'💰 Выручка {label}:\nЗБ: {f(acc["ЗБ"])} с\nОВИР: {f(acc["ОВИР"])} с\n'
            f'Сеть: {f(acc["ЗБ"]+acc["ОВИР"])} с')

def tool_poster_query(metric='расходы', category=None, date_from=None, date_to=None, **_):
    df = date_from or str(today_local().replace(day=1))
    dt = date_to or str(today_local())
    out=[]
    for loc,tok in POSTER.items():
        url=f'https://joinposter.com/api/finance.getTransactions?{urllib.parse.urlencode(dict(token=tok,dateFrom=df,dateTo=dt))}'
        txs=[t for t in requests.get(url,timeout=60).json().get('response',[]) if t.get('delete')!='1']
        s=0.0
        for t in txs:
            cat=(t.get('category_name') or '')
            amt=float(t['amount'])/100
            if category and category.lower() not in cat.lower(): continue
            if metric.startswith('расход') and amt<0: s+=-amt
            elif metric.startswith('выруч') and amt>0 and cat=='Кассовые смены': s+=amt
        out.append(f'{loc}: {int(round(s)):,}'.replace(',',' ')+' с')
    cat_lbl = f' по «{category}»' if category else ''
    return f'📊 {metric.capitalize()}{cat_lbl} {df}…{dt}:\n'+'\n'.join(out)

BUDGET_SS = '1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
BUDGET_CATS = {'Дом','Машина','Гаджеты','Подписки','Рассрочка','Кафе','Продукты','Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна','Курение','Одежда/Обувь','Развлечение','Обучение','Семья','Подарки','Путешествие','Прочее'}
DEBT_CATS = {'Оплата кредита'}  # тип «Погашение» — вне расходов (зона «Сбережения и долг»)
INCOME_CATS = {'Зарплата','Прочий доход'}
SAVINGS_CATS = {'Накопления / Подушка','Инвестиции'}  # тип «Накопление» — вне расходов
def _budget_append(tab, row):
    # USER_ENTERED — дата (ISO) становится настоящей датой, суммы числами; месяца-колонки больше нет
    r = SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{BUDGET_SS}/values/{tab}:append'
        '?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS', json={'values':[row]}, timeout=30)
    r.raise_for_status()
    # держим журнал отсортированным по дате, а не по порядку ввода (Loans — только A:E, сводку G:H не трогаем)
    gid={'Operations':0,'Loans':215071340}.get(tab.split('!')[0])
    if gid is not None:
        SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{BUDGET_SS}:batchUpdate',
            json={'requests':[{'sortRange':{'range':{'sheetId':gid,'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':5},
                'sortSpecs':[{'dimensionIndex':0,'sortOrder':'ASCENDING'}]}}]}, timeout=30).raise_for_status()
_cap = lambda x: (x[:1].upper()+x[1:]) if x else x
def _money(n):
    """Сумма для показа: целые — без дробей, дробные — как есть (не округляем, чтобы не врать)."""
    v=float(n)
    return f'{int(v):,}'.replace(',',' ') if v.is_integer() else f'{v:,.2f}'.replace(',',' ')
def _resolve_date(date_str):
    """Дата операции: переданная YYYY-MM-DD или сегодня. Возвращает (дата, месяц)."""
    d = None
    if date_str:
        try: d = datetime.date.fromisoformat(str(date_str)[:10])
        except Exception: d = None
    d = d or today_local()
    return str(d), d.strftime('%Y-%m')

# ── Быстрый ввод: «Категория Сумма [Дата] [Комментарий]» — без догадок модели ──
def _quick_map():
    m={}
    def add(name, kind, canon):
        m[name.lower().replace('ё','е')] = (kind, canon)
    for c in BUDGET_CATS: add(c,'расход',c)
    for c in INCOME_CATS: add(c,'доход',c)
    add('Кредит','доход','Кредит')
    for c in SAVINGS_CATS: add(c,'накопление',c)
    add('Оплата кредита','погашение','Оплата кредита')
    # синонимы/сокращения
    for alias,(k,c) in {
      'зп':('доход','Зарплата'),'зарплата':('доход','Зарплата'),
      'подушка':('накопление','Накопления / Подушка'),'накопления':('накопление','Накопления / Подушка'),
      'инвестиции':('накопление','Инвестиции'),'крипта':('накопление','Инвестиции'),
      'погашение':('погашение','Оплата кредита'),'погашение кредита':('погашение','Оплата кредита'),
      'лечение':('расход','Лечение / Медикаменты'),'медикаменты':('расход','Лечение / Медикаменты'),
      'аптека':('расход','Лечение / Медикаменты'),'врач':('расход','Лечение / Медикаменты'),
      'зал':('расход','Абонемент в зал'),'абонемент':('расход','Абонемент в зал'),'фитнес':('расход','Абонемент в зал'),
      'спортпит':('расход','Спортивное питание'),'протеин':('расход','Спортивное питание'),
      'массаж':('расход','Массаж / Сауна'),'сауна':('расход','Массаж / Сауна'),'баня':('расход','Массаж / Сауна'),
      'бады':('расход','БАДы'),'витамины':('расход','БАДы'),
      'одежда':('расход','Одежда/Обувь'),'обувь':('расход','Одежда/Обувь'),
      'сигареты':('расход','Курение'),'стики':('расход','Курение'),
      'бензин':('расход','Машина'),'авто':('расход','Машина'),
      'продукты':('расход','Продукты'),'базар':('расход','Продукты'),
      'аренда':('расход','Дом'),'коммуналка':('расход','Дом'),
      'такси':('расход','Прочее'),
      'парковка':('расход','Машина'),'оплата парковка':('расход','Машина'),
      'вода':('расход','Продукты'),'вода с магазина':('расход','Продукты'),
      'еда':('расход','Продукты'),'еда с магазина':('расход','Продукты'),
      'стройматериал':('расход','Дом'),'стройматериалы':('расход','Дом'),
      'помощь брату':('расход','Семья'),'помощь родителям':('расход','Семья'),
      'подарок':('расход','Подарки'),'цветы':('расход','Подарки'),
      'кофе':('расход','Кафе'),'ресторан':('расход','Кафе'),'обед':('расход','Кафе'),
      'интернет':('расход','Подписки'),'телефон':('расход','Подписки'),'связь':('расход','Подписки'),
      'мойка':('расход','Машина'),'ремонт авто':('расход','Машина'),
    }.items(): add(alias,k,c)
    return m
QUICK_CATS=_quick_map()

CURRENCY = {'см','сом','сомони','смн','tjs','с','c'}
# Слова, после которых строка — не трата, а вопрос или задача
NOT_SPEND = ('напомн','покаж','скольк','выручк','задач','отчет','сделай','добав',
             'проверь','посчитай','что ','когда','почему','сводк','остаток')
def _strip_currency(s):
    """Убирает хвост-валюту: «вода см» → «вода», «см» → «»."""
    w = [x for x in str(s).split() if x.lower().replace('ё','е').strip('.,;:') not in CURRENCY]
    return ' '.join(w).strip(' ,;:-.')

def _parse_quick(text):
    """«Курение 20 20.08.2026 Стики» → (kind, категория, сумма, ISO-дата, комментарий) или None."""
    t=' '.join(str(text).strip().split())
    if not t or '\n' in str(text).strip(): return None
    low=t.lower().replace('ё','е')
    # самое длинное совпадение имени категории в начале строки
    best=None
    for name in QUICK_CATS:
        if low.startswith(name) and (len(low)==len(name) or not low[len(name)].isalpha()):
            if best is None or len(name)>len(best): best=name
    if not best: return None
    kind,cat=QUICK_CATS[best]
    rest=t[len(best):].strip(' ,;:-')
    # сумма — первое число в остатке (не обязательно сразу после категории)
    m=re.search(r'(\d+(?:[.,]\d+)?)', rest)
    if not m: return None
    before=rest[:m.start()].strip(' ,;:-')      # текст между категорией и суммой → в комментарий
    amount=float(m.group(1).replace(',','.'))
    rest=rest[m.end():].strip()
    # дата: 20.08.2026 / 20.08.26 / 20.08 / 2026-08-20, разделитель . / ,
    iso=None
    dm=re.match(r'^(\d{4}-\d{2}-\d{2})\b\s*(.*)$', rest, re.S)
    if dm:
        iso=dm.group(1); rest=dm.group(2).strip()
    else:
        dm=re.match(r'^(\d{1,2})[./,](\d{1,2})(?:[./,](\d{2,4}))?\b\s*(.*)$', rest, re.S)
        if dm:
            dd,mm=int(dm.group(1)),int(dm.group(2))
            yy=dm.group(3); year=today_local().year
            if yy: year=int(yy)+2000 if len(yy)==2 else int(yy)
            try:
                iso=str(datetime.date(year,mm,dd)); rest=dm.group(4).strip()
            except ValueError: return None
    # комментарий: текст до суммы + хвост после даты, без мусора
    com=" ".join(x for x in (before, rest) if x).strip(' ,;:-.')
    com=re.sub(r'^\W+|\W+$', '', _strip_currency(com))
    return kind,cat,amount,iso,com,False

def _parse_quick_loose(text):
    """Строка вида «Доставка торта 40 см» — категории такой нет, но это явно трата.
    Не выбрасываем: пишем в «Прочее», текст — в комментарий, и помечаем флагом,
    чтобы в подтверждении было видно, что категорию я не распознал.
    Работает ТОЛЬКО внутри пачки — одиночное сообщение уходит модели, она умнее."""
    t=' '.join(str(text).strip().split())
    if not t or len(t)>70 or '?' in t: return None
    m=re.search(r'(\d+(?:[.,]\d+)?)', t)
    if not m: return None
    before=t[:m.start()].strip(' ,;:-')
    if not before or not (1 <= len(before.split()) <= 5): return None
    if not re.fullmatch(r'[^\d]+', before): return None
    amount=float(m.group(1).replace(',','.'))
    rest=t[m.end():].strip()
    iso=None
    dm=re.match(r'^(\d{4}-\d{2}-\d{2})\b\s*(.*)$', rest, re.S)
    if dm:
        iso=dm.group(1); rest=dm.group(2).strip()
    else:
        dm=re.match(r'^(\d{1,2})[./,](\d{1,2})(?:[./,](\d{2,4}))?\b\s*(.*)$', rest, re.S)
        if dm:
            dd,mm=int(dm.group(1)),int(dm.group(2))
            yy=dm.group(3); year=today_local().year
            if yy: year=int(yy)+2000 if len(yy)==2 else int(yy)
            try: iso=str(datetime.date(year,mm,dd)); rest=dm.group(4).strip()
            except ValueError: return None
    # после суммы и даты не должно остаться НИЧЕГО, кроме валюты:
    # «Напомни завтра в 10 позвонить в банк» — это не трата, а задача
    if _strip_currency(rest): return None
    com=re.sub(r'^\W+|\W+$', '', _strip_currency(before))
    if not com: return None
    if any(w in com.lower().replace('ё','е') for w in NOT_SPEND): return None
    return 'расход','Прочее',amount,iso,com,True

def _parse_quick_lines(text):
    """Многострочный быстрый ввод: разбирает КАЖДУЮ строку отдельно.
    Возвращает (список разобранных операций, список неразобранных строк).
    Нужно, чтобы пачка операций задним числом не терялась в модели."""
    lines = [l.strip() for l in str(text).splitlines() if l.strip()]
    if len(lines) < 2:
        return [], []
    ok, bad = [], []
    for ln in lines:
        q = _parse_quick(ln) or _parse_quick_loose(ln)
        if q:
            ok.append(q)
        else:
            bad.append(ln)
    # считаем пачкой, только если разобралось большинство строк
    if len(ok) < 2 or len(ok) < len(lines) * 0.5:
        return [], []
    return ok, bad


def tool_add_budget_entry(amount, category='Прочее', kind='расход', comment='', date=None, **_):
    """Запись дохода/расхода в бюджет (лист Operations). Тип с заглавной, комментарий обязателен."""
    is_income = str(kind).lower().startswith('дох')
    is_saving = str(kind).lower().startswith('нак') or category in SAVINGS_CATS
    is_debt   = str(kind).lower().startswith('пог') or category=='Оплата кредита'
    if is_debt:
        typ='Погашение'; cat='Оплата кредита'          # вынесено из расходов в «Сбережения и долг»
    elif is_saving:
        typ='Накопление'; cat = category if category in SAVINGS_CATS else 'Накопления / Подушка'
    elif is_income:
        typ='Доход'; cat = category if category in INCOME_CATS else 'Зарплата'
    else:
        typ='Расход'; cat = category if category in BUDGET_CATS else 'Прочее'
    d, _ = _resolve_date(date)
    com = _cap((comment or '').strip())
    _budget_append('Operations!A:E', [d, typ, cat, float(amount), com])
    when = '' if d==str(today_local()) else f' ({d})'
    return f'💵 {typ}: {_money(amount)} с · {cat}{when}' + (f' · {com}' if com else '')

# ── Контакты и отправка людям в Telegram ──────────────────────────────────────
def _contacts():
    r = SHEETS.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Контакты!A2:C', timeout=20)
    out={}
    for row in (r.json().get('values',[]) if r.status_code==200 else []):
        if len(row)>=2 and row[0].strip(): out[row[0].strip().lower()] = (row[1], row[0])
    return out

def _contact_add(name, chat_id, username):
    SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Контакты!A:D:append'
        '?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
        json={'values':[[name, str(chat_id), username, str(today_local())]]}, timeout=20)

_BOT_ID=[None]
def _bot_id():
    if _BOT_ID[0] is None:
        try: _BOT_ID[0]=tg('getMe').get('result',{}).get('id')
        except Exception: _BOT_ID[0]=0
    return _BOT_ID[0]

def _shift_log(group, author, kind, content):
    SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Смены!A:F:append'
        '?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
        json={'values':[[str(today_local()), now_local().strftime('%H:%M'), group, author, kind, content]]}, timeout=20)

def tool_shift_report(date=None, **_):
    """Сводка со смен (сообщения и фото из групп) за день. По умолчанию — вчера."""
    d = date or str(today_local()-datetime.timedelta(days=1))
    r=SHEETS.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Смены!A2:F',timeout=30)
    rows=[x for x in (r.json().get('values',[]) if r.status_code==200 else []) if x and x[0]==d]
    if not rows: return f'📋 Со смен за {d}: ничего не поступало'
    from collections import defaultdict
    byg=defaultdict(list)
    for x in rows:
        g=x[2] if len(x)>2 else '?'; kind=x[4] if len(x)>4 else ''; cont=x[5] if len(x)>5 else ''
        byg[g].append(f'  {"🖼" if kind=="фото" else "•"} {cont[:120]}')
    out=[f'📋 Закрытие смен за {d}:']
    for g,items in byg.items():
        out.append(f'\n<b>{g}</b>')
        out+=items
    return '\n'.join(out)

def tool_send_telegram(name, text, **_):
    """Отправить сообщение человеку из контактов (он должен был стартовать бота)."""
    c=_contacts(); key=str(name).strip().lower()
    match = c.get(key) or next((v for k,v in c.items() if key in k or k in key), None)
    if not match:
        return f'⚠️ Нет контакта «{name}». Пусть он напишет боту /start, тогда добавится.'
    cid, real = match
    tg('sendMessage', chat_id=cid, text=text)
    return f'📨 Отправлено {real}: {text[:120]}'

def tool_add_credit(amount, kind='получен', name='', comment='', date=None, **_):
    """Кредит: 'получен' → доход + лист Кредиты; 'погашение' → расход «Оплата кредита». date опционально."""
    got = str(kind).startswith('получ')
    d, _ = _resolve_date(date); amt=float(amount)
    when = '' if d==str(today_local()) else f' ({d})'
    nm=_cap((name or '').strip()) or '—'; com=_cap((comment or '').strip())
    if got:
        _budget_append('Operations!A:E', [d,'Доход','Кредит',amt, nm if nm!='—' else com])
        _budget_append('Loans!A:E', [d,'Получен', nm, amt, com])
        return f'🏦 Кредит получен: {_money(amt)} с' + (f' · {nm}' if nm!='—' else '') + f'{when} (в доходах + долг)'
    else:
        _budget_append('Operations!A:E', [d,'Погашение','Оплата кредита',amt, nm if nm!='—' else com])
        _budget_append('Loans!A:E', [d,'Погашение', nm, amt, com])
        return f'🏦 Погашение кредита: {_money(amt)} с' + (f' · {nm}' if nm!='—' else '') + f'{when} (минус долг, не расход)'

def tool_capture_note(text, **_):
    """Заметка → база Входящие в Notion (не эфемерный диск)."""
    _notion_post('pages', {'parent':{'database_id':NIDS.get('inbox')},'properties':{
        'Заметка':{'title':[{'text':{'content':text}}]},
        'Дата':{'date':{'start':str(today_local())}},
        'Статус':{'select':{'name':'Новое'}}}})
    return f'📝 Записал во входящие: {text}'

def _notion_query(db, flt=None):
    payload = {'filter':flt} if flt else {}
    r = requests.post(f'https://api.notion.com/v1/databases/{db}/query', headers=NH, json=payload, timeout=30)
    r.raise_for_status(); return r.json().get('results',[])

def tool_list_tasks(kind='тактическая', **_):
    db = NIDS.get('sdb') if kind.startswith('страт') else NIDS.get('tdb')
    items=[]
    for p in _notion_query(db):
        pr=p['properties']
        title=''.join(x['plain_text'] for x in pr['Задача']['title'])
        st=(pr.get('Статус',{}).get('select') or {}).get('name','')
        if st=='Готово': continue
        items.append(f'• {title}' + (f' — {st}' if st else ''))
    hdr = '🏛 Стратегические задачи:' if kind.startswith('страт') else '🎯 Тактические задачи:'
    return hdr+'\n'+('\n'.join(items) if items else 'пусто')

def tool_list_violations(period='неделя', **_):
    today=today_local()
    since = today - datetime.timedelta(days=1 if period.startswith('дн') else 7 if period.startswith('нед') else 30)
    items=[]
    for p in _notion_query(NIDS.get('vdb')):
        pr=p['properties']
        d=(pr.get('Дата',{}).get('date') or {}).get('start','')
        if d and d < str(since): continue
        desc=''.join(x['plain_text'] for x in pr['Нарушение']['title'])
        pt=(pr.get('Точка',{}).get('select') or {}).get('name','')
        emp=''.join(x['plain_text'] for x in pr.get('Сотрудник',{}).get('rich_text',[]))
        items.append(f'• {d[5:]} {pt} {emp}: {desc}'.replace('  ',' '))
    return f'🚨 Нарушения ({period}):\n'+('\n'.join(items) if items else 'нет')

# ── Google Workspace (Gmail + Календарь) через делегирование ──────────────────
AGENT_GOOGLE_USER = os.environ.get('AGENT_GOOGLE_USER','').strip() or 'base@azizkhaidarov.com'
_gws_cache = {}
def gws(scopes):
    key = ','.join(scopes)
    if key in _gws_cache: return _gws_cache[key]
    raw = os.environ.get('ROMASHKA_SA_JSON')
    info = json.loads(raw) if raw else json.load(open(os.path.join(CRED,'romashka-drive.json')))
    creds = service_account.Credentials.from_service_account_info(info, scopes=scopes, subject=AGENT_GOOGLE_USER)
    sess = AuthorizedSession(creds); _gws_cache[key]=sess; return sess

def tool_send_email(to, subject, body, **_):
    import base64, email.message
    m = email.message.EmailMessage()
    m['To']=to; m['Subject']=subject; m.set_content(body)
    raw = base64.urlsafe_b64encode(m.as_bytes()).decode()
    s = gws(['https://www.googleapis.com/auth/gmail.modify'])
    r = s.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send', json={'raw':raw}, timeout=30)
    r.raise_for_status()
    return f'✉️ Письмо отправлено: {to} — «{subject}»'

def tool_list_events(date=None, **_):
    d = date or str(today_local())
    s = gws(['https://www.googleapis.com/auth/calendar'])
    tmin=f'{d}T00:00:00Z'; tmax=f'{d}T23:59:59Z'
    r = s.get('https://www.googleapis.com/calendar/v3/calendars/primary/events',
              params={'timeMin':tmin,'timeMax':tmax,'singleEvents':'true','orderBy':'startTime'}, timeout=30)
    r.raise_for_status()
    evs = r.json().get('items',[])
    if not evs: return f'📅 На {d}: событий нет'
    out=[f'📅 {d}:']
    for e in evs:
        st=(e.get('start',{}).get('dateTime') or e.get('start',{}).get('date',''))[11:16]
        out.append(f'{st} — {e.get("summary","(без названия)")}')
    return '\n'.join(out)

def tool_create_event(title, date, time='10:00', duration_min=60, **_):
    s = gws(['https://www.googleapis.com/auth/calendar'])
    start=f'{date}T{time}:00'
    hh,mm=map(int,time.split(':')); end_min=hh*60+mm+int(duration_min)
    end=f'{date}T{end_min//60:02d}:{end_min%60:02d}:00'
    body={'summary':title,'start':{'dateTime':start,'timeZone':'Asia/Dushanbe'},
          'end':{'dateTime':end,'timeZone':'Asia/Dushanbe'}}
    r = s.post('https://www.googleapis.com/calendar/v3/calendars/primary/events', json=body, timeout=30)
    r.raise_for_status()
    return f'📅 Событие создано: {date} {time} — {title}'

def tool_revenue_by_month(**_):
    rows=_sheet_rows()
    from collections import defaultdict
    m=defaultdict(lambda:defaultdict(float))
    for r in rows:
        if len(r)<3: continue
        if r[1] in ('ЗБ','ОВИР'):
            try: m[r[0][:7]][r[1]]+=float(r[2] or 0)
            except: pass
    f=lambda n: f'{int(round(n)):,}'.replace(',',' ')
    out=['📈 Выручка по месяцам (ЗБ / ОВИР / Сеть):']
    for mm in sorted(m)[-6:]:
        z,o=m[mm]['ЗБ'],m[mm]['ОВИР']
        out.append(f'{mm}: {f(z)} / {f(o)} / {f(z+o)}')
    return '\n'.join(out)

TOOLS_SPEC = [
 {'type':'function','function':{'name':'add_task','description':'Добавить задачу в Notion. Тактическая — оперативная (эта неделя), стратегическая — долгосрочная (по этапам).',
   'parameters':{'type':'object','properties':{
     'title':{'type':'string'},'kind':{'type':'string','enum':['тактическая','стратегическая']},
     'assignee':{'type':'string','enum':['Азиз','Владимир','Дилчу','Claude']},'due':{'type':'string','description':'YYYY-MM-DD'}},
     'required':['title']}}},
 {'type':'function','function':{'name':'add_violation','description':'Записать нарушение сотрудника.',
   'parameters':{'type':'object','properties':{
     'point':{'type':'string','enum':['ЗБ','ОВИР']},'description':{'type':'string'},'employee':{'type':'string'},
     'category':{'type':'string','enum':['Телефон','Гигиена','Отсутствие','Опоздание','Санитария','Качество','Прочее']}},
     'required':['point','description']}}},
 {'type':'function','function':{'name':'get_revenue','description':'Выручка за период.',
   'parameters':{'type':'object','properties':{'period':{'type':'string','enum':['день','неделя','месяц','год']}},'required':['period']}}},
 {'type':'function','function':{'name':'poster_query','description':'Расходы или выручка по Poster за период, опционально по категории.',
   'parameters':{'type':'object','properties':{'metric':{'type':'string','enum':['расходы','выручка']},
     'category':{'type':'string'},'date_from':{'type':'string'},'date_to':{'type':'string'}},'required':['metric']}}},
 {'type':'function','function':{'name':'capture_note','description':'Сохранить мысль/заметку во входящие.',
   'parameters':{'type':'object','properties':{'text':{'type':'string'}},'required':['text']}}},
 {'type':'function','function':{'name':'shift_report','description':'Сводка со смен: что персонал скидывал в группы (остатки, фото закрытия, заметки) за день. Для «отчёт по сменам», «что со смен вчера».',
   'parameters':{'type':'object','properties':{'date':{'type':'string','description':'YYYY-MM-DD, по умолчанию вчера'}},'required':[]}}},
 {'type':'function','function':{'name':'send_telegram','description':'Отправить сообщение человеку ИЛИ в группу в Telegram (Владимиру, Дилчу, поставщику, рабочий чат). Для «напиши X», «запости в группу Y», «объяви команде».',
   'parameters':{'type':'object','properties':{'name':{'type':'string','description':'имя человека или название группы из контактов'},'text':{'type':'string'}},'required':['name','text']}}},
 {'type':'function','function':{'name':'add_budget_entry','description':'Записать личный доход/расход в бюджет-ПНЛ. Если в сообщении несколько трат — вызови для каждой отдельно. Категорию бери СТРОГО из enum. Правила: аренда/коммуналка/дом→Дом; бензин/ремонт авто/мойка→Машина; покупка или ремонт техники/наушников/чехол/ламинат/стекло/аксессуар→Гаджеты; ОПЛАТА телефона/интернета/связь/Claude/любая подписка→Подписки; платёж/оплата по рассрочке/рассрочка/Alif/Салом→Рассрочка; кафе/ресторан/кофе→Кафе; продукты/базар→Продукты; врач/аптека/зубы/лечение→Лечение / Медикаменты; протеин/спортпит→Спортивное питание; фитнес/зал/абонемент→Абонемент в зал; витамины/добавки→БАДы; массаж/сауна/баня→Массаж / Сауна; сигареты→Курение; одежда/обувь→Одежда/Обувь; кино/отдых/свидание/хобби→Развлечение; курс/книга/учёба→Обучение; родители/помощь родным→Семья; подарок→Подарки; поездка/билеты/отель→Путешествие; непонятно→Прочее. Накопления (тип «накопление», НЕ расход): отложил/накопил/в подушку/на чёрный день→Накопления / Подушка; инвестировал/акции/крипто/вклад→Инвестиции. Погашение долга (тип «погашение», НЕ расход): оплатил/погасил/внёс по кредиту→Оплата кредита. Доход: зарплата→Зарплата, иной приход→Прочий доход. ВСЕГДА заполняй comment — краткое описание траты из сообщения (что купил/на что), напр. «кофе 50 в старбаксе»→comment="кофе в старбаксе"; «продукты 800»→comment="продукты". Если в сообщении вообще нет описания (только сумма) — оставь comment пустым.',
   'parameters':{'type':'object','properties':{
     'amount':{'type':'string','description':'сумма числом, например "160"'},'category':{'type':'string','enum':['Дом','Машина','Гаджеты','Подписки','Рассрочка','Кафе','Продукты','Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна','Курение','Одежда/Обувь','Развлечение','Обучение','Семья','Подарки','Оплата кредита','Путешествие','Прочее','Накопления / Подушка','Инвестиции','Зарплата','Прочий доход']},
     'kind':{'type':'string','enum':['расход','доход','накопление','погашение']},'comment':{'type':'string'},'date':{'type':'string','description':'YYYY-MM-DD, если операция задним числом'}},'required':['amount','comment']}}},
 {'type':'function','function':{'name':'add_credit','description':'Кредит/займ. Получение кредита (приходуется как доход) или погашение (расход). Для «взял кредит», «получил займ», «оплатил кредит», «погасил кредит».',
   'parameters':{'type':'object','properties':{
     'amount':{'type':'string'},'kind':{'type':'string','enum':['получен','погашение']},'name':{'type':'string','description':'кто/название кредита'},'comment':{'type':'string'},'date':{'type':'string','description':'YYYY-MM-DD, если задним числом'}},'required':['amount','kind']}}},
 {'type':'function','function':{'name':'list_tasks','description':'ПОКАЗАТЬ существующие задачи (не создавать). Для вопросов «какие задачи», «что мне сделать».',
   'parameters':{'type':'object','properties':{'kind':{'type':'string','enum':['тактическая','стратегическая']}},'required':['kind']}}},
 {'type':'function','function':{'name':'list_violations','description':'ПОКАЗАТЬ нарушения за период (не создавать).',
   'parameters':{'type':'object','properties':{'period':{'type':'string','enum':['день','неделя','месяц']}},'required':['period']}}},
 {'type':'function','function':{'name':'revenue_channels','description':'Разбивка выручки по каналам: в заведении, навынос, доставка + СНБЖ отдельно. Для «сколько навынос», «доля доставки», «сколько СНБЖ», «каналы продаж».',
   'parameters':{'type':'object','properties':{'period':{'type':'string','enum':['день','неделя','месяц','год']}},'required':[]}}},
 {'type':'function','function':{'name':'revenue_by_month','description':'Динамика выручки по месяцам (последние 6). Для «динамика продаж», «выручка по месяцам», «за несколько месяцев».',
   'parameters':{'type':'object','properties':{},'required':[]}}},
 {'type':'function','function':{'name':'send_email','description':'Отправить письмо (Gmail) от имени Азиза.',
   'parameters':{'type':'object','properties':{'to':{'type':'string'},'subject':{'type':'string'},'body':{'type':'string'}},'required':['to','subject','body']}}},
 {'type':'function','function':{'name':'list_events','description':'Показать события календаря на дату (по умолчанию сегодня).',
   'parameters':{'type':'object','properties':{'date':{'type':'string','description':'YYYY-MM-DD'}},'required':[]}}},
 {'type':'function','function':{'name':'create_event','description':'Создать событие в календаре.',
   'parameters':{'type':'object','properties':{'title':{'type':'string'},'date':{'type':'string','description':'YYYY-MM-DD'},'time':{'type':'string','description':'HH:MM'},'duration_min':{'type':'string'}},'required':['title','date']}}},
]
TOOLS = {'add_task':tool_add_task,'add_violation':tool_add_violation,'get_revenue':tool_get_revenue,
         'poster_query':tool_poster_query,'capture_note':tool_capture_note,'send_telegram':tool_send_telegram,'shift_report':tool_shift_report,'add_budget_entry':tool_add_budget_entry,'add_credit':tool_add_credit,
         'list_tasks':tool_list_tasks,'list_violations':tool_list_violations,'revenue_by_month':tool_revenue_by_month,'revenue_channels':tool_revenue_channels,
         'send_email':tool_send_email,'list_events':tool_list_events,'create_event':tool_create_event}

# Инструменты, которые ЧТО-ТО ЗАПИСЫВАЮТ/ОТПРАВЛЯЮТ — требуют подтверждения. Чтение — сразу.
WRITE_TOOLS = {'add_task','add_violation','capture_note','send_email','create_event','add_budget_entry','add_credit','send_telegram'}
PENDING = {}  # chat_id -> [(fn, args), ...] ожидают «да/нет»
AFFIRM = {'да','ага','угу','подтверждаю','подтвердить','ок','окей','ok','yes','+','давай','верно','точно','да.','ок.'}
DENY   = {'нет','не','отмена','отмени','отменить','no','неверно','не надо','нет.'}

def describe_action(fn, args):
    if fn=='add_task':
        kind=args.get('kind','тактическая'); who=args.get('assignee'); due=args.get('due')
        extra=(f' · {who}' if who else '')+(f' · до {due}' if due else '')
        return f'✅ Задача ({kind}): {args.get("title","")}{extra}'
    if fn=='add_violation':
        emp=args.get('employee'); cat=args.get('category','Прочее')
        return f'🚨 Нарушение — {args.get("point","?")}{(" · "+emp) if emp else ""} · {cat}: {args.get("description","")}'
    if fn=='capture_note':
        return f'📝 Заметка: {args.get("text","")}'
    if fn=='add_budget_entry':
        c0 = args.get('category','Прочее'); kw=str(args.get('kind','расход')).lower()
        if kw.startswith('пог') or c0=='Оплата кредита':
            k='Погашение'; c='Оплата кредита'
        elif kw.startswith('нак') or c0 in SAVINGS_CATS:
            k='Накопление'; c = c0 if c0 in SAVINGS_CATS else 'Накопления / Подушка'
        elif kw.startswith('дох'):
            k='Доход'; c = c0 if c0 in INCOME_CATS else 'Зарплата'
        else:
            k='Расход'; c = c0 if c0 in BUDGET_CATS else 'Прочее'
        return f'💵 {k}: {args.get("amount",0)} с · {c}'+(' · '+args.get('comment','') if args.get('comment') else '')
    if fn=='send_telegram':
        return f'📨 Написать {args.get("name","")}: {args.get("text","")[:200]}'
    if fn=='add_credit':
        return f'🏦 Кредит {args.get("kind","получен")}: {args.get("amount",0)} с'+(' · '+args.get('name','') if args.get('name') else '')
    if fn=='send_email':
        return f'✉️ Письмо → {args.get("to","")}\nТема: {args.get("subject","")}\n{args.get("body","")[:300]}'
    if fn=='create_event':
        return f'📅 Событие: {args.get("date","")} {args.get("time","10:00")} — {args.get("title","")}'
    return f'{fn}({args})'

SYSTEM = ('Ты — исполнительный ассистент Азиза, операционного директора сети кафе «Ромашка» '
 '(две точки: ЗБ Лохути, ОВИР Турсунзода). Азиз пишет/говорит по-русски, коротко. '
 'Пойми намерение и вызови нужный инструмент. ВАЖНО: если Азиз ПРОСИТ ПОКАЗАТЬ задачи/нарушения — '
 'используй list_tasks/list_violations, НЕ создавай новые. add_task/add_violation — только когда явно просят добавить/записать. '
 'Если данных не хватает (например, на кого нарушение) — переспроси одним вопросом, не выдумывай. '
 'Отвечай кратко, по-деловому, на «ты». '
 'Сегодня '+str(today_local())+'. Если сказано «вчера», «5 июля», «позавчера» — вычисли дату (YYYY-MM-DD) от сегодняшней и передай в параметр date.')

# ── Мозг (Groq по умолчанию, OpenAI-совместимый tool-calling) ─────────────────
def brain(history):
    if ANTHRO_KEY:
        return _brain_anthropic(history)
    return _brain_groq(history)

def _brain_groq(history):
    msgs=[{'role':'system','content':SYSTEM}]+history
    r=requests.post('https://api.groq.com/openai/v1/chat/completions',
        headers={'Authorization':f'Bearer {GROQ_KEY}','Content-Type':'application/json'},
        json={'model':'llama-3.3-70b-versatile','messages':msgs,'tools':TOOLS_SPEC,'tool_choice':'auto','temperature':0.2},
        timeout=60)
    # Groq строго валидирует tool-calls: при несовпадении даёт 400 tool_use_failed.
    if r.status_code==400 and 'tool_use_failed' in r.text:
        try:
            gen=r.json()['error'].get('failed_generation','')
            import re
            mm=re.search(r'<function=(\w+)>(\{.*\})</function>', gen, re.S)
            if mm:
                return _run_calls([(mm.group(1), json.loads(mm.group(2)))])
        except Exception:
            pass
        return 'Не разобрал — переформулируй, пожалуйста (например: «кино 160, снеки 92»).'
    r.raise_for_status()
    m=r.json()['choices'][0]['message']
    if m.get('tool_calls'):
        calls=[(tc['function']['name'], json.loads(tc['function']['arguments'] or '{}')) for tc in m['tool_calls']]
        return _run_calls(calls)
    return m.get('content') or 'Не понял, повтори иначе.'

def _run_calls(calls):
    """Чтение — сразу. Запись — откладываем в PENDING и просим подтвердить."""
    reads=[]; writes=[]
    for fn,args in calls:
        # комментарий обязателен для трат/доходов — если пусто, просим уточнить
        if fn=='add_budget_entry' and not str(args.get('comment','')).strip():
            return f'✍️ На что именно {int(float(args.get("amount",0)))} с? Добавь описание — комментарий обязателен (например: «{int(float(args.get("amount",0)))} продукты вода»).'
        if fn in WRITE_TOOLS: writes.append((fn,args))
        else:
            try: reads.append(TOOLS[fn](**args))
            except Exception as e: reads.append(f'⚠️ Ошибка «{fn}»: {e}')
    out=reads[:]
    if writes:
        PENDING[ALLOWED]=writes
        out.append('❓ Подтверди:\n'+'\n'.join(describe_action(fn,args) for fn,args in writes)+'\n\nОтветь «да» или «нет».')
    return '\n'.join(out) if out else 'Не понял, повтори иначе.'

def _brain_anthropic(history):
    tools=[{'name':t['function']['name'],'description':t['function']['description'],
            'input_schema':t['function']['parameters']} for t in TOOLS_SPEC]
    r=requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key':ANTHRO_KEY,'anthropic-version':'2023-06-01','content-type':'application/json'},
        json={'model':'claude-3-5-sonnet-20241022','max_tokens':1024,'system':SYSTEM,
              'messages':history,'tools':tools},timeout=60)
    r.raise_for_status(); data=r.json()
    calls=[]; texts=[]
    for block in data.get('content',[]):
        if block['type']=='tool_use':
            calls.append((block['name'], block['input']))
        elif block['type']=='text' and block['text'].strip():
            texts.append(block['text'].strip())
    if calls:
        return _run_calls(calls)
    return '\n'.join(texts) or 'Не понял, повтори иначе.'

# ── Аудит ─────────────────────────────────────────────────────────────────────
def audit(kind, text, result):
    try:
        SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/{AUDIT_TAB}!A:D:append'
            '?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
            json={'values':[[now_local().strftime('%Y-%m-%d %H:%M'),kind,text[:400],result[:400]]]},timeout=20)
    except Exception as e:
        log.warning(f'audit fail: {e}')

# ── Основной цикл ─────────────────────────────────────────────────────────────
def _save_checklist_photo(file_id, name):
    """Фото из чек-листа → на Drive, возвращаем ссылку."""
    content,_ = _tg_download(file_id)
    folder = NIDS.get('shift_photos')
    nm = f'{name}-{now_local().strftime("%H%M%S")}.jpg'
    meta = {'name': nm, 'parents':[folder]} if folder else {'name': nm}
    up = SHEETS.post('https://www.googleapis.com/upload/drive/v3/files'
                     '?uploadType=multipart&supportsAllDrives=true&fields=webViewLink',
        files={'data':('m',json.dumps(meta),'application/json'),
               'file':(nm,content,'image/jpeg')}, timeout=120).json()
    return up.get('webViewLink','')


def handle(msg):
    chat=msg.get('chat',{}); chat_id=str(chat['id']); ctype=chat.get('type','private')
    # Группа: регистрируем + собираем содержимое смен (сообщения, фото)
    if ctype in ('group','supergroup'):
        title=chat.get('title','Группа')
        try:
            if str(chat_id) not in [v[0] for v in _contacts().values()]:
                _contact_add(title, chat_id, 'группа')
                send(f'👥 Бот добавлен в группу: <b>{title}</b>. Собираю сообщения и фото; постить: «запости в {title} …»')
        except Exception as e:
            log.warning(f'group capture: {e}')
        # если бот сам постил — не логируем
        if str(msg.get('from',{}).get('id'))==str(_bot_id()): return
        author=' '.join(x for x in [msg.get('from',{}).get('first_name'),msg.get('from',{}).get('last_name')] if x) or 'Аноним'
        try:
            if 'photo' in msg:
                content,_=_tg_download(msg['photo'][-1]['file_id'])
                folder=NIDS.get('shift_photos')
                nm=f'{title}-{now_local().strftime("%Y%m%d-%H%M%S")}.jpg'
                meta={'name':nm,'parents':[folder]} if folder else {'name':nm}
                up=SHEETS.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=webViewLink',
                    files={'data':('m',json.dumps(meta),'application/json'),'file':(nm,content,'image/jpeg')},timeout=120).json()
                cap=msg.get('caption','')
                _shift_log(title, author, 'фото', (cap+' ' if cap else '')+up.get('webViewLink',''))
            elif msg.get('text'):
                _shift_log(title, author, 'текст', msg['text'])
        except Exception as e:
            log.warning(f'shift log: {e}')
        return
    # Чек-листы смены — доступны всем из листа «Команда», не только Азизу
    try:
        import ops_checklist
        if ops_checklist.on_message(chat_id, msg, SHEETS, tg,
                                    notify=send, today=today_local(),
                                    save_photo=_save_checklist_photo):
            return
    except Exception as e:
        log.warning(f'checklist: {e}')

    if ALLOWED and chat_id!=ALLOWED:
        # Чужой в личке: команды не выполняем, но захватываем контакт
        frm=msg.get('from',{})
        fname=' '.join(x for x in [frm.get('first_name'),frm.get('last_name')] if x) or 'Без имени'
        uname='@'+frm.get('username') if frm.get('username') else ''
        try:
            if str(chat_id) not in [v[0] for v in _contacts().values()]:
                _contact_add(fname, chat_id, uname)
                send(f'📇 Новый контакт написал боту: <b>{fname}</b> {uname} (id {chat_id}). Теперь можешь: «напиши {fname.split()[0]} …»')
        except Exception as e:
            log.warning(f'contact capture: {e}')
        tg('sendMessage', chat_id=chat_id, text='Это бот Азиза. Он получит ваш контакт и свяжется.'); return
    kind='text'; text=msg.get('text','') or msg.get('caption','')
    # Файл-документ → Drive + обратная связь
    if 'document' in msg:
        typing()
        try:
            doc=msg['document']; content,_=_tg_download(doc['file_id'])
            r=handle_file(doc.get('file_name','файл'), content, doc.get('mime_type','application/octet-stream'), msg.get('caption',''))
            send(r); audit('file', doc.get('file_name',''), r[:400]); return
        except Exception as e:
            send(f'⚠️ Не смог обработать файл: {e}'); return
    # Фото → Drive + анализ (Claude, если есть ключ)
    if 'photo' in msg:
        typing()
        try:
            ph=msg['photo'][-1]; content,path=_tg_download(ph['file_id'])
            up=drive_upload(f'photo-{now_local().strftime("%Y%m%d-%H%M%S")}.jpg', content, 'image/jpeg')
            cap=msg.get('caption','')
            link=up.get("webViewLink","")
            # Чек → читаем и предлагаем запись в бюджет
            is_receipt = any(w in cap.lower() for w in ('чек','квитанц','receipt','покупк'))
            if is_receipt:
                if not ANTHRO_KEY:
                    send(f'🧾 Чек сохранил: <a href="{link}">открыть</a>\n(чтение чеков требует ключ Claude — добавь ANTHROPIC_API_KEY)'); return
                rc=analyze_receipt(content)
                total=float(rc.get('total') or 0)
                if total<=0:
                    send(f'🧾 Чек сохранил, но сумму не разобрал: <a href="{link}">открыть</a>\nНапиши сумму текстом.'); return
                cat=rc.get('category') if rc.get('category') in BUDGET_CATS else 'Прочее'
                com=_cap((rc.get('merchant') or rc.get('summary') or 'чек').strip())
                PENDING[ALLOWED]=[('add_budget_entry',{'amount':str(int(total)),'category':cat,'kind':'расход','comment':com})]
                send(f'🧾 Чек прочитан: <a href="{link}">фото</a>\n❓ Подтверди:\n💵 Расход: {_money(total)} с · {cat} · {com}\n\nОтветь «да» или «нет».'); return
            r=f'🖼 Фото сохранил на Drive: <a href="{link}">открыть</a>'
            if ANTHRO_KEY:
                r+='\n\n'+analyze_image(content, cap)
            elif cap:
                r+='\n\n'+brain([{'role':'user','content':cap}])
            else:
                r+='\n(анализ фото ИИ выключен — нужен ключ Claude. Или добавь подпись с командой.)'
            send(r); audit('photo', cap, r[:300]); return
        except Exception as e:
            send(f'⚠️ Не смог сохранить фото: {e}'); return
    if 'voice' in msg or 'audio' in msg:
        kind='voice'; typing()
        try:
            text=transcribe((msg.get('voice') or msg.get('audio'))['file_id'])
            send(f'🎙 <i>{text}</i>')
        except Exception as e:
            send(f'⚠️ Не смог расшифровать голос: {e}'); return
    if not text: return
    low = text.strip().lower().rstrip('!.')
    # Ждём подтверждения отложенного действия?
    if PENDING.get(ALLOWED):
        if low in AFFIRM:
            acts = PENDING.pop(ALLOWED); res=[]
            for fn,args in acts:
                try: res.append(TOOLS[fn](**args))
                except Exception as e: res.append(f'⚠️ Ошибка «{fn}»: {e}')
            r='\n'.join(res); send(r); audit('confirm', text, r); return
        if low in DENY:
            PENDING.pop(ALLOWED, None); send('Отменил, ничего не записал.'); return
        dropped = PENDING.pop(ALLOWED, None)  # новое сообщение — сбрасываем ожидание
        if dropped:
            send(f'⚠️ Предыдущая запись НЕ сохранена — не было «да». Отменено: {len(dropped)} операц.')
    if text.strip().lower() in ('/start','/помощь','/help'):
        send('🌸 Кидай голос или текст: задачи, нарушения, «выручка за неделю», «сколько потратили на аренду в июне», заметки. Действия с записью я делаю после твоего «да».\n\n'
             '💵 Быстрый ввод бюджета: <b>Категория Сумма Дата Комментарий</b>\n'
             'Например: <code>Курение 20 20.08.2026 Стики</code> — покажу и запишу после «да».'); return
    # Быстрый ввод пачкой: несколько операций, каждая своей строкой
    multi, bad = _parse_quick_lines(text)
    if multi:
        acts, lines, loose_n = [], [], 0
        for kind,cat,amount,iso,com,loose in multi:
            amt_s = str(int(amount)) if float(amount).is_integer() else str(amount)
            a={'amount':amt_s,'category':cat,'kind':kind,'comment':com}
            if iso: a['date']=iso
            acts.append(('add_budget_entry',a))
            when = iso if iso else 'сегодня'
            mark = ' ⚠️ категорию не понял → Прочее' if loose else ''
            if loose: loose_n += 1
            lines.append(f'{describe_action("add_budget_entry",a)} · {when}{mark}')
        PENDING[ALLOWED]=acts
        msg=f'❓ Подтверди — {len(acts)} операц.:\n\n' + '\n'.join(lines)
        if bad:
            msg += '\n\n⚠️ НЕ РАСПОЗНАЛ (не запишу):\n' + '\n'.join('· '+b[:60] for b in bad)
        send(msg + '\n\nОтветь «да» или «нет».')
        audit('quick-multi', text, f'ожидает подтверждения: {len(acts)} шт '
              f'(в «Прочее» без категории: {loose_n}), не распознано {len(bad)}')
        return

    # Быстрый ввод бюджета — точный формат; категория задана явно, но пишем после «да»
    q=_parse_quick(text)
    if q:
        kind,cat,amount,iso,com,_loose=q
        amt_s = str(int(amount)) if float(amount).is_integer() else str(amount)
        args={'amount':amt_s,'category':cat,'kind':kind,'comment':com}
        if iso: args['date']=iso
        PENDING[ALLOWED]=[('add_budget_entry',args)]
        when = f' · {iso}' if iso else ' · сегодня'
        send(f'{describe_action("add_budget_entry",args)}{when}\n\nЗаписать? (да/нет)')
        audit('quick', text, 'ожидает подтверждения'); return
    typing()
    try:
        reply=brain([{'role':'user','content':text}])
    except Exception as e:
        reply=f'⚠️ Сбой мозга: {e}'
    send(reply); audit(kind,text,reply)

def run():
    for need,name in [(TG_TOKEN,'TELEGRAM_BOT_TOKEN'),(ALLOWED,'TELEGRAM_CHAT_ID'),(GROQ_KEY,'GROQ_API_KEY')]:
        if not need: log.error(f'Нет {name}'); sys.exit(1)
    log.info('🌸 Ромашка-агент запущен')
    try:
        import ops_webapp
        ops_webapp.setup(SHEETS, tg, send, TG_TOKEN)
        ops_webapp._CTX['folder'] = NIDS.get('shift_photos')
        _, _port = ops_webapp.serve_in_background()
        log.info(f'Mini App слушает порт {_port}; адрес — WEBAPP_URL='
                 f'{os.environ.get("WEBAPP_URL", "не задан")}')
    except Exception as e:
        log.error(f'Mini App не поднялся: {e}')
    try: send('🌸 Агент на связи. Кидай голос или текст.')
    except Exception: pass
    offset=0
    while True:
        try:
            res=tg('getUpdates', offset=offset, timeout=25,
                   allowed_updates=['message','my_chat_member','callback_query'])
            for upd in res.get('result') or []:
                offset=upd['update_id']+1
                if 'callback_query' in upd:
                    # кнопки чек-листов
                    try:
                        import ops_checklist
                        ops_checklist.on_callback(upd['callback_query'], SHEETS, tg,
                                                  notify=send, today=today_local())
                    except Exception as e: log.error(f'callback: {e}')
                elif 'message' in upd:
                    try: handle(upd['message'])
                    except Exception as e: log.error(f'handle: {e}')
                elif 'my_chat_member' in upd:
                    # бота добавили/удалили из группы
                    try:
                        cm=upd['my_chat_member']; chat=cm.get('chat',{})
                        if chat.get('type') in ('group','supergroup') and cm.get('new_chat_member',{}).get('status') in ('member','administrator'):
                            title=chat.get('title','Группа'); cid=str(chat['id'])
                            if cid not in [v[0] for v in _contacts().values()]:
                                _contact_add(title, cid, 'группа')
                                send(f'👥 Бот добавлен в группу: <b>{title}</b>. Теперь: «запости в {title} …»')
                    except Exception as e: log.error(f'my_chat_member: {e}')
        except requests.RequestException as e:
            log.warning(f'net: {e}'); time.sleep(5)
        except Exception as e:
            log.error(f'loop: {e}'); time.sleep(5)

if __name__=='__main__':
    run()
