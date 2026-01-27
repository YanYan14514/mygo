import os
import json
import requests
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- [1] 配置區：資料夾清單 ---
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

# --- [2] 載入環境變數 (GitHub Secrets) ---
def get_env_secrets():
    return {
        'gdrive_json': json.loads(os.getenv('GDRIVE_JSON')),
        'threads_token': os.getenv('THREADS_TOKEN'),
        'threads_user_id': os.getenv('THREADS_USER_ID')
    }

def main():
    secrets = get_env_secrets()
    
    # 讀取進度 (資料夾索引, 圖片編號)
    if not os.path.exists(PROGRESS_FILE):
        f_idx, i_idx = 0, 1
    else:
        with open(PROGRESS_FILE, 'r') as f:
            f_idx, i_idx = map(int, f.read().strip().split(','))

    if f_idx >= len(FOLDER_LIST):
        print("🎉 全劇終，太棒了！")
        return

    current_folder = FOLDER_LIST[f_idx]
    filename = f"frame_{i_idx:04d}.jpg"

    # --- [3] Google Drive 找圖 ---
    creds = service_account.Credentials.from_service_account_info(
        secrets['gdrive_json'], scopes=['https://www.googleapis.com/auth/drive.readonly'])
    service = build('drive', 'v3', credentials=creds)

    query = f"'{current_folder['id']}' in parents and name = '{filename}'"
    results = service.files().list(q=query, fields="files(id)").execute()
    items = results.get('files', [])

    if not items:
        print(f"⏭️ {current_folder['name']} 播完或找不到 {filename}，跳下一集")
        with open(PROGRESS_FILE, 'w') as f: f.write(f"{f_idx + 1},1")
        return

    file_id = items[0]['id']
    # 這是直接下載網址，Threads 伺服器會來這裡抓圖
    image_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    # --- [4] Threads API 發布 ---
    print(f"🚀 正在發送：{current_folder['name']} - {filename}")
    
    # 第一步：建立媒體容器
    base_url = "https://graph.threads.net/v1.0"
    create_url = f"{base_url}/{secrets['threads_user_id']}/threads"
    
    payload = {
        'media_type': 'IMAGE',
        'image_url': image_url,
        'text': f"MyGO!!!!! {current_folder['name']} \nFrame: {i_idx}", # 這裡可以自訂文字
        'access_token': secrets['threads_token']
    }
    
    res = requests.post(create_url, data=payload).json()
    
    if 'id' in res:
        creation_id = res['id']
        # 第二步：正式發布 (等一下讓伺服器抓圖)
        time.sleep(10) 
        publish_url = f"{base_url}/{secrets['threads_user_id']}/threads_publish"
        publish
