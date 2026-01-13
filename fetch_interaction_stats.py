import time
import json
import csv
import os
import traceback
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# 配置文件路径
COOKIES_PATH = "cookies.json"
STATS_CSV_PATH = "interaction_data.csv"

def init_driver():
    """初始化浏览器驱动"""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def load_cookies(driver):
    """加载保存的cookies"""
    if not os.path.exists(COOKIES_PATH):
        print("❌ 未找到 cookies.json")
        return False
    driver.get("https://creator.xiaohongshu.com/")
    with open(COOKIES_PATH, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    for ck in cookies:
        ck.pop("sameSite", None)
        driver.add_cookie(ck)
    driver.refresh()
    return True

def get_stats():
    """获取小红书笔记数据"""
    driver = init_driver()
    try:
        if not load_cookies(driver): return

        print("🚀 进入创作者平台...")
        driver.get("https://creator.xiaohongshu.com/new/note-manager")
        
        # 等待页面加载完成
        wait = WebDriverWait(driver, 20)
        # 以"发布于"文字作为页面加载完成的标识
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '发布于')]")))
        time.sleep(5)  # 额外等待确保动态内容加载

        # 定位所有笔记行
        # 通过查找包含"发布于"的div来定位笔记条目
        print("📊 开始查找笔记...")
        note_rows = driver.find_elements(By.XPATH, "//div[.//div[contains(text(), '发布于')]]")
        
        # 存储解析结果
        results = {}

        for row in note_rows:
            try:
                # 提取笔记标题
                # 先尝试查找标题类元素，如果没有再查找长文本
                title_els = row.find_elements(By.XPATH, ".//div[contains(@class, 'title')] | .//span[contains(@class, 'title')]")
                if not title_els:
                    title_els = row.find_elements(By.XPATH, ".//div[string-length(text()) > 2]")
                
                if not title_els: continue
                title = title_els[0].text.strip()
                
                # 跳过页面标题和空标题
                if title in ["全部笔记", "已发布", "审核中", "未通过", "笔记管理"] or not title:
                    continue

                # 提取互动数据
                # 查找所有span元素，筛选出数字或带w的数据
                all_spans = row.find_elements(By.TAG_NAME, "span")
                counts = []
                for s in all_spans:
                    txt = s.text.strip()
                    # 匹配纯数字或带w的单位
                    if txt.isdigit() or (len(txt) > 1 and txt[:-1].replace('.','').isdigit() and txt[-1].lower() == 'w'):
                        counts.append(txt)
                
                # 小红书数据顺序固定：阅读、点赞、收藏、评论、分享
                if len(counts) >= 2:
                    results[title] = {
                        "标题": title,
                        "阅读": counts[0] if len(counts) > 0 else "0",
                        "点赞": counts[1] if len(counts) > 1 else "0",
                        "收藏": counts[2] if len(counts) > 2 else "0",
                        "评论": counts[3] if len(counts) > 3 else "0",
                        "分享": counts[4] if len(counts) > 4 else "0",
                        "采集时间": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
            except:
                continue

        # 保存并显示结果
        if results:
            data_list = list(results.values())
            with open(STATS_CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data_list[0].keys())
                writer.writeheader()
                writer.writerows(data_list)
            print(f"✅ 成功采集 {len(data_list)} 篇笔记数据")
            for r in data_list:
                print(f"  - {r['标题'][:12]}: 阅 {r['阅读']}, 赞 {r['点赞']}, 藏 {r['收藏']}")
        else:
            print("⚠️ 没有解析到数据，可能是页面结构变化")
            driver.save_screenshot("failed_page.png")
            print("📸 已保存页面截图 failed_page.png")

    except Exception:
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    get_stats()