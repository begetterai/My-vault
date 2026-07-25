#!/usr/bin/env python3
"""Создаёт личный месячный бюджет (пустой) и шарит Азизу."""
import os, json
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

SHARE_TO = 'base@azizkhaidarov.com'
creds=service_account.Credentials.from_service_account_file(
    '/home/user/My-vault/scripts/credentials/romashka-drive.json',
    scopes=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive'])
s=AuthorizedSession(creds)

MONTHS=['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек']
EXP=['Машина','Кафе','Телефон','Здоровье','Курение','Магазин','Прочее']

# создать книгу в папке общего диска (SA не может в своём Drive)
MAIN='1MpzfxZVhLUVUwo6p2QcoCMoqxxYEdMjm'
f=s.post('https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
    json={'name':'Личный бюджет','mimeType':'application/vnd.google-apps.spreadsheet','parents':[MAIN]}).json()
sid=f['id']
# переименовать первый лист в «Бюджет 2026»
meta=s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}?fields=sheets.properties').json()
first_id=meta['sheets'][0]['properties']['sheetId']
s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate',
    json={'requests':[{'updateSheetProperties':{'properties':{'sheetId':first_id,'title':'Бюджет 2026'},'fields':'title'}}]})

# собрать значения
header=['Категория']+MONTHS+['Итого год']
rows=[header, ['ДОХОД']+['']*13, ['Доход']+['']*12+['=SUM(B3:M3)']]
rows.append(['']*14)
rows.append(['РАСХОДЫ']+['']*13)
first_exp=len(rows)+1  # 1-индекс строки первой категории расходов
for e in EXP:
    r=len(rows)+1
    rows.append([e]+['']*12+[f'=SUM(B{r}:M{r})'])
last_exp=len(rows)
# Итого расходы
tr=len(rows)+1
tot=['Итого расходы']
for col in 'BCDEFGHIJKLM':
    tot.append(f'=SUM({col}{first_exp}:{col}{last_exp})')
tot.append(f'=SUM(B{tr}:M{tr})')
rows.append(tot)
# Остаток = Доход - Итого расходы
os_row=len(rows)+1
ost=['Остаток']
for col in 'BCDEFGHIJKLM':
    ost.append(f'={col}3-{col}{tr}')
ost.append(f'=SUM(B{os_row}:M{os_row})')
rows.append(ost)

s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/Бюджет 2026!A1?valueInputOption=USER_ENTERED',
      json={'values':rows})

# форматирование: жирные заголовки-секции, шапка
sheet_id=first_id
def bold_row(r0, bg=None):
    fmt={'textFormat':{'bold':True}}
    if bg: fmt['backgroundColor']=bg
    return {'repeatCell':{'range':{'sheetId':sheet_id,'startRowIndex':r0,'endRowIndex':r0+1},
        'cell':{'userEnteredFormat':fmt},'fields':'userEnteredFormat.textFormat.bold'+(',userEnteredFormat.backgroundColor' if bg else '')}}
reqs=[
    bold_row(0,{'red':0.85,'green':0.9,'blue':0.98}),      # шапка
    bold_row(1,{'red':0.82,'green':0.94,'blue':0.82}),     # ДОХОД
    bold_row(4,{'red':0.98,'green':0.87,'blue':0.83}),     # РАСХОДЫ
    bold_row(tr-1),                                         # Итого расходы
    bold_row(os_row-1,{'red':0.95,'green':0.95,'blue':0.8}),# Остаток
    {'updateSheetProperties':{'properties':{'sheetId':sheet_id,'gridProperties':{'frozenRowCount':1,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
]
s.post(f'https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate',json={'requests':reqs})

# поделиться с Азизом (writer)
s.post(f'https://www.googleapis.com/drive/v3/files/{sid}/permissions?supportsAllDrives=true&sendNotificationEmail=true',
       json={'role':'writer','type':'user','emailAddress':SHARE_TO})

print('Бюджет создан:', sid)
print('URL: https://docs.google.com/spreadsheets/d/'+sid)
