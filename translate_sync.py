import os
import json
import time
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
    
    file_list = drive.ListFile({'q': f"'{FOLDER_ID}' in parents and trashed=false"}).GetList()
    input_file = next((f for f in file_list if f['title'] == 'input.txt'), None)
    output_file = next((f for f in file_list if f['title'] == 'output.txt'), None)

    if not input_file:
        print("未发现 input.txt")
        return

    input_content = input_file.GetContentString(encoding='utf-8')
    existing_output = output_file.GetContentString(encoding='utf-8') if output_file else ""
    
    processed_originals = [line.replace("原文: ", "").strip() for line in existing_output.split('\n') if line.startswith("原文: ")]

    paragraphs = [p.strip() for p in input_content.split('\n') if p.strip()]
    new_translations = []
    has_new = False

    for para in paragraphs:
        for section in split_text(para, MAX_CHARS):
            if section in processed_originals: continue
            
            try:
                print(f"正在翻译: {section[:20]}...")
                result = translator.translate(section, src='en', dest='zh-cn')
                new_translations.append(f"原文: {section}\n译文: {result.text}\n\n")
                has_new = True
                time.sleep(1)
            except Exception as e:
                print(f"报错: {e}")

    if has_new:
        full_output = existing_output + "".join(new_translations)
        if not output_file:
            output_file = drive.CreateFile({'title': 'output.txt', 'parents': [{'id': FOLDER_ID}]})
        output_file.SetContentString(full_output)
        output_file.Upload()
        print("✅ 云端已更新")
    else:
        print("☕ 无需更新")

if __name__ == "__main__":
    run_translation()
