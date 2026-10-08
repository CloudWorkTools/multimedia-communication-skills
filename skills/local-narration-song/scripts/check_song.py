#!/usr/bin/env python3
"""核對歌詞、獨立 ASR、SRT 及媒體完整性；不認證演唱自然度。"""
import argparse
import difflib
import json
import math
from pathlib import Path
import re
import subprocess
import unicodedata

from opencc import OpenCC

CC = OpenCC('t2s')


def normalize(text):
    text = re.sub(r'\[(?:verse|chorus|bridge|intro|outro|pre-chorus|instrumental)[^\]\n]*\]', '', text, flags=re.I)
    text = re.sub(r'<[^>]*>', '', text)
    return ''.join(c for c in CC.convert(unicodedata.normalize('NFKC', text)).casefold() if c.isalnum())


def read_lyrics(path):
    text = path.read_text(encoding='utf-8-sig')
    if path.suffix.lower() != '.json':
        return text
    data = json.loads(text)
    if isinstance(data, list):
        rows = data
    else:
        rows = next((data[k] for k in ['performance_lines', 'original_lines', 'lines'] if k in data), None)
        if rows is None:
            rows = [r for s in data['scenes'] for r in s.get('lines', s.get('cues', []))]
    return '\n'.join(r if isinstance(r, str) else r['text'] for r in rows)


def parse_srt(text):
    def stamp(t):
        match = re.fullmatch(r'(\d+):(\d{2}):(\d{2})[,.](\d{3})', t.strip())
        if not match:
            raise ValueError(f'非法 SRT 時間：{t}')
        h, m, s, ms = map(int, match.groups())
        if m >= 60 or s >= 60:
            raise ValueError(f'非法 SRT 時間：{t}')
        return h*3600+m*60+s+ms/1000
    rows = []
    for block in re.split(r'\n\s*\n', text.strip()):
        lines = block.splitlines()
        i = 1 if lines and lines[0].strip().isdigit() else 0
        if len(lines) <= i+1 or '-->' not in lines[i]:
            raise ValueError('SRT 缺少時間或字幕文字')
        a, b = lines[i].split('-->')
        rows.append({'start': stamp(a), 'end': stamp(b), 'text': '\n'.join(lines[i+1:])})
    return rows


def asr_words(data):
    words = [w for s in data.get('segments', []) for w in s.get('words', [])]
    chars, times = '', []
    for w in words:
        text = normalize(w['word'])
        chars += text
        # ponytail: 保留整詞範圍，不能將多字詞均分成虛假的逐字界。
        times.extend([(float(w['start']), float(w['end']))]*len(text))
    observed = normalize(data.get('text') or ''.join(s['text'] for s in data.get('segments', [])))
    return observed, times if chars == observed else []


def assess(expected, observed, captions, times, duration, tolerance=.3):
    expected, observed = normalize(expected), normalize(observed)
    errors, differences, mapping = [], [], {}
    if not expected:
        raise ValueError('採用歌詞不可為空')
    for kind, a, b, c, d in difflib.SequenceMatcher(None, expected, observed, autojunk=False).get_opcodes():
        if kind == 'equal':
            mapping.update(zip(range(a, b), range(c, d)))
        else:
            differences.append({'kind': kind, 'expected': expected[a:b], 'recognized': observed[c:d],
                                'expected_index': a, 'recognized_index': c})
    if normalize(''.join(c['text'] for c in captions)) != expected:
        errors.append('字幕全文與採用歌詞不同')
    checks, cursor = [], 0
    for i, row in enumerate(captions):
        a, b = row['start'], row['end']
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration+.001):
            errors.append(f'字幕 {i+1} 時間超界或長度非法')
        if i and a < captions[i-1]['end']-.001:
            errors.append(f'字幕 {i+1} 與上一句重疊或倒序')
        text = normalize(row['text'])
        item = {'line': i+1, 'text': row['text'], 'subtitle_start': a, 'subtitle_end': b,
                'timing_status': 'unverified'}
        first, last = mapping.get(cursor), mapping.get(cursor+len(text)-1)
        if text and times and first is not None and last is not None and last < len(times):
            start, end = times[first][0], times[last][1]
            if math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration+.1:
                delta = [a-start, b-end]
                item.update({'asr_word_start': start, 'asr_word_end': end,
                             'delta_seconds': delta, 'asr_boundaries_are_whole_words': True,
                             'timing_status': 'review' if max(map(abs, delta)) > tolerance else 'within_tolerance'})
        checks.append(item)
        cursor += len(text)
    if not captions:
        errors.append('沒有字幕')
    review = bool(differences) or any(c['timing_status'] != 'within_tolerance' for c in checks)
    status = 'technical_errors' if errors else 'review_required' if review else 'automated_checks_passed_manual_review_pending'
    return {'status': status, 'expected_characters': len(expected), 'recognized_characters': len(observed),
            'asr_differences': differences,
            'possible_omissions': [d for d in differences if d['kind']=='delete' or len(d['expected'])>len(d['recognized'])],
            'possible_additions': [d for d in differences if d['kind']=='insert' or len(d['recognized'])>len(d['expected'])],
            'technical_errors': errors, 'subtitle_checks': checks, 'timing_tolerance_seconds': tolerance,
            'diff_method': 'SequenceMatcher; ASR 差異是疑點，不是真實漏字的證明',
            'human_listening_verified': False, 'manual_review_pending': ['字音與漏唱聽辨', '節奏與旋律自然度', '和聲、換氣、接縫及音色'],
            'exit_code': 2 if errors else 1 if review else 0}


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def self_test():
    captions = parse_srt('1\n00:00:00,100 --> 00:00:01,900\n方形圓形\n')
    times = [(.1, .5), (.5, .9), (.9, 1.3), (1.3, 1.9)]
    ok = assess('方形圓形', '方形圆形', captions, times, 2)
    assert ok['exit_code'] == 0 and not ok['human_listening_verified']
    missing = assess('方形圓形', '方形形', captions, [times[0], times[1], times[3]], 2)
    assert missing['exit_code'] == 1 and missing['possible_omissions'][0]['expected'] == '圆'
    shifted = assess('方形圓形', '方形圆形', [dict(captions[0], start=.9)], times, 2)
    assert shifted['exit_code'] == 1 and shifted['subtitle_checks'][0]['timing_status'] == 'review'
    wrong = assess('方形圓形', '方形圆形', [dict(captions[0], text='方形', end=3)], times, 2)
    assert wrong['exit_code'] == 2 and len(wrong['technical_errors']) == 2
    assert assess('方形圓形', '方形圆形', captions, [], 2)['exit_code'] == 1
    repeated = [dict(captions[0], text='你你我')]
    assert assess('你你我', '你我', repeated, [], 2)['possible_omissions'][0]['expected'] == '你'
    assert normalize('[Verse 1]\n你你／AI') == '你你ai'
    print('通過：繁簡、重複字、漏字疑點、字幕偏移、文字／時間錯誤與缺少詞界的檢查。')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['lyrics', 'asr', 'subtitles', 'audio', 'video', 'report']:
        p.add_argument('--'+name, type=Path)
    p.add_argument('--tolerance', type=float, default=.3)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
        return
    if not all([args.lyrics, args.asr, args.subtitles, args.audio, args.report]):
        p.error('需要 --lyrics --asr --subtitles --audio --report')
    if args.report.resolve() in [f.resolve() for f in [args.lyrics,args.asr,args.subtitles,args.audio,args.video] if f]:
        p.error('檢查報告不能覆寫輸入檔案')
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        p.error('tolerance 需為非負有限值')
    try:
        media = probe(args.audio)
        duration = float(media['format']['duration'])
        if not math.isfinite(duration) or duration <= 0 or not any(s['codec_type']=='audio' for s in media['streams']):
            raise ValueError('音檔需有完整音軌及有效長度')
        observed, times = asr_words(json.loads(args.asr.read_text(encoding='utf-8-sig')))
        report = assess(read_lyrics(args.lyrics), observed, parse_srt(args.subtitles.read_text(encoding='utf-8-sig')), times, duration, args.tolerance)
        report['audio_duration_seconds'] = duration
        if args.video:
            video = probe(args.video)
            streams = {s['codec_type']: s for s in video['streams']}
            if not {'video', 'audio'} <= streams.keys():
                report['technical_errors'].append('影片缺少畫面或音軌')
            for kind in ['audio', 'video']:
                if kind in streams:
                    length = float(streams[kind].get('duration', video['format']['duration']))
                    if not math.isfinite(length) or abs(length-duration) > .1:
                        report['technical_errors'].append(f'影片 {kind} 長度與完整歌曲差異超過 0.1 秒')
            report['video_duration_seconds'] = float(video['format']['duration'])
        if report['technical_errors']:
            report.update(status='technical_errors', exit_code=2)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as e:
        report = {'status': 'technical_errors', 'technical_errors': [str(e)], 'human_listening_verified': False, 'exit_code': 2}
    report['inputs'] = {k: str(getattr(args,k).resolve()) for k in ['lyrics','asr','subtitles','audio','video'] if getattr(args,k)}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:report.get(k) for k in ['status','expected_characters','recognized_characters','exit_code']},ensure_ascii=False))
    raise SystemExit(report['exit_code'])


if __name__ == '__main__':
    main()
