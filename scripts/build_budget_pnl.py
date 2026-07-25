#!/usr/bin/env python3
"""Личный бюджет-ПНЛ: Операции (журнал) + ПНЛ (свод) + Кредиты (учёт долга)."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)

EXP=['Машина','Кафе','Телефон','Здоровье','Курение','Магазин','Оплата кредита','Прочее']
YM=[f'2026-{m:02d}' for m in range(1,13)]
COLS='BCDEFGHIJKLM'

def api(method, path, **kw):
    r=getattr(s,method)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw)
    r.raise_for_status(); return r.json() if r.text else {}

# ── листы: Операции, ПНЛ, Кредиты ──
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
def sif(colletter, kind, cat_ref=None, cat_literal=None):
    crit = f',Операции!$C:$C,$A{cat_ref}' if cat_ref else (f',Операции!$C:$C,"{cat_literal}"' if cat_literal else '')
    return f'=SUMIFS(Операции!$D:$D,Операции!$F:$F,{colletter}$2,Операции!$B:$B,"{kind}"{crit})'
rows=[['Категория']+YM+['Итого год'], ['(ключи→)']+YM+['']]
# 3 Доход, 4 Кредиты получено
rows.append(['Доход']+[sif(c,'доход',cat_literal='Доход') for c in COLS]+['=SUM(B3:M3)'])
rows.append(['Кредиты получено']+[sif(c,'доход',cat_literal='Кредит') for c in COLS]+['=SUM(B4:M4)'])
rows.append(['РАСХОДЫ']+['']*13)
first_exp=6
for i,e in enumerate(EXP):
    rr=first_exp+i
    rows.append([e]+[sif(c,'расход',cat_ref=rr) for c in COLS]+[f'=SUM(B{rr}:M{rr})'])
last_exp=first_exp+len(EXP)-1
tr=last_exp+1
rows.append(['Итого расходы']+[f'=SUM({c}{first_exp}:{c}{last_exp})' for c in COLS]+[f'=SUM(B{tr}:M{tr})'])
osr=tr+1
rows.append(['Остаток']+[f'=({c}3+{c}4)-{c}{tr}' for c in COLS]+[f'=SUM(B{osr}:M{osr})'])
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/ПНЛ!A1?valueInputOption=USER_ENTERED',
      json={'values':rows})

# ── Кредиты: журнал + баланс ──
cred=[['КРЕДИТЫ — учёт долга','','','',''],
      ['Всего получено','=SUMIF($B$7:$B$1000,"Получен",$D$7:$D$1000)','','',''],
      ['Всего погашено','=SUMIF($B$7:$B$1000,"Погашение",$D$7:$D$1000)','','',''],
      ['Текущий долг','=B2-B3','','',''],
      ['','','','',''],
      ['Дата','Операция','Кредит','Сумма','Комментарий']]
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Кредиты!A1?valueInputOption=USER_ENTERED',
      json={'values':cred})

# ── формат ──
def bold(sheet,r,bg=None):
    f={'textFormat':{'bold':True}}; fields='userEnteredFormat.textFormat.bold'
    if bg: f['backgroundColor']=bg; fields+=',userEnteredFormat.backgroundColor'
    return {'repeatCell':{'range':{'sheetId':sheet,'startRowIndex':r,'endRowIndex':r+1},'cell':{'userEnteredFormat':f},'fields':fields}}
pnl=ids['ПНЛ']; cr=ids['Кредиты']
fmt=[
 bold(pnl,0,{'red':0.85,'green':0.9,'blue':0.98}),
 bold(pnl,2,{'red':0.82,'green':0.94,'blue':0.82}),   # Доход
 bold(pnl,3,{'red':0.82,'green':0.94,'blue':0.82}),   # Кредиты получено
 bold(pnl,tr-1),                                       # Итого расходы
 bold(pnl,osr-1,{'red':0.95,'green':0.95,'blue':0.8}),# Остаток
 {'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':2,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
 {'updateDimensionProperties':{'range':{'sheetId':pnl,'dimension':'ROWS','startIndex':1,'endIndex':2},'properties':{'hiddenByUser':True},'fields':'hiddenByUser'}},
 bold(cr,0,{'red':0.98,'green':0.87,'blue':0.83}),
 bold(cr,3,{'red':0.95,'green':0.9,'blue':0.7}),       # Текущий долг
 bold(cr,5,{'red':0.9,'green':0.9,'blue':0.9}),        # шапка журнала
]
api('post',':batchUpdate',json={'requests':fmt})
print('Бюджет с кредитами перестроен:', 'https://docs.google.com/spreadsheets/d/'+SID)
