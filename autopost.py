import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
FOLDER_LIST = [
    {'name': 'mygo123_part1', 'id': '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'},
    {'name': 'mygo123_part2', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    {'name': 'mygo4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    {'name': 'mygo5', 'id': '1NW98O1i6EkO_SlZWqLtNBO78N-vveugw'},
    {'name': 'mygo6', 'id': '1F6vmpH2PCZ-H8qQ1OGxFDqEJBmS_zJ9k'},
    {'name': 'mygo7', 'id': '11-IHOKWb4PR9aCxJtieJxgCfQ3OTh5H7'},
    {'name': 'mygo8', 'id': '1IJtDejmjTNVFOEFyCumvDzWgCND-HQmA'},
    {'name': 'mygo9', 'id': '14keTQu3tqM3qSYcECLd3ub3MzTP6LC5F'},
    {'name': 'mygo10', 'id': '11LK0p3lr8S_Gn_ZLiSIOjaI5gSoNAnCZ'},
    {'name': 'mygo11', 'id': '1RVE45ulNjLMZ9iypOUzZZDUnAUKavkQK'},
    {'name': 'mygo12', 'id': '1CHTpS_abB6SsLcgQBCMtLhKnKgMbLjgd'},
    {'name': 'mygo13', 'id': '1cVtofiJZDEbhNlNhtHcg0DOEO6nPsCPf'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, filename):
    try:
        query = f"'{folder_id}' in parents and name = '{filename}'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])
        if not items: return None
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        local_path = "temp.jpg"
        with open(local_path, "wb") as f:
            f.write(fh.getbuffer())
        return local_path
    except Exception as e:
        print(f"下載圖片出錯: {e}")
        return None

def main():
    # 讀取 Secrets
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    
    if not gdrive_json or not session_id:
        print("❌ 缺少必要的 Secrets 設定 (GDRIVE_JSON 或 THREADS_SESSION_ID)")
        return

    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)

    # 讀取初始進度
    if not os.path.exists(PROGRESS_FILE):
        f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

    with sync_playwright() as p:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=user_agent,
            locale="zh-TW"
        )
        page = context.new_page()

        # --- 使用 Cookie 登入 ---
        print("🔑 Authorization: 使用 Session Cookie...")
        context.add_cookies([{
            'name': 'sessionid',
            'value': session_id,
            'domain': '.threads.net',
            'path': '/',
            'secure': True,
            'httpOnly': True,
            'sameSite': 'Lax'
        }])
        
        try:
            page.goto("https://www.threads.net/", wait_until="networkidle")
            time.sleep(5) 
            if not page.query_selector('svg[aria-label="建立內容"]'):
                print("❌ Cookie 登入失敗，請檢查 THREADS_SESSION_ID 是否過期")
                return
            print("✅ Cookie 登入成功！")
        except Exception as e:
            print(f"❌ 登入過程發生異常: {e}")
            return

        # --- 發文循環 (一次運行發 6 張) ---
        for i in range(6):
            if f_idx >= len(FOLDER_LIST):
                print("🏁 全劇終！")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"📸 準備下載: {folder['name']} / {filename}")
            img_path = download_image(drive_service, folder['id'], filename)

            if not img_path:
                print(f"⏭️ 找不到檔案 {filename}，跳轉至下一集第一張")
                f_idx += 1
                i_idx = 1
                continue

            try:
            # 1. 增加超時到 90 秒，並將等待條件改為 domcontentloaded (只要結構出來就好)
            print("🌐 正在開啟 Threads 頁面...")
            page.goto("https://www.threads.net/", wait_until="domcontentloaded", timeout=90000)
            
            # 2. 給一點緩衝時間讓 Cookie 生效
            time.sleep(10) 
            
            # 3. 檢查是否登入成功
            if page.query_selector('svg[aria-label="建立內容"]') or page.query_selector('svg[aria-label="New thread"]'):
                print("✅ Cookie 登入成功！")
            else:
                # 如果找不到按鈕，可能是首頁還沒載入完，再等一下下
                print("⏳ 找不到發文按鈕，嘗試最後等待...")
                page.wait_for_selector('svg[aria-label*="建立"], svg[aria-label*="thread"]', timeout=30000)
                print("✅ Cookie 登入成功！")
                
        except Exception as e:
            page.screenshot(path="login_error.png") # 失敗時截圖
            print(f"❌ 登入失敗或頁面載入過慢: {e}")
            return
                
        browser.close()

if __name__ == "__main__":
    main()

