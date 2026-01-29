import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
# 這裡的名字改為跟你的雲端硬碟完全一致 (大小寫要注意)
FOLDER_LIST = [
    {'name': 'MyGo123', 'id': '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'},
    {'name': 'Mygo4', 'id': '1TyKoUKlsuARHQ59gViPU4H9SKT2JbERD'},
    {'name': 'Mygo5', 'id': '1NW98O1i6EkO_SlZWqLtNBO78N-vveugw'},
    {'name': 'Mygo6', 'id': '1F6vmpH2PCZ-H8qQ1OGxFDqEJBmS_zJ9k'},
    {'name': 'Mygo7', 'id': '11-IHOKWb4PR9aCxJtieJxgCfQ3OTh5H7'},
    {'name': 'Mygo8', 'id': '1IJtDejmjTNVFOEFyCumvDzWgCND-HQmA'},
    {'name': 'Mygo9', 'id': '14keTQu3tqM3qSYcECLd3ub3MzTP6LC5F'},
    {'name': 'Mygo10', 'id': '11LK0p3lr8S_Gn_ZLiSIOjaI5gSoNAnCZ'},
    {'name': 'Mygo11', 'id': '1RVE45ulNjLMZ9iypOUzZZDUnAUKavkQK'},
    {'name': 'Mygo12', 'id': '1CHTpS_abB6SsLcgQBCMtLhKnKgMbLjgd'},
    {'name': 'Mygo13', 'id': '1cVtofiJZDEbhNlNhtHcg0DOEO6nPsCPf'}
]
PROGRESS_FILE = 'progress.txt'

def download_image(service, folder_id, filename):
    """強力下載邏輯：不依賴 API 搜尋，直接列出檔案比對"""
    try:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)"
        ).execute()
        items = results.get('files', [])
        
        target_id = None
        for item in items:
            # 只要檔名（不分大小寫）包含 frame_0001 這種關鍵字就抓
            if filename.lower() in item['name'].lower():
                target_id = item['id']
                print(f"✅ 找到匹配檔案: {item['name']}")
                break
        
        if not target_id:
            return None

        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        local_path = "temp.jpg"
        with open(local_path, "wb") as f:
            f.write(fh.getbuffer())
        return local_path
    except Exception as e:
        print(f"❌ Google Drive 下載出錯: {e}")
        return None

def main():
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    
    if not gdrive_json or not session_id:
        print("❌ 缺少 Secrets 設定")
        return

    # 初始化 Google Drive
    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)

    # 讀取進度
    if not os.path.exists(PROGRESS_FILE):
        f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 設定繁體中文與視窗大小
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            locale="zh-TW",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("🔑 登入 Threads...")
        context.add_cookies([{
            'name': 'sessionid', 'value': session_id, 'domain': '.threads.net',
            'path': '/', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'
        }])
        
        # 循環發佈 (預設一次 6 張)
        for i in range(6):
            if f_idx >= len(FOLDER_LIST):
                print("🏁 所有資料夾已處理完畢")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"📸 準備處理: {folder['name']} 第 {i_idx} 張圖")
            
            img_path = download_image(drive_service, folder['id'], filename)
            
            if not img_path:
                print(f"⏭️ 找不到檔案 {filename}，跳轉至下一資料夾")
                f_idx += 1
                i_idx = 1
                continue

            try:
                page.goto("https://www.threads.net/", wait_until="networkidle", timeout=60000)
                time.sleep(10) # 緩衝加載
                
                # 1. 偵測發文按鈕
                post_btn_selector = 'svg[aria-label*="建立"], svg[aria-label*="thread"], div[role="button"]:has-text("建立")'
                page.wait_for_selector(post_btn_selector, timeout=30000)
                page.click(post_btn_selector, force=True)
                
                # 2. 等待並填寫文字
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                time.sleep(2)
                
                mm, ss = divmod(i_idx, 60)
                content = f"BanG Dream! It's MyGO!!!!! 第 {f_idx + 1} 集 {mm:02d}:{ss:02d}"
                page.fill('div[role="textbox"]', content)
                
                # 3. 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label*="附加"], svg[aria-label*="Attach"]', force=True)
                fc_info.value.set_files(img_path)
                
                print("📤 圖片上傳中...")
                time.sleep(15) # 確保上傳完畢
                
                # 4. 發佈貼文
                publish_btn = 'div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")'
                page.click(publish_btn)
                
                print(f"🎉 成功發佈貼文 ({i+1}/6)！")

                # 更新進度並寫入檔案
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
                
                if i < 5:
                    print("⏳ 間隔冷卻 600 秒...")
                    time.sleep(600)
                    
            except Exception as e:
                print(f"❌ 發文過程出錯: {e}")
                page.screenshot(path=f"error_report_{i}.png")
                break
                
        browser.close()

if __name__ == "__main__":
    main()
