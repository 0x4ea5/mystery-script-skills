"""Check a reviewed dialogue manifest, resume chapter rendering, and package audio."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from common import ASSETS, parse_script, read_manifest, stamp, voice_signature

def run(command):
    result = subprocess.run(command, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', errors='replace')[-6000:])
    return result

def escape_metadata(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\\n').replace('=', '\\=').replace(';', '\\;').replace('#', '\\#')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=ASSETS / 'voices')
    parser.add_argument('--voices', type=Path, default=ASSETS / 'voices/声线模板.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--name', default='全流程模拟_穿插对话')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--batch-size', type=int, default=8)
    args = parser.parse_args()
    assert args.name and not re.search(r'[<>:\\/?*|]', args.name) and args.name not in ['.', '..']
    manifest = read_manifest(args.manifest)
    items = manifest['chapters']
    assert len({str(c['directory']) for c in items}) == len(items), 'Use a separate folder for each chapter'
    voices = json.loads(args.voices.read_text(encoding='utf-8'))
    assert (args.models / 'Qwen3-TTS-12Hz-1.7B-Base/config.json').is_file(), 'Missing local Base model'
    signature = voice_signature(args.references, voices, args.models)
    for c in items:
        assert c.get('reviewed') is True, f"Adaptation gate check pending: {c['id']}"
        c['source_text'] = c['source'].read_text(encoding='utf-8')
        c['turns'] = parse_script(c['source_text'], voices)
        c['sha'] = hashlib.sha256(c['source_text'].encode('utf-8')).hexdigest()
    if args.check:
        print(json.dumps({'chapters': len(items), 'turns': sum(len(c['turns']) for c in items), 'speakers': sorted({t['speaker'] for c in items for t in c['turns']}), 'voice_signature': signature}, ensure_ascii=False))
        return
    for c in items:
        state_path = c['directory'] / '本地配音制作状态.json'
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
        reusable = state.get('status') == 'complete' and state.get('script_sha256') == c['sha'] and state.get('voice_signature') == signature and state.get('output', {}).get('path') == c['name'] + '.mp3'
        if args.render and not reusable:
            log = c['directory'] / '配音运行.log'
            print('Rendering:', c['id'], flush=True)
            with log.open('a', encoding='utf-8') as handle:
                result = subprocess.run([sys.executable, '-X', 'utf8', '-u', str(Path(__file__).with_name('render_dialogue.py')), '--script', str(c['source']), '--output', str(c['directory']), '--models', str(args.models.resolve()), '--references', str(args.references.resolve()), '--voices', str(args.voices.resolve()), '--name', c['name'], '--batch-size', str(args.batch_size)], stdout=handle, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f"Rendering stopped: {c['id']}; inspect {log}")
            state = json.loads(state_path.read_text(encoding='utf-8'))
        assert state.get('status') == 'complete' and state.get('script_sha256') == c['sha'] and state.get('voice_signature') == signature and state.get('output', {}).get('path') == c['name'] + '.mp3', f"Render missing or changed: {c['id']}"
        output = state['output']
        assert [(t['speaker'], t['text']) for t in output['turns']] == [(t['speaker'], t['text']) for t in c['turns']], f"Turn order mismatch: {c['id']}"
        for t in output['turns']:
            assert max(0.3, len(t['text']) / 12) < t['duration_seconds'] < max(12, len(t['text']) / 2 + 6), 'Suspicious speech duration'
        c['state'] = state
        c['wav'] = c['directory'] / Path(output['path']).with_suffix('.wav').name
        c['mp3'] = c['directory'] / output['path']
        c['info'] = sf.info(c['wav'])
        assert c['info'].samplerate == 24000 and c['info'].channels == 1
        assert abs(c['info'].duration - output['duration_seconds']) < 0.02

    destination = (args.output or args.manifest.resolve().parent / '成品').resolve()
    assert destination not in [c['directory'] for c in items], 'Package into a separate output folder'
    destination.mkdir(parents=True, exist_ok=True)
    chapter_data, text_data, subtitles, scripts = [], [], [], []
    total_frames, sub_number, rate = 0, 0, 24000
    gap = float(manifest.get('chapter_gap_seconds', 3))
    assert 0 <= gap <= 30
    master_wav = destination / (args.name + '.wav')
    with sf.SoundFile(master_wav, 'w', samplerate=rate, channels=1, subtype='PCM_16') as target:
        for i, c in enumerate(items):
            output = c['state']['output']
            start = total_frames / rate
            with sf.SoundFile(c['wav']) as audio:
                for block in audio.blocks(blocksize=rate * 30, dtype='int16'):
                    target.write(block)
            total_frames += c['info'].frames
            if i + 1 < len(items):
                target.write(np.zeros(round(rate * gap), dtype='int16'))
                total_frames += round(rate * gap)
            part = destination / '分章' / c['id']
            part.mkdir(parents=True, exist_ok=True)
            for suffix in ['.mp3', '.srt']:
                shutil.copy2(c['mp3'].with_suffix(suffix), part / c['mp3'].with_suffix(suffix).name)
            (part / '穿插对话稿.txt').write_text(c['source_text'], encoding='utf-8')
            chapter_data.append({'round': c['id'], 'title': c['title'], 'start_seconds': start, 'duration_seconds': c['info'].duration, 'audio': (part / c['mp3'].name).relative_to(destination).as_posix(), 'segments': output['chapters']})
            text_data.append([{'speaker': voices[t['speaker']].get('label', t['speaker']), 'text': t['text'], 'start': t['start_seconds']} for t in output['turns']])
            scripts.append(c['id'] + ' ' + c['title'] + '\n\n' + c['source_text'])
            for t in output['turns']:
                sub_number += 1
                begin = start + t['start_seconds']
                subtitles.extend([str(sub_number), stamp(begin, True) + ' --> ' + stamp(begin + t['duration_seconds'], True), voices[t['speaker']].get('label', t['speaker']) + '：' + t['text'], ''])
    duration = total_frames / rate
    metadata = [';FFMETADATA1', 'title=' + escape_metadata(manifest.get('title', args.name)), 'artist=AI合成声线']
    for i, c in enumerate(chapter_data):
        end = chapter_data[i + 1]['start_seconds'] if i + 1 < len(items) else duration
        metadata.extend(['[CHAPTER]', 'TIMEBASE=1/1000', f"START={round(c['start_seconds'] * 1000)}", f'END={round(end * 1000)}', 'title=' + escape_metadata(c['round'] + ' ' + c['title'])])
    meta_file = destination / '整段章节.ffmetadata'
    meta_file.write_text('\n'.join(metadata) + '\n', encoding='utf-8')
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    master_mp3 = destination / (args.name + '.mp3')
    run([ffmpeg, '-v', 'error', '-nostdin', '-y', '-i', str(master_wav), '-f', 'ffmetadata', '-i', str(meta_file), '-map', '0:a', '-map_metadata', '1', '-map_chapters', '1', '-af', 'loudnorm=I=-18:TP=-1.5:LRA=11', '-codec:a', 'libmp3lame', '-b:a', '128k', str(master_mp3)])
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(master_mp3)], capture_output=True)
    assert len(re.findall(r'Chapter #0:\d+', probe.stderr.decode('utf-8', errors='replace'))) == len(items)
    for audio in [master_mp3] + [destination / c['audio'] for c in chapter_data]:
        run([ffmpeg, '-v', 'error', '-nostdin', '-i', str(audio), '-f', 'null', '-'])
    (destination / (args.name + '.srt')).write_text('\n'.join(subtitles), encoding='utf-8')
    (destination / '全流程对白稿.txt').write_text('\n\n'.join(scripts), encoding='utf-8')
    (destination / '章节时间.txt').write_text('\n'.join(stamp(c['start_seconds']) + ' ' + c['round'] + ' ' + c['title'] for c in chapter_data), encoding='utf-8')
    storage_key = 'local-dialogue-audio:' + hashlib.sha256(str(args.manifest.resolve()).encode('utf-8')).hexdigest()[:16]
    data = json.dumps({'chapters': chapter_data, 'turns': text_data, 'master': master_mp3.name, 'storageKey': storage_key}, ensure_ascii=False).replace('</', r'<\/')
    page = (ASSETS / 'player.html').read_text(encoding='utf-8').replace('__DATA__', data).replace('__TITLE__', html.escape(manifest.get('title', args.name)))
    (destination / '打开这里听.html').write_text(page, encoding='utf-8')
    note = f'AI合成配音。{len(items)}章，{sub_number}段发言，{stamp(duration)}。\n按次发言对齐字幕；非逐字人工听校。\n' + manifest.get('source_note', '口语对话改编；阅读节点和出处见对白稿。')
    (destination / '收听说明.txt').write_text(note, encoding='utf-8')
    templates = destination / '固定声线'
    templates.mkdir(exist_ok=True)
    for key in voices:
        shutil.copy2(args.references / (key + '.wav'), templates / (key + '.wav'))
    (templates / '声线模板.json').write_text(json.dumps(voices, ensure_ascii=False, indent=2), encoding='utf-8')
    report = {'status': 'complete', 'chapters': len(items), 'turns': sub_number, 'seconds': duration, 'voice_signature': signature, 'ordered_text_matches': True, 'all_mp3_decoded': True, 'embedded_chapters': len(items)}
    (destination / '成品核验.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    package = destination / (args.name + '_音频与对白稿.zip')
    members = [master_mp3, master_mp3.with_suffix('.srt')] + [destination / name for name in ['全流程对白稿.txt', '章节时间.txt', '打开这里听.html', '收听说明.txt', '成品核验.json']]
    members += [templates / (key + '.wav') for key in voices] + [templates / '声线模板.json']
    for c in chapter_data:
        audio = destination / c['audio']
        members += [audio, audio.with_suffix('.srt'), audio.parent / '穿插对话稿.txt']
    with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for f in members:
            archive.write(f, f.relative_to(destination).as_posix())
    with zipfile.ZipFile(package) as archive:
        assert archive.testzip() is None
    print(json.dumps(dict(report, mp3=str(master_mp3), package=str(package)), ensure_ascii=False))

if __name__ == '__main__':
    main()
