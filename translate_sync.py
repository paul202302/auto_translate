import os
import json
import time
import random
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

   paragraphs = [p.strip() for p in input_content.split('\n\n') if p.strip()]
    
    new_translations = []
    has_new = False

    for para in paragraphs:
        # 清洗一下段落内部的多余换行，让它变成连续的一长条
        clean_para = para.replace('\n', ' ')
        
        # 智能切分超长段落（如果单段真的超过3000字）
        sub_sections = split_text(clean_para, MAX_CHARS)
        
        for section in sub_sections:
            if section in processed_originals: continue
            
            try:
                print(f"正在处理自然段: {section[:30]}...")
                result = translator.translate(section, src='en', dest='zh-cn')
                
                # 【修改点2】输出格式优化：一段原文 + 一段译文
                new_segment = f"原文:\n{section}\n\n译文:\n{result.text}\n\n"
                new_segment += "-"*30 + "\n\n" # 加个分割线更美观
                
                new_translations.append(new_segment)
                has_new = True
                time.sleep(random.uniform(2, 20)) # 稍微增加间隔，防止被封
            except Exception as e:
                print(f"报错: {e}")
            counter += 1 
            if counter % 20 == 0:
                print(f"已连续处理 {counter} 段，触发大休息，防止被封...")
                time.sleep(random.randint(90, 120)) # 休息 1.5 到 2 分钟

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
