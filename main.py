import cv2
import numpy as np
import time
import os
import shutil
import gc
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

import drawer
import getTxt
import cv2 as cv
import argparse


def get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return 'ffmpeg'


def check_ffmpeg():
    try:
        ffmpeg_path = get_ffmpeg_path()
        result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def add_audio_to_video(input_video, output_video):
    if not os.path.exists(input_video):
        print(f'警告: 视频文件不存在: {input_video}')
        return False

    ffmpeg_path = get_ffmpeg_path()
    if not os.path.exists(ffmpeg_path):
        print('警告: ffmpeg 未安装，无法添加音频')
        return False

    temp_output = output_video.replace('.mp4', '_temp.mp4').replace('.avi', '_temp.avi')

    cmd = [ffmpeg_path, '-i', output_video, '-i', input_video, '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v', '-map', '1:a?', '-y', temp_output]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and os.path.exists(temp_output):
            if os.path.exists(output_video):
                os.remove(output_video)
            os.rename(temp_output, output_video)
            print('音频已添加到视频！')
            return True
        else:
            print(f'添加音频失败: {result.stderr}')
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
    except Exception as e:
        print(f'添加音频异常: {str(e)}')
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False


def arg_parse():
    parser = argparse.ArgumentParser(
        usage="python %(prog)s [参数名] [参数值]"
    )
    parser.add_argument(
        "--input", help="输入的视频或图片文件路径", required=True, type=str
    )
    parser.add_argument(
        "--output_dir", help="输出目录", default='./output', type=str
    )
    parser.add_argument(
        "--frames_dir", help="中转帧图片目录", default='./frames_output', type=str
    )
    parser.add_argument(
        "--name", help="输出文件名", default='output.' + str(int(time.time())), type=str
    )
    parser.add_argument(
        "--mp4", help="是否输出MP4格式文件，仅在--pic参数为false时有效（默认avi）", action='store_true', default=False
    )
    parser.add_argument(
        "--times", help="视频转字符块分辨率下降的倍数，建议不小于4。该数值越小，处理越慢。（默认为6）", default=8, type=int
    )
    parser.add_argument(
        "--keep_audio", help="是否需要保留音频（默认保留）", action='store_true', default=True
    )
    parser.add_argument(
        "--pic", help="是否处理图片（要求--input参数指向一张图片。默认为否，表示处理文本）", action='store_true', default=False
    )
    parser.add_argument(
        "--mapping_str", help="与灰阶相映射的字符集，不建议改动，不支持中文字符", default='MN#HQ$OC?&>!:-. ', type=str
    )
    parser.add_argument(
        "--keep_frames", help="是否保留中转帧图片（默认删除）", action='store_true', default=False
    )
    parser.add_argument(
        "--skip_frames", help="跳帧处理，每N帧处理1帧（例如2表示每2帧处理1帧，跳过1帧）。默认为1（处理所有帧）", default=1, type=int
    )
    parser.add_argument(
        "--threads", help="并行处理的线程数，默认为4", default=4, type=int
    )
    parser.add_argument(
        "--color", help="是否使用彩色模式（默认黑白）", action='store_true', default=False
    )
    options, _ = parser.parse_known_args()
    return options


opt = arg_parse()


def process_single_frame(args):
    frame_data, frame_num, times, mapping_str, w, h, frames_dir, use_color = args
    if use_color:
        strs, colors = getTxt.to_txt(frame_data, mapping_str, times, return_colors=True)
        txt_frame = drawer.draw(strs, (int(7 * w / times), int(7 * h / times)), colors)
    else:
        strs = getTxt.to_txt(frame_data, mapping_str, times)
        txt_frame = drawer.draw(strs, (int(7 * w / times), int(7 * h / times)))
    frame_path = os.path.join(frames_dir, f'frame_{frame_num:06d}.jpg')
    cv.imwrite(frame_path, np.asarray(txt_frame))
    del txt_frame
    return frame_num


def generate_video():
    video = cv.VideoCapture(opt.input)
    times = opt.times
    w, h = int(video.get(cv.CAP_PROP_FRAME_WIDTH)), int(video.get(cv.CAP_PROP_FRAME_HEIGHT))
    print(f'视频尺寸: {w}x{h}')

    fps = video.get(cv.CAP_PROP_FPS)
    frame_count = video.get(cv.CAP_PROP_FRAME_COUNT)

    frames_dir = opt.frames_dir
    if not os.path.exists(frames_dir):
        os.makedirs(frames_dir)
    print(f'中转帧图片目录: {frames_dir}')
    print(f'跳帧设置: 每{opt.skip_frames}帧处理1帧')
    print(f'并行线程数: {opt.threads}')

    skip = opt.skip_frames
    threads = opt.threads

    original_video_path = None
    if opt.keep_audio and opt.input:
        original_video_path = opt.input
        print('将保留原视频音频')

    frames_to_process = []
    frame_mapping = {}

    print('正在读取视频帧...')
    use_color = opt.color
    print(f'彩色模式: {"是" if use_color else "否"}')
    cnt = 0
    actual_cnt = 0
    while video.isOpened():
        ret, frame = video.read()
        if not ret:
            break
        cnt += 1
        if cnt % skip != 0:
            continue
        actual_cnt += 1
        if use_color:
            frame_data = frame
        else:
            frame_data = cv.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames_to_process.append((frame_data, actual_cnt, times, opt.mapping_str, w, h, frames_dir, use_color))
        frame_mapping[actual_cnt] = cnt
        del frame

    video.release()
    del video
    gc.collect()
    print(f'总帧数: {int(frame_count)}，将处理: {actual_cnt} 帧 (跳帧比: 1/{skip})')

    start_time = time.time()

    if threads > 1:
        print(f'使用 {threads} 线程并行处理...')
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = {executor.submit(process_single_frame, args): args[1] for args in frames_to_process}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % 10 == 0 or completed == actual_cnt:
                    elapsed = time.time() - start_time
                    progress = (completed / actual_cnt) * 100
                    remaining = (elapsed / completed) * (actual_cnt - completed) if completed > 0 else 0
                    print(f'\r处理进度: [{completed}/{actual_cnt}] {progress:.1f}% | 已用时: {int(elapsed)}s | 预计剩余: {int(remaining)}s', end='', flush=True)
    else:
        print('使用单线程处理...')
        for i, args in enumerate(frames_to_process):
            process_single_frame(args)
            if (i + 1) % 10 == 0 or (i + 1) == len(frames_to_process):
                elapsed = time.time() - start_time
                progress = ((i + 1) / len(frames_to_process)) * 100
                remaining = (elapsed / (i + 1)) * (len(frames_to_process) - i - 1) if (i + 1) > 0 else 0
                print(f'\r处理进度: [{i+1}/{actual_cnt}] {progress:.1f}% | 已用时: {int(elapsed)}s | 预计剩余: {int(remaining)}s', end='', flush=True)

    del frames_to_process
    gc.collect()
    print(f'\n帧处理完成！共处理 {actual_cnt} 帧，耗时 {int(time.time() - start_time)} 秒')

    print('正在合并图片...')
    merge_start_time = time.time()

    output_dir = opt.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    first_frame = cv.imread(os.path.join(frames_dir, 'frame_000001.jpg'))
    nh, nw, _ = first_frame.shape

    if opt.mp4:
        suffix = '.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'avc1')
    else:
        suffix = '.avi'
        fourcc = cv2.VideoWriter_fourcc(*'XVID')

    full_name = os.path.join(output_dir, opt.name + suffix)
    out_fps = int(fps / skip + 0.5)

    try:
        res_video = cv2.VideoWriter(
            full_name,
            fourcc,
            out_fps,
            (nw, nh)
        )

        if not res_video.isOpened():
            print(f'警告: 视频写入器初始化失败，尝试使用MJPEG编码...')
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            res_video = cv2.VideoWriter(full_name, fourcc, out_fps, (nw, nh))

        res_video.write(first_frame)
        del first_frame

        for i in range(2, actual_cnt + 1):
            frame_path = os.path.join(frames_dir, f'frame_{i:06d}.jpg')
            frame_img = cv.imread(frame_path)
            if frame_img is None:
                print(f'警告: 无法读取帧 {i}')
                continue
            res_video.write(frame_img)
            del frame_img
            if i % 50 == 0:
                merge_elapsed = time.time() - merge_start_time
                progress = (i / actual_cnt) * 100
                print(f'\r合并进度: [{i}/{actual_cnt}] {progress:.1f}% | 已用时: {int(merge_elapsed)}s', end='', flush=True)
                gc.collect()

        res_video.release()
        del res_video
        print(f'\n视频合并完成！耗时 {int(time.time() - merge_start_time)} 秒')

        if opt.keep_audio and original_video_path:
            print('正在添加音频到视频...')
            if add_audio_to_video(original_video_path, full_name):
                print('音频添加成功！')
            else:
                print('音频添加失败，将保留无声视频')

    except Exception as e:
        print(f'视频合并失败: {str(e)}')
        if 'res_video' in locals():
            del res_video
        raise

    if opt.keep_frames:
        print(f'保留中转帧图片目录: {frames_dir}')
    else:
        if os.path.exists(frames_dir):
            try:
                shutil.rmtree(frames_dir)
                print(f'已删除中转帧图片目录: {frames_dir}')
            except Exception as e:
                print(f'删除帧目录失败: {str(e)}')
        else:
            print(f'中转帧图片目录不存在，无需删除')

    gc.collect()
    print(f"转换成功！视频保存为：{full_name}")
    print(f"输出帧率: {out_fps} fps (原: {int(fps)} fps)")


def generate_pic():
    use_color = opt.color
    if use_color:
        img = cv.imread(opt.input)
        strs, colors = getTxt.to_txt(img, opt.mapping_str, opt.times, return_colors=True)
        times = opt.times
        h, w = img.shape[:2]
        txt_img = np.asarray(drawer.draw(strs, (int(7 * w / times), int(7 * h / times)), colors))
    else:
        img = cv.imread(opt.input, 0)
        strs = getTxt.to_txt(img, opt.mapping_str, opt.times)
        times = opt.times
        h, w = img.shape
        txt_img = np.asarray(drawer.draw(strs, (int(7 * w / times), int(7 * h / times))))
    output_dir = opt.output_dir
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    full_name = os.path.join(output_dir, opt.name + '.jpg')
    cv.imwrite(full_name, txt_img)
    print("转换成功！图片保存为：" + full_name)


if __name__ == '__main__':
    if not opt.pic:
        generate_video()
    else:
        generate_pic()
