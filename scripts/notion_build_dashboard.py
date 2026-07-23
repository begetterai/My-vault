#!/usr/bin/env python3
"""Строит Notion с нуля: Дашборд наверху + страницы документов по группам."""
import os, json, time, datetime, requests
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

TOK = open('/home/user/My-vault/scripts/credentials/notion.token').read().strip()
H = {'Authorization': f'Bearer {TOK}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
ROOT = json.load(open('/home/user/My-vault/scripts/credentials/notion_ids.json'))['root']
API = 'https://api.notion.com/v1'
SS = '1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'

def post(path, payload):
    for a in range(4):
        r = requests.post(f'{API}/{path}', headers=H, json=payload, timeout=30)
        if r.status_code == 429: time.sleep(2); continue
        if r.status_code != 200: print('ERR', r.status_code, r.text[:300]); raise SystemExit
        return r.json()
def add(bid, children):
    for i in range(0, len(children), 90):
        r = requests.patch(f'{API}/blocks/{bid}/children', headers=H, json={'children': children[i:i+90]}, timeout=30)
        if r.status_code != 200: print('ERR', r.status_code, r.text[:300]); raise SystemExit
def page(parent, title, icon):
    return post('pages', {'parent':{'page_id':parent},'icon':{'type':'emoji','emoji':icon},
        'properties':{'title':{'title':[{'text':{'content':title}}]}}})['id']
def t(c): return [{'text':{'content':c}}]
def h1(c): return {'heading_1':{'rich_text':t(c)}}
def h2(c): return {'heading_2':{'rich_text':t(c)}}
def h3(c): return {'heading_3':{'rich_text':t(c)}}
def para(c): return {'paragraph':{'rich_text':t(c)}}
def call(c,e,col='default'): return {'callout':{'rich_text':t(c),'icon':{'type':'emoji','emoji':e},'color':col}}
def bm(url,cap): return {'bookmark':{'url':url,'caption':t(cap)}}
def link_row(name, url):
    return {'bulleted_list_item':{'rich_text':[{'type':'text','text':{'content':name,'link':{'url':url}}}]}}
def divider(): return {'divider':{}}

# ── Данные выручки из Sheet ──────────────────────────────────────────────────
creds = service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s = AuthorizedSession(creds)
rows = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS}/values/Данные_Poster!A2:G', timeout=30).json().get('values',[])
today = datetime.date.today()
yday = today - datetime.timedelta(days=1)
mon = today.strftime('%Y-%m')
mtd = {'ЗБ':0.0,'ОВИР':0.0}; yd = {'ЗБ':0.0,'ОВИР':0.0}
for r in rows:
    if len(r)<3: continue
    d,loc = r[0],r[1]
    try: rev=float(r[2] or 0)
    except: continue
    if loc in mtd and d.startswith(mon): mtd[loc]+=rev
    if d==str(yday) and loc in yd: yd[loc]=rev
PLAN={'ЗБ':354000,'ОВИР':277000}
def fmt(n): return f'{int(round(n)):,}'.replace(',',' ')
days_passed=today.day-1 if today.day>1 else 1

# ── Дашборд ──────────────────────────────────────────────────────────────────
dash = page(ROOT, 'Дашборд', '📊')
rev_table = {'table':{'table_width':5,'has_column_header':True,'has_row_header':False,'children':[
    {'table_row':{'cells':[t('Точка'),t('План/мес'),t('Факт MTD'),t('% плана'),t('Вчера')]}},
    {'table_row':{'cells':[t('ЗБ Лохути'),t(fmt(PLAN['ЗБ'])),t(fmt(mtd['ЗБ'])),
        t(f"{round(mtd['ЗБ']/PLAN['ЗБ']*100)}%"),t(fmt(yd['ЗБ']))]}},
    {'table_row':{'cells':[t('ОВИР Турсунзода'),t(fmt(PLAN['ОВИР'])),t(fmt(mtd['ОВИР'])),
        t(f"{round(mtd['ОВИР']/PLAN['ОВИР']*100)}%"),t(fmt(yd['ОВИР']))]}},
    {'table_row':{'cells':[t('Сеть'),t(fmt(PLAN['ЗБ']+PLAN['ОВИР'])),t(fmt(mtd['ЗБ']+mtd['ОВИР'])),
        t(f"{round((mtd['ЗБ']+mtd['ОВИР'])/(PLAN['ЗБ']+PLAN['ОВИР'])*100)}%"),t(fmt(yd['ЗБ']+yd['ОВИР']))]}},
]}}
add(dash, [
    call(f'Обновлено {today.strftime("%d.%m.%Y")} · прошло {days_passed} дн. месяца · данные из Poster (бот обновляет утром)','📊','blue_background'),
    h2('💰 Выручка — план / факт'),
    rev_table,
    divider(),
])
# Тактические задачи (inline DB)
tdb = post('databases', {'parent':{'page_id':dash},'title':t('🎯 Тактические задачи'),'is_inline':True,
    'properties':{'Задача':{'title':{}},
        'Статус':{'select':{'options':[{'name':'Не начато','color':'gray'},{'name':'В работе','color':'blue'},{'name':'Готово','color':'green'}]}},
        'Срок':{'date':{}},
        'Кто':{'select':{'options':[{'name':'Азиз'},{'name':'Владимир'},{'name':'Дилчу'},{'name':'Claude'}]}}}})['id']
for q,st,who in [
    ('Poster ОВИР — оплатить (просрочен с 01.05)','Не начато','Азиз'),
    ('Раздать телефоны+сетку управляющим, собрать подписи','Не начато','Азиз'),
    ('Провести Beeyor и базар в Poster при оплате','Не начато','Азиз'),
]:
    post('pages',{'parent':{'database_id':tdb},'properties':{'Задача':{'title':t(q)},'Статус':{'select':{'name':st}},'Кто':{'select':{'name':who}}}})

# Стратегические задачи (inline DB)
sdb = post('databases', {'parent':{'page_id':dash},'title':t('🏛 Стратегические задачи'),'is_inline':True,
    'properties':{'Задача':{'title':{}},
        'Этап':{'select':{'options':[{'name':'Июль','color':'red'},{'name':'Август','color':'orange'},{'name':'Сентябрь','color':'yellow'},{'name':'Q4','color':'green'},{'name':'2027','color':'blue'}]}},
        'Статус':{'select':{'options':[{'name':'Не начато','color':'gray'},{'name':'В работе','color':'blue'},{'name':'Готово','color':'green'}]}}}})['id']
for q,et,st in [
    ('Собрать чек-листы смены + регламент инкассации','Июль','Не начато'),
    ('Все расходы в Poster → оживить P&L','Август','Не начато'),
    ('Должностные карты + KPI с бонусами','Сентябрь','Не начато'),
    ('Система найма и онбординг','Q4','Не начато'),
    ('Вырастить директора сети (выход из операционки)','2027','Не начато'),
]:
    post('pages',{'parent':{'database_id':sdb},'properties':{'Задача':{'title':t(q)},'Этап':{'select':{'name':et}},'Статус':{'select':{'name':st}}}})

# Нарушения за вчера (inline DB, fresh)
vdb = post('databases', {'parent':{'page_id':dash},'title':t('🚨 Нарушения'),'is_inline':True,
    'properties':{'Нарушение':{'title':{}},'Дата':{'date':{}},
        'Точка':{'select':{'options':[{'name':'ЗБ','color':'green'},{'name':'ОВИР','color':'blue'}]}},
        'Сотрудник':{'rich_text':{}},
        'Категория':{'select':{'options':[{'name':'Телефон','color':'red'},{'name':'Гигиена','color':'yellow'},{'name':'Отсутствие','color':'orange'},{'name':'Опоздание','color':'purple'},{'name':'Санитария','color':'brown'},{'name':'Качество','color':'pink'},{'name':'Прочее','color':'gray'}]}},
        'Статус':{'select':{'options':[{'name':'Новое','color':'red'},{'name':'Разобрано','color':'green'}]}}}})['id']
add(dash, [para('Фильтруй базу по дате, чтобы видеть нарушения за нужный день. Новые добавляются сюда.')])

print('Дашборд готов:', dash)
json.dump({'root':ROOT,'dash':dash,'tdb':tdb,'sdb':sdb,'vdb':vdb},
          open('/home/user/My-vault/scripts/credentials/notion_ids.json','w'))
