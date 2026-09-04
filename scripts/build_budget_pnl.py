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

# структура расходов: блоки названы по смыслу (сверху обязательное, снизу хотелки)
# «Оплата кредита» вынесена из расходов в зону «Сбережения и долг» (это не потребление)
EXP_STRUCT=[
 ('block','Итого — Обязательное / Быт', ['Дом','Машина','Подписки','Рассрочка','Семья']),
 ('block','Итого — Еда', ['Продукты','Кафе']),
 ('block','Итого — Здоровье / Тело', ['Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна']),
 ('block','Итого — Хотелки / Досуг', ['Одежда/Обувь','Гаджеты','Подарки','Развлечение','Путешествие','Обучение','Курение']),
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

# Сбережения и долг — ВНЕ расходов (накопления = перевод себе; погашение = уменьшение долга; оба не потребление)
add('', ['']*12, '')
r_savhdr = add('СБЕРЕЖЕНИЯ И ДОЛГ', ['']*12, '')
# (метка в PnL, тип в Operations, категория в Operations)
SAV_STRUCT=[('Накопления / Подушка','Накопление','Накопления / Подушка'),
            ('Инвестиции','Накопление','Инвестиции'),
            ('Погашение кредита','Погашение','Оплата кредита')]
sav_start=len(rows)+1; sav_row={}
for label,kind,opcat in SAV_STRUCT:
    rr=add(label, [sif(m,kind,opcat) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; sav_row[label]=rr
sav_end=len(rows); r_cushion=sav_row['Накопления / Подушка']
r_sav = add('Итого — сбережения и долг', [f'=SUM({col}{sav_start}:{col}{sav_end})' for col in COLS], f'=SUM(N{sav_start}:N{sav_end})')
# Норма сбережений считается только от накоплений. Погашение кредита —
# это возврат чужих денег, а не отложенное себе: в августе 2026 при нулевой
# подушке дашборд показывал «норма сбережений 13,9 %», потому что в неё
# попали 974 сомони погашения. Число говорило, что человек сберегает,
# когда он не сберегает. Строка вне SUM(sav_start:sav_end) — итог не меняется.
r_pay=sav_row['Погашение кредита']
r_savonly = add('Итого — накопления (без погашения долга)',
                [f'={col}{r_cushion}+{col}{sav_row["Инвестиции"]}' for col in COLS],
                f'=N{r_cushion}+N{sav_row["Инвестиции"]}')

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
TYPES=['Доход','Расход','Накопление','Погашение']
CATS_ALL=['Зарплата','Прочий доход','Кредит',
 'Дом','Машина','Одежда/Обувь','Семья','Гаджеты','Подписки','Рассрочка','Подарки','Продукты','Кафе','Развлечение',
 'Лечение / Медикаменты','Спортивное питание','Абонемент в зал','БАДы','Массаж / Сауна',
 'Обучение','Курение','Оплата кредита','Путешествие','Прочее','Накопления / Подушка','Инвестиции']
def validation(sheet,col0,values):
    return {'setDataValidation':{'range':{'sheetId':sheet,'startRowIndex':1,'endRowIndex':1000,'startColumnIndex':col0,'endColumnIndex':col0+1},
      'rule':{'condition':{'type':'ONE_OF_LIST','values':[{'userEnteredValue':v} for v in values]},'showCustomUi':True,'strict':True}}}
ops=ids['Operations']
reqs+= [validation(ops,1,TYPES), validation(ops,2,CATS_ALL)]
# сортировка журналов по дате (по возрастанию): Operations и Loans (A:E, сводку G:H не трогаем)
reqs.append({'sortRange':{'range':{'sheetId':ops,'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':5},
    'sortSpecs':[{'dimensionIndex':0,'sortOrder':'ASCENDING'}]}})
if 'Loans' in ids:
    reqs.append({'sortRange':{'range':{'sheetId':ids['Loans'],'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':5},
        'sortSpecs':[{'dimensionIndex':0,'sortOrder':'ASCENDING'}]}})

api('post',':batchUpdate',json={'requests':reqs})
print('PnL перестроен. Строк:', len(rows), '| валидация Тип+Категория добавлена')

# ============================ ДАШБОРД ============================
DASH='Дашборд'
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}
# сохраняем введённые пользователем данные (план по категориям, месяц, цель подушки) перед пересборкой
prev={}
if DASH in ids:
    for rrow in api('get',f'/values/{DASH}!A1:B120?valueRenderOption=UNFORMATTED_VALUE').get('values',[]):
        # сохраняем ТОЛЬКО числовые значения (план, месяц, цель) — текст (легенда) игнорируем,
        # иначе описания из легенды (Семья/Продукты/Кафе) затекают в колонку «План»
        if rrow and str(rrow[0]).strip() and len(rrow)>1 and isinstance(rrow[1],(int,float)):
            prev[rrow[0]]= rrow[1]
if DASH not in ids:
    resp=api('post',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':DASH,'index':1}}}]})
    dash_id=resp['replies'][0]['addSheet']['properties']['sheetId']
else:
    dash_id=ids[DASH]; api('post',f'/values/{DASH}!A1:Z400:clear',json={})

def pref(r): return f'=INDEX(PnL!B{r}:M{r},1,$B$2)'   # значение выбранного месяца из строки PnL
D=[]
def d(*cells): D.append(list(cells)); return len(D)

# 1) Заголовок + селектор месяца
d('ЛИЧНЫЙ БЮДЖЕТ — ДАШБОРД')
d('Месяц (1–12):', prev.get('Месяц (1–12):',8),
  '=CHOOSE($B$2,"Январь","Февраль","Март","Апрель","Май","Июнь","Июль","Август","Сентябрь","Октябрь","Ноябрь","Декабрь")')
d('')
# 2) Итоги месяца — горизонтальная лента KPI (метки + значения)
h_kpi=d('ИТОГИ МЕСЯЦА')
kpi_lbl=d('Заработано','Потрачено','Отложено + долг','Остаток (кэш)','Чистый без кредитов','Норма сбереж.')
kr=len(D)+1
kpi_val=d(pref(r_earn),pref(r_exp),pref(r_sav),pref(r_bal),pref(r_net),
          f'=IFERROR({pref(r_savonly)[1:]}/A{kr},0)')
d('')
# 3) План / факт по категориям
h_pf=d('ПЛАН / ФАКТ ПО КАТЕГОРИЯМ')
h_tbl=d('Категория','План/мес','Факт','Δ план−факт','Доля','Статус')
first_cat=len(D)+1
for c in exp_order:
    rr=cat_row[c]; row=len(D)+1
    d(c, prev.get(c,''), f'=INDEX(PnL!B{rr}:M{rr},1,$B$2)', f'=B{row}-C{row}',
      f'=IFERROR(C{row}/$B${kpi_val},0)',
      f'=IF(AND(B{row}<>"",C{row}>B{row}),"⚠ перерасход","")')
last_cat=len(D); row=len(D)+1
r_tot=d('ИТОГО', f'=SUM(B{first_cat}:B{last_cat})', pref(r_exp), f'=B{row}-C{row}',
        f'=IFERROR(C{row}/$B${kpi_val},0)', '')
d('')
# 4) Подушка безопасности (цель редактируешь ты)
h_cush=d('ПОДУШКА БЕЗОПАСНОСТИ')
r_cmon=d('Цель подушки (мес расходов):', prev.get('Цель подушки (мес расходов):',3))
r_cavg=d('Среднемесячный расход', f'=IFERROR(PnL!N{r_exp}/COUNTIF(PnL!B{r_exp}:M{r_exp},">0"),0)')
r_cgoal=d('Цель подушки (сумма)', f'=B{r_cmon}*B{r_cavg}')
r_csav=d('Накоплено в подушку', f'=PnL!N{r_cushion}')
r_cprog=d('Прогресс к цели', f'=IFERROR(B{r_csav}/B{r_cgoal},0)')
r_cleft=d('Осталось накопить', f'=MAX(B{r_cgoal}-B{r_csav},0)')
d('')
# 5) Динамика по месяцам
h_dyn=d('ДИНАМИКА ПО МЕСЯЦАМ')
h_dyn2=d('Показатель','Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек','Год')
dyn_first=len(D)+1
def dynrow(label,r): d(label,*[f'=PnL!{col}{r}' for col in COLS],f'=PnL!N{r}')
dynrow('Заработано',r_earn); dynrow('Потрачено',r_exp); dynrow('Отложено + долг',r_sav); dynrow('Остаток (кэш)',r_bal)
# Накопления и погашение долга — двумя строками, чтобы деньги не пропали
# из виду после того, как погашение убрано из нормы сбережений.
dynrow('Отложено себе',r_savonly); dynrow('Погашение долга',r_pay)
r_dnorm=d('Норма сбережений',*[f'=IFERROR(PnL!{col}{r_savonly}/PnL!{col}{r_earn},0)' for col in COLS],
          f'=IFERROR(PnL!N{r_savonly}/PnL!N{r_earn},0)')
d('')
# 6) Легенда
h_leg=d('ЛЕГЕНДА КАТЕГОРИЙ')
d('Семья','регулярная помощь родным (разовый подарок → «Подарки»)')
d('Продукты','еда домой')
d('Кафе','еда вне дома')
d('Развлечение','досуг без еды')
d('Погашение кредита','возврат долга — не расход, живёт в зоне «Сбережения и долг»')
put(f'{DASH}!A1',D)

# ── формат дашборда: рамки, выравнивание, числа/проценты, ширины ──
def fmt(r0,r1,c0,c1,**uf):
    return {'repeatCell':{'range':{'sheetId':dash_id,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
        'cell':{'userEnteredFormat':uf},'fields':','.join('userEnteredFormat.'+k for k in uf)}}
def pct(r0,r1,c0,c1): return fmt(r0,r1,c0,c1,numberFormat={'type':'PERCENT','pattern':'0.0%'})
def rght(r0,r1,c0,c1): return fmt(r0,r1,c0,c1,horizontalAlignment='RIGHT')
def box(r0,r1,c0,c1):
    return {'updateBorders':{'range':{'sheetId':dash_id,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
        'top':{'style':'SOLID'},'bottom':{'style':'SOLID'},'left':{'style':'SOLID'},'right':{'style':'SOLID'},
        'innerHorizontal':{'style':'SOLID'},'innerVertical':{'style':'SOLID'}}}
# деньги: #,##0.00 (нули → «0.00», без хвостовой точки как у #,##0.##); счётчики — целыми
numreset=fmt(0,80,0,14,numberFormat={'type':'NUMBER','pattern':'#,##0.00'})
intfmt=lambda r0,r1,c0,c1: fmt(r0,r1,c0,c1,numberFormat={'type':'NUMBER','pattern':'#,##0'})
dreqs=[whole(dash_id),numreset]
dreqs+=[boldrow(dash_id,x) for x in [1,h_kpi,kpi_lbl,kpi_val,h_pf,h_tbl,r_tot,h_cush,r_cgoal,h_dyn,h_dyn2,h_leg]]
dreqs+=[pct(kpi_val-1,kpi_val,5,6), pct(first_cat-1,r_tot,4,5), pct(r_cprog-1,r_cprog,1,2), pct(r_dnorm-1,r_dnorm,1,14)]
dreqs+=[intfmt(1,2,1,2), intfmt(r_cmon-1,r_cmon,1,2)]  # месяц и «цель (мес)» — целые
dreqs+=[rght(kpi_val-1,kpi_val,0,6), rght(first_cat-1,r_tot,1,5), rght(r_cmon-1,r_cleft,1,2), rght(dyn_first-1,r_dnorm,1,14)]
dreqs+=[box(kpi_lbl-1,kpi_val,0,6), box(h_tbl-1,r_tot,0,6), box(r_cmon-1,r_cleft,0,2), box(h_dyn2-1,r_dnorm,0,14)]
dreqs+=[
 {'updateDimensionProperties':{'range':{'sheetId':dash_id,'dimension':'COLUMNS','startIndex':0,'endIndex':1},'properties':{'pixelSize':230},'fields':'pixelSize'}},
 {'updateDimensionProperties':{'range':{'sheetId':dash_id,'dimension':'COLUMNS','startIndex':1,'endIndex':14},'properties':{'pixelSize':92},'fields':'pixelSize'}},
 {'updateSheetProperties':{'properties':{'sheetId':dash_id,'gridProperties':{'frozenRowCount':2}},'fields':'gridProperties.frozenRowCount'}},
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
 ['Всего погашено','=SUMIFS(Operations!$D:$D,Operations!$B:$B,"Погашение",Operations!$C:$C,"Оплата кредита")'],
 ['Текущий долг','=H1-H2'],
])
print('Loans связан с погашениями (Operations → «Оплата кредита»).')
