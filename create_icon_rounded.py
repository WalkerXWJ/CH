# 此脚本生成圆角图片
import os
from PIL import Image, ImageDraw

def create_rounded_icon(input_path, output_path, size=1024, corner_radius=180):
    """
    将输入图片转换为 macOS 风格的圆角图标（.png 或 .icns）
    
    :param input_path: 输入图片路径（如 icon.png）
    :param output_path: 输出图片路径（如 icon_rounded.png）
    :param size: 图标尺寸（默认 1024x1024）
    :param corner_radius: 圆角半径（默认 180，适用于 1024x1024）
    """
    # 打开图片并调整大小
    img = Image.open(input_path).convert("RGBA")
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # 创建圆角蒙版
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    
    # 绘制圆角矩形
    draw.rounded_rectangle(
        [(0, 0), (size, size)],
        radius=corner_radius,
        fill=255
    )
    
    # 应用蒙版
    rounded_img = Image.new("RGBA", (size, size))
    rounded_img.paste(img, (0, 0), mask)
    
    # 保存圆角图标
    rounded_img.save(output_path)
    print(f"圆角图标已保存: {output_path}")

def convert_to_icns(png_path, icns_path):
    """
    将 PNG 图标转换为 .icns 格式（macOS 应用图标格式）
    
    :param png_path: 输入 PNG 路径
    :param icns_path: 输出 .icns 路径
    """
    # 创建临时目录存放图标尺寸
    temp_dir = "icon_temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 生成不同尺寸的图标（macOS 需要多种尺寸）
    sizes = [16, 32, 128, 256, 512, 1024]
    for size in sizes:
        # 缩放图片
        img = Image.open(png_path).convert("RGBA")
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        # 保存临时文件
        temp_path = os.path.join(temp_dir, f"icon_{size}x{size}.png")
        img.save(temp_path)
    
    # 使用 macOS 的 `iconutil` 生成 .icns
    cmd = f'iconutil -c icns {temp_dir} -o {icns_path}'
    os.system(cmd)
    print(f".icns 图标已保存: {icns_path}")
    
    # 清理临时文件
    for size in sizes:
        temp_path = os.path.join(temp_dir, f"icon_{size}x{size}.png")
        if os.path.exists(temp_path):
            os.remove(temp_path)
    os.rmdir(temp_dir)

if __name__ == "__main__":
    input_icon = "icon.png"  # 输入图标（PNG）
    rounded_png = "icon_rounded.png"  # 圆角 PNG 图标
    final_icns = "Icon.icns"  # 最终 .icns 图标
    
    # 1. 生成圆角 PNG
    create_rounded_icon(input_icon, rounded_png)
    
    # 2. 转换为 .icns
    convert_to_icns(rounded_png, final_icns)