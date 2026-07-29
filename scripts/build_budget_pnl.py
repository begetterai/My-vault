#!/usr/bin/env python3
"""Личный бюджет: Operations + PnL + Loans (англ. вкладки, даты, фильтр, свод по категориям)."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)

INCOME=['Зарплата','Прочий доход']
EXP=['Дом','Машина','Гаджеты','Подписки','Кафе','Продукты','Здоровье','Курение',
     'Одежда/Обувь','Развлечение','Обучение','Семья','Подарки','Оплата кредита','Путешествие','Прочее']
MON=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
COLS='BCDEFGHIJKLM'
CAP=lambda x:(x[:1].upper()+x[1:]) if x else x
MIGRATE={'магазин':'Продукты'}  # старые→новые категории
import re
def iso(d):
    d=(d or '').strip()
    if re.match(r'^\d{4}-\d{2}-\d{2}$',d): return d
    m=re.match(r'^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$',d)  # dd.mm.yyyy
    if m: return f'{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}'
    return d

def api(m,path,**kw):
    r=getattr(s,m)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw); r.raise_for_status()
    return r.json() if r.text else {}
def get(rng): return s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/{rng}',timeout=30).json().get('values',[])
def put(rng,vals,ue=True):
    s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/{rng}?valueInputOption={"USER_ENTERED" if ue else "RAW"}',json={'values':vals},timeout=30).raise_for_status()

# ── прочитать и мигрировать старые данные ──
old_ops=get('Операции!A2:F') or get('Operations!A2:E')
ops=[]
for r in old_ops:
    if len(r)<4: continue
    d=iso(r[0]); typ=CAP((r[1] or '').strip()); cat=r[2].strip();
    cat=MIGRATE.get(cat.lower(),cat)
    try: amt=float(r[3])
    except: continue
    com=CAP((r[4] if len(r)>4 else '').strip())
    ops.append([d,typ,cat,amt,com])
old_loans=get('Кредиты!A2:E') or get('Loans!A2:E')
loans=[[iso(r[0]),CAP(r[1]) if len(r)>1 else '',r[2] if len(r)>2 else '', float(r[3]) if len(r)>3 and r[3] else 0, (r[4] if len(r)>4 else '')] for r in old_loans if r and len(r)>=3]

# ── переименовать листы в англ. ──
meta=api('get','?fields=sheets.properties')
byid={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}
rename={'Операции':'Operations','ПНЛ':'PnL','Кредиты':'Loans'}
reqs=[{'updateSheetProperties':{'properties':{'sheetId':byid[ru],'title':en},'fields':'title'}} for ru,en in rename.items() if ru in byid]
if reqs: api('post',':batchUpdate',json={'requests':reqs})
meta=api('get','?fields=sheets.properties')
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in meta['sheets']}

# ── Operations: A-E, даты, фильтр ──
api('post',f'/values/Operations!A:F:clear' if False else ':batchUpdate',json={'requests':[]}) if False else None
s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Operations!A:Z:clear',timeout=30)
put('Operations!A1',[['Дата','Тип','Категория','Сумма','Комментарий']])
if ops: put('Operations!A2',ops)  # USER_ENTERED → даты станут датами
opid=ids['Operations']
api('post',':batchUpdate',json={'requests':[
    # формат колонки Дата
    {'repeatCell':{'range':{'sheetId':opid,'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':1},
      'cell':{'userEnteredFormat':{'numberFormat':{'type':'DATE','pattern':'dd.mm.yyyy'}}},'fields':'userEnteredFormat.numberFormat'}},
    # шапка жирная + заморозка
    {'repeatCell':{'range':{'sheetId':opid,'startRowIndex':0,'endRowIndex':1},'cell':{'userEnteredFormat':{'textFormat':{'bold':True},'backgroundColor':{'red':0.85,'green':0.9,'blue':0.98}}},'fields':'userEnteredFormat'}},
    {'updateSheetProperties':{'properties':{'sheetId':opid,'gridProperties':{'frozenRowCount':1}},'fields':'gridProperties.frozenRowCount'}},
    # ФИЛЬТР на A1:E
    {'setBasicFilter':{'filter':{'range':{'sheetId':opid,'startRowIndex':0,'startColumnIndex':0,'endColumnIndex':5}}}},
]})

# ── PnL: свод по категориям, SUMIFS по диапазону дат ──
def sifm(col_m, kind, cat):
    return (f'=SUMIFS(Operations!$D:$D,Operations!$A:$A,">="&DATE(2026,{col_m},1),'
            f'Operations!$A:$A,"<"&DATE(2026,{col_m}+1,1),Operations!$B:$B,"{kind}",Operations!$C:$C,"{cat}")')
def sifmr(col_m, kind, row):
    return (f'=SUMIFS(Operations!$D:$D,Operations!$A:$A,">="&DATE(2026,{col_m},1),'
            f'Operations!$A:$A,"<"&DATE(2026,{col_m}+1,1),Operations!$B:$B,"{kind}",Operations!$C:$C,$A{row})')
rows=[['Категория']+MON+['Итого год']]
r=2; inc_rows=[]
for name in INCOME:
    rows.append([name]+[sifm(m,'Доход',name) for m in range(1,13)]+[f'=SUM(B{r}:M{r})']); inc_rows.append(r); r+=1
rows.append(['Кредиты получено']+[sifm(m,'Доход','Кредит') for m in range(1,13)]+[f'=SUM(B{r}:M{r})']); inc_rows.append(r); r+=1
income_row=r
rows.append(['ИТОГО доход']+['='+'+'.join(f'{c}{x}' for x in inc_rows) for c in COLS]+[f'=SUM(B{r}:M{r})']); r+=1
rows.append(['РАСХОДЫ']+['']*13); r+=1
first_exp=r
for e in EXP:
    rows.append([e]+[sifmr(m,'Расход',r) for m in range(1,13)]+[f'=SUM(B{r}:M{r})']); r+=1
last_exp=r-1
rows.append(['Итого расходы']+[f'=SUM({c}{first_exp}:{c}{last_exp})' for c in COLS]+[f'=SUM(B{r}:M{r})']); tr=r; r+=1
rows.append(['Остаток']+[f'={c}{income_row}-{c}{tr}' for c in COLS]+[f'=SUM(B{r}:M{r})']); osr=r
put('PnL!A1',rows)
pnl=ids['PnL']
def bold(sheet,row,bg=None):
    f={'textFormat':{'bold':True}}; fields='userEnteredFormat.textFormat.bold'
    if bg: f['backgroundColor']=bg; fields+=',userEnteredFormat.backgroundColor'
    return {'repeatCell':{'range':{'sheetId':sheet,'startRowIndex':row,'endRowIndex':row+1},'cell':{'userEnteredFormat':f},'fields':fields}}
api('post',':batchUpdate',json={'requests':[
    bold(pnl,0,{'red':0.85,'green':0.9,'blue':0.98}),
    bold(pnl,income_row-1,{'red':0.82,'green':0.94,'blue':0.82}),
    bold(pnl,first_exp-2,{'red':0.98,'green':0.87,'blue':0.83}),  # РАСХОДЫ
    bold(pnl,tr-1),
    bold(pnl,osr-1,{'red':0.95,'green':0.95,'blue':0.8}),
    {'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':1,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
    # форсируем ЧИСЛОВОЙ формат на весь свод (иначе Sheets красит формулы с DATE() как даты)
    {'repeatCell':{'range':{'sheetId':pnl,'startRowIndex':1,'startColumnIndex':1,'endColumnIndex':14},
      'cell':{'userEnteredFormat':{'numberFormat':{'type':'NUMBER','pattern':'#,##0.##'}}},'fields':'userEnteredFormat.numberFormat'}},
]})

# ── Loans ──
s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/Loans!A:Z:clear',timeout=30)
put('Loans!A1',[['Дата','Операция','Кредит','Сумма','Комментарий','','Всего получено','=SUMIF(B:B,"Получен",D:D)']])
put('Loans!G2',[['Всего погашено','=SUMIF(B:B,"Погашение",D:D)'],['Текущий долг','=H1-H2']])
if loans: put('Loans!A2',loans)
lid=ids['Loans']
api('post',':batchUpdate',json={'requests':[
    {'repeatCell':{'range':{'sheetId':lid,'startRowIndex':1,'startColumnIndex':0,'endColumnIndex':1},'cell':{'userEnteredFormat':{'numberFormat':{'type':'DATE','pattern':'dd.mm.yyyy'}}},'fields':'userEnteredFormat.numberFormat'}},
    bold(lid,0,{'red':0.9,'green':0.9,'blue':0.9}),
]})
print('Готово: Operations / PnL / Loans, мигрировано операций:', len(ops))
