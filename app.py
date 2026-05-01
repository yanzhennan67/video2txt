from flask import Flask, request, jsonify, send_from_directory
import os
import subprocess
import tempfile
import uuid
import logging
from logging.handlers import RotatingFileHandler
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['OUTPUT_FOLDER'] = './output'
app.config['LOG_FOLDER'] = './logs'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs(app.config['LOG_FOLDER'], exist_ok=True)

log_file = os.path.join(app.config['LOG_FOLDER'], 'web_process.log')
file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))
logger = logging.getLogger('web_processor')
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)

progress_store = {}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/generate', methods=['POST'])
def generate_video():
    try:
        if 'video' not in request.files:
            return jsonify({'success': False, 'error': '请上传视频文件'})

        video_file = request.files['video']
        if video_file.filename == '':
            return jsonify({'success': False, 'error': '请选择视频文件'})

        task_id = str(uuid.uuid4())
        temp_filename = f"temp_{task_id}.mp4"
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
        video_file.save(temp_path)

        times = request.form.get('times', '8')
        color = request.form.get('color', 'false')
        keep_audio = request.form.get('keep_audio', 'true')
        keep_frames = request.form.get('keep_frames', 'false')
        mp4 = request.form.get('mp4', 'false')
        name = request.form.get('name', f'output_{int(uuid.uuid4().time)}')
        mapping_str = request.form.get('mapping_str', 'MN#HQ$OC?&>!:-. ')
        skip_frames = request.form.get('skip_frames', '1')
        threads = request.form.get('threads', '4')

        logger.info(f"[{task_id}] 接收参数: keep_frames={keep_frames}, keep_audio={keep_audio}, color={color}, mp4={mp4}")

        output_name = name or f'output_{int(uuid.uuid4().time)}'

        frames_dir = os.path.join('./frames_output', f'frames_{task_id[:8]}')

        command = ['python', 'main.py', '--input', temp_path, '--name', output_name,
                   '--output_dir', './output', '--times', times,
                   '--frames_dir', frames_dir,
                   '--skip_frames', skip_frames, '--threads', threads]

        if color == 'true':
            command.append('--color')

        if keep_audio == 'true':
            command.append('--keep_audio')

        if keep_frames == 'true':
            command.append('--keep_frames')

        if mp4 == 'true':
            command.append('--mp4')

        command.extend(['--mapping_str', mapping_str])

        progress_store[task_id] = {
            'progress': 0,
            'message': '准备中...',
            'status': 'pending'
        }

        thread = threading.Thread(target=process_video, args=(task_id, temp_path, command))
        thread.daemon = True
        thread.start()

        logger.info(f"[{task_id}] 任务已启动，跳帧={skip_frames}，线程={threads}")
        return jsonify({'success': True, 'task_id': task_id})

    except Exception as e:
        logger.error(f"生成失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

def process_video(task_id, temp_path, command):
    """后台处理视频"""
    logger.info(f"[{task_id}] 开始处理视频")
    try:
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors='replace',
            env=env
        )

        output_file = None
        logger.info(f"[{task_id}] 开始读取子进程输出...")
        for line in process.stdout:
            line = line.strip()
            logger.info(f"[{task_id}] [DEBUG] 读取到行: {repr(line)}")

            if '处理进度:' in line and '[' in line and ']' in line and '%' in line:
                try:
                    bracket_start = line.find('[')
                    bracket_end = line.find(']')
                    if bracket_start != -1 and bracket_end != -1:
                        progress_str = line[bracket_start+1:bracket_end]
                        parts = progress_str.split('/')
                        if len(parts) >= 2:
                            current = int(parts[0].strip())
                            total = int(parts[1].strip())
                            if total > 0:
                                progress = min(int((current / total) * 60), 60)
                                progress_store[task_id] = {
                                    'progress': progress,
                                    'message': f'正在处理帧: {current}/{total}',
                                    'status': 'processing',
                                    'current_frame': current,
                                    'total_frames': total,
                                    'phase': 'processing'
                                }
                except Exception as e:
                    logger.error(f"[{task_id}] 解析处理进度失败: {str(e)}")

            if '合并进度:' in line and '[' in line and ']' in line and '%' in line:
                try:
                    bracket_start = line.find('[')
                    bracket_end = line.find(']')
                    if bracket_start != -1 and bracket_end != -1:
                        progress_str = line[bracket_start+1:bracket_end]
                        parts = progress_str.split('/')
                        if len(parts) >= 2:
                            current = int(parts[0].strip())
                            total = int(parts[1].strip())
                            if total > 0:
                                progress = 60 + min(int((current / total) * 30), 30)
                                progress_store[task_id] = {
                                    'progress': progress,
                                    'message': f'正在合并视频: {current}/{total}',
                                    'status': 'processing',
                                    'current_frame': current,
                                    'total_frames': total,
                                    'phase': 'merging'
                                }
                except Exception as e:
                    logger.error(f"[{task_id}] 解析合并进度失败: {str(e)}")

            if '帧处理完成' in line:
                progress_store[task_id] = {
                    'progress': 60,
                    'message': '帧处理完成，开始合并视频...',
                    'status': 'processing',
                    'phase': 'merging'
                }

            if '视频合并完成' in line:
                progress_store[task_id] = {
                    'progress': 90,
                    'message': '视频合并完成，正在清理...',
                    'status': 'processing',
                    'phase': 'audio'
                }

            if '正在添加音频' in line or '音频已添加到视频' in line or '音频添加成功' in line:
                progress_store[task_id] = {
                    'progress': 95,
                    'message': '正在处理音频...',
                    'status': 'processing',
                    'phase': 'audio'
                }

            if '转换成功' in line:
                output_file = line.split('保存为：')[-1].strip() if '保存为：' in line else None

          

        process.wait()
        logger.info(f"[{task_id}] 进程退出，返回码: {process.returncode}")

        if process.returncode == 0 and output_file:
            filename = os.path.basename(output_file)
            progress_store[task_id] = {
                'progress': 100,
                'message': '转换成功！',
                'status': 'completed',
                'filename': filename,
                'phase': 'completed'
            }
            logger.info(f"[{task_id}] 转换成功: {output_file}")
        else:
            logger.error(f"[{task_id}] 处理失败，返回码: {process.returncode}")
            progress_store[task_id] = {
                'progress': 0,
                'message': '处理失败',
                'status': 'error',
                'phase': 'error'
            }

    except Exception as e:
        logger.error(f"[{task_id}] 异常: {str(e)}")
        import traceback
        logger.error(f"[{task_id}] 详细错误:\n{traceback.format_exc()}")
        progress_store[task_id] = {
            'progress': 0,
            'message': f'错误: {str(e)}',
            'status': 'error'
        }
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    if task_id in progress_store:
        return jsonify({'success': True, 'data': progress_store[task_id]})
    else:
        return jsonify({'success': False, 'error': '任务不存在'})

@app.route('/api/preview')
def preview_video():
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({'success': False, 'error': '缺少文件名参数'})

        filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        if not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '文件不存在'})

        from flask import send_file
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filepath)
        return send_file(filepath, mimetype=mime_type or 'video/mp4')

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/history')
def get_history():
    try:
        files = []
        for filename in os.listdir(app.config['OUTPUT_FOLDER']):
            filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            if os.path.isfile(filepath) and filename.endswith(('.mp4', '.avi')):
                files.append({
                    'filename': filename,
                    'size': os.path.getsize(filepath),
                    'mtime': os.path.getmtime(filepath)
                })
        files.sort(key=lambda x: x['mtime'], reverse=True)
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/logs')
def get_logs():
    try:
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        logs = None
        for encoding in encodings:
            try:
                with open(log_file, 'r', encoding=encoding) as f:
                    logs = f.read()
                break
            except UnicodeDecodeError:
                continue

        if logs is None:
            logs = '[无法读取日志文件，请手动查看 logs/web_process.log]'

        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        return jsonify({'success': True, 'logs': f'[读取日志失败: {str(e)}]'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
