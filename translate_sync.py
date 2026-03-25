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
FOLDER_ID = '1aWo5knX19YKecj88BYNQis4scqv9jKs9'     # 填入你的 Google Drive 文件夹 ID
MAX_CHARS = 3000              # 单次翻译最大字符限制
# ==========================================

def get_drive():
    # 从 GitHub Secrets 读取环境变量
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
    counter = 0  # <--- 1. 在这里初始化计数器
    
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false"}).GetList()
    input_file = next((f for f in file_list if f['title'] == 'input.txt'), None)
    output_file = next((f for f in file_list if f['title'] == 'output.txt'), None)

    if not input_file:
        print("未发现 input.txt")
        return

    input_content = input_file.GetContentString(encoding='utf-8')
    existing_output = output_file.GetContentString(encoding='utf-8') if output_file else ""
    
    processed_originals = [line.replace("原文: ", "").strip() for line in existing_output.split('\n') if line.startswith("原文: ")]

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', input_content) if p.strip()]
    
    new_translations = []
    has_new = False
    counter = 0

    for para in paragraphs:
        # 1. 查重：如果这一段已经存在于输出文件中，直接跳过
        # 这样即便任务中断重跑，也不会重复翻译
        if para[:50] in existing_output: 
            continue
            
        # 2. 清洗段落内不必要的单换行（让它变成流畅的一长条）
        clean_section = para.replace('\n', ' ')
        
        # 3. 处理超长段落（保险起见）
        sub_sections = split_text(clean_section, MAX_CHARS)
        
        for section in sub_sections:
            try:
                print(f"正在翻译新段落: {section[:30]}...")
                result = translator.translate(section, src='en', dest='zh-cn')
                
                # --- 严格对照格式 ---
                # 每翻译完一个 section，立刻打包成 原文+译文
                formatted_block = f"原文:\n{section}\n\n译文:\n{result.text}\n\n"
                formatted_block += "-"*30 + "\n\n"
                
                new_translations.append(formatted_block)
                has_new = True
                
                # 4. 计数与休息（防封）
                counter += 1
                time.sleep(random.uniform(3, 8))
                
                if counter % 15 == 0:
                    print(f"--- 已翻译 {counter} 段，保护性长休息 ---")
                    time.sleep(random.randint(60, 90))
                    
            except Exception as e:
                print(f"该段翻译失败: {e}")
                continue

    if has_new:
        full_output = existing_output + "".join(new_translations)
        if not output_file:
            # 修改这里：增加 supportsAllDrives 确保权限正确透传
            output_file = drive.CreateFile({
                'title': 'output.txt', 
                'parents': [{'id': FOLDER_ID}]
            })
        
        output_content = full_output
        output_file.SetContentString(output_content)
        
        # 核心修改点：上传时增加这个参数，让它占用你的配额而不是机器人的
        output_file.Upload(param={'supportsAllDrives': True}) 
        print("✅ 云端已更新")
    else:
        print("☕ 无需更新")

if __name__ == "__main__":
    run_translation()
