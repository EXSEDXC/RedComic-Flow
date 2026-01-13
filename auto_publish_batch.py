import os
import sys
import time
import json
import csv
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

# --- 基础配置 ---
COOKIES_PATH = "cookies.json"  #cookies文件名
CSV_PATH = "series_story.csv"  #读取的csv文件名
IMAGE_DIR = "images"           #图片文件夹
# ---------------

def init_driver():
    """初始化浏览器，集成防检测配置"""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # 移除自动化控制特征，降低风控风险
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 修改浏览器指纹，防止被识别为 webdriver
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    })
    return driver

# 全局初始化浏览器
browser = init_driver()

def save_cookies():
    """将当前登录状态持久化到本地文件"""
    try:
        cookies = browser.get_cookies()
        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=4)
        print("[System] Cookie 已同步至本地")
    except Exception as e:
        print(f"[Error] Cookie 保存失败: {e}")

def login():
    """处理登录逻辑：优先尝试 Cookie，失效则切换为手动扫码"""
    print("\n>>> 正在验证登录状态...")
    browser.get("https://creator.xiaohongshu.com/publish/publish?type=image&from=tab_switch")
    time.sleep(2)
    
    if os.path.exists(COOKIES_PATH):
        try:
            with open(COOKIES_PATH, "r", encoding="utf-8") as f:
                cookie_list = json.load(f)
            for ck in cookie_list:
                # 剔除无效字段，修正域名偏差
                ck.pop("sameSite", None)
                ck.pop("storeId", None)
                if ck.get("domain", "").startswith("."):
                    ck["domain"] = ck["domain"][1:]
                browser.add_cookie(ck)
            browser.refresh()
            time.sleep(3)
        except Exception:
            pass
            
    if "login" in browser.current_url:
        print("[Notice] Cookie 失效，请在弹出的浏览器中手动扫码登录")
        input("   -> 登录完成后请在此处按回车键继续...")
        save_cookies()
    
    print("[Success] 登录验证通过")

def upload_note(image_filenames, title, main_body, tags):
    """执行单条笔记的上云发布流程"""
    print(f"\n[任务启动] 标题: {title}")
    target_url = "https://creator.xiaohongshu.com/publish/publish?type=image&from=tab_switch&target=image"
    browser.get(target_url)
    time.sleep(3)

    try:
        # 1. 处理图片上传
        abs_paths = [os.path.abspath(os.path.join(IMAGE_DIR, n.strip())) 
                     for n in image_filenames if os.path.exists(os.path.join(IMAGE_DIR, n.strip()))]
        if not abs_paths:
            print("  ! 跳过：未找到有效的图片文件")
            return
        
        upload_input = WebDriverWait(browser, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        upload_input.send_keys("\n".join(abs_paths))
        print(f"  - 正在上传 {len(abs_paths)} 张图片...")
        time.sleep(10 + len(abs_paths) * 2) # 根据图片数量动态预留上传时间

        # 2. 填写标题
        title_el = WebDriverWait(browser, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder, '填写标题')]"))
        )
        browser.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", title_el, title)

        # 3. 正文注入（通过 DOM 注入提高长文本效率，模拟 P 标签换行）
        print("  - 注入正文内容...")
        desc_box = WebDriverWait(browser, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".tiptap.ProseMirror"))
        )
        browser.execute_script("""
            const div = arguments[0];
            div.innerHTML = '<p>' + arguments[1].replace(/\\n/g, "</p><p>") + '</p>';
            div.dispatchEvent(new Event('input', { bubbles: true }));
        """, desc_box, main_body)
        time.sleep(1)

        # 4. 模拟交互式输入话题（触发平台推荐机制，增加流量权重）
        if tags:
            print(f"  - 正在通过模拟键盘输入标签: {tags}")
            # 将光标聚焦并移至文案末尾
            browser.execute_script("""
                const el = arguments[0];
                const range = document.createRange();
                const sel = window.getSelection();
                range.selectNodeContents(el);
                range.collapse(false);
                sel.removeAllRanges();
                sel.addRange(range);
                el.focus();
            """, desc_box)
            
            actions = ActionChains(browser)
            actions.send_keys(Keys.ENTER).perform()
            
            for tag in tags:
                actions.send_keys("#").perform()
                time.sleep(0.5)
                actions.send_keys(tag).perform()
                
                # 等待系统话题推荐菜单弹出
                try:
                    WebDriverWait(browser, 3).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(@class, 'suggestion') or contains(@class, 'topic-item')]"))
                    )
                    time.sleep(0.5)
                    actions.send_keys(Keys.ENTER).perform() # 选中第一个推荐
                    print(f"    + 标签已挂载: #{tag}")
                except Exception:
                    # 未匹配到推荐时，通过空格闭合话题
                    actions.send_keys(Keys.SPACE).perform()
                    print(f"    ~ 标签未匹配(已强制闭合): #{tag}")
                
                time.sleep(0.8)

        # 5. 执行最终发布
        time.sleep(2)
        pub_btn = WebDriverWait(browser, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'publishBtn') or contains(., '发布')]"))
        )
        browser.execute_script("arguments[0].click();", pub_btn)
        print("[Success] 该条笔记发布指令已发出")
        time.sleep(8)

    except Exception:
        print("\n[Error] 发布流程中断，详细堆栈如下:")
        traceback.print_exc()
        input("\n等待人工干预... 处理完毕后按回车处理 CSV 下一行内容")

import json

def start():
    """主程序入口：读取 CSV 并分发任务"""
    with open("app_config.json", "r", encoding="utf-8") as f:
        conf = json.load(f)
    GAP = int(conf.get("publish_gap", 45))
    
    try:
        login()
        if not os.path.exists(CSV_PATH):
            print(f"[Fatal] 找不到数据源文件: {CSV_PATH}")
            return
            
        with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 兼容中英文逗号的图片列表
                img_names = row['图片文件名'].replace('，', ',').split(',')
                content = row['生成的文案'].strip()
                
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                if not lines: continue
                
                # 取第一行作为标题，限制字符长度
                title = lines[0][:20]
                body_parts = []
                tags = []
                
                # 区分正文与话题标签
                for line in lines[1:]:
                    if any(k in line for k in ["标签：", "标签:", "话题：", "话题:"]):
                        raw = line.replace("标签","").replace("话题","").replace("：","").replace(":","").replace("，",",")
                        tags = [t.strip() for t in raw.split(",") if t.strip()]
                    else:
                        body_parts.append(line)
                
                upload_note(img_names, title, "\n".join(body_parts), tags)
                
                # 模拟真人操作间隔，规避风控检测
                print(f"[Wait] 进入 45s 发布冷却期...")
                time.sleep(45)
    finally:
        browser.quit()
        print("\n>>> 脚本运行结束")

if __name__ == "__main__":
    start()