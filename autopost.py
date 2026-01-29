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
    {'name': 'Episode 1-3', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    {'name': 'Episode 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    {'name': 'Episode 5', 'id': '1NW98O1i6EkO_SlZWqLtNBO78N-vveugw'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, target_idx):
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=1000
        ).execute()
        items = sorted(results.get('files', []), key=lambda x: x['name'])
        
        if not items: return None

        # 如果找不到指定序號，就抓該資料夾的第一個檔案 (解決起始序號不是 0001 的問題)
        target_id = None
        target_name = f"frame_{target_idx:04d}"
        
        for item in items:
            if target_name in item['name']:
                target_id = item['id']
                print(f"🎯 找到指定檔案: {item['name']}")
                break
        
        if not target_id and target_idx == 1:
            target_id = items[0]['id']
            print(f"⚠️ 找不到 0001，自動抓取首個檔案: {items[0]['name']}")

        if not target_id: return None

        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f:
            f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ Drive 錯誤: {e}")
        return None

def main():
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    if not gdrive_json or not session_id: return

    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)

    if not os.path.exists(PROGRESS_FILE):
        f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800}, locale="zh-TW")
        page = context.new_page()
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            print(f"🔎 處理 {folder['name']} / 第 {i_idx} 張")
            
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path:
                f_idx += 1; i_idx = 1; continue

            try:
                page.goto("https://www.threads.net/")
                time.sleep(15)
                
                # 強力點擊邏輯
                btn_selector = 'svg[aria-label*="建立"], div[role="button"]:has-text("建立")'
                page.wait_for_selector(btn_selector, timeout=30000)
                
                # 嘗試點擊直到輸入框出現
                for _ in range(3):
                    page.click(btn_selector, force=True)
                    time.sleep(5)
                    if page.locator('div[role="textbox"]').is_visible():
                        break
                
                page.wait_for_selector('div[role="textbox"]', timeout=20000)
                content = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {i_idx}"
                page.fill('div[role="textbox"]', content)
                
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label*="附加"]', force=True)
                fc_info.value.set_files(img_path)
                
                print("📤 上傳中...")
                time.sleep(20) 
                
                page.click('div[role="button"]:has-text("發佈")')
                print(f"🎉 成功發佈貼文！")

                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ 錯誤: {e}")
                page.screenshot(path="last_error.png")
                break
        browser.close()

if __name__ == "__main__":
    main()
