# -*- coding: utf-8 -*-
"""
英语听读练习 - 后端API
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi
import re
import os
import json

app = Flask(__name__)
CORS(app)

PROGRESS_DIR = os.path.join(os.path.dirname(__file__), 'progress_data')
os.makedirs(PROGRESS_DIR, exist_ok=True)


def extract_video_id(url):
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def split_into_segments(transcript, min_duration=15, max_duration=30):
    segments = []
    current = []
    current_start = None

    for entry in transcript:
        if current_start is None:
            current_start = entry['start']
        current.append(entry)
        duration = entry['start'] + entry['duration'] - current_start

        if duration >= max_duration:
            segments.append({
                'start': current_start,
                'end': entry['start'] + entry['duration'],
                'subtitles': current
            })
            current = []
            current_start = None
        elif duration >= min_duration and entry['text'].rstrip().endswith(('.', '!', '?')):
            segments.append({
                'start': current_start,
                'end': entry['start'] + entry['duration'],
                'subtitles': current
            })
            current = []
            current_start = None

    if current:
        segments.append({
            'start': current_start,
            'end': current[-1]['start'] + current[-1]['duration'],
            'subtitles': current
        })

    return segments


@app.route('/api/load_video', methods=['POST'])
def load_video():
    data = request.json
    url = data.get('url', '').strip()
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': '无法识别视频链接'}), 400

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=['en'])
        entries = []
        for s in transcript:
            entries.append({
                'start': s.start,
                'duration': s.duration,
                'text': s.text.strip()
            })
        segments = split_into_segments(entries)
        return jsonify({
            'videoId': video_id,
            'totalSegments': len(segments),
            'segments': segments
        })
    except Exception as e:
        return jsonify({'error': f'获取字幕失败: {str(e)}'}), 500


@app.route('/api/save_progress', methods=['POST'])
def save_progress():
    data = request.json
    nickname = data.get('nickname', '').strip()
    if not nickname:
        return jsonify({'error': '昵称不能为空'}), 400
    safe_name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', nickname)
    filepath = os.path.join(PROGRESS_DIR, f'{safe_name}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'status': 'ok'})


@app.route('/api/get_progress', methods=['GET'])
def get_progress():
    nickname = request.args.get('nickname', '').strip()
    if not nickname:
        return jsonify({'error': '昵称不能为空'}), 400
    safe_name = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', nickname)
    filepath = os.path.join(PROGRESS_DIR, f'{safe_name}.json')
    if not os.path.exists(filepath):
        return jsonify({'data': None})
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify({'data': data})


@app.route('/')
def index():
    return app.send_static_file('index.html')


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
