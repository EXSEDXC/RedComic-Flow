import pygame
import threading
import sys
import json
import os
import importlib
import pyperclip
from dotenv import load_dotenv

# 1. 初始化与环境配置
load_dotenv() # 加载根目录 .env 中的 API Key
pygame.init()

WIDTH, HEIGHT = 1100, 750
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("小红书自动化全链路控制台")

# 颜色配置
BG_COLOR = (10, 15, 25)
PANEL_COLOR = (20, 30, 45)
ACCENT_COLOR = (0, 255, 200)
TEXT_COLOR = (200, 220, 240)
INPUT_BG = (30, 45, 65)

# 2. 资源加载
def load_system_font(size):
    candidates = ['microsoftyahei', 'msyh', 'simhei', 'simsun']
    for name in candidates:
        path = pygame.font.match_font(name)
        if path: return pygame.font.Font(path, size)
    return pygame.font.SysFont('SimHei', size)

font_main = load_system_font(22)
font_log = load_system_font(16)
font_label = load_system_font(14)

CONFIG_FILE = "app_config.json"

def load_config():
    """从本地读取配置，若无则使用默认值"""
    default = {"keyword": "抽卡漫画", "max_notes": "10", "publish_gap": "45", "use_qwen_filter": False}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return {**default, **json.load(f)}
        except: return default
    return default

def save_config(data):
    """保存当前 UI 的配置到 JSON"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 3. UI 组件类
class InputField:
    def __init__(self, x, y, w, h, label, key, val):
        self.rect = pygame.Rect(x, y, w, h)
        self.label, self.key, self.text = label, key, str(val)
        self.active = False
    def draw(self, surf):
        pygame.draw.rect(surf, INPUT_BG, self.rect, border_radius=6)
        color = ACCENT_COLOR if self.active else (80, 100, 120)
        pygame.draw.rect(surf, color, self.rect, 2, border_radius=6)
        surf.blit(font_label.render(self.label, True, (160, 180, 200)), (self.rect.x, self.rect.y - 20))
        surf.blit(font_log.render(self.text, True, (240, 240, 240)), (self.rect.x + 10, self.rect.y + 11))

class Button:
    def __init__(self, x, y, w, h, text, action_id):
        self.rect = pygame.Rect(x, y, w, h)
        self.text, self.action_id = text, action_id
    def draw(self, surf, hover):
        bg = (35, 55, 75) if hover else PANEL_COLOR
        pygame.draw.rect(surf, bg, self.rect, border_radius=8)
        pygame.draw.rect(surf, ACCENT_COLOR, self.rect, 2, border_radius=8)
        t_surf = font_main.render(self.text, True, TEXT_COLOR)
        surf.blit(t_surf, (self.rect.centerx - t_surf.get_width()//2, self.rect.centery - t_surf.get_height()//2))

# 4. 业务逻辑控制
config = load_config()
inputs = [
    InputField(800, 120, 250, 45, "搜索关键词", "keyword", config["keyword"]),
    InputField(800, 210, 250, 45, "有效采集数量", "max_notes", config["max_notes"]),
    InputField(800, 300, 250, 45, "发布间隔(秒)", "publish_gap", config["publish_gap"])
]
use_filter = config.get("use_qwen_filter", False)
filter_rect = pygame.Rect(800, 380, 250, 50)
logs = ["系统初始化完成", "API Key 已准备就绪"]
is_running = False

def add_log(msg):
    logs.append(f"> {msg}")
    if len(logs) > 20: logs.pop(0)

def run_task(action_id, btn_text):
    """在子线程中运行业务脚本"""
    global is_running
    is_running = True
    add_log(f"任务启动: {btn_text}")
    try:
        if action_id == "1":
            import spider
            importlib.reload(spider)
            spider.main()
        elif action_id == "2":
            import rewrite_images
            importlib.reload(rewrite_images); rewrite_images.main()
        elif action_id == "3":
            import auto_publish_batch
            importlib.reload(auto_publish_batch); auto_publish_batch.start()
        elif action_id == "4":
            import fetch_interaction_stats
            importlib.reload(fetch_interaction_stats); fetch_interaction_stats.get_stats()
        elif action_id == "5":
            import visualize_stats
            importlib.reload(visualize_stats); visualize_stats.generate_report()
        add_log("任务正常结束")
    except Exception as e:
        add_log(f"错误: {str(e)[:50]}...")
    finally:
        is_running = False

# 5. 主循环
def main():
    global use_filter, is_running
    clock = pygame.time.Clock()
    
    # 定义左侧 5 个功能按钮
    btn_list = [
        Button(50, 100, 280, 60, "1. 采集 (Spider)", "1"),
        Button(50, 180, 280, 60, "2. AI 文案改写", "2"),
        Button(50, 260, 280, 60, "3. 批量自动发布", "3"),
        Button(50, 340, 280, 60, "4. 采集互动数据", "4"),
        Button(50, 420, 280, 60, "5. 可视化报表", "5")
    ]

    while True:
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            
            # 输入框处理
            for inp in inputs:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    inp.active = inp.rect.collidepoint(event.pos)
                    if inp.active: pygame.key.start_text_input()
                if inp.active:
                    if event.type == pygame.TEXTINPUT: inp.text += event.text
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKSPACE:
                        inp.text = inp.text[:-1]

            # 按钮与开关点击
            if event.type == pygame.MOUSEBUTTONDOWN and not is_running:
                if filter_rect.collidepoint(event.pos):
                    use_filter = not use_filter
                
                for btn in btn_list:
                    if btn.rect.collidepoint(event.pos):
                        # 点击任意按钮前先保存当前所有 UI 配置
                        current_cfg = {i.key: i.text for i in inputs}
                        current_cfg["use_qwen_filter"] = use_filter
                        save_config(current_cfg)
                        # 启动线程
                        threading.Thread(target=run_task, args=(btn.action_id, btn.text), daemon=True).start()

        # --- 渲染逻辑 ---
        screen.fill(BG_COLOR)
        pygame.draw.line(screen, ACCENT_COLOR, (0, 65), (WIDTH, 65), 2)
        screen.blit(font_main.render("XHS 自动化全链路控制台 v3.3", True, ACCENT_COLOR), (20, 20))

        # 绘制按钮
        for btn in btn_list:
            btn.draw(screen, btn.rect.collidepoint(mx, my))
        
        # 绘制输入框
        for inp in inputs: inp.draw(screen)

        # 绘制视觉过滤开关
        f_color = ACCENT_COLOR if use_filter else (120, 120, 120)
        pygame.draw.rect(screen, INPUT_BG, filter_rect, border_radius=6)
        pygame.draw.rect(screen, f_color, filter_rect, 2, border_radius=6)
        f_txt = "Qwen 视觉过滤: 开启" if use_filter else "Qwen 视觉过滤: 关闭"
        screen.blit(font_log.render(f_txt, True, f_color), (filter_rect.x + 15, filter_rect.y + 15))

        # 绘制日志区
        pygame.draw.rect(screen, PANEL_COLOR, (360, 100, 410, 560), border_radius=10)
        for i, line in enumerate(logs):
            screen.blit(font_log.render(line, True, (180, 190, 200)), (375, 115 + i*26))

        # 状态灯
        pygame.draw.circle(screen, (220, 60, 60) if is_running else (60, 220, 100), (45, 710), 8)
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()