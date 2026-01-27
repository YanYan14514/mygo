import os
import requests

# 從環境變數抓取金鑰
TOKEN = os.getenv("THREADS_TOKEN")
USER_ID = os.getenv("THREADS_USER_ID")
PROGRESS_FILE = "progress.txt"
IMAGE_FOLDER = "mygo1" # 你的圖片資料夾

def post_to_threads():
    # 1. 讀取進度
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "w") as f: f.write("1")
        current_index = 1
    else:
        with open(PROGRESS_FILE, "r") as f:
            current_index = int(f.read().strip())

    # 2. 組合檔名 (假設你的檔名是 frame_0001.jpg, frame_0002.jpg...)
    img_name = f"frame_{current_index:04d}.jpg"
    img_path = os.path.join(IMAGE_FOLDER, img_name)


    # 3. 取得圖片在 GitHub 上的網址 (這步是 Threads API 要求的)
    # 請把下面的 "你的帳號" 和 "你的Repo" 改掉
    github_raw_url = f"https://raw.githubusercontent.com/你的帳號/你的Repo/main/{IMAGE_FOLDER}/{img_name}"

    print(f"🎬 正在發布第 {current_index} 張圖：{img_name}")

    # --- 呼叫 Threads API (這部分需要你的 Token 才能動) ---
    # (此處省略 API 實作，邏輯跟之前一樣)
    # ---------------------------------------------------

    # 4. 成功後，更新進度
    with open(PROGRESS_FILE, "w") as f:
        f.write(str(current_index + 1))
    print(f"✅ 已將進度更新為 {current_index + 1}")

if __name__ == "__main__":
    post_to_threads()