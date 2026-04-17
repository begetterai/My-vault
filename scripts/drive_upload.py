#!/usr/bin/env python3
"""
Загрузка файлов в Google Drive (папка Ромашка).
Использование: import drive_upload; drive_upload.upload(filepath)
"""

import os
import json

CREDENTIALS = os.path.join(os.path.dirname(__file__), "credentials", "romashka-drive.json")
FOLDER_ID = "14NnVXa9k1h0dyS-vNch61A3-aSpJG_Jn"


def _get_session():
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_file(
        CREDENTIALS, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return AuthorizedSession(creds)


def upload(filepath: str, retries: int = 3) -> str | None:
    """Загрузить файл в Drive. Если файл с таким именем уже есть — обновить."""
    import time
    last_err = None
    for attempt in range(retries):
        try:
            result = _upload_once(filepath)
            return result
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    print(f"⚠️  Drive upload failed: {last_err}")
    return None


def _upload_once(filepath: str) -> str | None:
    try:
        session = _get_session()
        filename = os.path.basename(filepath)

        # Поиск существующего файла
        q = f"name='{filename}' and '{FOLDER_ID}' in parents and trashed=false"
        r = session.get(
            "https://www.googleapis.com/drive/v3/files",
            params={"q": q, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true", "fields": "files(id,name)"},
        )
        files = r.json().get("files", [])

        with open(filepath, "rb") as f:
            content = f.read()

        metadata = json.dumps({"name": filename, "parents": [FOLDER_ID]})
        body = (
            b"--bound\r\nContent-Type: application/json\r\n\r\n"
            + metadata.encode()
            + b"\r\n--bound\r\nContent-Type: text/markdown\r\n\r\n"
            + content
            + b"\r\n--bound--"
        )
        headers = {"Content-Type": "multipart/related; boundary=bound"}

        if files:
            file_id = files[0]["id"]
            # Обновить содержимое без смены метаданных
            r = session.patch(
                f"https://www.googleapis.com/upload/drive/v3/files/{file_id}?uploadType=media&supportsAllDrives=true",
                data=content,
                headers={"Content-Type": "text/markdown"},
            )
        else:
            r = session.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true",
                data=body,
                headers=headers,
            )

        d = r.json()
        if "id" in d:
            file_id = d["id"]
            url = f"https://drive.google.com/file/d/{file_id}/view"
            print(f"☁️  Drive: {url}")
            return url
        else:
            raise Exception(f"Drive API error: {d}")

    except Exception:
        raise


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        upload(sys.argv[1])
