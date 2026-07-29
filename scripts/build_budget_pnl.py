#!/usr/bin/env python3
"""Личный бюджет-ПНЛ: Операции (журнал) + ПНЛ (свод) + Кредиты (долг). Финальные категории."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)

INCOME=['Зарплата','Прочий доход']         # обычные доходы (Кредит — отдельной строкой)
EXP=['Дом','Машина','Гаджеты','Подписки','Кафе','Продукты','Здоровье','Курение',
     'Одежда/Обувь','Развлечение','Обучение','Семья','Подарки','Оплата кредита','Путешествие','Прочее']
YM=[f'2026-{m:02d}' for m in range(1,13)]
COLS='BCDEFGHIJKLM'

def api(method, path, **kw):
    r=getattr(s,method)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw)
    r.raise_for_status(); return r.json() if r.text else {}

# ── листы ──
meta=api('get','?fields=sheets.properties')
titles={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}
reqs=[]
first_id=list(titles.values())[0]
if 'Операции' not in titles: reqs.append({'updateSheetProperties':{'properties':{'sheetId':first_id,'title':'Операции'},'fields':'title'}})
for t in ('ПНЛ','Кредиты'):
    if t not in titles: reqs.append({'addSheet':{'properties':{'title':t}}})
if reqs: api('post',':batchUpdate',json={'requests':reqs})
meta=api('get','?fields=sheets.properties')
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}

# ── Операции ──
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Операции!A1?valueInputOption=RAW',
      json={'values':[['Дата','Тип','Категория','Сумма','Комментарий','Месяц']]})

# ── ПНЛ ──
def sif(col, kind, cat):
    return f'=SUMIFS(Операции!$D:$D,Операции!$F:$F,{col}$2,Операции!$B:$B,"{kind}",Операции!$C:$C,"{cat}")'
def sifr(col, kind, row):
    return f'=SUMIFS(Операции!$D:$D,Операции!$F:$F,{col}$2,Операции!$B:$B,"{kind}",Операции!$C:$C,$A{row})'
rows=[['Категория']+YM+['Итого год'], ['(ключи→)']+YM+['']]
r=3
inc_rows=[]
for name in INCOME:
    rows.append([name]+[sif(c,'доход',name) for c in COLS]+[f'=SUM(B{r}:M{r})']); inc_rows.append(r); r+=1
rows.append(['Кредиты получено']+[sif(c,'доход','Кредит') for c in COLS]+[f'=SUM(B{r}:M{r})']); cred_row=r; r+=1
inc_all=inc_rows+[cred_row]
income_row=r
rows.append(['ИТОГО доход']+[f'=' + '+'.join(f'{c}{x}' for x in inc_all) for c in COLS]+[f'=SUM(B{r}:M{r})']); r+=1
rows.append(['РАСХОДЫ']+['']*13); r+=1
first_exp=r
for e in EXP:
    rows.append([e]+[sifr(c,'расход',r) for c in COLS]+[f'=SUM(B{r}:M{r})']); r+=1
last_exp=r-1
rows.append(['Итого расходы']+[f'=SUM({c}{first_exp}:{c}{last_exp})' for c in COLS]+[f'=SUM(B{r}:M{r})']); tr=r; r+=1
rows.append(['Остаток']+[f'={c}{income_row}-{c}{tr}' for c in COLS]+[f'=SUM(B{r}:M{r})']); osr=r
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/ПНЛ!A1?valueInputOption=USER_ENTERED',json={'values':rows})

# ── Кредиты ──
cred=[['Дата','Операция','Кредит','Сумма','Комментарий','','Всего получено','=SUMIF(B:B,"Получен",D:D)']]
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Кредиты!A1?valueInputOption=USER_ENTERED',json={'values':cred})
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Кредиты!G2?valueInputOption=USER_ENTERED',
      json={'values':[['Всего погашено','=SUMIF(B:B,"Погашение",D:D)'],['Текущий долг','=H1-H2']]})

# ── формат ──
def bold(sheet,row,bg=None):
    f={'textFormat':{'bold':True}}; fields='userEnteredFormat.textFormat.bold'
    if bg: f['backgroundColor']=bg; fields+=',userEnteredFormat.backgroundColor'
    return {'repeatCell':{'range':{'sheetId':sheet,'startRowIndex':row,'endRowIndex':row+1},'cell':{'userEnteredFormat':f},'fields':fields}}
pnl=ids['ПНЛ']; cr=ids['Кредиты']
fmt=[
 bold(pnl,0,{'red':0.85,'green':0.9,'blue':0.98}),
 bold(pnl,income_row-1,{'red':0.82,'green':0.94,'blue':0.82}),
 bold(pnl,tr-1),
 bold(pnl,osr-1,{'red':0.95,'green':0.95,'blue':0.8}),
 {'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':2,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
 {'updateDimensionProperties':{'range':{'sheetId':pnl,'dimension':'ROWS','startIndex':1,'endIndex':2},'properties':{'hiddenByUser':True},'fields':'hiddenByUser'}},
 bold(cr,0,{'red':0.9,'green':0.9,'blue':0.9}),
]
api('post',':batchUpdate',json={'requests':fmt})
print('ПНЛ перестроен с финальными категориями:', 'https://docs.google.com/spreadsheets/d/'+SID)
