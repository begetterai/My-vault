#!/usr/bin/env python3
"""Загрузка ТТК-карточки .xlsx в папку Drive «Полуфабрикаты v2».
Если файл с таким именем уже есть — обновляет содержимое (не плодит дубли)."""
import os, sys, json
os.environ['REQUESTS_CA_BUNDLE']='/etc/ssl/certs/ca-certificates.crt'
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

FOLDER='1MpzoYuRYYoZGgZU11WeVyROP0yZaNbHT'  # Полуфабрикаты v2
XLSX_MIME='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
creds=service_account.Credentials.from_service_account_file(
  '/home/user/My-vault/scripts/credentials/romashka-drive.json',
  scopes=['https://www.googleapis.com/auth/drive'])
s=AuthorizedSession(creds)

def find(name):
    q=f"name='{name}' and '{FOLDER}' in parents and trashed=false"
    r=s.get('https://www.googleapis.com/drive/v3/files',params={'q':q,'fields':'files(id,name)',
        'includeItemsFromAllDrives':'true','supportsAllDrives':'true'},timeout=30)
    f=r.json().get('files',[])
    return f[0]['id'] if f else None

def upload(path, name=None):
    name=name or os.path.basename(path)
    data=open(path,'rb').read()
    fid=find(name)
    if fid:
        r=s.patch(f'https://www.googleapis.com/upload/drive/v3/files/{fid}?uploadType=media&supportsAllDrives=true',
            headers={'Content-Type':XLSX_MIME}, data=data, timeout=120)
        r.raise_for_status(); return ('updated', fid, name)
    meta={'name':name,'parents':[FOLDER]}
    import requests
    boundary='----ttkboundary'
    body=(f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+
          json.dumps(meta)+f'\r\n--{boundary}\r\nContent-Type: {XLSX_MIME}\r\n\r\n').encode()+data+f'\r\n--{boundary}--'.encode()
    r=s.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true',
        headers={'Content-Type':f'multipart/related; boundary={boundary}'}, data=body, timeout=120)
    r.raise_for_status(); return ('created', r.json()['id'], name)

if __name__=='__main__':
    print(upload(sys.argv[1]))
