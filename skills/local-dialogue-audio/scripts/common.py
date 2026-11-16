"""Shared source, voice and timing checks. No model or network initialization."""
import hashlib
import json
from pathlib import Path
import re

ASSETS = Path(__file__).resolve().parent.parent / 'assets'

def parse_script(text, voices):
    if text.count('=== 配音正文 ===') != 1 or text.count('=== 正文结束') != 1:
        raise ValueError('Require exactly one body start and one end marker')
    body = text.split('=== 配音正文 ===', 1)[1].split('=== 正文结束', 1)[0]
    chapter, turns = '', []
    for number, raw in enumerate(body.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('〔'):
            if not line.endswith('〕'):
                raise ValueError(f'Unclosed reading marker at body line {number}')
            continue
        if line.startswith('--- ') and line.endswith(' ---'):
            chapter = line[4:-4].strip()
            continue
        match = re.fullmatch(r'([A-Za-z][A-Za-z0-9_-]*)：(.*)', line)
        if not match or not match[2].strip():
            raise ValueError(f'Unrecognized body line {number}: {line}')
        speaker, spoken = match[1], match[2].strip()
        if speaker not in voices:
            raise ValueError(f'Unknown speaker: {speaker}')
        turns.append({'speaker': speaker, 'text': spoken, 'chapter': chapter})
    if not turns:
        raise ValueError('Empty dialogue')
    return turns

def voice_signature(refs, voices, models):
    signature = hashlib.sha256(b'local-dialogue-audio-v1')
    signature.update(str(Path(models).resolve()).encode('utf-8'))
    config = Path(models) / 'Qwen3-TTS-12Hz-1.7B-Base/config.json'
    if config.exists():
        signature.update(config.read_bytes())
    for speaker in sorted(voices):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', speaker) or not isinstance(voices[speaker].get('reference_text'), str) or not voices[speaker]['reference_text'].strip():
            raise ValueError('Voice ids must be safe identifiers with nonempty reference text')
        signature.update(speaker.encode('utf-8'))
        signature.update(voices[speaker]['reference_text'].encode('utf-8'))
        signature.update((Path(refs) / (speaker + '.wav')).read_bytes())
    return signature.hexdigest()

def stamp(seconds, srt=False):
    ms = round(seconds * 1000)
    value = f'{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}'
    return value + f',{ms % 1000:03d}' if srt else value

def read_manifest(path):
    path = Path(path).resolve()
    data = json.loads(path.read_text(encoding='utf-8'))
    chapters = data.get('chapters', [])
    if not chapters or len({c['id'] for c in chapters}) != len(chapters):
        raise ValueError('Need nonempty chapters with unique ids')
    for c in chapters:
        if re.search(r'[<>:\\/?*|]', c['id']) or c['id'] in ['.', '..']:
            raise ValueError('Chapter id must be a safe folder name')
        c['directory'] = (path.parent / c['folder']).resolve()
        c['source'] = (c['directory'] / c.get('script', '穿插对话稿.txt')).resolve()
        c.setdefault('name', c['id'] + '_七声线')
        if re.search(r'[<>:\\/?*|]', c['name']) or c['name'] in ['.', '..']:
            raise ValueError('Audio name must be a safe basename')
    return data
