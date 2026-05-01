import cv2
import numpy as np
import time
import os
import shutil
import gc
import argparse


def arg_parse():
    parser = argparse.ArgumentParser(
        usage="python merge_frames.py --frames_dir ./frames_output --name output"
    )
    parser.add_argument(
        "--frames_dir", help="中转帧图片目录", required=True, type=str
    )
    parser.add_argument(
        "--output_dir", help="输出目录", default='./output', type=str
    )
    parser.add_argument(
        "--name", help="输出文件名", required=True, type=str
    )
    parser.add_argument(
        "--fps", help="输出视频帧率", default=30, type=int
    )
    parser.add_argument(
        "--mp4", help="是否输出MP4格式文件", action='store_true', default=False
    )
    options = parser.parse_args()
    return options


def merge_frames():
    opt = arg_parse()

    frames_dir = opt.frames_dir
    output_dir = opt.output_dir

    if not os.path.exists(frames_dir):
        print(f'错误: 目录不存在 {frames_dir}')
        return

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    frame_files = [f for f in os.listdir(frames_dir) if f.endswith('.jpg')]
    if not frame_files:
        print(f'错误: 目录 {frames_dir} 中没有找到 .jpg 文件')
        return

    frame_files.sort()
    print(f'找到 {len(frame_files)} 个帧图片')

    first_frame = cv2.imread(os.path.join(frames_dir, frame_files[0]))
    if first_frame is None:
        print(f'错误: 无法读取第一帧 {frame_files[0]}')
        return

    nh, nw, _ = first_frame.shape
    print(f'视频尺寸: {nw}x{nh}')

    if opt.mp4:
        suffix = '.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    else:
        suffix = '.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')

    full_name = os.path.join(output_dir, opt.name + suffix)

    print(f'创建视频: {full_name}')
    print(f'帧率: {opt.fps} fps')

    res_video = cv2.VideoWriter(
        full_name,
        fourcc,
        opt.fps,
        (nw, nh)
    )

    if not res_video.isOpened():
        print(f'警告: 视频写入器初始化失败，尝试使用MJPEG编码...')
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        res_video = cv2.VideoWriter(full_name, fourcc, opt.fps, (nw, nh))

    if not res_video.isOpened():
        print(f'错误: 无法创建视频写入器')
        return

    res_video.write(first_frame)
    del first_frame

    start_time = time.time()
    total = len(frame_files)

    for i, filename in enumerate(frame_files[1:], 1):
        frame_path = os.path.join(frames_dir, filename)
        frame_img = cv2.imread(frame_path)
        if frame_img is None:
            print(f'警告: 无法读取帧 {filename}')
            continue
        res_video.write(frame_img)
        del frame_img

        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            progress = ((i + 1) / total) * 100
            remaining = (elapsed / (i + 1)) * (total - i - 1) if (i + 1) > 0 else 0
            print(f'\r合并进度: [{i+1}/{total}] {progress:.1f}% | 已用时: {int(elapsed)}s | 预计剩余: {int(remaining)}s', end='')
            gc.collect()

    res_video.release()
    print(f'\n视频合并完成！耗时 {int(time.time() - start_time)} 秒')
    print(f'视频保存为: {full_name}')

    file_size = os.path.getsize(full_name) / (1024 * 1024)
    print(f'文件大小: {file_size:.2f} MB')


if __name__ == '__main__':
    merge_frames()
