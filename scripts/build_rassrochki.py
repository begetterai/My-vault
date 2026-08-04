#!/usr/bin/env python3
"""Лист «Рассрочки» (BNPL Alif/«Салом») в бюджете: остаток долга, ежемесячный платёж,
осталось платежей, дата следующего. + сведение общего долга (рассрочки + кредиты Loans).
Стиль: Times New Roman 13, без цвета, рамки/жирный/выравнивание (правило Азиза).
Данные — снимок из приложения; колонки «Осталось»/«Остаток долга» обновляешь по мере оплаты
(при повторном запуске эти значения сохраняются по названию покупки)."""
import os
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SID='1Cn3QwTy2AiW4Kjw2PLNniZuB_2LyQ2ES8nOCgHPKDIE'
FONT='Times New Roman'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets'])
s=AuthorizedSession(creds)
def api(m,path,**kw):
    r=getattr(s,m)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw); r.raise_for_status()
    return r.json() if r.text else {}
def put(rng,vals):
    s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/{rng}?valueInputOption=USER_ENTERED',
          json={'values':vals},timeout=30).raise_for_status()

SHEET='Рассрочки'
ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}

# данные-снимок из приложения (Покупка, Магазин, Ежемес., Осталось мес, Остаток долга, След. платёж)
DATA=[
 ['Покупка (Салом) 44,99/мес','Alif (Салом)',44.99,4,179.94,'10.08.2026'],
 ['Гарри Поттер — комплект 7 книг','Alif (Салом)',59,5,295.00,'25.08.2026'],
 ['Покупка (Салом) 210,83/мес','Alif (Салом)',210.83,9,1897.50,'10.09.2026'],
]
# сохраняем ручные правки (Осталось/Остаток) по названию покупки
if SHEET in ids:
    for r in api('get',f'/values/{SHEET}!A3:E30?valueRenderOption=UNFORMATTED_VALUE').get('values',[]):
        if len(r)>=5 and r[0]:
            for d in DATA:
                if d[0]==r[0]:
                    if isinstance(r[3],(int,float)): d[3]=r[3]
                    if isinstance(r[4],(int,float)): d[4]=r[4]
    sid=ids[SHEET]; api('post',f'/values/{SHEET}!A1:H40:clear',json={})
else:
    resp=api('post',':batchUpdate',json={'requests':[{'addSheet':{'properties':{'title':SHEET,'index':4}}}]})
    sid=resp['replies'][0]['addSheet']['properties']['sheetId']

rows=[['РАССРОЧКИ (BNPL · Alif «Салом»)','','','','',''],
      ['Покупка','Магазин','Ежемес. платёж','Осталось платежей','Остаток долга','След. платёж']]
first=3
for drow in DATA: rows.append(drow)
last=2+len(DATA)
tot=last+1
rows.append(['ИТОГО','',f'=SUM(C{first}:C{last})','',f'=SUM(E{first}:E{last})',''])
rows.append(['','','','','',''])
r_rass=tot+2   # Остаток по рассрочкам
rows.append(['Остаток по рассрочкам:', f'=E{tot}','','','',''])
r_cred=r_rass+1
rows.append(['Долг по кредитам (Эсхата, Loans):', '=Loans!H3','','','',''])
r_all=r_cred+1
rows.append([f'ОБЩИЙ ДОЛГ:', f'=B{r_rass}+B{r_cred}','','','',''])
rows.append(['','','','','',''])
r_mon=r_all+2
rows.append(['Ежемесячно по рассрочкам:', f'=C{tot}','','','',''])
put(f'{SHEET}!A1',rows)

# ── форматирование ──
def fmt(r0,r1,c0,c1,**uf):
    return {'repeatCell':{'range':{'sheetId':sid,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
        'cell':{'userEnteredFormat':uf},'fields':','.join('userEnteredFormat.'+k for k in uf)}}
def bold(r): return fmt(r-1,r,0,6,textFormat={'fontFamily':FONT,'fontSize':13,'bold':True})
def box(r0,r1,c0,c1):
    return {'updateBorders':{'range':{'sheetId':sid,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
        'top':{'style':'SOLID'},'bottom':{'style':'SOLID'},'left':{'style':'SOLID'},'right':{'style':'SOLID'},
        'innerHorizontal':{'style':'SOLID'},'innerVertical':{'style':'SOLID'}}}
reqs=[fmt(0,40,0,6,textFormat={'fontFamily':FONT,'fontSize':13,'bold':False},backgroundColor={'red':1,'green':1,'blue':1})]
reqs+=[fmt(0,40,0,6,numberFormat={'type':'NUMBER','pattern':'#,##0.##'})]           # по умолчанию
reqs+=[fmt(first-1,tot,2,3,numberFormat={'type':'NUMBER','pattern':'#,##0.00'})]     # Ежемес.
reqs+=[fmt(first-1,tot,4,5,numberFormat={'type':'NUMBER','pattern':'#,##0.00'})]     # Остаток долга
reqs+=[fmt(first-1,last,3,4,numberFormat={'type':'NUMBER','pattern':'#,##0'})]       # Осталось платежей — целые
reqs+=[fmt(r_rass-1,r_mon,1,2,numberFormat={'type':'NUMBER','pattern':'#,##0.00'})]  # блок долга (B)
reqs+=[fmt(first-1,tot,2,5,horizontalAlignment='RIGHT'), fmt(r_rass-1,r_mon,1,2,horizontalAlignment='RIGHT')]
reqs+=[bold(1),bold(2),bold(tot),bold(r_all)]
reqs+=[box(1,tot,0,6)]
reqs+=[
 {'updateDimensionProperties':{'range':{'sheetId':sid,'dimension':'COLUMNS','startIndex':0,'endIndex':1},'properties':{'pixelSize':270},'fields':'pixelSize'}},
 {'updateDimensionProperties':{'range':{'sheetId':sid,'dimension':'COLUMNS','startIndex':1,'endIndex':6},'properties':{'pixelSize':130},'fields':'pixelSize'}},
 {'updateSheetProperties':{'properties':{'sheetId':sid,'gridProperties':{'frozenRowCount':2}},'fields':'gridProperties.frozenRowCount'}},
]
api('post',':batchUpdate',json={'requests':reqs})
print(f'Лист «Рассрочки» собран: {len(DATA)} рассрочки. Общий долг в строке {r_all}.')
