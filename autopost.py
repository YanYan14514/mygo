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
    
    f_idx, i_idx = (0, 1)
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            if line: f_idx, i_idx = map(int, line.split(','))

    with sync_playwright() as p:
        # 使用真實瀏覽器參數
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        
        # 強制注入 Cookie 到所有可能的網域
        for domain in [".threads.net", "www.threads.net", ".threads.com", "www.threads.com"]:
            context.add_cookies([
                {'name': 'sessionid', 'value': s_id, 'domain': domain, 'path': '/'},
                {'name': 'ds_user_id', 'value': u_id, 'domain': domain, 'path': '/'},
                {'name': 'csrftoken', 'value': c_tk, 'domain': domain, 'path': '/'}
            ])
        
        page = context.new_page()
        print(f"🌐 準備發佈：Episode {f_idx}, Frame {i_idx}")

        try:
            # 前往發文介面
            page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
            time.sleep(8)
            page.screenshot(path="1_after_load.png")

            if "login" in page.url:
                print(f"🚨 登入失效！頁面停留在: {page.url}")
                return

            # 嘗試定位發文框 (Threads 可能有多種結構)
            textbox = page.locator('div[role="textbox"]').first
            if not textbox.is_visible():
                print("⚠️ 未直接看到發文框，嘗試點擊起始按鈕...")
                page.click('text="什麼新新鮮事？"', timeout=5000) # 繁體中文適配
                time.sleep(2)

            img_path = download_image(drive_service, FOLDER_LIST[f_idx]['id'], i_idx)
            if img_path:
                print("🖋️ 填寫內文...")
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {FOLDER_LIST[f_idx]['name']} - Frame {i_idx} #MyGO")
                
                print("🖼️ 上傳圖片...")
                # 這裡改用更穩定的選擇器
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="Attach"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                time.sleep(12) # 等待圖片處理
                page.screenshot(path="2_before_post.png")

                # 點擊發佈
                post_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                if post_btn.is_enabled():
                    post_btn.click()
                    print("🚀 已點擊發佈按鈕，等待回應...")
                    time.sleep(10)
                    page.screenshot(path="3_after_post.png")
                    
                    # 成功後更新進度
                    with open(PROGRESS_FILE, 'w') as f:
                        f.write(f"{f_idx},{i_idx+1}")
                    print(f"🎉 任務完成！下一張：{i_idx+1}")
                else:
                    print("❌ 發佈按鈕無法點擊（可能是圖片還沒傳完）")
            
        except Exception as e:
            print(f"❌ 執行異常: {e}")
            page.screenshot(path="error_fatal.png")
            
        browser.close()

if __name__ == "__main__":
    main()
