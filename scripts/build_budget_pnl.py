#!/usr/bin/env python3
"""Перестраивает «Личный бюджет» в ПНЛ: вкладка Операции (журнал) + ПНЛ (свод SUMIFS)."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)

EXP=['Машина','Кафе','Телефон','Здоровье','Курение','Магазин','Прочее']
YM=[f'2026-{m:02d}' for m in range(1,13)]

def api(method, path, **kw):
    r=getattr(s,method)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw)
    r.raise_for_status(); return r.json() if r.text else {}

# ── привести листы к нужным: Операции + ПНЛ ──
meta=api('get','?fields=sheets.properties')
existing={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}
reqs=[]
# переименовать первый лист в Операции
first_title=list(existing)[0]; first_id=existing[first_title]
if 'Операции' not in existing:
    reqs.append({'updateSheetProperties':{'properties':{'sheetId':first_id,'title':'Операции'},'fields':'title'}})
if 'ПНЛ' not in existing:
    reqs.append({'addSheet':{'properties':{'title':'ПНЛ'}}})
if reqs: api('post',':batchUpdate',json={'requests':reqs})
meta=api('get','?fields=sheets.properties')
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}
# удалить лишние листы (старый Бюджет 2026, если остался отдельно)
extra=[sid for t,sid in ids.items() if t not in ('Операции','ПНЛ')]
if extra:
    api('post',':batchUpdate',json={'requests':[{'deleteSheet':{'sheetId':x}} for x in extra]})
    meta=api('get','?fields=sheets.properties')
    ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}

# ── Операции: журнал ──
op_header=[['Дата','Тип','Категория','Сумма','Комментарий','Месяц']]
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Операции!A1?valueInputOption=RAW',
      json={'values':op_header})

# ── ПНЛ: свод по SUMIFS ──
# строка 1: Категория | 2026-01 ... 2026-12 | Итого
rows=[['Категория']+YM+['Итого год']]
def sumifs_income(colletter):
    return f'=SUMIFS(Операции!$D:$D,Операции!$F:$F,{colletter}$2,Операции!$B:$B,"доход")'
def sumifs_exp(colletter,row_cat_ref):
    return f'=SUMIFS(Операции!$D:$D,Операции!$F:$F,{colletter}$2,Операции!$C:$C,$A{row_cat_ref},Операции!$B:$B,"расход")'
COLS='BCDEFGHIJKLM'  # 12 месяцев
# строка «ключей месяцев» в скрытой строке? Проще: положим YM в строку 2 как подпись, а формулы ссылаются на неё.
# Row layout (1-index):
# 1 header (Категория + месяцы + Итого)
# 2 служебная строка с YM-ключами (для SUMIFS)
# 3 Доход
# 4.. расходы
row_ym=['(ключи→)']+YM+['']
rows.append(row_ym)
# Доход (row 3)
rows.append(['Доход']+[sumifs_income(c) for c in COLS]+['=SUM(B3:M3)'])
first_exp_row=4
for i,e in enumerate(EXP):
    rr=first_exp_row+i
    rows.append([e]+[sumifs_exp(c,rr) for c in COLS]+[f'=SUM(B{rr}:M{rr})'])
last_exp_row=first_exp_row+len(EXP)-1
# Итого расходы
tr=last_exp_row+1
rows.append(['Итого расходы']+[f'=SUM({c}{first_exp_row}:{c}{last_exp_row})' for c in COLS]+[f'=SUM(B{tr}:M{tr})'])
# Остаток = Доход - Итого расходы
osr=tr+1
rows.append(['Остаток']+[f'={c}3-{c}{tr}' for c in COLS]+[f'=SUM(B{osr}:M{osr})'])
s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/ПНЛ!A1?valueInputOption=USER_ENTERED',
      json={'values':rows})

# ── формат ──
pnl_id=ids['ПНЛ']
def bold(r,bg=None):
    f={'textFormat':{'bold':True}}; fields='userEnteredFormat.textFormat.bold'
    if bg: f['backgroundColor']=bg; fields+=',userEnteredFormat.backgroundColor'
    return {'repeatCell':{'range':{'sheetId':pnl_id,'startRowIndex':r,'endRowIndex':r+1},'cell':{'userEnteredFormat':f},'fields':fields}}
fmt=[
 bold(0,{'red':0.85,'green':0.9,'blue':0.98}),
 bold(2,{'red':0.82,'green':0.94,'blue':0.82}),      # Доход
 bold(tr-1),                                          # Итого расходы
 bold(osr-1,{'red':0.95,'green':0.95,'blue':0.8}),   # Остаток
 {'updateSheetProperties':{'properties':{'sheetId':pnl_id,'gridProperties':{'frozenRowCount':2,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
 {'updateDimensionProperties':{'range':{'sheetId':pnl_id,'dimension':'ROWS','startIndex':1,'endIndex':2},'properties':{'hiddenByUser':True},'fields':'hiddenByUser'}},  # скрыть строку-ключи
]
api('post',':batchUpdate',json={'requests':fmt})
print('ПНЛ перестроен:', 'https://docs.google.com/spreadsheets/d/'+SID)
