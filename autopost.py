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
        target_id = None
        target_name = f"frame_{target_idx:04d}"
        for item in items:
            if target_name in item['name']:
                target_id = item['id']
                print(f"🎯 找到指定檔案: {item['name']}")
                break
        if not target_id and target_idx == 1:
            target_id = items[0]['id']
            print(f"⚠️ 找不到 0001，抓取首個: {items[0]['name']}")
        if not target_id: return None
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ Drive 錯誤: {e}"); return None

def main():
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    if not gdrive_json or not session_id: return
    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)
    if not os.path.exists(PROGRESS_FILE): f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 模擬更真實的視窗大小
        context = browser.new_context(viewport={'width': 1920, 'height': 1080}, locale="zh-TW")
        page = context.new_page()
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            print(f"🔎 處理 {folder['name']} / 第 {i_idx} 張")
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: f_idx += 1; i_idx = 1; continue

            try:
                # 關鍵改動：直接進入發文意圖頁面
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
                time.sleep(10)
                
                # 檢測輸入框是否存在 (intent 頁面的輸入框通常更易抓取)
                textbox = page.locator('div[role="textbox"]')
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                
                mm, ss = divmod(i_idx, 60)
                content = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {i_idx}"
                textbox.fill(content)
                print(f"✍️ 已填寫文案")
                
                # 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    # intent 頁面的附加按鈕可能不同，使用模糊搜尋
                    page.locator('svg[aria-label*="附加"], svg[aria-label*="Attach"], svg[aria-label*="媒體"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 上傳圖片中...")
                time.sleep(20) 
                
                # 發佈
                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                post_btn.click()
                
                # 等待發佈成功的跳轉或消失
                time.sleep(10)
                print(f"🎉 成功發佈貼文！")

                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: 
                    print("⏳ 冷卻中...")
                    time.sleep(600)
            except Exception as e:
                print(f"❌ 錯誤: {e}")
                page.screenshot(path=f"error_step_{i}.png")
                break
        browser.close()

if __name__ == "__main__": main()
