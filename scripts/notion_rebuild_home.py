#!/usr/bin/env python3
"""Пересобирает главную Notion: дашборд ПРЯМО на главной сверху, документы — ниже."""
import os, json, time, datetime, requests
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

TOK = open('/home/user/My-vault/scripts/credentials/notion.token').read().strip()
H = {'Authorization': f'Bearer {TOK}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
ROOT = json.load(open('/home/user/My-vault/scripts/credentials/notion_ids.json'))['root']
API='https://api.notion.com/v1'; SS='1bTDELaAo8Ft9WIQqeWDFQQzp5rrDDHiRZ4VpFo-D4m8'

def post(p,pl):
    for a in range(4):
        r=requests.post(f'{API}/{p}',headers=H,json=pl,timeout=30)
        if r.status_code==429: time.sleep(2); continue
        if r.status_code!=200: print('ERR',r.status_code,r.text[:250]); raise SystemExit
        return r.json()
def add(bid,ch):
    out=[]
    for i in range(0,len(ch),90):
        r=requests.patch(f'{API}/blocks/{bid}/children',headers=H,json={'children':ch[i:i+90]},timeout=30)
        if r.status_code!=200: print('ERR',r.status_code,r.text[:250]); raise SystemExit
        out+=r.json()['results']
    return out
def subpage(title,icon):
    return post('pages',{'parent':{'page_id':ROOT},'icon':{'type':'emoji','emoji':icon},'properties':{'title':{'title':[{'text':{'content':title}}]}}})['id']
def t(c): return [{'text':{'content':c}}]
def h2(c): return {'heading_2':{'rich_text':t(c)}}
def h3(c): return {'heading_3':{'rich_text':t(c)}}
def para(c): return {'paragraph':{'rich_text':t(c)}}
def call(c,e,col='default'): return {'callout':{'rich_text':t(c),'icon':{'type':'emoji','emoji':e},'color':col}}
def divider(): return {'divider':{}}
def gl(i): return f'https://docs.google.com/document/d/{i}'
def gs(i): return f'https://docs.google.com/spreadsheets/d/{i}'
def L(name,url): return {'bulleted_list_item':{'rich_text':[{'type':'text','text':{'content':name,'link':{'url':url}}}]}}
def linkpage(pid): return {'link_to_page':{'type':'page_id','page_id':pid}}

# ── 0. Очистить главную полностью ──
r=requests.get(f'{API}/blocks/{ROOT}/children?page_size=100',headers=H,timeout=30)
for b in r.json().get('results',[]):
    requests.delete(f"{API}/blocks/{b['id']}",headers=H,timeout=30); time.sleep(0.15)

# ── 1. Данные выручки ──
creds=service_account.Credentials.from_service_account_file('/home/user/My-vault/scripts/credentials/romashka-drive.json',scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)
rows=s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SS}/values/Данные_Poster!A2:G',timeout=30).json().get('values',[])
today=datetime.date.today(); yday=today-datetime.timedelta(days=1); mon=today.strftime('%Y-%m')
import calendar
dim=calendar.monthrange(today.year,today.month)[1]  # дней в месяце
week_days={str(yday-datetime.timedelta(days=i)) for i in range(7)}  # последние 7 дней
day_f={'ЗБ':0.0,'ОВИР':0.0}; week_f={'ЗБ':0.0,'ОВИР':0.0}; mtd={'ЗБ':0.0,'ОВИР':0.0}; year_f={'ЗБ':0.0,'ОВИР':0.0}
yr=str(today.year)
for r_ in rows:
    if len(r_)<3: continue
    d,loc=r_[0],r_[1]
    if loc not in day_f: continue
    try: rev=float(r_[2] or 0)
    except: continue
    if d.startswith(yr): year_f[loc]+=rev
    if d.startswith(mon): mtd[loc]+=rev
    if d in week_days: week_f[loc]+=rev
    if d==str(yday): day_f[loc]=rev
PLAN={'ЗБ':354000,'ОВИР':277000}
def f(n): return f'{int(round(n)):,}'.replace(',',' ')
def pct(fact,plan): return f'{round(fact/plan*100)}%' if plan else '—'
def rev_table(title, fact, plan_div):
    """plan_div: делитель месячного плана (1=месяц, dim=день, dim/7=неделя)"""
    pz,po=PLAN['ЗБ']/plan_div,PLAN['ОВИР']/plan_div
    return [{'heading_3':{'rich_text':t(title)}},
     {'table':{'table_width':4,'has_column_header':True,'children':[
       {'table_row':{'cells':[t('Точка'),t('План'),t('Факт'),t('%')]}},
       {'table_row':{'cells':[t('ЗБ'),t(f(pz)),t(f(fact['ЗБ'])),t(pct(fact['ЗБ'],pz))]}},
       {'table_row':{'cells':[t('ОВИР'),t(f(po)),t(f(fact['ОВИР'])),t(pct(fact['ОВИР'],po))]}},
       {'table_row':{'cells':[t('Сеть'),t(f(pz+po)),t(f(fact['ЗБ']+fact['ОВИР'])),t(pct(fact['ЗБ']+fact['ОВИР'],pz+po))]}},
     ]}}]

# ── 2. Дашборд ПРЯМО на главной ──
dw_cols={'type':'column_list','column_list':{'children':[
    {'type':'column','column':{'children': rev_table(f'📅 День (вчера, {yday.strftime("%d.%m")})', day_f, dim)}},
    {'type':'column','column':{'children': rev_table('📆 Неделя (7 дней)', week_f, dim/7)}},
]}}
my_cols={'type':'column_list','column_list':{'children':[
    {'type':'column','column':{'children': rev_table(f'🗓 Месяц (MTD, {today.day-1} дн.)', mtd, 1)}},
    {'type':'column','column':{'children': rev_table(f'📈 Год ({yr}, YTD)', year_f, 1/12)}},
]}}
add(ROOT,
 [call(f'Открыл — увидел всё. Обновлено {today.strftime("%d.%m.%Y")}, прошло {today.day-1} дн. месяца. Выручка без п/ф (СНБЖ). Цифры из Poster (бот утром).','🌸','yellow_background'),
  h2('💰 Выручка — план / факт'),
  dw_cols, my_cols]
)
tdb=post('databases',{'parent':{'page_id':ROOT},'title':t('🎯 Тактические задачи'),'is_inline':True,
 'properties':{'Задача':{'title':{}},
  'Статус':{'select':{'options':[{'name':'Не начато','color':'gray'},{'name':'В работе','color':'blue'},{'name':'Готово','color':'green'}]}},
  'Срок':{'date':{}},'Кто':{'select':{'options':[{'name':'Азиз'},{'name':'Владимир'},{'name':'Дилчу'},{'name':'Claude'}]}}}})['id']
for q,st,who in [('Poster ОВИР — оплатить (просрочен с 01.05)','Не начато','Азиз'),
    ('Раздать телефоны+сетку управляющим, собрать подписи','Не начато','Азиз'),
    ('Провести Beeyor и базар в Poster при оплате','Не начато','Азиз')]:
    post('pages',{'parent':{'database_id':tdb},'properties':{'Задача':{'title':t(q)},'Статус':{'select':{'name':st}},'Кто':{'select':{'name':who}}}})
sdb=post('databases',{'parent':{'page_id':ROOT},'title':t('🏛 Стратегические задачи'),'is_inline':True,
 'properties':{'Задача':{'title':{}},
  'Этап':{'select':{'options':[{'name':'Июль','color':'red'},{'name':'Август','color':'orange'},{'name':'Сентябрь','color':'yellow'},{'name':'Q4','color':'green'},{'name':'2027','color':'blue'}]}},
  'Статус':{'select':{'options':[{'name':'Не начато','color':'gray'},{'name':'В работе','color':'blue'},{'name':'Готово','color':'green'}]}}}})['id']
for q,et in [('Собрать чек-листы смены + регламент инкассации','Июль'),('Все расходы в Poster → оживить P&L','Август'),
    ('Должностные карты + KPI с бонусами','Сентябрь'),('Система найма и онбординг','Q4'),('Вырастить директора сети','2027')]:
    post('pages',{'parent':{'database_id':sdb},'properties':{'Задача':{'title':t(q)},'Этап':{'select':{'name':et}},'Статус':{'select':{'name':'Не начато'}}}})
vdb=post('databases',{'parent':{'page_id':ROOT},'title':t('🚨 Нарушения (за вчера — фильтруй по дате)'),'is_inline':True,
 'properties':{'Нарушение':{'title':{}},'Дата':{'date':{}},
  'Точка':{'select':{'options':[{'name':'ЗБ','color':'green'},{'name':'ОВИР','color':'blue'}]}},
  'Сотрудник':{'rich_text':{}},
  'Категория':{'select':{'options':[{'name':'Телефон','color':'red'},{'name':'Гигиена','color':'yellow'},{'name':'Отсутствие','color':'orange'},{'name':'Опоздание','color':'purple'},{'name':'Санитария','color':'brown'},{'name':'Качество','color':'pink'},{'name':'Прочее','color':'gray'}]}},
  'Статус':{'select':{'options':[{'name':'Новое','color':'red'},{'name':'Разобрано','color':'green'}]}}}})['id']

add(ROOT,[divider(), h2('📁 Документы')])

# ── 3. Страницы документов (ниже дашборда) ──
sop=subpage('SOP и регламенты','📄')
add(sop,[call('V.0 — черновик, V.1+ — готов','📄','gray_background'),
 h3('Управление'),
 L('SOP — Управляющий (V.1)',gl('10vfIchEJ0Qklc7QYq7o-q7HaYtrHNNaWJA6Wxdwf854')),
 L('SOP — Управляющий ЗБ, Владимир (V.1)',gl('1MCU_lKa_lpCPh5CdLWmZcMU6EAGzU8pxiQm6Z2aLfXc')),
 L('SOP — Управляющий ОВИР, Дилчу (V.1)',gl('1hmVutQPQHuVbvxPX9EUlQsVSwKw900puEUaIPHxZjOo')),
 L('SOP — Старший повар (V.0)',gl('1D6WEztGzM5oTwsSZUzhkNlOozrBHUj2Ejdas0Ao8nkg')),
 L('Оргструктура 2026',gl('1AgGban4JJ-io6V64O4_nJmdpyxYvqkCWXgYcVeCC31E')),
 h3('Должностные'),
 L('SOP — Кассир (V.1)',gl('13MpNsYFtnwyhKfOUQMDXNM_1uxsiEVpf5opbAhMXuO4')),
 L('SOP — Повар (V.1)',gl('13aYCe-gBJ3GLIkaeaYidxGWEX3ogCTsRZXmCPC_Z7Ow')),
 L('SOP — Бариста (V.1)',gl('13Lxp-1wYV9NttvCH02ODdAKtM6RLk5-MuiwI6eZ62Qg')),
 L('SOP — Уборщица (V.1)',gl('13nVBtrsOm097J-RJnpJvTIFMx4tMIjqQ9XBD6PmadQ0')),
 L('Регламент кассира — Касса и Poster (V.2)',gl('1VEy9ZUzAdGUq2msP47f6k8qzlWNsvKf4oPSvgmXA53M')),
 h3('Дисциплина и HR'),
 L('Onboarding (V.0)',gl('1FooHt7LChfrPDzUn4AWZp7wyx8SJ3IsAj6eSSuANEX0')),
 L('Кассовая дисциплина (V.0)',gl('1FlBVnPkQkZV4QBUyBYq4Xh_0Rw9aO63P2eXgCPO7hW8')),
 L('Правила урегулирования конфликтов (V.1)',gl('186Wm0wV6vouDVxF7dSuwj8wdOgNmT0o3HsGgfo_V7R0')),
 L('Культурный код (Персонал)',gl('12GO9J6JOR83_IXmJ4urP4y_dla9l8Oh-wrBVs3BQS4s')),
])
fin=subpage('Финансовые документы','💰')
add(fin,[L('Категории расходов в Poster (V.1)',gl('1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s')),
 L('Протокол проверки транзакций (V.1)',gl('1UBMAN45H4vxwMTV9i-m8g4bx7scIej_b89sONWr1Ch0')),
 L('Правила — Super P&L',gl('1ybEYLMeC43z0g7WD38xI4RR2ENAoY8HQGQGjcqGGmN0')),
 L('Правила — Дневной трекер',gl('11VuNq-xUKU3E16l2OHNiPPGPvnpooPOo_XQgvDcU22I')),
 L('Архитектура Poster и P&L',gl('1w98KIgsHP3twOB5xS_2HeL9RW2tttaElRJtyRnf-m68')),
 L('Тренинг по инвентаризации (V.1)',gl('1T5tnXq-j8D6axpd4tu5VsK8pPbN3bkRxSloGFSOsg-U')),
 L('Тренинг по списаниям (V.1)',gl('1dcUP_-Tlzq11yUgGrJ_uzz33ZjpH_grAFQVHiux9GfA')),
])
proc=subpage('Процессы и стандарты','⚙️')
add(proc,[L('Генеральная уборка (V.1)',gl('15xD4N1hoFAlOaCbTA8ku7Y8j3u56dj8bjP8BBbBb9Bk')),
 L('Хранение продуктов и инвентаря (V.1)',gl('13rMzSH4xKhcpIWYjN4hylP92Wfxggri-LUn6vPXEzGw')),
 L('Приём товаров (V.0)',gl('1F9OBuY6wZf7VbaK-5hzDAGL94U6wnJDgjQb6chVG0wk')),
 L('Заявка с цеха (V.0)',gl('1DIXWsM0-S-6Sqs4E5Y3qJalBvnHMLBnbyWo-SGajAG4')),
 L('Эксплуатация кофемашины',gl('1hT7qf0JQH1aUdAxQa7Hm5azbRBo5KhlmtoeFUdGTXQg')),
 L('Работа вытяжки (V.0)',gl('18YFCexVO1DDtqu6SlbInvu9-RhVVm2-oBOjBM2ZTglw')),
 L('Экономия электроэнергии (V.1)',gl('19oE3lX1Oh7ECj8UHBVF9_dcNkDXNVUq8YaxXPYimP00')),
])
ttk=subpage('ТТК — техкарты','🍽')
add(ttk,[L('Барная карта — Полное меню (ТТК сводка)',gs('1lGyfPuviZDcKBQp9_vixmlimZ7n2gXXHXSKfDtRk-48')),
 L('Аудит меню 2026',gl('1weeXMF9ETFzLh7sQNRHoIamL3rpe4brpaX2ObtjM03k')),
 h3('Шаурмы'),
 L('Говяжья «Стандарт»',gl('18RFiG1aYDo1NsBBe62f2eapk2cVXJkXSvLiL4IxmDVk')),
 L('Куриная «Стандарт»',gl('1oQUysKscQUaTZrUOULDBwXoSK-Frq9Qz0jpS595VIOg')),
 L('Говяжья «Полкило»',gl('1QfNTDsFWjUm7ioNR4C_RawXl53ig3Hu5o3h_lVtl5Dg')),
 L('Куриная «Полкило»',gl('1ahH7oqsnziaPPSDf8matqRNJigo6MBR1JUgXLO2QIdc')),
 L('«Дружба народов»',gl('1iBQJH5n252FVweTxLZp8roVFT9JstN1C1tEJALvOXiY')),
 L('«Комсомольская»',gl('1s-rMOGa6lSZqDPf3qk6i6FUxvjPSEfYHKzm72bHtCH8')),
 L('«Пионерская»',gl('1dnOsrpOd6kpN5y97NOln8yZzhf67HhyG6lqa65FSB0A')),
 L('«Сырная»',gl('1wjskAecSoKO_y0zFPAJOX5dzGbxYWHn6k2UfoZsxf78')),
 L('«Чехова»',gl('15CWvS8ijyMSmpiAj_HiUj0PIKmboBEdsBKgSX9wV8w4')),
 h3('Питы, салаты, соусы'),
 L('Пита говяжья',gl('1Mhgx5MWMHCwkWpgcQolQf-wTVP2DI2ErvTGe6DVEPLs')),
 L('Пита куриная',gl('1Eqnhh-4iajK20b151lckhp17F7sQHbzQwHZ62Ui0bJw')),
 L('Кесадилья',gl('1tTSZzis2pWzTgfO80vPWL83Lat-Rdk5YVCXInwhTwtA')),
 L('Салат «Цезарь»',gl('1I268LTDlAQJLigODu327l3CZDu2QCVzeTevSr0YArC0')),
 L('Салат «Цезарь с креветкой»',gl('1pGX94qDXd3oNEkyPtgIB6685OXQPJ7dD7YxISEk4wzY')),
 L('Салат «Греческий»',gl('1qVsmaaagvZ5lGxUmGwqW9L9QON2d-Ykwv4vld8Lrw5o')),
 L('Соус «Икорный»',gl('1WHL4_ngKeHrn3i49fgAi3OeOoowO1LXJFOdArdXB8SU')),
 h3('Торты'),
 L('«Медовик»',gl('1i7BaPCiOfdBkHk9c3tEpoenbIlnoPA2fORJJsBB9MBw')),
 L('«Наполеон»',gl('1b_TGVZxD9iVN-CKd7GWeuzKiI44WU9Q5UjPP9jol03Y')),
])
json.dump({'root':ROOT,'tdb':tdb,'sdb':sdb,'vdb':vdb,'sop':sop,'fin':fin,'proc':proc,'ttk':ttk},
          open('/home/user/My-vault/scripts/credentials/notion_ids.json','w'))
print('Главная пересобрана: дашборд сверху, документы ниже')
