import os
import json
import time
import io
import re
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from playwright.sync_api import sync_playwright

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
        results = service.files().list(q=f"'{folder_id}' in parents and trashed = false", fields="files(id, name)", pageSize=1000).execute()
        items = sorted(results.get('files', []), key=lambda x: x['name'])
        if not items: return None
        first_name = items[0]['name']
        match = re.search(r'(\d+)', first_name)
        if not match: return None
        actual_num = int(match.group(1)) + (target_idx - 1)
        actual_pattern = f"{actual_num:04d}"
        target_id = next((i['id'] for i in items if actual_pattern in i['name']), None)
        if not target_id: return None
        request = service.files().get_media(fileId=target_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: _, done = downloader.next_chunk()
        with open("temp.jpg", "wb") as f: f.write(fh.getbuffer())
        return "temp.jpg"
    except: return None

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
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        context.add_cookies([{'name': 'sessionid', 'value': session_id, 'domain': '.threads.net', 'path': '/'}])
        
        for i in range(6):
            if f_idx >= len(FOLDER_LIST): break
            folder = FOLDER_LIST[f_idx]
            img_path = download_image(drive_service, folder['id'], i_idx)
            if not img_path: f_idx += 1; i_idx = 1; continue

            try:
                print(f"🌐 正在導向 Threads 發文頁面...")
                page.goto("https://www.threads.net/intent/post", wait_until="load", timeout=90000)
                time.sleep(20)
                
                # 點擊螢幕中央來確保焦點
                page.mouse.click(500, 500)
                time.sleep(2)

                # 嘗試自動點擊「繼續」按鈕（如果有）
                for btn_text in ["繼續", "Continue", "Log in", "登入"]:
                    btn = page.get_by_role("button", name=re.compile(btn_text, re.I))
                    if btn.is_visible():
                        print(f"👆 點擊了: {btn_text}")
                        btn.click()
                        time.sleep(10)

                # 如果 textbox 還是沒出現，嘗試用鍵盤呼叫
                if not page.locator('div[role="textbox"]').is_visible():
                    print("⌨️ 嘗試模擬鍵盤操作喚醒輸入框...")
                    page.keyboard.press("Tab")
                    time.sleep(2)

                page.wait_for_selector('div[role="textbox"]', timeout=40000)
                textbox = page.locator('div[role="textbox"]')
                
                # 計算時間
                mm, ss = divmod(i_idx, 60)
                caption = f"BanG Dream! It's MyGO!!!!! {folder['name']} - {mm:02d}:{ss:02d}"
                textbox.fill(caption)
                
                # 上傳圖片
                with page.expect_file_chooser() as fc_info:
                    # 使用多種可能標籤尋找媒體按鈕
                    media_btn = page.locator('svg[aria-label*="媒體"], svg[aria-label*="附加"], svg[aria-label*="Attach"]').first
                    media_btn.click(force=True)
                fc_info.value.set_files(img_path)
                
                print(f"📤 圖片已加入，準備發佈 {folder['name']} / {i_idx}...")
                time.sleep(15) 
                
                # 點擊發佈
                publish_btn = page.locator('div[role="button"]:has-text("發佈"), div[role="button"]:has-text("Post")').first
                publish_btn.click(force=True)
                
                # 等待完成
                time.sleep(15)
                print(f"🎉 成功發佈第 {i+1} 篇！")
                
                i_idx += 1
                with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx},{i_idx}")
                if i < 5: time.sleep(300)
            except Exception as e:
                print(f"❌ 發生錯誤: {e}")
                page.screenshot(path=f"error_snap_{i}.png")
                # 檢測是否被要求登入
                if "login" in page.url.lower():
                    print("🚨 警告：Session 已失效，請更新 THREADS_SESSION_ID Secret！")
                break
        browser.close()

if __name__ == "__main__": main()
