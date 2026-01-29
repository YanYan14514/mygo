import os
import json
import time
import io
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
FOLDER_LIST = [
    {'name': 'Ep 1-3', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    {'name': 'Ep 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'}
]
PROGRESS_FILE = 'progress.txt'

def main():
    print("🎬 程式啟動...")
    
    # 檢查環境變數
    s_id = os.getenv('THREADS_SESSION_ID')
    u_id = os.getenv('THREADS_USER_ID')
    c_tk = os.getenv('THREADS_CSRF_TOKEN')
    g_js = os.getenv('GDRIVE_JSON')

    print(f"🔍 環境檢查: SESSION_ID={bool(s_id)}, USER_ID={bool(u_id)}, CSRF={bool(c_tk)}, GDRIVE={bool(g_js)}")

    if not all([s_id, u_id, c_tk, g_js]):
        print("❌ 錯誤：Secrets 設定不完整，請檢查 GitHub Settings -> Secrets")
        sys.exit(1)

    try:
        creds = service_account.Credentials.from_service_account_info(json.loads(g_js))
        drive_service = build('drive', 'v3', credentials=creds)
        print("✅ Google Drive 驗證成功")
    except Exception as e:
        print(f"❌ Google Drive 驗證失敗: {e}")
        sys.exit(1)

    with sync_playwright() as p:
        print("🌐 啟動瀏覽器...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        context.add_cookies([
            {'name': 'sessionid', 'value': s_id.strip(), 'domain': '.threads.net', 'path': '/'},
            {'name': 'ds_user_id', 'value': u_id.strip(), 'domain': '.threads.net', 'path': '/'},
            {'name': 'csrftoken', 'value': c_tk.strip(), 'domain': '.threads.net', 'path': '/'}
        ])
        
        page = context.new_page()
        print("🔗 嘗試進入 Threads 發文頁面...")
        
        try:
            page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
            time.sleep(10)
            page.screenshot(path="debug_page_load.png")
            print(f"📸 頁面已載入，目前 URL: {page.url}")
            
            if "login" in page.url:
                print("🚨 登入無效，被導向登入頁。請更新 Cookie！")
            else:
                textbox = page.locator('div[role="textbox"]')
                if textbox.is_visible():
                    print("🎯 成功找到發文框！")
                    # 這裡可以暫時先不發文，先測通登入
                else:
                    print("❓ 找不到發文框，可能 DOM 結構改變")
        except Exception as e:
            print(f"❌ 頁面操作失敗: {e}")
            page.screenshot(path="debug_error.png")
            
        browser.close()
        print("🏁 程式結束")

if __name__ == "__main__":
    main()
