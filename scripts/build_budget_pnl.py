#!/usr/bin/env python3
"""Личный бюджет: Operations + PnL (блоки, переходящий остаток) + Loans.
Стиль: Times New Roman 13, без цветовой заливки (правило оформления Азиза)."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
FONT='Times New Roman'; SIZE=13
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)
MON=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
COLS='BCDEFGHIJKLM'
def api(m,path,**kw):
    r=getattr(s,m)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw); r.raise_for_status()
    return r.json() if r.text else {}
def put(rng,vals):
    s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/{rng}?valueInputOption=USER_ENTERED',json={'values':vals},timeout=30).raise_for_status()
# локаль en_US — иначе формулы с запятыми и ISO-даты ломаются (корень багов с датами)
api('post',':batchUpdate',json={'requests':[{'updateSpreadsheetProperties':{'properties':{'locale':'en_US'},'fields':'locale'}}]})
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}
pnl=ids['PnL']

def sif(m, kind, cat):
    return (f'=SUMIFS(Operations!$D:$D,Operations!$A:$A,">="&DATE(2026,{m},1),'
            f'Operations!$A:$A,"<"&DATE(2026,{m}+1,1),Operations!$B:$B,"{kind}",Operations!$C:$C,"{cat}")')

# структура расходов: ('block', подытог-имя, [категории]) или ('single', None, [категория])
EXP_STRUCT=[
 ('block','Итого блок 1', ['Дом','Машина','Одежда/Обувь','Семья','Гаджеты','Подписки','Подарки']),
 ('block','Итого блок 2', ['Продукты','Кафе','Развлечение']),
 ('block','Итого Здоровье / Тело', ['Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна']),
 ('single',None,['Обучение']),
 ('single',None,['Курение']),
 ('single',None,['Оплата кредита']),
 ('single',None,['Путешествие']),
 ('single',None,['Прочее']),
]

rows=[['Категория']+MON+['Итого год']]
def add(label, cells, year):
    rows.append([label]+cells+[year]); return len(rows)
r_prev = add('Остаток с предыдущего месяца', ['']*12, '')
r_zp   = add('Зарплата',        [sif(m,'Доход','Зарплата') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_oth  = add('Прочий доход',     [sif(m,'Доход','Прочий доход') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_earn = add('Доход заработанный', [f'={c}{r_zp}+{c}{r_oth}' for c in COLS], f'=N{r_zp}+N{r_oth}')
r_cred = add('Кредиты получено (в долг)', [sif(m,'Доход','Кредит') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_inc  = add('ИТОГО поступления (остаток + заработок + кредит)', [f'={c}{r_prev}+{c}{r_earn}+{c}{r_cred}' for c in COLS], f'=N{r_earn}+N{r_cred}')
add('', ['']*12, '')
r_exphdr = add('РАСХОДЫ', ['']*12, '')

subtotals=[]; standalone=[]; num=1; cat_row={}; exp_order=[]
for kind,subname,cats in EXP_STRUCT:
    if kind=='block':
        start=len(rows)+1
        for c in cats:
            rr=add(f'{num}. {c}', [sif(m,'Расход',c) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; num+=1
            cat_row[c]=rr; exp_order.append(c)
        end=len(rows)
        sub=add(subname, [f'=SUM({col}{start}:{col}{end})' for col in COLS], f'=SUM(N{start}:N{end})')
        subtotals.append(sub)
    else:
        c=cats[0]; rr=add(f'{num}. {c}', [sif(m,'Расход',c) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; num+=1
        standalone.append(rr); cat_row[c]=rr; exp_order.append(c)

parts=subtotals+standalone
r_exp = add('Итого расходы', ['='+'+'.join(f'{col}{p}' for p in parts) for col in COLS], '='+'+'.join(f'N{p}' for p in parts))

# Накопления / Инвестиции — отдельный блок ВНЕ расходов (отложенные деньги = не трата, а перевод себе)
add('', ['']*12, '')
r_savhdr = add('НАКОПЛЕНИЯ / ИНВЕСТИЦИИ', ['']*12, '')
sav_start=len(rows)+1; sav_row={}
for c in ['Накопления / Подушка','Инвестиции']:
    rr=add(c, [sif(m,'Накопление',c) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; sav_row[c]=rr
sav_end=len(rows); r_cushion=sav_row['Накопления / Подушка']
r_sav = add('Итого отложено', [f'=SUM({col}{sav_start}:{col}{sav_end})' for col in COLS], f'=SUM(N{sav_start}:N{sav_end})')

add('', ['']*12, '')
# Остаток (кэш) = все поступления − расходы − отложено; переходит на след. месяц
r_bal = add('Остаток (кэш, переходит на след. месяц)', [f'={col}{r_inc}-{col}{r_exp}-{col}{r_sav}' for col in COLS], f'=N{r_inc}-N{r_exp}-N{r_sav}')
# Справочно: результат без заёмных — сколько заработал минус потратил/отложил (минус = живёшь в долг)
r_net = add('Чистый результат без кредитов (справочно)', [f'={col}{r_earn}-{col}{r_exp}-{col}{r_sav}' for col in COLS], f'=N{r_earn}-N{r_exp}-N{r_sav}')
put('PnL!A1',rows)
# переходящий остаток пишем ПОСЛЕ основной таблицы (иначе перезатирается)
carry=['0']+[f'={COLS[k]}{r_bal}' for k in range(11)]
put(f'PnL!B{r_prev}:M{r_prev}',[carry])

# формат
def whole(sheet):
    return {'repeatCell':{'range':{'sheetId':sheet},
        'cell':{'userEnteredFormat':{'textFormat':{'fontFamily':FONT,'fontSize':SIZE,'bold':False},'backgroundColor':{'red':1,'green':1,'blue':1}}},
        'fields':'userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize,userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColor'}}
def boldrow(sheet,r0):
    return {'repeatCell':{'range':{'sheetId':sheet,'startRowIndex':r0-1,'endRowIndex':r0},'cell':{'userEnteredFormat':{'textFormat':{'bold':True}}},'fields':'userEnteredFormat.textFormat.bold'}}
reqs=[whole(pnl)]+[boldrow(pnl,rr) for rr in [1,r_earn,r_inc,r_exphdr,r_exp,r_savhdr,r_sav,r_bal,r_net]+subtotals]
reqs.append({'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':1,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}})
for t in ('Operations','Loans'):
    if t in ids: reqs+= [whole(ids[t]), boldrow(ids[t],1)]

# ── Валидация Operations: выпадающие списки на Тип и Категорию (защита от опечаток/утечек) ──
TYPES=['Доход','Расход','Накопление']
CATS_ALL=['Зарплата','Прочий доход','Кредит',
 'Дом','Машина','Одежда/Обувь','Семья','Гаджеты','Подписки','Подарки','Продукты','Кафе','Развлечение',
 'Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна',
 'Обучение','Курение','Оплата кредита','Путешествие','Прочее','Накопления / Подушка','Инвестиции']
def validation(sheet,col0,values):
    return {'setDataValidation':{'range':{'sheetId':sheet,'startRowIndex':1,'endRowIndex':1000,'startColumnIndex':col0,'endColumnIndex':col0+1},
      'rule':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':v} for v in values]},'showCustomUi':True,'strict':True}}}
ops=ids['Operations']
reqs+= [validation(ops,1,TYPES), validation(ops,2,CATS_ALL)]

api('post',':batchUpdate',json={'requests':reqs})
print('PnL перестроен. Строк:', len(rows), '| валидация Тип+Категория добавлена')

# ============================ ДАШБОРД ============================
DASH='Дашборд'
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}
# сохраняем введённые пользователем данные (план по категориям, месяц, цель подушки) перед пересборкой
prev={}
if DASH in ids:
    for rrow in api('get',f'/values/{DASH}!A1:B120?valueRenderOption=UNFORMATTED_VALUE').get('values',[]):
        if rrow and str(rrow[0]).strip():
            prev[rrow[0]]= rrow[1] if len(rrow)>1 else ''
if DASH not in ids:
    resp=api('post',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':DASH,'index':1}}}]})
    dash_id=resp['replies'][0]['addSheet']['properties']['sheetId']
else:
    dash_id=ids[DASH]; api('post',f'/values/{DASH}!A1:Z400:clear',json={})

def pref(r): return f'=INDEX(PnL!B{r}:M{r},1,$B$2)'   # значение выбранного месяца из строки PnL
D=[]
def d(*cells): D.append(list(cells)); return len(D)
d('Личный бюджет — Дашборд')
d('Месяц (1–12):', prev.get('Месяц (1–12):',8), '=CHOOSE($B$2,"Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь")')
d('')
h_metrics=d('КЛЮЧЕВЫЕ МЕТРИКИ (выбранный месяц)')
m_earn=d('Заработано', pref(r_earn))
d('Кредиты (в долг)', pref(r_cred))
m_exp=d('Потрачено', pref(r_exp))
m_sav=d('Отложено', pref(r_sav))
d('Остаток (кэш)', pref(r_bal))
d('Чистый результат без кредитов', pref(r_net))
r_norm=d('Норма сбережений', f'=IFERROR(B{m_sav}/B{m_earn},0)')
d('')
h_pf=d('ПЛАН / ФАКТ ПО КАТЕГОРИЯМ (выбранный месяц)')
h_tbl=d('Категория','План/мес','Факт','Δ план−факт','Исполнение','Доля в расходах','Статус')
first_cat=len(D)+1
for c in exp_order:
    rr=cat_row[c]; row=len(D)+1
    d(c,prev.get(c,''),f'=INDEX(PnL!B{rr}:M{rr},1,$B$2)',f'=B{row}-C{row}',
      f'=IFERROR(C{row}/B{row},"")',f'=IFERROR(C{row}/$B${m_exp},0)',
      f'=IF(AND(B{row}<>"",C{row}>B{row}),"⚠ перерасход","")')
last_cat=len(D)
row=len(D)+1
r_tot=d('ИТОГО',f'=SUM(B{first_cat}:B{last_cat})',pref(r_exp),f'=B{row}-C{row}',
        f'=IFERROR(C{row}/B{row},"")',f'=IFERROR(C{row}/$B${m_exp},0)','')
d('')
h_dyn=d('ДИНАМИКА ПО МЕСЯЦАМ')
h_dyn2=d('Показатель','Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек','Год')
def dynrow(label,r): d(label,*[f'=PnL!{col}{r}' for col in COLS],f'=PnL!N{r}')
dynrow('Заработано',r_earn); dynrow('Потрачено',r_exp); dynrow('Отложено',r_sav); dynrow('Остаток (кэш)',r_bal)
r_dnorm=d('Норма сбережений',*[f'=IFERROR(PnL!{col}{r_sav}/PnL!{col}{r_earn},0)' for col in COLS],
          f'=IFERROR(PnL!N{r_sav}/PnL!N{r_earn},0)')
d('')
# ── Подушка безопасности: цель (мес расходов × среднемес.расход) и прогресс ──
h_cush=d('ПОДУШКА БЕЗОПАСНОСТИ')
r_cmon=d('Цель подушки (мес расходов):', prev.get('Цель подушки (мес расходов):',3))
r_cavg=d('Среднемесячный расход', f'=IFERROR(PnL!N{r_exp}/COUNTIF(PnL!B{r_exp}:M{r_exp},">0"),0)')
r_cgoal=d('Цель подушки (сумма)', f'=B{r_cmon}*B{r_cavg}')
r_csav=d('Накоплено в подушку', f'=PnL!N{r_cushion}')
r_cprog=d('Прогресс к цели', f'=IFERROR(B{r_csav}/B{r_cgoal},0)')
r_cleft=d('Осталось накопить', f'=MAX(B{r_cgoal}-B{r_csav},0)')
put(f'{DASH}!A1',D)

# формат дашборда
def pctfmt(r0,r1,c0,c1):
    return {'repeatCell':{'range':{'sheetId':dash_id,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
        'cell':{'userEnteredFormat':{'numberFormat':{'type':'PERCENT','pattern':'0.0%'}}},'fields':'userEnteredFormat.numberFormat'}}
dreqs=[whole(dash_id)]+[boldrow(dash_id,x) for x in [1,h_metrics,h_pf,h_tbl,h_dyn,h_dyn2,r_tot,h_cush,r_cgoal]]
dreqs+= [pctfmt(r_norm-1,r_norm,1,2), pctfmt(first_cat-1,r_tot,4,6), pctfmt(r_dnorm-1,r_dnorm,1,14),
         pctfmt(r_cprog-1,r_cprog,1,2)]
dreqs+= [
 {'updateDimensionProperties':{'range':{'sheetId':dash_id,'dimension':'COLUMNS','startIndex':0,'endIndex':1},'properties':{'pixelSize':240},'fields':'pixelSize'}},
 {'updateDimensionProperties':{'range':{'sheetId':dash_id,'dimension':'COLUMNS','startIndex':1,'endIndex':14},'properties':{'pixelSize':82},'fields':'pixelSize'}},
 {'setDataValidation':{'range':{'sheetId':dash_id,'startRowIndex':1,'endRowIndex':2,'startColumnIndex':1,'endColumnIndex':2},
    'rule':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':str(i)} for i in range(1,13)]},'showCustomUi':True,'strict':True}}},
]
api('post',':batchUpdate',json={'requests':dreqs})
print('Дашборд собран. Строк:', len(D))

# ============================ ЛИСТ «СЧЕТА» (балансы + сверка) ============================
ACC='Счета'
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}
prevacc={}
if ACC in ids:
    for rrow in api('get',f'/values/{ACC}!A1:B80?valueRenderOption=UNFORMATTED_VALUE').get('values',[]):
        if rrow and str(rrow[0]).strip(): prevacc[rrow[0]]= rrow[1] if len(rrow)>1 else ''
    acc_id=ids[ACC]; api('post',f'/values/{ACC}!A1:D80:clear',json={})
else:
    resp=api('post',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':ACC,'index':2}}}]})
    acc_id=resp['replies'][0]['addSheet']['properties']['sheetId']
A=[]
def a(*c): A.append(list(c)); return len(A)
a('Личный бюджет — Счета и балансы')
a('')
a_hdr=a('Счёт','Баланс (факт, ввести вручную)')
DEFAULT_ACCS=['Наличные','Карта','Сбережения / вклад','Прочее']
first_acc=len(A)+1
for name in DEFAULT_ACCS: a(name, prevacc.get(name,''))
last_acc=len(A)
a_tot=a('ИТОГО по счетам', f'=SUM(B{first_acc}:B{last_acc})')
a('')
a_cash=a('Остаток по таблице (PnL, кэш выбр. месяца)', f'=INDEX(PnL!B{r_bal}:M{r_bal},1,{DASH}!$B$2)')
a_diff=a('Расхождение (счета − таблица)', f'=B{a_tot}-B{a_cash}')
a('')
a('Если расхождение ≠ 0 — есть неучтённые деньги или траты. Свести к нулю.')
put(f'{ACC}!A1',A)
areqs=[whole(acc_id)]+[boldrow(acc_id,x) for x in [1,a_hdr,a_tot,a_cash,a_diff]]
areqs+= [
 {'updateDimensionProperties':{'range':{'sheetId':acc_id,'dimension':'COLUMNS','startIndex':0,'endIndex':1},'properties':{'pixelSize':300},'fields':'pixelSize'}},
 {'updateDimensionProperties':{'range':{'sheetId':acc_id,'dimension':'COLUMNS','startIndex':1,'endIndex':2},'properties':{'pixelSize':160},'fields':'pixelSize'}},
]
api('post',':batchUpdate',json={'requests':areqs})
print('Лист «Счета» собран.')

# ============================ LOANS: связь с погашениями ============================
# Всего погашено берём из Operations (Расход / «Оплата кредита») — теперь долг считается сам
put('Loans!G1:H3',[
 ['Всего получено','=SUMIFS(Loans!$D:$D,Loans!$B:$B,"Получен")'],
 ['Всего погашено','=SUMIFS(Operations!$D:$D,Operations!$B:$B,"Расход",Operations!$C:$C,"Оплата кредита")'],
 ['Текущий долг','=H1-H2'],
])
print('Loans связан с погашениями (Operations → «Оплата кредита»).')
