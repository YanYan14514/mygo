import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 完整配置區 ---
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
                target_id = item['id']; break
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
        # 使用更擬真的 User Agent
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1024},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            print(f"🚀 處理集數: {folder['name']} / 第 {i_idx} 張")
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: f_idx += 1; i_idx = 1; continue

            try:
                # 1. 進入頁面
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
                time.sleep(15) # 給予極長等待
                
                # 2. 自動處理「登入/切換帳號」攔截框 (如果有出現的話)
                login_interceptor = page.locator('div[role="button"]:has-text("繼續"), div[role="button"]:has-text("登入")').first
                if login_interceptor.is_visible():
                    print("🛡️ 偵測到登入確認框，嘗試跳過...")
                    login_interceptor.click()
                    time.sleep(10)

                # 3. 等待輸入框 (改用更穩定的 locator)
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                textbox = page.locator('div[role="textbox"]')
                content = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {i_idx}"
                textbox.fill(content)
                
                # 4. 上傳
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 上傳中...")
                time.sleep(20) 
                
                # 5. 發佈
                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                post_btn.click()
                
                print(f"🎉 成功發佈 ({i+1}/6)")
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ Threads 錯誤: {e}")
                # 儲存錯誤截圖以便除錯
                page.screenshot(path=f"debug_screen_{i}.png")
                # 如果是 Session 過期，就沒必要繼續試下一張了
                if "timeout" in str(e).lower():
                    print("💡 建議：請檢查你的 THREADS_SESSION_ID 是否需要更新。")
                break
        browser.close()

if __name__ == "__main__": main()
