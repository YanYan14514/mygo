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
    {'name': 'mygo123', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
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
    try:
        # 直接搜尋該資料夾下所有檔案，列出來比對，避開精確搜尋失敗
        results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
        items = results.get('files', [])
        for item in items:
            if filename in item['name']: # 只要檔名包含 frame_0001 就抓
                file_id = item['id']
                request = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                with open("temp.jpg", "wb") as f:
                    f.write(fh.getbuffer())
                return "temp.jpg"
        return None
    except Exception as e:
        print(f"❌ 下載出錯: {e}")
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
        context = browser.new_context(viewport={'width': 1280, 'height': 900}, locale="zh-TW")
        page = context.new_page()

        print("🔑 設定 Session...")
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"🔍 尋找檔案: {folder['name']} / {filename}")
            
            img_path = download_image(drive_service, folder['id'], filename)
            if not img_path:
                print("⏭️ 找不到檔案，跳集")
                f_idx += 1; i_idx = 1; continue

            try:
                page.goto("https://www.threads.net/", wait_until="networkidle")
                time.sleep(8)
                
                # 改用更暴力的 selector 找按鈕
                create_btn = page.locator('div[role="button"]').filter(has_text="建立").first
                if not create_btn.is_visible():
                    create_btn = page.locator('svg[aria-label*="建立"]').first
                
                create_btn.click()
                print("🖱️ 已點擊建立按鈕")
                
                # 等待輸入框出現 (加長到 30 秒)
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                time.sleep(3)

                mm, ss = divmod(i_idx, 60)
                content = f"BanG Dream! It's MyGO!!!!! 第 {f_idx+1} 集 {mm:02d}:{ss:02d}"
                page.fill('div[role="textbox"]', content)
                
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 上傳中...")
                time.sleep(20) 
                
                page.locator('div[role="button"]').filter(has_text="發佈").first.click()
                print(f"🎉 成功發佈 ({i+1}/6)")

                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ 發文異常: {e}")
                page.screenshot(path=f"error_{i}.png")
                break
        browser.close()

if __name__ == "__main__":
    main()
