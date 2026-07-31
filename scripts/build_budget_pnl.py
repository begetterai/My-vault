#!/usr/bin/env python3
"""Личный бюджет: Operations + PnL (блоки, переходящий остаток) + Loans.
Стиль: Times New Roman 13, без цветовой заливки (правило оформления Азиза)."""
import os, re
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
COLS='BCDEFGHIJKLM'  # 12 месяцев
def api(m,path,**kw):
    r=getattr(s,m)(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}{path}',**kw); r.raise_for_status()
    return r.json() if r.text else {}
def put(rng,vals):
    s.put(f'https://sheets.googleapis.com/v4/spreadsheets/{SID}/values/{rng}?valueInputOption=USER_ENTERED',json={'values':vals},timeout=30).raise_for_status()

ids={sh['properties']['title']:sh['properties']['sheetId'] for sh in api('get','?fields=sheets.properties')['sheets']}
pnl=ids['PnL']

# ── SUMIFS по диапазону дат ──
def sif(m, kind, cat):
    return (f'=SUMIFS(Operations!$D:$D,Operations!$A:$A,">="&DATE(2026,{m},1),'
            f'Operations!$A:$A,"<"&DATE(2026,{m}+1,1),Operations!$B:$B,"{kind}",Operations!$C:$C,"{cat}")')

# порядок расходов по номерам 1-16
EXP=[(1,'Дом'),(2,'Машина'),(3,'Одежда/Обувь'),(4,'Семья'),(5,'Гаджеты'),(6,'Подписки'),(7,'Подарки'),
     (8,'Продукты'),(9,'Кафе'),(10,'Развлечение'),(11,'Здоровье / Тело'),(12,'Обучение'),
     (13,'Курение'),(14,'Оплата кредита'),(15,'Путешествие'),(16,'Прочее')]
BLOCKS=[(1,7),(8,10),(11,12)]  # блоки с итогом; 13-16 отдельно

rows=[['Категория']+MON+['Итого год']]
r=1
def add(label, cells, year):
    global r; rows.append([label]+cells+[year]); r=len(rows); return r
# доход
r_prev = add('Остаток с предыдущего месяца', ['']*12, '')          # заполним формулами ниже
r_zp   = add('Зарплата',        [sif(m,'Доход','Зарплата') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_oth  = add('Прочий доход',     [sif(m,'Доход','Прочий доход') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_cred = add('Кредиты получено', [sif(m,'Доход','Кредит') for m in range(1,13)], '=SUM(B{r}:M{r})'.format(r=len(rows)+1))
r_inc  = add('ИТОГО доход', [f'={c}{r_prev}+{c}{r_zp}+{c}{r_oth}+{c}{r_cred}' for c in COLS], f'=N{r_zp}+N{r_oth}+N{r_cred}')
add('', ['']*12, '')
r_exphdr = add('РАСХОДЫ', ['']*12, '')

# расходы по блокам
cat_rows={}; block_subtotals=[]; standalone=[]
i=0
def cat_year(rr): return f'=SUM(B{rr}:M{rr})'
while i < len(EXP):
    num,name=EXP[i]
    # начало блока?
    blk=next((b for b in BLOCKS if b[0]==num),None)
    if blk:
        start_row=len(rows)+1
        for n2 in range(blk[0],blk[1]+1):
            nm=dict(EXP)[n2]
            rr=add(f'{n2}. {nm}', [sif(m,'Расход',nm) for m in range(1,13)], '')
            rows[-1][-1]=cat_year(rr); cat_rows[nm]=rr
        end_row=len(rows)
        sub=add(f'Итого блок {blk[0]}–{blk[1]}',
                [f'=SUM({c}{start_row}:{c}{end_row})' for c in COLS],
                f'=SUM(N{start_row}:N{end_row})')
        block_subtotals.append(sub)
        i += (blk[1]-blk[0]+1)
    else:
        rr=add(f'{num}. {name}', [sif(m,'Расход',name) for m in range(1,13)], '')
        rows[-1][-1]=cat_year(rr); cat_rows[name]=rr; standalone.append(rr)
        i+=1

# итого расходы = сумма подытогов блоков + одиночных
parts = block_subtotals + standalone
r_exp = add('Итого расходы', ['='+'+'.join(f'{c}{p}' for p in parts) for c in COLS],
            '='+'+'.join(f'N{p}' for p in parts))
r_bal = add('Остаток', [f'={c}{r_inc}-{c}{r_exp}' for c in COLS], f'=N{r_inc}-N{r_exp}')

# переходящий остаток: B=0, каждый след. месяц = остаток прошлого
carry=['0']+[f'={COLS[k]}{r_bal}' for k in range(11)]  # B..L предыдущего → C..M текущего
put('PnL!B{0}:M{0}'.format(r_prev),[carry])

put('PnL!A1',rows)

# ── формат: Times New Roman 13, без цвета; жирные — заголовки/итоги ──
def whole(sheet):
    return {'repeatCell':{'range':{'sheetId':sheet},
        'cell':{'userEnteredFormat':{'textFormat':{'fontFamily':FONT,'fontSize':SIZE,'bold':False},
                'backgroundColor':{'red':1,'green':1,'blue':1}}},
        'fields':'userEnteredFormat.textFormat.fontFamily,userEnteredFormat.textFormat.fontSize,userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColor'}}
def boldrow(sheet,r0):
    return {'repeatCell':{'range':{'sheetId':sheet,'startRowIndex':r0-1,'endRowIndex':r0},
        'cell':{'userEnteredFormat':{'textFormat':{'bold':True}}},'fields':'userEnteredFormat.textFormat.bold'}}
reqs=[whole(pnl)]
for rr in [1, r_inc, r_exphdr, r_exp, r_bal]+block_subtotals:
    reqs.append(boldrow(pnl,rr))
reqs.append({'updateSheetProperties':{'properties':{'sheetId':pnl,'gridProperties':{'frozenRowCount':1,'frozenColumnCount':1}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}})
# тот же стиль на Operations и Loans (без цвета, TNR 13)
for t in ('Operations','Loans'):
    if t in ids:
        reqs.append(whole(ids[t])); reqs.append(boldrow(ids[t],1))
api('post',':batchUpdate',json={'requests':reqs})
print('PnL перестроен: блоки, переходящий остаток, TNR 13, без цвета. Строк:', len(rows))
