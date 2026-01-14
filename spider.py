import os
import csv
import time
import requests
import json
import shutil
import re
from PIL import Image
from io import BytesIO
from DrissionPage import ChromiumPage, ChromiumOptions
from openai import OpenAI
from dotenv import load_dotenv

# 加载环境变量配置文件
load_dotenv()

def get_config():
    """读取应用配置文件"""
    with open("app_config.json", "r", encoding="utf-8") as f:
        return json.load(f)

# 六格漫画识别提示词
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

def is_quality_ok(img_url, text_content, min_resolution, min_text_len):
    """
    基础质量过滤：检查分辨率和文本长度
    """
    # 1. 文本长度校验 (匹配中文字符)
    chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text_content)
    if len(chinese_chars) < min_text_len:
        print(f"  - [跳过] 文本字数不足 ({len(chinese_chars)} < {min_text_len})")
        return False

    # 2. 分辨率校验
    try:
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.xiaohongshu.com/'}
        response = requests.get(img_url, headers=headers, timeout=5)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            width, height = img.size
            if width < min_resolution or height < min_resolution:
                print(f"  - [跳过] 分辨率过低 ({width}x{height} < {min_resolution}p)")
                return False
        else:
            return False
    except Exception as e:
        print(f"  ! 分辨率检测异常: {e}")
        return False

    return True

def is_six_panel_comic(img_url, api_key):
    """使用视觉模型判断图片是否为六格漫画"""
    if not api_key: 
        return True
    try:
        # 初始化Qwen-VL客户端
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
    """下载图片到指定文件夹"""
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
    """清理当前页面并返回目标页面"""
    try:
        if 'explore' in page.url:
            page.back()
        else:
            page.get(url)
    except:
        page.get(url)

def main():
    # 获取配置参数
    conf = get_config()
    KEYWORD = conf.get("keyword", "抽卡漫画")
    MAX_NOTES = int(conf.get("max_notes", 10))
    
    # 过滤开关与参数
    USE_FILTER = conf.get("use_qwen_filter", False)      # 大模型识别开关
    USE_QUALITY_CHECK = conf.get("use_quality_check", False) # 基础过滤开关
    MIN_RES = int(conf.get("min_resolution", 500))       # 最低分辨率
    MIN_TEXT = int(conf.get("min_text_len", 10))         # 最低中文字数
    
    API_KEY = os.getenv("DASHSCOPE_API_KEY")
    SAVE_PATH = 'RedComic_Final_Fixed'

    # 初始化浏览器配置
    co = ChromiumOptions().set_argument('--disable-blink-features=AutomationControlled')
    page = ChromiumPage(co)
    
    print(f"任务启动 | 目标: {MAX_NOTES} | 基础过滤: {USE_QUALITY_CHECK} | AI识别: {USE_FILTER}")
    target_url = f'https://www.xiaohongshu.com/search_result?keyword={KEYWORD}'
    page.get(target_url)
    
    if not os.path.exists(SAVE_PATH): os.makedirs(SAVE_PATH)
    
    # 检查文件是否存在以决定是否写入表头
    csv_path = f'{SAVE_PATH}/metadata.csv'
    file_exists = os.path.exists(csv_path)
    csv_f = open(csv_path, 'a', encoding='utf-8-sig', newline='')
    writer = csv.writer(csv_f)
    
    # 修改：添加表头
    if not file_exists:
        writer.writerow(['序号', '标题', '正文', '链接', '图片数量'])

    count, history, scroll = 0, set(), 0
    
    while count < MAX_NOTES and scroll < 100:
        items = page.eles('.note-item')
        target_href, target_ele = None, None

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

            # 提取图片链接
            img_urls = []
            media = popup.ele('.media-container')
            if media:
                for img in media.eles('tag:img'):
                    src = img.attr('src')
                    if src and 'xhscdn.com' in src and 'avatar' not in src:
                        img_urls.append(src.split('?')[0])
            
            # 提取正文内容用于字数过滤和保存
            note_desc = popup.ele('.desc').text if popup.ele('.desc') else ""
            
            # --- 过滤逻辑开始 ---
            passed = True
            
            # 第一步：基础质量过滤 (分辨率 + 字数)
            if USE_QUALITY_CHECK and img_urls:
                if not is_quality_ok(img_urls[0], note_desc, MIN_RES, MIN_TEXT):
                    passed = False
            
            # 第二步：如果基础过滤通过且启用了AI过滤，则进行大模型识别
            if passed and USE_FILTER and img_urls:
                print(f"  > 正在进行 AI 识别: {target_href}")
                if not is_six_panel_comic(img_urls[0], API_KEY):
                    print("  - [跳过] 判定非六格漫画")
                    passed = False
            
            if not passed:
                clean_and_back(page, target_url)
                continue
            # --- 过滤逻辑结束 ---

            # 第三步：创建对应文件夹
            note_idx = count + 1
            temp_folder = os.path.join(SAVE_PATH, f"note_{note_idx}")
            if not os.path.exists(temp_folder): os.makedirs(temp_folder)
            
            # 第四步：下载图片
            success_dl = 0
            unique_urls = list(dict.fromkeys(img_urls))[:18]
            for i, url in enumerate(unique_urls):
                if download_img(url, temp_folder, f"{i+1}"):
                    success_dl += 1
            
            # 第五步：保存结果
            if success_dl > 0:
                title = popup.ele('.title').text if popup.ele('.title') else "无标题"
                # 修改：保存数据中增加正文 note_desc
                writer.writerow([note_idx, title, note_desc, target_href, success_dl])
                csv_f.flush()
                print(f"  + [成功] 第 {note_idx} 组保存完成: {title[:10]}...")
                count += 1 
            else:
                if os.path.exists(temp_folder): shutil.rmtree(temp_folder)
                print("  ! [失败] 未采集到有效图片，文件夹已清理")

            clean_and_back(page, target_url)

        except Exception as e:
            print(f"  ! 处理异常: {e}")
            clean_and_back(page, target_url)

    csv_f.close()
    print(f"\n任务结束 | 总计成功采集: {count}/{MAX_NOTES}")

if __name__ == '__main__':
    main()