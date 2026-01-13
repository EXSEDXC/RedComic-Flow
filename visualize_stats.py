import pandas as pd
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei'] 
plt.rcParams['axes.unicode_minus'] = False 

def generate_report(csv_path="interaction_data.csv"):
    """生成数据可视化报告"""
    try:
        # 1. 读取数据文件
        df = pd.read_csv(csv_path)
        
        # 数据清洗：处理带'w'的单位，转换为浮点数
        for col in ['阅读', '点赞', '收藏']:
            df[col] = df[col].astype(str).str.replace('w', '000').astype(float)

        # 2. 创建图表
        plt.figure(figsize=(12, 6))
        
        # 用柱状图展示阅读量
        plt.bar(df['标题'].str[:10], df['阅读'], color='skyblue', label='阅读量')
        
        # 用折线图展示点赞趋势（放大5倍以便观察）
        plt.plot(df['标题'].str[:10], df['点赞'] * 5, color='red', marker='o', label='点赞趋势(x5)')

        plt.title('小红书笔记互动数据分析图', fontsize=16)
        plt.xlabel('笔记标题(前10字)', fontsize=12)
        plt.ylabel('数值', fontsize=12)
        plt.xticks(rotation=45)  # 旋转x轴标签
        plt.legend()  # 显示图例
        plt.tight_layout()  # 调整布局

        # 3. 保存图表并显示
        plt.savefig('analysis_report.png')
        print("📊 可视化报告已生成：analysis_report.png")
        plt.show()

    except Exception as e:
        print(f"❌ 绘图失败，请确保已安装 pandas 和 matplotlib: {e}")

if __name__ == "__main__":
    generate_report()