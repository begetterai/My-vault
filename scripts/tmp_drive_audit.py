#!/usr/bin/env python3
"""
Задача 2: Аудит структуры Google Drive УК Ромашка
"""
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDS_FILE = '/home/user/My-vault/scripts/credentials/romashka-drive.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

creds = service_account.Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
service = build('drive', 'v3', credentials=creds)

# 1. Список Shared Drives
print("=== SHARED DRIVES ===")
try:
    drives_result = service.drives().list(pageSize=50).execute()
    drives = drives_result.get('drives', [])
    print(f"Найдено Shared Drives: {len(drives)}")
    for d in drives:
        print(f"  id={d['id']}  name={d['name']}")
except Exception as e:
    print(f"Ошибка drives.list: {e}")
    drives = []

# 2. Список файлов/папок во всех Shared Drives
print("\n=== ВСЕ ФАЙЛЫ (allDrives) ===")
try:
    all_items = []
    page_token = None
    while True:
        params = {
            'includeItemsFromAllDrives': True,
            'supportsAllDrives': True,
            'corpora': 'allDrives',
            'fields': 'nextPageToken,files(id,name,mimeType,parents,driveId)',
            'pageSize': 1000,
        }
        if page_token:
            params['pageToken'] = page_token
        result = service.files().list(**params).execute()
        items = result.get('files', [])
        all_items.extend(items)
        page_token = result.get('nextPageToken')
        if not page_token:
            break

    print(f"Всего объектов: {len(all_items)}")

    # Строим индексы
    id_to_item = {item['id']: item for item in all_items}
    folders = [item for item in all_items if item['mimeType'] == 'application/vnd.google-apps.folder']
    files   = [item for item in all_items if item['mimeType'] != 'application/vnd.google-apps.folder']

    print(f"Папок: {len(folders)}")
    print(f"Файлов: {len(files)}")

    # Строим дерево
    def get_path(item_id, id_to_item, depth=0):
        if depth > 10:
            return ''
        item = id_to_item.get(item_id)
        if not item:
            return ''
        parents = item.get('parents', [])
        if not parents:
            return item['name']
        parent_path = get_path(parents[0], id_to_item, depth+1)
        if parent_path:
            return f"{parent_path} / {item['name']}"
        return item['name']

    # Выводим все папки с путями
    print("\n=== ВСЕ ПАПКИ (иерархически) ===")
    folder_paths = []
    for folder in folders:
        path = get_path(folder['id'], id_to_item)
        folder_paths.append((path, folder['id'], folder['name']))

    folder_paths.sort(key=lambda x: x[0].lower())
    for path, fid, name in folder_paths:
        print(f"  [{fid}] {path}")

    # Ищем "меню и экраны" или похожее
    print("\n=== ПОИСК 'меню и экраны' / 'меню' / 'экран' ===")
    keywords = ['меню', 'экран', 'menu', 'screen']
    for item in all_items:
        name_lower = item['name'].lower()
        if any(kw in name_lower for kw in keywords):
            path = get_path(item['id'], id_to_item)
            mime = 'FOLDER' if item['mimeType'] == 'application/vnd.google-apps.folder' else 'FILE'
            print(f"  {mime}  {path}  [{item['id']}]")

    # Если drives найдены — выводим структуру по дискам
    if drives:
        print("\n=== СТРУКТУРА ПО ДИСКАМ ===")
        for drive in drives:
            drive_id = drive['id']
            drive_name = drive['name']
            drive_items = [item for item in all_items if item.get('driveId') == drive_id]
            print(f"\n--- Диск: {drive_name} (id={drive_id}) ---")
            print(f"  Объектов: {len(drive_items)}")
            drive_folders = [item for item in drive_items if item['mimeType'] == 'application/vnd.google-apps.folder']
            for folder in drive_folders:
                path = get_path(folder['id'], id_to_item)
                print(f"    ПАПКА: {path}  [{folder['id']}]")

except Exception as e:
    print(f"Ошибка files.list: {e}")
    import traceback
    traceback.print_exc()
