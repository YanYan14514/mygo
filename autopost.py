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
        target_name_part = f"{target_idx:04d}"
        target_id = next((i['id'] for i in items if target_name_part in i['name']), None)
        if not target_id: return None
        
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ 圖片下載失敗: {e}")
        return None

def main():
    # 強制從環境變數讀取三個關鍵 Cookie
    session_id = str(os.getenv('THREADS_SESSION_ID', '')).strip()
    user_id = str(os.getenv('THREADS_USER_ID', '')).strip()
    csrf_token = str(os.getenv('THREADS_CSRF_TOKEN', '')).strip()
    gdrive_json = os.getenv('GDRIVE_JSON')
    
    if not all([session_id, user_id, csrf_token]):
        print("❌ 錯誤：Cookie 資訊不完整 (THREADS_SESSION_ID, THREADS_USER_ID, THREADS_CSRF_TOKEN)")
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
        # 設定更接近真人的 User-Agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        # 注入完整身分資訊
        context.add_cookies([
            {'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'},
            {'name': 'ds_user_id', 'value': user_id, 'domain': '.threads.net', 'path': '/'},
            {'name': 'csrftoken', 'value': csrf_token, 'domain': '.threads.net', 'path': '/'}
        ])
        
        page = context.new_page()
        
        for i in range(3):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            
            if not img_path:
                f_idx += 1; i_idx = 1; continue

            try:
                print(f"🌐 前往發文頁面: {folder['name']} - {i_idx}")
                # 使用直接導向發文介面的網址
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle")
                time.sleep(10)
                
                # 偵測是否被攔截到登入頁
                if "login" in page.url:
                    print("🚨 Cookie 已失效，頁面被導向至登入頁。")
                    page.screenshot(path=f"login_intercepted_{i}.png")
                    break
                
                textbox = page.locator('div[role="textbox"]')
                if not textbox.is_visible():
                    print("🚨 找不到發文框，嘗試重新載入...")
                    page.screenshot(path=f"missing_textbox_{i}.png")
                    break

                textbox.fill(f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}")
                
                # 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    # 嘗試多種可能的媒體按鈕選擇器
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"], svg[aria-label*="Attach"]').first.click()
                fc_info.value.set_files(img_path)
                
                print(f"📤 圖片上傳中...")
                time.sleep(15) 
                
                # 尋找發佈按鈕
                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                if post_btn.is_enabled():
                    post_btn.click()
                    print(f"🎉 成功點擊發佈！")
                    time.sleep(10)
                    
                    # 更新進度
                    i_idx += 1
                    with open(PROGRESS_FILE, 'w') as f:
                        f.write(f"{f_idx},{i_idx}")
                else:
                    print("❌ 發佈按鈕尚未就緒 (不可點擊)")
                    page.screenshot(path=f"post_btn_disabled_{i}.png")
                    break
            except Exception as e:
                print(f"❌ 出錯: {e}")
                page.screenshot(path=f"error_step_{i}.png")
                break
        browser.close()

if __name__ == "__main__":
    main()
