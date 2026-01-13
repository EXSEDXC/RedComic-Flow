import os
import csv
import time
import requests
import json
import shutil  # 用于删除空文件夹
from DrissionPage import ChromiumPage, ChromiumOptions
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_config():
    with open("app_config.json", "r", encoding="utf-8") as f:
        return json.load(f)
prompt = """请严格判断这张图片是否为典型的「六格漫画」：
要求：
1. 必须是一张完整的大图
2. 里面清楚地划分出正好 6 个矩形（或近似矩形）漫画格子
3. 通常为 2×3 或 3×2 排列，也可能是其他六等分方式
4. 每个格子内通常有独立的漫画画面、人物或剧情片段

不符合以上任意一条就视为不是。
只回答以下两种之一，不要输出任何其他文字：
是
否"""
def is_six_panel_comic(img_url, api_key):
    """接入 Qwen-VL 判断是否为六格漫画"""
    if not api_key: 
        return True
    try:
        client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        completion = client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": img_url}}
            ]}]
        )
        res = completion.choices[0].message.content
        return "是" in res
    except Exception as e:
        print(f"  ! AI 识别异常: {e}")
        return True 

def download_img(url, folder, name):
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.xiaohongshu.com/'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            with open(os.path.join(folder, f"{name}.jpg"), 'wb') as f:
                f.write(res.content)
            return True
    except: return False
    return False

def clean_and_back(page, url):
    try:
        if 'explore' in page.url:
            page.back()
        else:
            page.get(url)
    except:
        page.get(url)

def main():
    conf = get_config()
    KEYWORD = conf.get("keyword", "抽卡漫画")
    MAX_NOTES = int(conf.get("max_notes", 10))
    USE_FILTER = conf.get("use_qwen_filter", False)
    API_KEY = os.getenv("DASHSCOPE_API_KEY")
    SAVE_PATH = 'RedComic_Final_Fixed'

    co = ChromiumOptions().set_argument('--disable-blink-features=AutomationControlled')
    page = ChromiumPage(co)
    
    print(f"任务启动 | 目标有效数量: {MAX_NOTES} | 视觉过滤: {USE_FILTER}")
    target_url = f'https://www.xiaohongshu.com/search_result?keyword={KEYWORD}'
    page.get(target_url)
    
    if not os.path.exists(SAVE_PATH): os.makedirs(SAVE_PATH)
    csv_f = open(f'{SAVE_PATH}/metadata.csv', 'a', encoding='utf-8-sig', newline='')
    writer = csv.writer(csv_f)

    count, history, scroll = 0, set(), 0
    
    # 核心修改：只有 count 达到 MAX_NOTES 才会停止
    while count < MAX_NOTES and scroll < 100:
        items = page.eles('.note-item')
        target_href = None
        target_ele = None

        for item in items:
            try:
                anchor = item.ele('tag:a', timeout=0.1)
                href = anchor.attr('href')
                if href and href not in history:
                    if not item.ele('.play-icon', timeout=0.1): 
                        target_ele, target_href = item, href
                        break
            except: continue
        
        if not target_ele:
            page.scroll.down(2000); scroll += 1; time.sleep(2)
            continue

        try:
            history.add(target_href)
            scroll = 0
            target_ele.scroll.to_see(); target_ele.click()
            popup = page.wait.ele_displayed('.note-container', timeout=8)
            if not popup:
                clean_and_back(page, target_url); continue

            # 1. 预提取图片 URL（不下载）
            img_urls = []
            media = popup.ele('.media-container')
            if media:
                for img in media.eles('tag:img'):
                    src = img.attr('src')
                    if src and 'xhscdn.com' in src and 'avatar' not in src:
                        img_urls.append(src.split('?')[0])
            
            # 2. AI 识别过滤
            if USE_FILTER and img_urls:
                print(f"  > 正在进行 AI 识别: {target_href}")
                if not is_six_panel_comic(img_urls[0], API_KEY):
                    print("  - [跳过] 判定非六格漫画")
                    clean_and_back(page, target_url); continue

            # 3. 只有通过识别后，才创建文件夹
            note_idx = count + 1
            temp_folder = os.path.join(SAVE_PATH, f"note_{note_idx}")
            if not os.path.exists(temp_folder): os.makedirs(temp_folder)
            
            # 4. 执行下载
            success_dl = 0
            unique_urls = list(dict.fromkeys(img_urls))[:18]
            for i, url in enumerate(unique_urls):
                if download_img(url, temp_folder, f"{i+1}"):
                    success_dl += 1
            
            # 5. 最终校验：如果下载成功数 > 0，才算有效采集
            if success_dl > 0:
                title = popup.ele('.title').text if popup.ele('.title') else "无标题"
                writer.writerow([note_idx, title, target_href, success_dl])
                csv_f.flush()
                print(f"  + [成功] 第 {note_idx} 组保存完成: {title[:10]}...")
                count += 1 # 只有到这里，计数器才加 1
            else:
                # 如果没下载到图，把刚建的空文件夹删了
                if os.path.exists(temp_folder):
                    shutil.rmtree(temp_folder)
                print("  ! [失败] 未采集到有效图片，文件夹已清理")

            clean_and_back(page, target_url)

        except Exception as e:
            print(f"  ! 处理异常: {e}")
            clean_and_back(page, target_url)

    csv_f.close()
    print(f"\n任务结束 | 总计成功采集: {count}/{MAX_NOTES}")

if __name__ == '__main__':
    main()