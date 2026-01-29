import os
import json
import time
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

# --- 完整配置區 ---
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
        # 1. 獲取檔案清單並排序
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="files(id, name)",
            pageSize=1000
        ).execute()
        items = results.get('files', [])
        
        if not items:
            print(f"❌ 資料夾是空的 (ID: {folder_id})")
            return None

        # --- 診斷：印出前 10 個檔名 ---
        items.sort(key=lambda x: x['name'])
        print(f"📁 診斷資料夾: 總共 {len(items)} 個檔案")
        print(f"📋 檔名前 10 名: {[i['name'] for i in items[:10]]}")

        # 2. 多重格式匹配
        target_patterns = [
            f"frame_{target_idx:04d}", 
            f"frame_{target_idx}.", 
            f"_{target_idx:04d}.",
            f"img_{target_idx:04d}"
        ]
        
        target_id = None
        for item in items:
            name_lower = item['name'].lower()
            if any(p.lower() in name_lower for p in target_patterns):
                target_id = item['id']
                print(f"🎯 匹配成功: {item['name']}")
                break
        
        # 3. 如果找不到特定序號，且是剛開始，抓排序後第一個
        if not target_id and target_idx == 1:
            target_id = items[0]['id']
            print(f"⚠️ 找不到對應編號，改抓資料夾內第一個檔案: {items[0]['name']}")

        if not target_id: return None

        # 4. 下載
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except Exception as e:
        print(f"❌ Drive 下載錯誤: {e}"); return None

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
            print(f"🚀 正在處理: {folder['name']} / 進度: 第 {i_idx} 張圖")
            
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path:
                print("⏭️ 找不到檔案，跳集")
                f_idx += 1; i_idx = 1; continue

            try:
                # 模擬真人流程：首頁 -> 發文頁
                page.goto("https://www.threads.net/", wait_until="networkidle", timeout=60000)
                time.sleep(5)
                page.goto("https://www.threads.net/intent/post", wait_until="networkidle", timeout=60000)
                time.sleep(12)
                
                # 若沒出現輸入框，嘗試截圖診斷
                if not page.locator('div[role="textbox"]').is_visible():
                    page.screenshot(path=f"blocked_notice_{i}.png")
                    print("🕵️ 頁面未就緒，嘗試點擊潛在彈窗...")
                    for txt in ["繼續", "同意", "確定"]:
                        btn = page.get_by_role("button", name=txt)
                        if btn.is_visible(): btn.click(); time.sleep(5)

                page.wait_for_selector('div[role="textbox"]', timeout=30000)
                textbox = page.locator('div[role="textbox"]')
                textbox.fill(f"BanG Dream! It's MyGO!!!!! {folder['name']} - Frame {i_idx}")
                
                with page.expect_file_chooser() as fc_info:
                    page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"]').first.click()
                fc_info.value.set_files(img_path)
                
                print("📤 圖片上傳中...")
                time.sleep(20) 
                
                page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first.click()
                print(f"🎉 成功發佈！")
                
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(600)
            except Exception as e:
                print(f"❌ Threads 錯誤: {e}")
                page.screenshot(path=f"final_error_{i}.png")
                break
        browser.close()

if __name__ == "__main__": main()
