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
    query = f"'{folder_id}' in parents and name = '{filename}'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items: return None
    
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    local_path = "temp.jpg"
    with open(local_path, "wb") as f:
        f.write(fh.getbuffer())
    return local_path

def main():
    # 載入密鑰
    secrets = {
        'gdrive': json.loads(os.getenv('GDRIVE_JSON')),
        'user': os.getenv('THREADS_USERNAME'),
        'pass': os.getenv('THREADS_PASSWORD')
    }

    # Google Drive 認證
    creds = service_account.Credentials.from_service_account_info(secrets['gdrive'])
    drive_service = build('drive', 'v3', credentials=creds)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()

        # 登入 Threads
        print("🔑 正在登入 Threads...")
        page.goto("https://www.threads.net/login")
        page.fill('input[placeholder*="帳號"]', secrets['user']) # 這裡用 placeholder 抓更穩
        page.fill('input[placeholder*="密碼"]', secrets['pass'])
        page.click('div[role="button"]:has-text("登入")')
        page.wait_for_url("https://www.threads.net/", timeout=60000)
        print("✅ 登入成功！")

        # 循環發送 5 張
        for _ in range(5):
            if not os.path.exists(PROGRESS_FILE):
                f_idx, i_idx = 0, 1
            else:
                with open(PROGRESS_FILE, 'r') as f:
                    f_idx, i_idx = map(int, f.read().strip().split(','))

            if f_idx >= len(FOLDER_LIST):
                print("🏁 全劇終！")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            
            print(f"📸 準備下載 {folder['name']} - {filename}")
            img_path = download_image(drive_service, folder['id'], filename)

            if not img_path:
                print(f"⏭️ 找不到檔案，跳下一集")
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx + 1},1")
                continue

            # 發文操作
            try:
                page.goto("https://www.threads.net/")
                page.click('div[role="presentation"] svg[aria-label="建立內容"]') # 點擊發文
                page.wait_for_selector('div[role="textbox"]')
                page.keyboard.type(f"MyGO!!!!! {folder['name']}\nFrame: {i_idx}")
                
                # 上傳圖片 (Playwright 的上傳方式)
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label="附加媒體"]') # 點擊上傳圖示
                file_chooser = fc_info.value
                file_chooser.set_files(img_path)
                
                time.sleep(3) # 等待圖片載入
                page.click('div[role="button"]:has-text("發佈")')
                print(f"✅ 已成功發佈：{filename}")

                # 更新進度
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx + 1}")
                
                print("⏳ 等待 600 秒後發送下一張...")
                time.sleep(600)

            except Exception as e:
                print(f"❌ 發佈過程出錯: {e}")
                break

        browser.close()

if __name__ == "__main__":
    main()
