import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

def debug_drive():
    gdrive_json = os.getenv('GDRIVE_JSON')
    if not gdrive_json:
        print("❌ 找不到 GDRIVE_JSON")
        return

    # 1. 登入
    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    service = build('drive', 'v3', credentials=creds)
    
    # 你提供的第一個資料夾 ID
    test_folder_id = '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'
    
    print(f"🕵️ 正在診斷資料夾 ID: {test_folder_id}")
    print(f"📧 使用帳號: {creds.service_account_email}")
    print("-" * 30)

    try:
        # 2. 嘗試獲取資料夾資訊
        folder_info = service.files().get(fileId=test_folder_id, fields="name").execute()
        print(f"✅ 成功存取資料夾！名稱為: {folder_info.get('name')}")
        
        # 3. 列出前 20 個檔案
        results = service.files().list(
            q=f"'{test_folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=20
        ).execute()
        items = results.get('files', [])

        if not items:
            print("💀 警告：資料夾是空的！程式帳號什麼都沒看到。")
            print("👉 請檢查：你是否真的把這個 Email 加入了『共用』名單？")
        else:
            print(f"找到 {len(items)} 個檔案：")
            for item in items:
                print(f" - {item['name']} (ID: {item['id']})")

    except Exception as e:
        print(f"❌ 存取失敗！錯誤原因: {e}")
        print("👉 這通常代表 ID 錯了，或者 Email 權限沒設對。")

if __name__ == "__main__":
    debug_drive()
