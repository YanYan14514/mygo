import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
# 這裡只認 ID，前面的 name 只是給你看日誌用的
FOLDER_LIST = [
    {'name': 'Episode 1', 'id': '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'},
    {'name': 'Episode 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    {'name': 'Episode 5', 'id': '1NW98O1i6EkO_SlZWqLtNBO78N-vveugw'},
    {'name': 'Episode 6', 'id': '1F6vmpH2PCZ-H8qQ1OGxFDqEJBmS_zJ9k'},
    {'name': 'Episode 7', 'id': '11-IHOKWb4PR9aCxJtieJxgCfQ3OTh5H7'},
    {'name': 'Episode 8', 'id': '1IJtDejmjTNVFOEFyCumvDzWgCND-HQmA'},
    {'name': 'Episode 9', 'id': '14keTQu3tqM3qSYcECLd3ub3MzTP6LC5F'},
    {'name': 'Episode 10', 'id': '11LK0p3lr8S_Gn_ZLiSIOjaI5gSoNAnCZ'},
    {'name': 'Episode 11', 'id': '1RVE45ulNjLMZ9iypOUzZZDUnAUKavkQK'},
    {'name': 'Episode 12', 'id': '1CHTpS_abB6SsLcgQBCMtLhKnKgMbLjgd'},
    {'name': 'Episode 13', 'id': '1cVtofiJZDEbhNlNhtHcg0DOEO6nPsCPf'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, filename):
    """強力下載：只認 ID 與檔案名稱，不分大小寫"""
    try:
        # 列出該 ID 資料夾下的所有內容
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)"
        ).execute()
        items = results.get('files', [])
        
        target_id = None
        for item in items:
            # 去掉空格後比對檔名
            if filename.lower().replace(" ", "") in item['name'].lower().replace(" ", ""):
                target_id = item['id']
                print(f"✅ 成功找到檔案: {item['name']}")
                break
        
        if not target_id:
            return None

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
        print(f"❌ Drive API 錯誤: {e}")
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

        print("🔑 注入 Session...")
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"📸 正在讀取 {folder['name']} 的 {filename}...")
            
            img_path = download_image(drive_service, folder['id'], filename)
            
            if not img_path:
                print(f"⏭️ 在 ID [{folder['id']}] 中找不到 {filename}，跳轉下一集")
                f_idx += 1; i_idx = 1; continue

            try:
                page.goto("https://www.threads.net/")
                time.sleep(15)
                
                # 點擊建立按鈕
                btn = page.locator('svg[aria-label*="建立"], svg[aria-label*="thread"], div[role="button"]:has-text("建立")').first
                btn.click(force=True)
                
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                
                mm, ss = divmod(i_idx, 60)
                content = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {mm:02d}:{ss:02d}"
                page.fill('div[role="textbox"]', content)
                
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label*="附加"], svg[aria-label*="Attach"]', force=True)
                fc_info.value.set_files(img_path)
                
                print("📤 發佈中...")
                time.sleep(20) 
                
                page.click('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")')
                print(f"🎉 成功發佈 ({i+1}/6)")

                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ 發文異常: {e}")
                break
        browser.close()

if __name__ == "__main__":
    main()
