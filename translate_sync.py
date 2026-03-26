import os
import json
import time
import random
import re
import subprocess  # 导入子进程模块用于执行 git 命令
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from googletrans import Translator

# ================= 配置区 =================
FOLDER_ID = '1aWo5knX19YKecj88BYNQis4scqv9jKs9'
MAX_CHARS = 2500 
# ==========================================

def git_push_file(filename, title):
    """每翻译完一章，执行一次 git 提交和推送"""
    try:
        # 1. 添加文件到暂存区
        subprocess.run(["git", "add", filename], check=True)
        
        # 2. 检查是否有变化需要提交
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            print(f"内无变化，跳过提交: {filename}")
            return

        # 3. 提交
        commit_msg = f"Auto-translate: {title}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        # 4. 推送前拉取，防止多个 action 同时跑导致冲突
        subprocess.run(["git", "pull", "origin", "main", "--rebase"], check=True)
        
        # 5. 推送
        subprocess.run(["git", "push"], check=True)
        print(f"🚀 已成功将 {filename} 同步至 GitHub 仓库")
    except Exception as e:
        print(f"❌ Git 同步失败 ({filename}): {e}")

def get_drive():
    creds_json = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')
    if not creds_json:
        raise Exception("错误：未能在 GitHub Secrets 中找到 GOOGLE_DRIVE_CREDENTIALS")
    keyfile_dict = json.loads(creds_json)
    scope = ['https://www.googleapis.com/auth/drive']
    gauth = GoogleAuth()
    gauth.auth_method = 'service'
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scope)
    return GoogleDrive(gauth)

def split_text(text, max_len):
    if len(text) <= max_len: return [text]
    parts = []
    while len(text) > 0:
        if len(text) <= max_len:
            parts.append(text); break
        cut = text.rfind('.', 0, max_len)
        if cut == -1: cut = max_len
        parts.append(text[:cut+1].strip())
        text = text[cut+1:].strip()
    return parts

def run_translation():
    drive = get_drive()
    translator = Translator()
    counter = 0 
    
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false"}).GetList()
    input_file = next((f for f in file_list if f['title'] == 'input.txt'), None)
   
    if not input_file:
        print("❌ 未发现 input.txt")
        return

    input_content = input_file.GetContentString(encoding='utf-8')
    
    # 按照 CHAPTER 标志切割原文
    chapters = re.split(r'(CHAPTER\s+[IVXLCDM]+\.)', input_content)

    chapter_list = []
    # 修正逻辑：如果开头不是 CHAPTER，则第一部分是 PREFACE
    if not input_content.strip().startswith("CHAPTER") and len(chapters) > 0:
        chapter_list.append(("PREFACE", chapters[0]))
        start_idx = 1
    else:
        # 如果以 CHAPTER 开头，chapters[0] 通常是空字符串
        start_idx = 1

    for i in range(start_idx, len(chapters), 2):
        if i >= len(chapters): break
        title = chapters[i].strip()
        content = chapters[i+1] if i+1 < len(chapters) else ""
        chapter_list.append((title, content))

    # --- 循环处理每一章 ---
    for title, content in chapter_list:
        safe_title = title.replace('.', '').replace(' ', '_')
        filename = f"{safe_title}.txt"

        if os.path.exists(filename):
            print(f"⏩ 章节 {title} 本地已存在，跳过...")
            continue

        print(f"\n{'='*20}")
        print(f"🚀 开始翻译章节: {title}")
        
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        new_chapter_translations = []

        for para in paragraphs:
            clean_section = para.replace('\n', ' ')
            sub_sections = split_text(clean_section, MAX_CHARS)
            
            for section in sub_sections:
                try:
                    print(f"正在翻译段落: {section[:30]}...")
                    result = translator.translate(section, src='en', dest='zh-cn')
                    
                    formatted_block = f"原文:\n{section}\n\n译文:\n{result.text}\n\n"
                    formatted_block += "-"*30 + "\n\n"
                    new_chapter_translations.append(formatted_block)
                    
                    counter += 1
                    time.sleep(random.uniform(3, 6))
                    if counter % 15 == 0:
                        print(f"--- 触发长休息 ---")
                        time.sleep(random.randint(60, 90))
                        
                except Exception as e:
                    print(f"❌ 翻译失败: {e}")
                    continue

        # 每翻译完一章，立即写入本地并推送到 GitHub
        if new_chapter_translations:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"CHAPTER TITLE: {title}\n\n")
                f.write("".join(new_chapter_translations))
            print(f"✅ 章节 {title} 已写入本地文件")
            
            # --- 核心改动：立即执行 Git 推送 ---
            git_push_file(filename, title)

if __name__ == "__main__":
    run_translation()
