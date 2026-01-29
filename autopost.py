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
    {'name': 'Ep 4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, target_idx):
    try:
        results = service.files().list(q=f"'{folder_id}' in parents and trashed = false", fields="files(id, name)", pageSize=1000).execute()
        items = sorted(results.get('files', []), key=lambda x: x['name'])
        target_name_part = f"{target_idx:04d}"
        target_id = next((i['id'] for i in items if target_name_part in i['name']), None)
        if not target_id: return None
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ 圖片下載失敗: {e}"); return None

def main():
    print("🎬 程式啟動...")
    s_id = str(os.getenv('THREADS_SESSION_ID', '')).strip()
    u_id = str(os.getenv('THREADS_USER_ID', '')).strip()
    c_tk = str(os.getenv('THREADS_CSRF_TOKEN', '')).strip()
    g_js = os.getenv('GDRIVE_JSON')

    if not all([s_id, u_id, c_tk]):
        print("❌ 錯誤：Cookie Secrets 不完整"); return

    creds = service_account.Credentials.from_service_account_info(json.loads(g_js))
    drive_service = build('drive', 'v3', credentials=creds)
    
    # 讀取目前進度
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: 
                parts = line.split(',')
                f_idx, i_idx = int(parts[0]), int(parts[1])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # 注入 Cookie 到所有相關網域
        for domain in [".threads.net", ".threads.com", "www.threads.net", "www.threads.com"]:
            context.add_cookies([
                {'name': 'sessionid', 'value': s_id, 'domain': domain, 'path': '/'},
                {'name': 'ds_user_id', 'value': u_id, 'domain': domain, 'path': '/'},
                {'name': 'csrftoken', 'value': c_tk, 'domain': domain, 'path': '/'}
            ])
        
        page = context.new_page()
        print(f"🌐 嘗試發佈：Episode {f_idx}, Frame {i_idx}")

        try:
            page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
            time.sleep(10)
            page.screenshot(path="1_after_load.png")

            if "login" in page.url:
                print(f"🚨 登入失效！目前網址: {page.url}"); return

            textbox = page.locator('div[role="textbox"]').first
            img_path = download_image(drive_service, FOLDER_LIST[f_idx]['id'], i_idx)
            
            if img_path:
                print("🖋️ 填寫內容與上傳圖片...")
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {FOLDER_LIST[f_idx]['name']} - Frame {i_idx}")
                
                with page.expect_file_chooser() as fc_info:
                    # 尋找媒體上傳按鈕
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"], svg[aria-label*="Attach"]').first.click()
                fc_info.value.set_files(img_path)
                
                time.sleep(15) # 等待圖片渲染
                page.screenshot(path="2_before_post.png")

                # 強力搜尋發佈按鈕
                post_btn = page.get_by_role("button", name="發佈").or_(page.get_by_role("button", name="Post"))
                
                if post_btn.is_enabled():
                    post_btn.click()
                    print("🚀 已點擊發佈，等待 10 秒...")
                    time.sleep(10)
                    page.screenshot(path="3_after_post.png")
                    
                    # 更新 progress.txt
                    new_i_idx = i_idx + 1
                    with open(PROGRESS_FILE, 'w') as f:
                        f.write(f"{f_idx},{new_i_idx}")
                    print(f"🎉 成功！進度已更新為 {f_idx},{new_i_idx}")
                else:
                    print("❌ 發佈按鈕處於禁用狀態")
            
        except Exception as e:
            print(f"❌ 發生異常: {e}")
            page.screenshot(path="error_log.png")
            
        browser.close()

if __name__ == "__main__":
    main()
