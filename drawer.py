from PIL import Image, ImageFont, ImageDraw


def draw(strs, size, colors=None):
    """
    在一页空白图片上画上strs所示的文字
    :param strs: 文字
    :param size: 尺寸
    :param colors: 颜色信息 (每行每字符的RGB颜色元组)
    :return: 得到的图片
    """
    font = ImageFont.truetype('assets/font/DEJAVUSANSMONO_0.TTF', 12)
    step_h = 14
    w, h = 2, 0
    img = Image.new("RGB", size, (255, 255, 255))
    img_w, img_h = size
    im_draw = ImageDraw.Draw(img)
    
    for y, s in enumerate(strs):
        current_w = w
        for x, char in enumerate(s):
            fill = (0, 0, 0)  # 默认黑色
            if colors is not None and y < len(colors) and x < len(colors[y]):
                fill = colors[y][x]
            im_draw.text((current_w, h), char, font=font, fill=fill)
            current_w += 8  # 每个字符宽度
        h += step_h
        if h > img_h:
            break
    return img