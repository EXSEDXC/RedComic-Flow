import os
import csv
import base64
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量并配置 API 密钥
load_dotenv()
api_key = os.getenv("DASHSCOPE_API_KEY")

if not api_key:
    print("[Error] 未在 .env 文件中找到有效密钥 (DASHSCOPE_API_KEY)")
    exit(1)

# 初始化模型客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

def encode_image_to_base64(image_path):
    """辅助函数：执行本地文件到 Base64 编码的转换"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        print(f"[Warning] 图像编码失败: {image_path} | {e}")
        return None

def generate_batch_story(image_paths):
    """
    聚合多张图片上下文，单次调用模型生成连贯文案
    """
    print(f"[Logic] 正在处理图像序列（共计 {len(image_paths)} 帧）...")
    
    # 使用提示词确保输出纯净
    content_list = [
        {
            "type": "text", 
            "text": (
                '''
你现在是纯文本小说作者，严禁使用任何 Markdown 语法。
请严格遵守以下所有限制条件，否则视为严重违规：

- 禁止出现任何形式的 ** 加粗
- 禁止出现任何形式的 * 斜体 或 *** - 禁止出现任何 # 号（包括单#、##、###、####）
- 禁止出现任何形式的标题符号
- 禁止使用 - 或 * 开头的列表
- 禁止使用 > 引用
- 禁止使用 ``` 代码块
- 禁止使用横线 ----- 
- 只能使用最普通的纯文本
【输出规则 - 违反即完全错误】
1. 整段输出只能有：标题（单独一行） + 空行 + 正文 + 空行 + 标签行
2. 标题行：只允许纯文字，不准出现 " ' 《 》 ** * # ( ) [ ] 等任何符号
3. 正文：普通段落文字，允许自然换行，禁止任何装饰符号
4. 标签行：只写 标签1, 标签2, 标签3, 标签4, 标签5  这种格式，禁止#禁止引号
5. 除了这三部分+空行，禁止出现任何其他文字，包括“标题”“故事”“以下是”等
输出结构必须严格按照这个顺序，且只包含这几部分，什么多余的符号、说明、序号都不要出现：

第一行：标题（就是一行普通文字）
空一行
第二部分：正文故事（200~300字）
空一行
第三部分：五个标签，用逗号分隔，例如：标签1, 标签2, 标签3, 标签4, 标签5

现在请根据我给你的图片顺序，创作一个完整连贯的故事。'''
            )
        }
    ]
    
    # 填充多图数据到消息列表
    for path in image_paths:
        base64_img = encode_image_to_base64(path)
        if base64_img:
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
            })

    try:
        # 调度多模态模型进行视觉推理
        completion = client.chat.completions.create(
            model="qwen-vl-plus", 
            messages=[{"role": "user", "content": content_list}],
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"[API Error] 调用异常: {str(e)}"

def main():
    # --- 路径定义 ---
    image_folder = "images"  
    output_file = "series_story.csv" 
    # ---------------

    if not os.path.exists(image_folder):
        print(f"[Error] 指定目录不存在: {image_folder}")
        return
        
    # 按名称排序以保证故事叙事顺序 (1.jpg, 2.jpg...)
    image_files = sorted([
        f for f in os.listdir(image_folder) 
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ])
    
    if not image_files:
        print("[Notice] 目标文件夹内未发现图片资产")
        return

    # 生成完整路径列表
    all_image_paths = [os.path.join(image_folder, f) for f in image_files]

    # 执行批处理生成
    story_content = generate_batch_story(all_image_paths)

    # 保存到本地
    with open(output_file, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["图片文件名", "生成的文案"])
        writer.writerow([", ".join(image_files), story_content])

    print(f"\n>>> 任务结束。文案已导出至: {output_file}")

if __name__ == "__main__":
    main()