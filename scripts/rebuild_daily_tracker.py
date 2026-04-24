#!/usr/bin/env python3
"""Дневной трекер v2 — полные данные кассовой смены."""
import json, os, time, datetime, urllib.request, urllib.parse
from calendar import monthrange
os.environ['REQUESTS_CA_BUNDLE'] = '/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

CREDS     = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials', 'romashka-drive.json')
FOLDER_ID = '1mYH2yvUiWnR5dKAYrFw_vQgM5SrvIH9g'
POSTER_TOKEN = '398711:8746917c4a23ea897774040e039dfb76'
FONT = 'Times New Roman'
PLAN_ZB, PLAN_OVIR = 300_000, 360_000
DAYS_RU = ['Пн','Вт','Ср','Чт','Пт','Сб','Вс']
MONTHS_RU = ['','Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']

def rgb(r,g,b): return {"red":r/255,"green":g/255,"blue":b/255}
C_DARK   = rgb(20,43,75);   C_SEC  = rgb(31,73,125);   C_WHITE = rgb(255,255,255)
C_GREEN  = rgb(198,239,206); C_RED  = rgb(255,199,206); C_GOLD  = rgb(255,242,204)
C_WKND   = rgb(230,230,245); C_CALC = rgb(219,229,241); C_AMB   = rgb(255,235,156)
C_LGRAY  = rgb(245,245,245)

# Column indices
CA,CB,CC,CD,CE,CF,CG,CH,CI,CJ,CK,CL,CM,CN,CO,CP,CQ,CR,CS,CT = range(20)
NCOLS = 20
HEADERS = ['Дата','День','Выручка (с)','Наличные','Alif','DC','Карта','Beeygor/Teztar',
           'Итого оплат','Расхождение','Инкасс. нал.','Ост. откр.','Расходы','Ост. закр.',
           'Нарастающий итог','% плана','Норма/день','Откл. от нормы','Прогноз','Нужно/день']
DATA_R0, DATA_R1, DR = 2, 367, 3

def poster_get(method, params=None):
    p = {'token': POSTER_TOKEN}
    if params: p.update(params)
    url = f"https://joinposter.com/api/{method}?{urllib.parse.urlencode(p)}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Bot/1.0'}), timeout=20) as r:
            return json.loads(r.read().decode())
    except: return {}

def pull_revenue():
    today, result = datetime.date.today(), {}
    for y,m in [(2026,1),(2026,2),(2026,3),(2026,4)]:
        if datetime.date(y,m,1) > today: break
        _,last = monthrange(y,m)
        end = min(datetime.date(y,m,last), today)
        ds, de = f"{y}{m:02d}01", end.strftime("%Y%m%d")
        print(f"  Poster {y}-{m:02d}...")
        for attempt in range(4):
            r = poster_get('dash.getAnalytics', {'dateFrom':ds,'dateTo':de})
            data = r.get('response',{}).get('data',[])
            if data:
                for i,val in enumerate(data):
                    d = datetime.date(y,m,i+1)
                    if d<=today and float(val or 0)>0: result[d]=float(val)
                break
            time.sleep(2**attempt)
        time.sleep(1)
    print(f"  Загружено {len(result)} дней")
    return result

def get_session():
    creds = service_account.Credentials.from_service_account_file(
        CREDS, scopes=['https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/spreadsheets'])
    return AuthorizedSession(creds)

def api_post(s, url, body):
    for i in range(5):
        try:
            r = s.post(url, headers={'Content-Type':'application/json'}, data=json.dumps(body), timeout=90)
            if r.status_code==503 or not r.content: time.sleep(2**i); continue
            return r
        except: time.sleep(2**i)
    return None

def write_values(s, ss_id, sheet, rows):
    body = {'valueInputOption':'USER_ENTERED','data':[{'range':f"'{sheet}'!A1",
            'values':[[str(c) if c!='' else '' for c in row] for row in rows]}]}
    r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}/values:batchUpdate', body)
    print(f"  {'✅' if r and r.status_code==200 else '❌'} values: {sheet}")

def apply_fmt(s, ss_id, reqs, label=''):
    for i in range(0,len(reqs),35):
        r = api_post(s, f'https://sheets.googleapis.com/v4/spreadsheets/{ss_id}:batchUpdate', {'requests':reqs[i:i+35]})
        ok = r and r.status_code==200
        print(f"  {'✅' if ok else '❌'} fmt {label} chunk {i//35+1}")
        if not ok and r: print(f"    {r.status_code}: {r.text[:300]}")
        time.sleep(0.3)

def rc(sid,r0,r1,c0,c1,bold=False,bg=None,fg=None,fs=11,align='LEFT',ft=None):
    tf={'fontFamily':FONT,'fontSize':fs,'bold':bold}
    if fg: tf['foregroundColor']=fg
    fmt={'textFormat':tf,'horizontalAlignment':align}
    if bg: fmt['backgroundColor']=bg
    if ft=='pct': fmt['numberFormat']={'type':'NUMBER','pattern':'0.0%'}
    elif ft=='num': fmt['numberFormat']={'type':'NUMBER','pattern':'#,##0'}
    elif ft=='num1': fmt['numberFormat']={'type':'NUMBER','pattern':'#,##0.0'}
    flds=['textFormat','horizontalAlignment','backgroundColor','numberFormat']
    return {'repeatCell':{'range':{'sheetId':sid,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},
            'cell':{'userEnteredFormat':fmt},'fields':','.join(f'userEnteredFormat.{f}' for f in flds)}}

def cw(sid,c,px): return {'updateDimensionProperties':{'range':{'sheetId':sid,'dimension':'COLUMNS','startIndex':c,'endIndex':c+1},'properties':{'pixelSize':px},'fields':'pixelSize'}}
def frz(sid,r=2,c=0): return {'updateSheetProperties':{'properties':{'sheetId':sid,'gridProperties':{'frozenRowCount':r,'frozenColumnCount':c}},'fields':'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}}
def mrg(sid,r0,r1,c0,c1): return {'mergeCells':{'range':{'sheetId':sid,'startRowIndex':r0,'endRowIndex':r1,'startColumnIndex':c0,'endColumnIndex':c1},'mergeType':'MERGE_ALL'}}
def cf(sid,formula,bg,c0=0,c1=NCOLS): return {'addConditionalFormatRule':{'rule':{'ranges':[{'sheetId':sid,'startRowIndex':DATA_R0,'endRowIndex':DATA_R1,'startColumnIndex':c0,'endColumnIndex':c1}],'booleanRule':{'condition':{'type':'CUSTOM_FORMULA','values':[{'userEnteredValue':formula}]},'format':{'backgroundColor':bg}}},'index':0}}

def build_rows(plan, revenue_data=None, is_svod=False, title_suffix=''):
    rows = [[f'РОМАШКА — Дневной трекер 2026 | {title_suffix} | ПЛАН {plan:,} с/мес']+['']*19, HEADERS]
    jan1 = datetime.date(2026,1,1)
    for m in range(1,13):
        _,last = monthrange(2026,m)
        for d in range(1,last+1):
            dt = datetime.date(2026,m,d)
            n = len(rows)+1
            # C: revenue
            if is_svod:
                c = f"=IF(AND('ЗБ'!C{n}=\"\",'ОВИР'!C{n}=\"\"),\"\",IFERROR('ЗБ'!C{n},0)+IFERROR('ОВИР'!C{n},0))"
            elif revenue_data and dt in revenue_data:
                c = revenue_data[dt]
            else:
                c = ''
            # D-H manual payments — svod sums both sheets
            if is_svod:
                d_=f"=IFERROR('ЗБ'!D{n},0)+IFERROR('ОВИР'!D{n},0)"
                e_=f"=IFERROR('ЗБ'!E{n},0)+IFERROR('ОВИР'!E{n},0)"
                f_=f"=IFERROR('ЗБ'!F{n},0)+IFERROR('ОВИР'!F{n},0)"
                g_=f"=IFERROR('ЗБ'!G{n},0)+IFERROR('ОВИР'!G{n},0)"
                h_=f"=IFERROR('ЗБ'!H{n},0)+IFERROR('ОВИР'!H{n},0)"
                k_=f"=IFERROR('ЗБ'!K{n},0)+IFERROR('ОВИР'!K{n},0)"
                m_=f"=IFERROR('ЗБ'!M{n},0)+IFERROR('ОВИР'!M{n},0)"
            else:
                d_=e_=f_=g_=h_=k_=m_=''
            # I: total payments
            i_ = f"=IF(C{n}=\"\",\"\",D{n}+E{n}+F{n}+G{n}+H{n})"
            # J: discrepancy
            j_ = f"=IF(C{n}=\"\",\"\",C{n}-I{n})"
            # L, N: balance — manual
            l_ = n_ = ''
            # O: cumulative
            if len(rows)==2:
                o_ = f"=IF(C{n}=\"\",\"\",C{n})"
            else:
                prev = n-1
                o_ = f"=IF(C{n}=\"\",\"\",IF(MONTH(A{n})=MONTH(A{prev}),O{prev}+C{n},C{n}))"
            # P-T: KPI
            p_ = f"=IFERROR(O{n}/{plan},\"\")"
            q_ = f"=IFERROR({plan}/DAY(EOMONTH(A{n},0)),\"\")"
            r_ = f"=IF(C{n}=\"\",\"\",C{n}-Q{n})"
            s_ = f"=IFERROR(O{n}/DAY(A{n})*DAY(EOMONTH(A{n},0)),\"\")"
            t_ = f"=IFERROR(IF(EOMONTH(A{n},0)<TODAY(),\"\",({plan}-O{n})/MAX(1,DAY(EOMONTH(A{n},0))-DAY(A{n})+1)),\"\")"
            rows.append([dt.strftime('%d.%m.%Y'), DAYS_RU[dt.weekday()],
                         c, d_, e_, f_, g_, h_, i_, j_, k_, l_, m_, n_,
                         o_, p_, q_, r_, s_, t_])
    return rows

def build_expenses_rows(location):
    return [[f'Расходы {location} 2026 — детализация по сменам']+['']*7,
            ['Дата','№','Наименование','Кол-во','Цена','Сумма','Цех','Комментарий']]

def build_months_rows():
    rows = [['РОМАШКА — Выручка по месяцам 2026']+['']*8,
            ['Месяц','План ЗБ','Выручка ЗБ','% ЗБ','План ОВИР','Выручка ОВИР','% ОВИР','СВОД','% СВОД']]
    day_offset = 2
    for m in range(1,13):
        _,last = monthrange(2026,m)
        lr = day_offset+last
        zr=f"='ЗБ'!O{lr}"; or_=f"='ОВИР'!O{lr}"
        rows.append([MONTHS_RU[m], PLAN_ZB, zr, f"=IFERROR({zr}/{PLAN_ZB},\"\")",
                     PLAN_OVIR, or_, f"=IFERROR({or_}/{PLAN_OVIR},\"\")",
                     f"=IFERROR({zr}+{or_},\"\")", f"=IFERROR(({zr}+{or_})/660000,\"\")"])
        day_offset += last
    return rows

def fmt_tracker(sid):
    r=[frz(sid),
       cw(sid,CA,90),cw(sid,CB,42),cw(sid,CC,100),
       cw(sid,CD,90),cw(sid,CE,75),cw(sid,CF,75),cw(sid,CG,65),cw(sid,CH,95),
       cw(sid,CI,90),cw(sid,CJ,85),
       cw(sid,CK,90),cw(sid,CL,80),cw(sid,CM,80),cw(sid,CN,80),
       cw(sid,CO,115),cw(sid,CP,75),cw(sid,CQ,90),cw(sid,CR,95),cw(sid,CS,95),cw(sid,CT,95),
       rc(sid,0,1,0,NCOLS,bold=True,bg=C_DARK,fg=C_WHITE,fs=13,align='CENTER'),
       mrg(sid,0,1,0,NCOLS),
       rc(sid,1,2,0,NCOLS,bold=True,bg=C_SEC,fg=C_WHITE,fs=10,align='CENTER'),
       # section colors on header
       rc(sid,1,2,CC,CC+1,bold=True,bg=rgb(31,73,125),fg=C_WHITE,fs=10,align='CENTER'),
       rc(sid,1,2,CD,CI,bold=True,bg=rgb(0,100,0),fg=C_WHITE,fs=10,align='CENTER'),
       rc(sid,1,2,CI,CJ+1,bold=True,bg=rgb(0,70,0),fg=C_WHITE,fs=10,align='CENTER'),
       rc(sid,1,2,CK,CK+1,bold=True,bg=rgb(180,95,6),fg=C_WHITE,fs=10,align='CENTER'),
       rc(sid,1,2,CL,CN+1,bold=True,bg=rgb(130,80,0),fg=C_WHITE,fs=10,align='CENTER'),
       rc(sid,1,2,CO,NCOLS,bold=True,bg=rgb(65,105,185),fg=C_WHITE,fs=10,align='CENTER'),
       # data rows base
       rc(sid,DATA_R0,DATA_R1,CA,CB+1,fs=10,align='LEFT'),
       rc(sid,DATA_R0,DATA_R1,CC,NCOLS,fs=10,align='RIGHT',ft='num'),
       rc(sid,DATA_R0,DATA_R1,CP,CP+1,fs=10,align='RIGHT',ft='pct'),
       rc(sid,DATA_R0,DATA_R1,CQ,CQ+1,fs=10,align='RIGHT',ft='num1'),
       # calculated cols bg
       rc(sid,DATA_R0,DATA_R1,CI,CJ+1,bg=C_CALC),
       rc(sid,DATA_R0,DATA_R1,CO,NCOLS,bg=C_CALC),
       # conditional
       cf(sid,f'=WEEKDAY($A{DR},2)>=6',C_WKND),
       cf(sid,f'=$A{DR}=TODAY()',C_GOLD),
       cf(sid,f'=AND($R{DR}<>"",$R{DR}>0)',C_GREEN,c0=CR,c1=CR+1),
       cf(sid,f'=AND($R{DR}<>"",$R{DR}<0)',C_RED,c0=CR,c1=CR+1),
       cf(sid,f'=AND($J{DR}<>"",$J{DR}<>0)',C_RED,c0=CJ,c1=CJ+1),
    ]
    return r

def fmt_expenses(sid):
    return [frz(sid,2,0), cw(sid,0,90),cw(sid,1,35),cw(sid,2,180),cw(sid,3,55),
            cw(sid,4,75),cw(sid,5,90),cw(sid,6,80),cw(sid,7,150),
            rc(sid,0,1,0,8,bold=True,bg=C_DARK,fg=C_WHITE,fs=13,align='CENTER'), mrg(sid,0,1,0,8),
            rc(sid,1,2,0,8,bold=True,bg=C_SEC,fg=C_WHITE,fs=10,align='CENTER'),
            rc(sid,2,500,5,6,fs=10,align='RIGHT',ft='num')]

def fmt_months(sid):
    r=[frz(sid,2,0),cw(sid,0,110),cw(sid,1,90),cw(sid,2,110),cw(sid,3,75),
       cw(sid,4,90),cw(sid,5,110),cw(sid,6,75),cw(sid,7,110),cw(sid,8,75),
       rc(sid,0,1,0,9,bold=True,bg=C_DARK,fg=C_WHITE,fs=13,align='CENTER'), mrg(sid,0,1,0,9),
       rc(sid,1,2,0,9,bold=True,bg=C_SEC,fg=C_WHITE,fs=10,align='CENTER')]
    for i in range(12):
        rr=i+2
        r+=[rc(sid,rr,rr+1,0,1,fs=10,bold=True,bg=C_LGRAY),
            rc(sid,rr,rr+1,1,9,fs=10,align='RIGHT',ft='num'),
            rc(sid,rr,rr+1,3,4,fs=10,align='RIGHT',ft='pct'),
            rc(sid,rr,rr+1,6,7,fs=10,align='RIGHT',ft='pct'),
            rc(sid,rr,rr+1,8,9,fs=10,align='RIGHT',ft='pct')]
    return r

def main():
    print('Poster...')
    rev = pull_revenue()
    s = get_session()
    print('Создаём файл...')
    r = api_post(s,'https://www.googleapis.com/drive/v3/files?supportsAllDrives=true',
                 {'name':'Ромашка — Дневной трекер 2026','mimeType':'application/vnd.google-apps.spreadsheet','parents':[FOLDER_ID]})
    ss = r.json()['id']; print(f'ID: {ss}')
    time.sleep(3)
    for attempt in range(5):
        r2 = s.get(f'https://sheets.googleapis.com/v4/spreadsheets/{ss}?fields=sheets.properties',timeout=30)
        try: def_sid=r2.json()['sheets'][0]['properties']['sheetId']; break
        except: time.sleep(3)
    r3 = api_post(s,f'https://sheets.googleapis.com/v4/spreadsheets/{ss}:batchUpdate',{'requests':[
        {'updateSheetProperties':{'properties':{'sheetId':def_sid,'title':'ЗБ'},'fields':'title'}},
        {'addSheet':{'properties':{'title':'ОВИР','index':1}}},
        {'addSheet':{'properties':{'title':'Свод','index':2}}},
        {'addSheet':{'properties':{'title':'Расходы ЗБ','index':3}}},
        {'addSheet':{'properties':{'title':'Расходы ОВИР','index':4}}},
        {'addSheet':{'properties':{'title':'Месяцы','index':5}}},
    ]})
    rpl=r3.json()['replies']
    sids={'ЗБ':def_sid,'ОВИР':rpl[1]['addSheet']['properties']['sheetId'],
          'Свод':rpl[2]['addSheet']['properties']['sheetId'],
          'Расходы ЗБ':rpl[3]['addSheet']['properties']['sheetId'],
          'Расходы ОВИР':rpl[4]['addSheet']['properties']['sheetId'],
          'Месяцы':rpl[5]['addSheet']['properties']['sheetId']}
    print(f'Sheets: {sids}')

    for name,plan,sfx,is_svod,rd in [
        ('ЗБ',PLAN_ZB,'ЗБ (Лохути 11)',False,rev),
        ('ОВИР',PLAN_OVIR,'ОВИР (Турсунзода)',False,None),
        ('Свод',PLAN_ZB+PLAN_OVIR,'СВОД (ЗБ + ОВИР)',True,None),
    ]:
        print(f'\n── {name} ──')
        write_values(s,ss,name,build_rows(plan,rd,is_svod,sfx))
        time.sleep(1)
        apply_fmt(s,ss,fmt_tracker(sids[name]),name)

    print('\n── Расходы ──')
    write_values(s,ss,'Расходы ЗБ',build_expenses_rows('ЗБ'))
    write_values(s,ss,'Расходы ОВИР',build_expenses_rows('ОВИР'))
    apply_fmt(s,ss,fmt_expenses(sids['Расходы ЗБ']),'Расходы ЗБ')
    apply_fmt(s,ss,fmt_expenses(sids['Расходы ОВИР']),'Расходы ОВИР')

    print('\n── Месяцы ──')
    write_values(s,ss,'Месяцы',build_months_rows())
    apply_fmt(s,ss,fmt_months(sids['Месяцы']),'Месяцы')

    print(f'\n✅ https://docs.google.com/spreadsheets/d/{ss}/edit')
    print(f'TRACKER_SS_ID = "{ss}"')

if __name__=='__main__': main()
