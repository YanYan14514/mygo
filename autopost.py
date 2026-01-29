import os
import json
import time
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 集數列表 (請根據需要增減) ---
FOLDER_LIST = [
    {'name': 'Ep 1-3', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
    {'name': 'Ep 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    # ... 其他集數
]
PROGRESS_FILE = 'progress.txt'

def main():
    # 讀取並強制轉換為字串，避免 GitHub 傳入奇怪的格式
    session_id = str(os.getenv('THREADS_SESSION_ID', '')).strip()
    gdrive_json = os.getenv('GDRIVE_JSON')
    
    if not session_id or session_id == "None":
        print("❌ 錯誤：未找到 THREADS_SESSION_ID，請檢查 Secrets 設定")
        return
        # 尋找對應索引的圖片
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
    session_id = os.getenv('THREADS_SESSION_ID')
    gdrive_json = os.getenv('GDRIVE_JSON')
    
    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)
    
    # 讀取進度 
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: f_idx, i_idx = map(int, line.split(','))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        
        # 關鍵：直接注入 Cookie 繞過登入
        context.add_cookies([
            {'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}
        ])
        
        page = context.new_page()
        print("🌐 正在使用 Cookie 跳轉至發文頁面...")
        
        for i in range(3): # 每次執行發 3 張
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            
            if not img_path:
                f_idx += 1; i_idx = 1; continue

            try:
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle")
                time.sleep(5)
                
                # 檢查發文框是否存在
                textbox = page.locator('div[role="textbox"]')
                if not textbox.is_visible():
                    print("🚨 Cookie 可能失效，請更新 THREADS_SESSION_ID")
                    page.screenshot(path="cookie_invalid.png")
                    break

                # 填寫內容
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}")
                
                # 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                time.sleep(10) # 等待圖片上傳
                
                # 發佈
                page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first.click()
                time.sleep(10)
                
                print(f"🎉 成功發佈：{folder['name']} 第 {i_idx} 張")
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
            except Exception as e:
                print(f"❌ 執行出錯: {e}")
                break
        browser.close()

if __name__ == "__main__":
    main()

