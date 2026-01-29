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
    {'name': 'mygo123', 'id': '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'},
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

def download_image(service, folder_id, target_filename):
    """強力下載版：列出所有檔案並手動比對"""
    try:
        # 獲取該資料夾下所有檔案列表
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=1000
        ).execute()
        items = results.get('files', [])
        
        if not items:
            print(f"⚠️ 資料夾內空無一物 (ID: {folder_id})")
            return None

        # 比對檔名 (不分大小寫，包含即可)
        target_file_id = None
        for item in items:
            if target_filename.lower() in item['name'].lower():
                target_file_id = item['id']
                print(f"✅ 找到匹配檔案: {item['name']} (ID: {target_file_id})")
                break
        
        if not target_file_id:
            return None

        # 下載檔案
        request = service.files().get_media(fileId=target_file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        with open("temp.jpg", "wb") as f:
            f.write(fh.getbuffer())
        return "temp.jpg"

    except Exception as e:
        print(f"❌ Google Drive 存取錯誤: {e}")
        return None

def main():
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    if not gdrive_json or not session_id:
        print("❌ Secrets 缺失")
        return

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
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()

        print("🔑 設定 Threads Session...")
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"🔍 正在嘗試從 {folder['name']} 下載 {filename}...")
            
            img_path = download_image(drive_service, folder['id'], filename)
            
            if not img_path:
                print(f"⏭️ 找不到檔案，跳下一集資料夾")
                f_idx += 1; i_idx = 1
                continue

            try:
                page.goto("https://www.threads.net/")
                time.sleep(10)
                
                # 點擊建立按鈕
                create_selector = 'svg[aria-label*="建立"], svg[aria-label*="thread"], div[role="button"]:has-text("建立")'
                page.wait_for_selector(create_selector, timeout=30000)
                page.click(create_selector, force=True)
                
                # 等待輸入框
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                time.sleep(3)

                # 設定文案
                mm, ss = divmod(i_idx, 60)
                content = f"BanG Dream! It's MyGO!!!!! 第 {f_idx + 1} 集 {mm:02d}:{ss:02d}"
                page.fill('div[role="textbox"]', content)
                
                # 點擊附加媒體
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label*="附加"], svg[aria-label*="Attach"]', force=True)
                fc_info.value.set_files(img_path)
                
                print("📤 上傳圖片中...")
                time.sleep(20) 
                
                # 點擊發佈
                post_confirm = 'div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")'
                page.click(post_confirm)
                print(f"🎉 成功發佈第 {i+1} 篇貼文！")

                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
                
                if i < 5:
                    print("⏳ 間隔冷卻 600 秒...")
                    time.sleep(600)
            except Exception as e:
                print(f"❌ Threads 發文失敗: {e}")
                page.screenshot(path=f"error_post_{i}.png")
                break
                
        browser.close()

if __name__ == "__main__":
    main()
