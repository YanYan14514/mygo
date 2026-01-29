import os
import json
import time
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 配置區 ---
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
        items = results.get('files', [])
        if not items: return None
        
        # 排序檔案
        items.sort(key=lambda x: x['name'])
        
        # 獲取起始編號 (例如 frame_3271 -> 提取出 3271)
        first_file_name = items[0]['name']
        match = re.search(r'(\d+)', first_file_name)
        if not match: return None
        
        start_num = int(match.group(1))
        # 計算當前應該抓取的實際編號
        actual_num = start_num + (target_idx - 1)
        actual_name_pattern = f"{actual_num:04d}" # 保持四位數格式

        target_id = None
        for item in items:
            if actual_name_pattern in item['name']:
                target_id = item['id']
                print(f"🎯 自動對齊編號！目標: {target_idx} -> 實際檔名: {item['name']}")
                break
        
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
        # 強制指定 User Agent 並關閉自動化偵測標記
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            
            if not img_path:
                print(f"⏭️ 找不到對應圖片，跳至下一集")
                f_idx += 1; i_idx = 1; continue

            try:
                # 增加隨機等待避免被偵測
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
                time.sleep(15)
                
                # 檢查是否需要點擊「繼續」
                login_btn = page.get_by_role("button", name=re.compile(r"繼續|Continue|登入|Log in", re.I)).first
                if login_btn.is_visible():
                    login_btn.click()
                    time.sleep(10)

                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                
                # 計算時間標籤 (假設 1 幀 = 1 秒)
                mm, ss = divmod(i_idx, 60)
                caption = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {mm:02d}:{ss:02d}"
                
                page.fill('div[role="textbox"]', caption)
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print(f"📤 正在發佈 {folder['name']} 第 {i_idx} 張...")
                time.sleep(20) 
                
                page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first.click()
                print(f"🎉 成功！")
                
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ Threads 錯誤: {e}")
                page.screenshot(path=f"error_{i}.png")
                break
        browser.close()

if __name__ == "__main__": main()
