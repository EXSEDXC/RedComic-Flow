import csv
import json
import os

def convert_csv_to_json(csv_path, base_image_dir, output_json):
    """
    将爬虫生成的 CSV 数据转换为 JSON 格式
    """
    data_dict = {}

    if not os.path.exists(csv_path):
        print(f"错误: 找不到文件 {csv_path}")
        return

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                idx = row['序号']
                title = row['标题']
                content = row['正文']
                count = int(row['图片数量'])
                
                # 对应图片存放的文件夹名称
                folder_name = f"note_{idx}"
                
                # 遍历该 note 下的所有图片
                for i in range(1, count + 1):
                    img_name = f"{i}.jpg"
                    # 构建相对路径 (相对于根目录)
                    relative_path = os.path.join(base_image_dir, folder_name, img_name)
                    
                    # 检查文件是否真的存在，避免死链
                    if os.path.exists(relative_path):
                        # JSON 的键：使用 文件夹_图片名 以确保唯一性
                        key_name = f"{folder_name}_{img_name}"
                        
                        data_dict[key_name] = {
                            "relative_path": relative_path,
                            "title": title,
                            "text_annotation": content,  # 文本标注
                            "original_note_url": row['链接']
                        }
        
        # 写入 JSON 文件
        with open(output_json, 'w', encoding='utf-8') as jf:
            json.dump(data_dict, jf, ensure_ascii=False, indent=4)
        
        print(f"转换成功！共处理 {len(data_dict)} 张图片标注。")
        print(f"结果已保存至: {output_json}")

    except Exception as e:
        print(f"处理过程中出现异常: {e}")

if __name__ == "__main__":
    # 配置路径
    CSV_FILE = os.path.join('RedComic_Final_Fixed', 'metadata.csv')
    IMAGE_DIR = 'RedComic_Final_Fixed'
    OUTPUT_FILE = 'annotations.json'

    convert_csv_to_json(CSV_FILE, IMAGE_DIR, OUTPUT_FILE)