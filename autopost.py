import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
# 請確保這些 Folder ID 與你的 Google Drive 網址對應
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
        query = f"'{folder_id}' in parents and name = '{filename}'"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])
        if not items:
            return None
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        local_path = "temp.jpg"
        with open(local_path, "wb") as f:
            f.write(fh.getbuffer())
        return local_path
    except Exception as e:
        print(f"❌ 下載圖片出錯: {e}")
        return None

def main():
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    
    if not gdrive_json or not session_id:
        print("❌ 缺少必要的 Secrets 設定 (GDRIVE_JSON 或 THREADS_SESSION_ID)")
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
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 720}, user_agent=user_agent, locale="zh-TW")
        page = context.new_page()

        print("🔑 Authorization: 嘗試使用 Session Cookie 登入...")
        context.add_cookies([{
            'name': 'sessionid', 'value': session_id, 'domain': '.threads.net',
            'path': '/', 'secure': True, 'httpOnly': True, 'sameSite': 'Lax'
        }])
        
        try:
            print("🌐 正在開啟 Threads 頁面...")
            page.goto("https://www.threads.net/", wait_until="domcontentloaded", timeout=90000)
            time.sleep(10) # 等待頁面渲染
            
            # 偵測登入狀態
            post_btn_selector = 'svg[aria-label*="建立"], svg[aria-label*="thread"], svg[aria-label="建立內容"]'
            if page.query_selector(post_btn_selector):
                print("✅ Cookie 登入成功！")
            else:
                print("⏳ 正在等待發文按鈕出現...")
                page.wait_for_selector(post_btn_selector, timeout=30000)
                print("✅ 找到按鈕，登入成功！")
        except Exception as e:
            print(f"❌ 登入階段異常: {e}")
            browser.close()
            return

        # --- 發文循環 (每次執行發 6 張) ---
        for i in range(6):
            if f_idx >= len(FOLDER_LIST):
                print("🏁 所有資料夾已處理完畢！")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"📸 正在搜尋: {folder['name']} / {filename}")
            
            img_path = download_image(drive_service, folder['id'], filename)

            if not img_path:
                print(f"⏭️ 找不到檔案 {filename}，嘗試跳轉到下一個資料夾")
                f_idx += 1
                i_idx = 1
                continue

            try:
                # 確保在首頁
                if page.url != "https://www.threads.net/":
                    page.goto("https://www.threads.net/")
                
                # 1. 點擊發文按鈕
                page.wait_for_selector(post_btn_selector, timeout=30000)
                page.click(post_btn_selector, force=True)
                
                # 2. 等待輸入框出現
                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                time.sleep(2)
                
                # 3. 準備內容
                mm, ss = divmod(i_idx, 60)
                ep_name = folder['name'].replace('mygo', '').replace('123_part1', '1').replace('123_part2', '1')
                content = f"BanG Dream! It's MyGO!!!!! 第 {ep_name} 集 {mm:02d}:{ss:02d}"
                
                # 4. 填寫文字與上傳圖片
                page.fill('div[role="textbox"]', content)
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label*="附加"], svg[aria-label*="Attach"]')
                fc_info.value.set_files(img_path)
                
                print(f"📤 圖片上傳中... ({content})")
                time.sleep(15) # 給予充足的上傳時間
                
                # 5. 點擊發佈
                post_confirm_selector = 'div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")'
                page.click(post_confirm_selector)
                
                print(f"🎉 成功發佈第 {i+1} 張圖片！")

                # 更新進度
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
                
                if i < 5:
                    print("⏳ 等待 600 秒後處理下一張...")
                    time.sleep(600)
                    
            except Exception as e:
                print(f"❌ 發文過程出錯: {e}")
                page.screenshot(path=f"error_step_{i}.png")
                break
                
        browser.close()

if __name__ == "__main__":
    main()
