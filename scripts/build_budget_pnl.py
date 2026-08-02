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
r_cred = add('Кредиты получено', [sif(m,'Доход','Кредит') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_inc  = add('ИТОГО доход', [f'={c}{r_prev}+{c}{r_zp}+{c}{r_oth}+{c}{r_cred}' for c in COLS], f'=N{r_zp}+N{r_oth}+N{r_cred}')
add('', ['']*12, '')
r_exphdr = add('РАСХОДЫ', ['']*12, '')

subtotals=[]; standalone=[]; num=1
for kind,subname,cats in EXP_STRUCT:
    if kind=='block':
        start=len(rows)+1
        for c in cats:
            rr=add(f'{num}. {c}', [sif(m,'Расход',c) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; num+=1
        end=len(rows)
        sub=add(subname, [f'=SUM({col}{start}:{col}{end})' for col in COLS], f'=SUM(N{start}:N{end})')
        subtotals.append(sub)
    else:
        c=cats[0]; rr=add(f'{num}. {c}', [sif(m,'Расход',c) for m in range(1,13)], ''); rows[-1][-1]=f'=SUM(B{rr}:M{rr})'; num+=1
        standalone.append(rr)

parts=subtotals+standalone
r_exp = add('Итого расходы', ['='+'+'.join(f'{col}{p}' for p in parts) for col in COLS], '='+'+'.join(f'N{p}' for p in parts))
r_bal = add('Остаток', [f'={col}{r_inc}-{col}{r_exp}' for col in COLS], f'=N{r_inc}-N{r_exp}')
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
reqs=[whole(pnl)]+[boldrow(pnl,rr) for rr in [1,r_inc,r_exphdr,r_exp,r_bal]+subtotals]
reqs.append({'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':1,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}})
for t in ('Operations','Loans'):
    if t in ids: reqs+= [whole(ids[t]), boldrow(ids[t],1)]
api('post',':batchUpdate',json={'requests':reqs})
print('PnL перестроен. Строк:', len(rows))
