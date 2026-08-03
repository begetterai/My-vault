#!/usr/bin/env python3
"""Меняет шрифт на Times New Roman 13 во ВСЕХ ячейках существующих ТТК-карточек
в папке «Полуфабрикаты v2». Правится только шрифт (name+size), всё остальное —
жирный, курсив, цвет текста, заливки, рамки, содержимое — сохраняется.
Работает через право редактирования SA (создавать файлы не нужно)."""
import os, io
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
import openpyxl
from copy import copy

FOLDER='1MpzoYuRYYoZGgZU11WeVyROP0yZaNbHT'
XLSX_MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
creds=service_account.Credentials.from_service_account_file(
  '/home/user/My-vault/scripts/credentials/romashka-drive.json',
  scopes=['https://www.googleapis.com/auth/drive'])
s=AuthorizedSession(creds)

def cards():
    q=(f"'{FOLDER}' in parents and trashed=false and mimeType='{XLSX_MIME}'")
    r=s.get('https://www.googleapis.com/drive/v3/files',params={'q':q,
        'fields':'files(id,name)','pageSize':200,
        'includeItemsFromAllDrives':'true','supportsAllDrives':'true'},timeout=30)
    return r.json().get('files',[])

def refont_bytes(data):
    wb=openpyxl.load_workbook(io.BytesIO(data))
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                f=c.font
                c.font=openpyxl.styles.Font(name='Times New Roman', size=13,
                    bold=f.bold, italic=f.italic, color=copy(f.color),
                    underline=f.underline, strike=f.strike)
    out=io.BytesIO(); wb.save(out); return out.getvalue()

def main():
    fs=cards()
    print(f"Карточек в папке: {len(fs)}")
    ok=0; skipped=[]
    for f in fs:
        try:
            new=None
            for attempt in range(6):
                r=s.get(f"https://www.googleapis.com/drive/v3/files/{f['id']}",
                    params={'alt':'media','supportsAllDrives':'true'},timeout=90)
                r.raise_for_status()
                try:
                    new=refont_bytes(r.content); break   # успех = zip полностью прочитан
                except Exception:
                    continue
            if new is None:
                raise ValueError('не удалось скачать/прочитать xlsx за 6 попыток')
            u=s.patch(f"https://www.googleapis.com/upload/drive/v3/files/{f['id']}?uploadType=media&supportsAllDrives=true",
                headers={'Content-Type':XLSX_MIME}, data=new, timeout=120)
            u.raise_for_status()
            print("  ✓ TNR13:", f['name']); ok+=1
        except Exception as e:
            print("  ⚠ пропуск:", f['name'], "—", type(e).__name__)
            skipped.append(f['name'])
    print(f"\nГотово: {ok} шрифт заменён; пропущено {len(skipped)}")
    if skipped:
        for n in skipped: print("   -",n)

if __name__=='__main__':
    main()
