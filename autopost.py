import os
import json
import time
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
FOLDER_LIST = [
    {'name': 'Ep 1-3', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    {'name': 'Ep 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    {'name': 'Ep 5', 'id': '1NW98O1i6EkO_SlZWqLtNBO78N-vveugw'},
    {'name': 'Ep 6', 'id': '1F6vmpH2PCZ-H8qQ1OGxFDqEJBmS_zJ9k'},
    {'name': 'Ep 7', 'id': '11-IHOKWb4PR9aCxJtieJxgCfQ3OTh5H7'},
    {'name': 'Ep 8', 'id': '1IJtDejmjTNVFOEFyCumvDzWgCND-HQmA'},
    {'name': 'Ep 9', 'id': '14keTQu3tqM3qSYcECLd3ub3MzTP6LC5F'},
    {'name': 'Ep 10', 'id': '11LK0p3lr8S_Gn_ZLiSIOjaI5gSoNAnCZ'},
    {'name': 'Ep 11', 'id': '1RVE45ulNjLMZ9iypOUzZZDUnAUKavkQK'},
    {'name': 'Ep 12', 'id': '1CHTpS_abB6SsLcgQBCMtLhKnKgMbLjgd'},
    {'name': 'Ep 13', 'id': '1cVtofiJZDEbhNlNhtHcg0DOEO6nPsCPf'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, target_idx):
    try:
        results = service.files().list(q=f"'{folder_id}' in parents and trashed = false", fields="files(id, name)", pageSize=1000).execute()
        items = sorted(results.get('files', []), key=lambda x: x['name'])
        if not items: return None
        match = re.search(r'(\d+)', items[0]['name'])
        if not match: return None
        actual_num = int(match.group(1)) + (target_idx - 1)
        actual_pattern = f"{actual_num:04d}"
        target_id = next((i['id'] for i in items if actual_pattern in i['name']), None)
        if not target_id: return None
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ 下載圖片失敗: {e}")
        return None

def main():
    username = os.getenv('THREADS_USERNAME')
    password = os.getenv('THREADS_PASSWORD')
    gdrive_json = os.getenv('GDRIVE_JSON')
    
    if not username or not password:
        print("❌ 錯誤：未設定 THREADS_USERNAME 或 THREADS_PASSWORD")
        return

    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)
    
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: f_idx, i_idx = map(int, line.split(','))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("🌐 進入登入頁面...")
        page.goto("https://www.threads.net/login", wait_until="networkidle")
        time.sleep(8)

        print("⌨️ 嘗試填寫帳密...")
        try:
            # 針對 Instagram 登入欄位
            page.wait_for_selector('input[name="username"]', timeout=15000)
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
        except:
            print("⚠️ 找不到標準欄位，嘗試 Tab 盲填...")
            page.keyboard.press("Tab")
            time.sleep(0.5)
            page.keyboard.type(username)
            page.keyboard.press("Tab")
            time.sleep(0.5)
            page.keyboard.type(password)
            page.keyboard.press("Enter")

        print("⏳ 等待登入跳轉（40秒）...")
        time.sleep(40)
        page.screenshot(path="after_login_attempt.png")

        # 開始發文流程
        for i in range(3):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: 
                f_idx += 1; i_idx = 1
                continue

            try:
                print(f"🚀 準備發佈: {folder['name']} - {i_idx}")
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle")
                time.sleep(10)

                textbox = page.locator('div[role="textbox"]')
                if not textbox.is_visible():
                    print("🚨 登入可能失敗，找不到發文框。")
                    page.screenshot(path="no_textbox.png")
                    break
                
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}")
                
                # 修正：同步模式下的 expect_file_chooser
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"], svg[aria-label*="Attach"]').first.click()
                file_chooser = fc_info.value
                file_chooser.set_files(img_path)
                
                print("📤 上傳中...")
                time.sleep(12)

                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                if post_btn.is_enabled():
                    post_btn.click()
                    print(f"🎉 成功：{folder['name']} - {i_idx}")
                    time.sleep(10)
                    
                    i_idx += 1
                    with open(PROGRESS_FILE, 'w') as f:
                        f.write(f"{f_idx},{i_idx}")
                else:
                    print("❌ 按鈕不可點擊")
                    break

            except Exception as e:
                print(f"❌ 錯誤: {e}")
                break

        browser.close()

if __name__ == "__main__":
    main()
