import os
import json
import time
import random
import re
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
from googletrans import Translator

# ================= 配置区 =================
FOLDER_ID = '1aWo5knX19YKecj88BYNQis4scqv9jKs9'
MAX_CHARS = 2500 
# ==========================================

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
    
    # 获取云端 input.txt
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false"}).GetList()
    input_file = next((f for f in file_list if f['title'] == 'input.txt'), None)
   
    if not input_file:
        print("❌ 未发现 input.txt")
        return

    input_content = input_file.GetContentString(encoding='utf-8')
    
    # 按照 CHAPTER 标志切割原文
    # 匹配格式如: CHAPTER I. CHAPTER II.
    chapters = re.split(r'(CHAPTER\s+[IVXLCDM]+\.)', input_content)

    chapter_list = []
    if not input_content.startswith("CHAPTER") and len(chapters) > 0:
        chapter_list.append(("PREFACE", chapters[0]))
        start_idx = 1
    else:
        start_idx = 1

    for i in range(start_idx, len(chapters), 2):
        title = chapters[i].strip()
        content = chapters[i+1] if i+1 < len(chapters) else ""
        chapter_list.append((title, content))

    # --- 循环处理每一章 ---
    for title, content in chapter_list:
        # 规范化文件名，例如: output_CHAPTER_I.txt
        safe_title = title.replace('.', '').replace(' ', '_')
        filename = f"{safe_title}.txt"

        # 【查重】如果 GitHub 仓库已经有这个章节了，直接跳过
        if os.path.exists(filename):
            print(f"⏩ 章节 {title} 已存在，跳过...")
            continue

        print(f"🚀 开始翻译章节: {title}")
        
        # 将本章内容按自然段切分
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
                    
                    # 休息防封
                    counter += 1
                    time.sleep(random.uniform(3, 6))
                    if counter % 15 == 0:
                        print(f"--- 触发长休息 ---")
                        time.sleep(random.randint(60, 90))
                        
                except Exception as e:
                    print(f"❌ 翻译失败: {e}")
                    continue

        # 每翻译完一章，立即写入一个本地文件
        if new_chapter_translations:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"CHAPTER TITLE: {title}\n\n")
                f.write("".join(new_chapter_translations))
            print(f"✅ 章节 {title} 已保存为 {filename}")

if __name__ == "__main__":
    run_translation()
