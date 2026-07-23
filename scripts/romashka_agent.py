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
import os, sys, json, time, logging, datetime, urllib.parse
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
             'Дата':{'date':{'start':str(datetime.date.today())}},
             'Точка':{'select':{'name':point}},
             'Категория':{'select':{'name':category}},
             'Статус':{'select':{'name':'Новое'}}}
    if employee: props['Сотрудник']={'rich_text':[{'text':{'content':employee}}]}
    _notion_post('pages', {'parent':{'database_id':NIDS.get('vdb')},'properties':props})
    who = f' ({employee})' if employee else ''
    return f'🚨 Нарушение записано — {point}{who}: {description}'

def _sheet_rows():
    r = SHEETS.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/Данные_Poster!A2:G', timeout=30)
    r.raise_for_status(); return r.json().get('values',[])

def tool_get_revenue(period='день', **_):
    rows = _sheet_rows()
    today = datetime.date.today(); yday = today - datetime.timedelta(days=1)
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
    df = date_from or str(datetime.date.today().replace(day=1))
    dt = date_to or str(datetime.date.today())
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

def tool_capture_note(text, **_):
    """Заметка → база Входящие в Notion (не эфемерный диск)."""
    _notion_post('pages', {'parent':{'database_id':NIDS.get('inbox')},'properties':{
        'Заметка':{'title':[{'text':{'content':text}}]},
        'Дата':{'date':{'start':str(datetime.date.today())}},
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
    today=datetime.date.today()
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
 {'type':'function','function':{'name':'list_tasks','description':'ПОКАЗАТЬ существующие задачи (не создавать). Для вопросов «какие задачи», «что мне сделать».',
   'parameters':{'type':'object','properties':{'kind':{'type':'string','enum':['тактическая','стратегическая']}},'required':['kind']}}},
 {'type':'function','function':{'name':'list_violations','description':'ПОКАЗАТЬ нарушения за период (не создавать).',
   'parameters':{'type':'object','properties':{'period':{'type':'string','enum':['день','неделя','месяц']}},'required':['period']}}},
 {'type':'function','function':{'name':'revenue_by_month','description':'Динамика выручки по месяцам (последние 6). Для «динамика продаж», «выручка по месяцам», «за несколько месяцев».',
   'parameters':{'type':'object','properties':{},'required':[]}}},
]
TOOLS = {'add_task':tool_add_task,'add_violation':tool_add_violation,'get_revenue':tool_get_revenue,
         'poster_query':tool_poster_query,'capture_note':tool_capture_note,
         'list_tasks':tool_list_tasks,'list_violations':tool_list_violations,'revenue_by_month':tool_revenue_by_month}

SYSTEM = ('Ты — исполнительный ассистент Азиза, операционного директора сети кафе «Ромашка» '
 '(две точки: ЗБ Лохути, ОВИР Турсунзода). Азиз пишет/говорит по-русски, коротко. '
 'Пойми намерение и вызови нужный инструмент. ВАЖНО: если Азиз ПРОСИТ ПОКАЗАТЬ задачи/нарушения — '
 'используй list_tasks/list_violations, НЕ создавай новые. add_task/add_violation — только когда явно просят добавить/записать. '
 'Если данных не хватает (например, на кого нарушение) — переспроси одним вопросом, не выдумывай. '
 'Отвечай кратко, по-деловому, на «ты». '
 'Сегодня '+str(datetime.date.today())+'.')

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
    r.raise_for_status()
    m=r.json()['choices'][0]['message']
    if m.get('tool_calls'):
        results=[]
        for tc in m['tool_calls']:
            fn=tc['function']['name']; args=json.loads(tc['function']['arguments'] or '{}')
            try: results.append(TOOLS[fn](**args))
            except Exception as e: results.append(f'⚠️ Ошибка «{fn}»: {e}')
        return '\n'.join(results)
    return m.get('content') or 'Не понял, повтори иначе.'

def _brain_anthropic(history):
    tools=[{'name':t['function']['name'],'description':t['function']['description'],
            'input_schema':t['function']['parameters']} for t in TOOLS_SPEC]
    r=requests.post('https://api.anthropic.com/v1/messages',
        headers={'x-api-key':ANTHRO_KEY,'anthropic-version':'2023-06-01','content-type':'application/json'},
        json={'model':'claude-3-5-sonnet-20241022','max_tokens':1024,'system':SYSTEM,
              'messages':history,'tools':tools},timeout=60)
    r.raise_for_status(); data=r.json()
    outs=[]
    for block in data.get('content',[]):
        if block['type']=='tool_use':
            try: outs.append(TOOLS[block['name']](**block['input']))
            except Exception as e: outs.append(f'⚠️ Ошибка «{block["name"]}»: {e}')
        elif block['type']=='text' and block['text'].strip():
            outs.append(block['text'].strip())
    return '\n'.join(outs) or 'Не понял, повтори иначе.'

# ── Аудит ─────────────────────────────────────────────────────────────────────
def audit(kind, text, result):
    try:
        SHEETS.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SS_ID}/values/{AUDIT_TAB}!A:D:append'
            '?valueInputOption=RAW&insertDataOption=INSERT_ROWS',
            json={'values':[[datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),kind,text[:400],result[:400]]]},timeout=20)
    except Exception as e:
        log.warning(f'audit fail: {e}')

# ── Основной цикл ─────────────────────────────────────────────────────────────
def handle(msg):
    chat_id=str(msg['chat']['id'])
    if ALLOWED and chat_id!=ALLOWED:
        tg('sendMessage', chat_id=chat_id, text='⛔ Нет доступа.'); return
    kind='text'; text=msg.get('text','')
    if 'voice' in msg or 'audio' in msg:
        kind='voice'; typing()
        try:
            text=transcribe((msg.get('voice') or msg.get('audio'))['file_id'])
            send(f'🎙 <i>{text}</i>')
        except Exception as e:
            send(f'⚠️ Не смог расшифровать голос: {e}'); return
    if not text: return
    if text.strip().lower() in ('/start','/помощь','/help'):
        send('🌸 Кидай голос или текст: задачи, нарушения, «выручка за неделю», «сколько потратили на аренду в июне», заметки. Я сам разложу.'); return
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
    try: send('🌸 Агент на связи. Кидай голос или текст.')
    except Exception: pass
    offset=0
    while True:
        try:
            res=tg('getUpdates', offset=offset, timeout=25, allowed_updates=['message'])
            for upd in res.get('result') or []:
                offset=upd['update_id']+1
                if 'message' in upd:
                    try: handle(upd['message'])
                    except Exception as e: log.error(f'handle: {e}')
        except requests.RequestException as e:
            log.warning(f'net: {e}'); time.sleep(5)
        except Exception as e:
            log.error(f'loop: {e}'); time.sleep(5)

if __name__=='__main__':
    run()
