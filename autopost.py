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
    print("🎬 程式啟動...")
    s_id = str(os.getenv('THREADS_SESSION_ID', '')).strip()
    u_id = str(os.getenv('THREADS_USER_ID', '')).strip()
    c_tk = str(os.getenv('THREADS_CSRF_TOKEN', '')).strip()
    g_js = os.getenv('GDRIVE_JSON')

    if not all([s_id, u_id, c_tk]):
        print("❌ 錯誤：Cookie Secrets 不完整")
        return

    creds = service_account.Credentials.from_service_account_info(json.loads(g_js))
    drive_service = build('drive', 'v3', credentials=creds)
    
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: f_idx, i_idx = map(int, line.split(','))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        
        # 關鍵修正：同時注入 .net 和 .com
        for domain in [".threads.net", ".threads.com"]:
            context.add_cookies([
                {'name': 'sessionid', 'value': s_id, 'domain': domain, 'path': '/'},
                {'name': 'ds_user_id', 'value': u_id, 'domain': domain, 'path': '/'},
                {'name': 'csrftoken', 'value': c_tk, 'domain': domain, 'path': '/'}
            ])
        
        page = context.new_page()
        print(f"🌐 準備發佈：Folder {f_idx}, Image {i_idx}")

        try:
            # 前往 .net 的發文頁面，因為目前大部分導向還是從這開始
            page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
            time.sleep(10)
            page.screenshot(path="after_load.png")

            textbox = page.locator('div[role="textbox"]')
            if not textbox.is_visible():
                print(f"🚨 登入無效，目前網址: {page.url}")
                return

            img_path = download_image(drive_service, FOLDER_LIST[f_idx]['id'], i_idx)
            if img_path:
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {FOLDER_LIST[f_idx]['name']} - Frame {i_idx}")
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 上傳中...")
                time.sleep(15)
                
                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                if post_btn.is_enabled():
                    post_btn.click()
                    time.sleep(10)
                    print(f"🎉 成功！進度更新為 {f_idx},{i_idx+1}")
                    with open(PROGRESS_FILE, 'w') as f:
                        f.write(f"{f_idx},{i_idx+1}")
                else:
                    print("❌ 按鈕無法點擊")
            
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")
            page.screenshot(path="error.png")
            
        browser.close()

if __name__ == "__main__":
    main()
