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
    {'name': 'mygo123_part1', 'id': '1ej8KQ7dV5Vi2DvpJ0rw-Bv17T3DTisma'},
    {'name': 'mygo123_part2', 'id': '1Ba2FHg9U4CCp5ZRloeObj3w9k0B0FN_m'},
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
        if not items: return None
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
        print(f"下載圖片出錯: {e}")
        return None

def main():
    # 讀取 Secrets
    gdrive_json = os.getenv('GDRIVE_JSON')
    session_id = os.getenv('THREADS_SESSION_ID')
    
    if not gdrive_json or not session_id:
        print("❌ 缺少必要的 Secrets 設定 (GDRIVE_JSON 或 THREADS_SESSION_ID)")
        return

    creds = service_account.Credentials.from_service_account_info(json.loads(gdrive_json))
    drive_service = build('drive', 'v3', credentials=creds)

    # 讀取初始進度
    if not os.path.exists(PROGRESS_FILE):
        f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            line = f.read().strip()
            f_idx, i_idx = map(int, line.split(',')) if line else (0, 1)

    with sync_playwright() as p:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent=user_agent,
            locale="zh-TW"
        )
        page = context.new_page()

        # --- 使用 Cookie 登入 ---
        print("🔑 Authorization: 使用 Session Cookie...")
        context.add_cookies([{
            'name': 'sessionid',
            'value': session_id,
            'domain': '.threads.net',
            'path': '/',
            'secure': True,
            'httpOnly': True,
            'sameSite': 'Lax'
        }])
        
        try:
            page.goto("https://www.threads.net/", wait_until="networkidle")
            time.sleep(5) 
            if not page.query_selector('svg[aria-label="建立內容"]'):
                print("❌ Cookie 登入失敗，請檢查 THREADS_SESSION_ID 是否過期")
                return
            print("✅ Cookie 登入成功！")
        except Exception as e:
            print(f"❌ 登入過程發生異常: {e}")
            return

        # --- 發文循環 (一次運行發 6 張) ---
        for i in range(6):
            if f_idx >= len(FOLDER_LIST):
                print("🏁 全劇終！")
                break

            folder = FOLDER_LIST[f_idx]
            filename = f"frame_{i_idx:04d}.jpg"
            print(f"📸 準備下載: {folder['name']} / {filename}")
            img_path = download_image(drive_service, folder['id'], filename)

            if not img_path:
                print(f"⏭️ 找不到檔案 {filename}，跳轉至下一集第一張")
                f_idx += 1
                i_idx = 1
                continue

            try:
                # 重新回到首頁確保按鈕存在
                page.goto("https://www.threads.net/")
                page.wait_for_selector('svg[aria-label="建立內容"]', timeout=30000)
                page.click('svg[aria-label="建立內容"]')
                page.wait_for_selector('div[role="textbox"]')
                
                # 時間與文案換算
                mm, ss = divmod(i_idx, 60)
                ep_num = folder['name'].replace('mygo', '').replace('123_part1', '1').replace('123_part2', '1')
                content = f"BanG Dream! It's MyGO!!!!! 第 {ep_num} 集 {mm:02d}:{ss:02d}"
                
                page.keyboard.type(content)
                with page.expect_file_chooser() as fc_info:
                    page.click('svg[aria-label="附加媒體"]')
                fc_info.value.set_files(img_path)
                
                time.sleep(7) # 增加等待圖片載入的時間
                page.click('div[role="button"]:has-text("發佈")')
                print(f"✅ 已成功發佈 ({i+1}/6): {content}")

                # 更新進度變數
                i_idx += 1
                
                # 立即將進度寫入本地檔案 (為了最後 commit 回去)
                with open(PROGRESS_FILE, 'w') as f:
                    f.write(f"{f_idx},{i_idx}")
                
                if i < 5:
                    print("⏳ 等待 600 秒發送下一張...")
                    time.sleep(600)
                    
            except Exception as e:
                print(f"❌ 發文過程出錯: {e}")
                break
                
        browser.close()

if __name__ == "__main__":
    main()
