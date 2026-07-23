#!/usr/bin/env python3
"""Строит в Notion реестр документов Ромашки + категорийные блоки."""
import os, json, time, requests
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
TOK = open('/home/user/My-vault/scripts/credentials/notion.token').read().strip()
H = {'Authorization': f'Bearer {TOK}', 'Notion-Version': '2022-06-28', 'Content-Type': 'application/json'}
IDS = json.load(open('/home/user/My-vault/scripts/credentials/notion_ids.json'))
API = 'https://api.notion.com/v1'
DOCS_PAGE = IDS['docs']

def post(path, payload):
    for a in range(4):
        r = requests.post(f'{API}/{path}', headers=H, json=payload, timeout=30)
        if r.status_code == 429: time.sleep(2); continue
        if r.status_code != 200: print('ERR', r.status_code, r.text[:300]); raise SystemExit
        return r.json()
def gl(id_): return f'https://docs.google.com/document/d/{id_}'

# ── Реестр документов: (Название, Категория, Статус, Приоритет, ссылка) ────────
# Статус: Готов / Черновик / Собрать(нет)
D = [
# УПРАВЛЕНИЕ
('SOP — Управляющий (V.1)','Управление','Готов','—',gl('10vfIchEJ0Qklc7QYq7o-q7HaYtrHNNaWJA6Wxdwf854')),
('SOP — Управляющий ЗБ, Владимир (V.1)','Управление','Готов','—',gl('1MCU_lKa_lpCPh5CdLWmZcMU6EAGzU8pxiQm6Z2aLfXc')),
('SOP — Управляющий ОВИР, Дилчу (V.1)','Управление','Готов','—',gl('1hmVutQPQHuVbvxPX9EUlQsVSwKw900puEUaIPHxZjOo')),
('SOP — Старший повар (V.0)','Управление','Черновик','P1',gl('1D6WEztGzM5oTwsSZUzhkNlOozrBHUj2Ejdas0Ao8nkg')),
('Ромашка — Оргструктура 2026','Управление','Готов','—',gl('1AgGban4JJ-io6V64O4_nJmdpyxYvqkCWXgYcVeCC31E')),
('Ромашка — Брифинг с управляющими Май 2026','Управление','Готов','—',gl('1wr7hBGHmboSezdsYeNHDkzIEMm_juzfOfinNKMB6Efs')),
# ДОЛЖНОСТНЫЕ SOP
('SOP — Кассир (V.1)','Должностные','Готов','—',gl('13MpNsYFtnwyhKfOUQMDXNM_1uxsiEVpf5opbAhMXuO4')),
('SOP — Повар (V.1)','Должностные','Готов','—',gl('13aYCe-gBJ3GLIkaeaYidxGWEX3ogCTsRZXmCPC_Z7Ow')),
('SOP — Бариста (V.1)','Должностные','Готов','—',gl('13Lxp-1wYV9NttvCH02ODdAKtM6RLk5-MuiwI6eZ62Qg')),
('SOP — Уборщица (V.1)','Должностные','Готов','—',gl('13nVBtrsOm097J-RJnpJvTIFMx4tMIjqQ9XBD6PmadQ0')),
# ДИСЦИПЛИНА / HR
('Правило телефонов на смене','Дисциплина/HR','Готов','P1','notion'),
('Дисциплинарная сетка','Дисциплина/HR','Готов','P1','notion'),
('Onboarding (V.0)','Дисциплина/HR','Черновик','P1',gl('1FooHt7LChfrPDzUn4AWZp7wyx8SJ3IsAj6eSSuANEX0')),
('Кассовая дисциплина (V.0)','Дисциплина/HR','Черновик','P1',gl('1FlBVnPkQkZV4QBUyBYq4Xh_0Rw9aO63P2eXgCPO7hW8')),
('Правила урегулирования конфликтов (V.1)','Дисциплина/HR','Готов','—',gl('186Wm0wV6vouDVxF7dSuwj8wdOgNmT0o3HsGgfo_V7R0')),
('Культурный код (Персонал)','Дисциплина/HR','Готов','—',gl('12GO9J6JOR83_IXmJ4urP4y_dla9l8Oh-wrBVs3BQS4s')),
('Стратегический Культурный код','Дисциплина/HR','Готов','—',gl('11rvDi4WQj41EVXuKSHrqpb8dIKiX8NRtHCENooQjKx8')),
# ФИНАНСЫ / УЧЁТ
('Регламент кассира — Касса и Poster (V.2)','Финансы/учёт','Готов','—',gl('1VEy9ZUzAdGUq2msP47f6k8qzlWNsvKf4oPSvgmXA53M')),
('Ромашка — Категории расходов в Poster (V.1)','Финансы/учёт','Готов','—',gl('1pFqgbDmThuQF2qvtG_oqMY7BrNd81rt-bKynycv7g4s')),
('Протокол проверки транзакций Poster (V.1)','Финансы/учёт','Готов','—',gl('1UBMAN45H4vxwMTV9i-m8g4bx7scIej_b89sONWr1Ch0')),
('Правила — Super P&L','Финансы/учёт','Готов','—',gl('1ybEYLMeC43z0g7WD38xI4RR2ENAoY8HQGQGjcqGGmN0')),
('Правила — Дневной трекер','Финансы/учёт','Готов','—',gl('11VuNq-xUKU3E16l2OHNiPPGPvnpooPOo_XQgvDcU22I')),
('Архитектура Poster и логика P&L','Финансы/учёт','Готов','—',gl('1w98KIgsHP3twOB5xS_2HeL9RW2tttaElRJtyRnf-m68')),
('Тренинг по инвентаризации (V.1)','Финансы/учёт','Готов','—',gl('1T5tnXq-j8D6axpd4tu5VsK8pPbN3bkRxSloGFSOsg-U')),
('Тренинг по списаниям (V.1)','Финансы/учёт','Готов','—',gl('1dcUP_-Tlzq11yUgGrJ_uzz33ZjpH_grAFQVHiux9GfA')),
# ПРОЦЕССЫ / ЭКСПЛУАТАЦИЯ
('SOP — Генеральная уборка (V.1)','Процессы','Готов','—',gl('15xD4N1hoFAlOaCbTA8ku7Y8j3u56dj8bjP8BBbBb9Bk')),
('Правила хранения продуктов и инвентаря (V.1)','Процессы','Готов','—',gl('13rMzSH4xKhcpIWYjN4hylP92Wfxggri-LUn6vPXEzGw')),
('Правила приёма товаров (V.0)','Процессы','Черновик','P2',gl('1F9OBuY6wZf7VbaK-5hzDAGL94U6wnJDgjQb6chVG0wk')),
('SOP — Заявка с цеха (V.0)','Процессы','Черновик','P2',gl('1DIXWsM0-S-6Sqs4E5Y3qJalBvnHMLBnbyWo-SGajAG4')),
('Правила работы вытяжки (V.0)','Процессы','Черновик','P3',gl('18YFCexVO1DDtqu6SlbInvu9-RhVVm2-oBOjBM2ZTglw')),
('Чеклист эксплуатации кофемашины','Процессы','Готов','—',gl('1hT7qf0JQH1aUdAxQa7Hm5azbRBo5KhlmtoeFUdGTXQg')),
('Экономия электроэнергии и климат (V.1)','Процессы','Готов','—',gl('19oE3lX1Oh7ECj8UHBVF9_dcNkDXNVUq8YaxXPYimP00')),
# КУХНЯ / ТТК (свод)
('Барная карта — Полное меню (ТТК сводка)','Кухня/ТТК','Готов','—','https://docs.google.com/spreadsheets/d/1lGyfPuviZDcKBQp9_vixmlimZ7n2gXXHXSKfDtRk-48'),
('Аудит меню — Ромашка 2026','Кухня/ТТК','Готов','—',gl('1weeXMF9ETFzLh7sQNRHoIamL3rpe4brpaX2ObtjM03k')),
('ТТК — Шаурмы, питы, салаты, соусы, п/ф (~30 карт)','Кухня/ТТК','Готов','—','https://drive.google.com/drive/folders/root'),
# ── К СОЗДАНИЮ (по методу 12 шагов) ──
('Чек-лист открытия смены','Процессы','Собрать','P1','—'),
('Чек-лист закрытия смены','Процессы','Собрать','P1','—'),
('Регламент инкассации и сверки кассы','Финансы/учёт','Собрать','P1','—'),
('Регламент закупки на базаре (Махмуд)','Процессы','Собрать','P1','—'),
('Регламент доставки Beeyor (приём + комплектация)','Процессы','Собрать','P2','—'),
('Должностные карты 6 ролей (1 стр. каждая)','Управление','Собрать','P2','—'),
('KPI-карты с бонусами (управляющий, старший, повар, кассир)','Управление','Собрать','P2','—'),
('Профиль кандидата (кассир / повар)','Дисциплина/HR','Собрать','P2','—'),
]

# ── База ──
db = post('databases', {'parent': {'page_id': DOCS_PAGE},
  'title':[{'text':{'content':'Реестр документов'}}], 'is_inline': True,
  'properties': {
    'Документ': {'title': {}},
    'Категория': {'select': {'options':[
        {'name':'Управление','color':'blue'},{'name':'Должностные','color':'purple'},
        {'name':'Дисциплина/HR','color':'red'},{'name':'Финансы/учёт','color':'green'},
        {'name':'Процессы','color':'orange'},{'name':'Кухня/ТТК','color':'yellow'}]}},
    'Статус': {'select': {'options':[
        {'name':'Готов','color':'green'},{'name':'Черновик','color':'yellow'},{'name':'Собрать','color':'red'}]}},
    'Приоритет': {'select': {'options':[
        {'name':'P1','color':'red'},{'name':'P2','color':'orange'},{'name':'P3','color':'gray'},{'name':'—','color':'default'}]}},
    'Ссылка': {'url': {}},
  }})['id']

for name, cat, st, pri, link in D:
    props = {
      'Документ': {'title':[{'text':{'content':name}}]},
      'Категория': {'select':{'name':cat}},
      'Статус': {'select':{'name':st}},
      'Приоритет': {'select':{'name':pri}},
    }
    if link and link.startswith('http'):
        props['Ссылка'] = {'url': link}
    post('pages', {'parent':{'database_id':db}, 'properties':props})

# сводка
готов = sum(1 for d in D if d[2]=='Готов')
черн = sum(1 for d in D if d[2]=='Черновик')
собр = sum(1 for d in D if d[2]=='Собрать')
print(f'Реестр создан: {len(D)} записей | Готов {готов} · Черновик {черн} · Собрать {собр}')
print('db_id', db)
