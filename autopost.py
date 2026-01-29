import os
import json
import time
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 (請確保 FOLDER_LIST 完整) ---
FOLDER_LIST = [
    {'name': 'Ep 1-3', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    # ... 補齊其他集數 ...
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
    except: return None

def main():
    # 讀取 Secret
    gdrive_json = os.getenv('GDRIVE_JSON')
    username = os.getenv('THREADS_USERNAME')
    password = os.getenv('THREADS_PASSWORD')
    
    if not gdrive_json or not username:
        print("❌ 缺少環境變數！")
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
        # 模擬超真實瀏覽器
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("🔐 正在執行自動登入...")
        page.goto("https://www.threads.net/login", wait_until="networkidle")
        time.sleep(5)
        
        # 輸入帳密
        page.fill('input[placeholder*="帳號"], input[name="username"]', username)
        page.fill('input[placeholder*="密碼"], input[name="password"]', password)
        page.click('button[type="submit"]')
        
        print("⏳ 等待登入跳轉...")
        time.sleep(15)
        
        # 處理「儲存登入資訊」或「稍後再說」的彈窗
        for _ in range(2):
            not_now = page.get_by_role("button", name=re.compile(r"稍後再說|Not now|以後", re.I))
            if not_now.is_visible():
                not_now.click()
                time.sleep(5)

        for i in range(3): # 每次跑 3 張，降低風險
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: f_idx += 1; i_idx = 1; continue

            try:
                print(f"🚀 發佈: {folder['name']} - {i_idx}")
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle")
                time.sleep(10)

                # 填寫內容
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                page.fill('div[role="textbox"]', f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}")
                
                # 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                time.sleep(10) 
                
                # 發佈
                page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first.click()
                time.sleep(10)
                print(f"🎉 成功！")
                
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                time.sleep(300) # 間隔 5 分鐘
            except Exception as e:
                print(f"❌ 錯誤: {e}")
                page.screenshot(path=f"error_{i}.png")
                break
        browser.close()

if __name__ == "__main__": main()
