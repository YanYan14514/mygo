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
    while not done:
        status, done = downloader.next_chunk()
    local_path = "temp.jpg"
    with open(local_path, "wb") as f:
        f.write(fh.getbuffer())
    return local_path

def main():
    secrets = {
        'gdrive': json.loads(os.getenv('GDRIVE_JSON')),
        'user': os.getenv('THREADS_USERNAME'),
        'pass': os.getenv('THREADS_PASSWORD')
    }
    creds = service_account.Credentials.from_service_account_info(secrets['gdrive'])
    drive_service = build('drive', 'v3', credentials=creds)

    with sync_playwright() as p:
        # 1. 啟動瀏覽器時就直接注入偽裝的 User-Agent
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        browser = p.chromium.launch(headless=True)
        
        # 2. 建立 Context 並設定語言為中文，這樣按鈕名字才不會跑掉
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=user_agent,
            locale="zh-TW"
        )
        page = context.new_page()

        print("🔑 正在登入 Threads...")
        page.goto("https://www.threads.net/login", wait_until="networkidle")
        
        try:
            # 等待輸入框出現
            page.wait_for_selector('input', timeout=60000)
            
            # 抓取頁面上所有輸入框並填寫
            inputs = page.query_selector_all('input')
            if len(inputs) >= 2:
                inputs[0].fill(secrets['user'])
                inputs[1].fill(secrets['pass'])
                time.sleep(1) # 稍微停頓模擬真人
            
            # 點擊登入按鈕 (同時支援中英文)
            login_btn = page.locator('button[type="submit"], div[role="button"]:has-text("登入"), div[role="button"]:has-text("Log in")').first
            login_btn.click()
            
            # 等待跳轉，時間給長一點，因為登入有時候會卡
            page.wait_for_url("https://www.threads.net/", timeout=60000)
            print("✅ 登入成功！")
            
        except Exception as e:
            # 如果還是失敗，截一張圖存下來，方便我們 debug
            page.screenshot(path="login_error.png")
            print(f"❌ 登入失敗或超時，已截圖存檔。錯誤: {e}")
            raise

        for i in range(6):
            if not os.path.exists(PROGRESS_FILE):
                f_idx, i_idx = 0, 1
            else:
                with open(PROGRESS_FILE, 'r') as f:
                    line = f.read().strip()
                    f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

            if f_idx >= len(FOLDER_LIST):
                print("🏁 全劇終！")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            img_path = download_image(drive_service, folder['id'], filename)

            if not img_path:
                print(f"⏭️ 找不到檔案，跳下一集")
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx + 1},1")
                continue

            try:
                page.goto("https://www.threads.net/")
                page.wait_for_selector('svg[aria-label="建立內容"]', timeout=30000)
                page.click('svg[aria-label="建立內容"]')
                page.wait_for_selector('div[role="textbox"]')
                
                # 時間換算 (一秒一張)
                mm, ss = divmod(i_idx, 60)
                ep_num = folder['name'].replace('mygo', '').replace('123_part1', '1').replace('123_part2', '1')
                content = f"BanG Dream! It's MyGO!!!!! 第 {ep_num} 集 {mm:02d}:{ss:02d}"
                
                page.keyboard.type(content)
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label="附加媒體"]')
                fc_info.value.set_files(img_path)
                
                time.sleep(5) 
                page.click('div[role="button"]:has-text("發佈")')
                print(f"✅ 已成功發佈：{content}")

                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx + 1}")
                
                if i < 5:
                    print("⏳ 等待 600 秒...")
                    time.sleep(600)
            except Exception as e:
                print(f"❌ 出錯: {e}")
                break
        browser.close()

if __name__ == "__main__":
    main()



