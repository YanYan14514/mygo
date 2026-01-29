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
    {'name': 'Ep 7', 'id': '11-IHOKWb4PR9aCxJtieJxgCf (省略)'}, # 此處建議保留你原本的完整清單
]
# ... (請確保 FOLDER_LIST 包含你完整的 1-13 集 ID)

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
    # 讀取所有 Secret
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    user_id = os.getenv('THREADS_USER_ID')
    csrf_token = os.getenv('THREADS_CSRF_TOKEN')
    
    if not all([gdrive_json, session_id, user_id, csrf_token]):
        print("❌ 缺少環境變數 (Secrets)！")
        return

    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)
    
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: f_idx, i_idx = map(int, line.split(','))

    with sync_playwright() as p:
        # 強力偽裝
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        
        # 注入三重 Cookie
        context.add_cookies([
            {'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'},
            {'name': 'ds_user_id', 'value': user_id, 'domain': '.threads.net', 'path': '/'},
            {'name': 'csrftoken', 'value': csrf_token, 'domain': '.threads.net', 'path': '/'}
        ])
        
        page = context.new_page()
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: f_idx += 1; i_idx = 1; continue

            try:
                print(f"🚀 [集數 {folder['name']} - 第 {i_idx} 張] 正在啟動發佈流程...")
                
                # 直接導向 Intent 頁面，有了 Triple Cookie 成功率會大增
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
                time.sleep(10)

                # 偵測是否被導向登入頁
                if "login" in page.url:
                    print("🚨 登入憑證已失效，請更新 Secrets！")
                    page.screenshot(path="login_failed.png")
                    break

                # 等待並填寫內容
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                caption = f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}"
                page.fill('div[role="textbox"]', caption)
                
                # 媒體上傳
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 正在上傳至 Threads...")
                time.sleep(15) 
                
                # 按下發佈
                publish_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                publish_btn.click()
                
                time.sleep(10)
                print(f"🎉 第 {i+1} 篇貼文成功！")
                
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
                
                if i < 5: 
                    print("⏳ 冷卻中 (600s)...")
                    time.sleep(600)
                    
            except Exception as e:
                print(f"❌ 發生錯誤: {e}")
                page.screenshot(path=f"step_fail_{i}.png")
                break
        browser.close()

if __name__ == "__main__": main()
