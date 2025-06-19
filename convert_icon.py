# 脚本将icon.jpg转换成icon.png
from PIL import Image

def convert_jpg_to_png(input_file, output_file):
    try:
        # 打开 JPG 图片
        img = Image.open(input_file)
        
        # 保存为 PNG 格式
        img.save(output_file, 'PNG')
        
        print(f"转换成功！已将 '{input_file}' 转换为 '{output_file}'")
    except Exception as e:
        print(f"转换失败：{e}")

if __name__ == "__main__":
    input_filename = "icon.jpg"   # 输入的 JPG 文件名
    output_filename = "icon.png"  # 输出的 PNG 文件名

    convert_jpg_to_png(input_filename, output_filename)