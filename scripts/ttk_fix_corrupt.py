#!/usr/bin/env python3
"""Перезаписывает битые ТТК-карточки в папке рабочими TNR13-версиями.
Берёт спеки из spec_fix.json (+ «Классический» из spec_3.json), собирает xlsx,
и PATCH-ом перезаписывает ВСЕ файлы в папке с таким именем (лечит и дубли)."""
import os, io, json, sys
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
sys.path.insert(0,'/home/user/My-vault/scripts')
from ttk_card import build_card
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

FOLDER='1MpzoYuRYYoZGgZU11WeVyROP0yZaNbHT'
XLSX='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
SP="/tmp/claude-0/-home-user-My-vault/606dd1b1-a624-5ef2-a06e-c6a894e680ba/scratchpad"
creds=service_account.Credentials.from_service_account_file(
  '/home/user/My-vault/scripts/credentials/romashka-drive.json',scopes=['https://www.googleapis.com/auth/drive'])
s=AuthorizedSession(creds)

def by_name(name):
    r=s.get('https://www.googleapis.com/drive/v3/files',params={
      'q':f"name='{name}' and '{FOLDER}' in parents and trashed=false",
      'fields':'files(id,name)','includeItemsFromAllDrives':'true','supportsAllDrives':'true'},timeout=30)
    return r.json().get('files',[])

def overwrite(fid, data):
    u=s.patch(f"https://www.googleapis.com/upload/drive/v3/files/{fid}?uploadType=media&supportsAllDrives=true",
        headers={'Content-Type':XLSX}, data=data, timeout=120); u.raise_for_status()

def main():
    specs=json.load(open(f"{SP}/spec_fix.json"))
    klass=[x for x in json.load(open(f"{SP}/spec_3.json")) if 'Классическ' in x['key']]
    specs+=klass
    print("Карточек к перезаписи:",len(specs))
    for sp in specs:
        path=f"{SP}/{sp['filename']}"; build_card(sp, path)
        data=open(path,'rb').read()
        files=by_name(sp['filename'])
        if not files:
            print(f"  ⚠ в папке нет файла «{sp['filename']}» — пропуск (создать SA не может)"); continue
        for f in files:
            overwrite(f['id'], data)
        print(f"  ✓ перезаписано ({len(files)} шт.): {sp['filename']}")

if __name__=='__main__':
    main()
