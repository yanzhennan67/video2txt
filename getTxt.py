import cv2 as cv
import numpy as np


def down_sample(img, times):
    """
    将图片缩小一定倍数
    :param img 图片
    :param times 缩小倍数
    :return: 缩小后的图片
    """
    if len(img.shape) == 2:
        h, w = img.shape  # 灰度图
    else:
        h, w = img.shape[:2]  # 彩色图
    h_new, w_new = int(h / (2 * times)), int(w / times)
    return cv.resize(img, (w_new, h_new))


def enhance_contrast(img):
    """
    用线性增强提高图片的对比度
    :param img: 图片
    :return: 增强后的结果
    """
    i_max = np.max(img)
    i_min = np.min(img)
    if i_max == i_min:
        # 返回原图
        return img.astype(np.uint8)
    o_min, o_max = 0, 255
    a = float(o_max - o_min) / (i_max - i_min)
    b = o_min - a * i_min
    enhanced_img = a * img + b
    return enhanced_img.astype(np.uint8)


def get_brightness(img):
    """获取图像的亮度（灰度值）"""
    if len(img.shape) == 3:
        # 彩色图转换为亮度
        return cv.cvtColor(img, cv.COLOR_BGR2GRAY)
    return img


def to_txt(img, mapping_str, times, return_colors=False):
    """
    将图像转换成文字信息，每个字符串为一行
    :param img: 图片
    :param mapping_str: 用于与色阶相映射的字符
    :param times: 缩小的倍数
    :param return_colors: 是否返回颜色信息
    :return: 所有的字符数组，或 (字符数组, 颜色数组)
    """
    img_small = down_sample(img, times)
    
    # 提取亮度用于字符选择
    brightness = get_brightness(img_small)
    brightness = enhance_contrast(brightness)
    
    res_strs = []
    colors = []
    section_w = 256 / len(mapping_str)
    
    for y in range(brightness.shape[0]):
        line_str = ''
        line_colors = []
        for x in range(brightness.shape[1]):
            char_idx = int(brightness[y, x] / section_w)
            char_idx = min(char_idx, len(mapping_str) - 1)
            line_str += mapping_str[char_idx]
            
            if return_colors:
                if len(img_small.shape) == 3:
                    b, g, r = img_small[y, x]
                    r, g, b = float(r) / 255.0, float(g) / 255.0, float(b) / 255.0
                    brightness_val = 0.299 * r + 0.587 * g + 0.114 * b
                    saturation_factor = 1.5
                    if brightness_val > 0:
                        sat = max(0, max(r, g, b) - min(r, g, b)) / brightness_val
                        sat = min(sat * saturation_factor, 1.0)
                        if sat > 0:
                            if r == brightness_val:
                                r = brightness_val + (r - brightness_val) * saturation_factor
                            if g == brightness_val:
                                g = brightness_val + (g - brightness_val) * saturation_factor
                            if b == brightness_val:
                                b = brightness_val + (b - brightness_val) * saturation_factor
                    contrast_factor = 1.3
                    brightness_boost = 0.05
                    r = min(1.0, max(0.0, (r - 0.5) * contrast_factor + 0.5 + brightness_boost))
                    g = min(1.0, max(0.0, (g - 0.5) * contrast_factor + 0.5 + brightness_boost))
                    b = min(1.0, max(0.0, (b - 0.5) * contrast_factor + 0.5 + brightness_boost))
                    line_colors.append((int(r * 255), int(g * 255), int(b * 255)))
                else:
                    val = int(brightness[y, x])
                    line_colors.append((val, val, val))
        
        res_strs.append(line_str)
        if return_colors:
            colors.append(line_colors)
    
    if return_colors:
        return res_strs, colors
    return res_strs