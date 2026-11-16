"""Local Qwen3-TTS voice design, stable voice reuse, and turn-ordered rendering."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / 'assets'
OUT = SOURCE = MODELS = REFS = CLIPS = None
VOICES = dict()
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import imageio_ffmpeg
import numpy as np
import soundfile as sf
import torch

from common import parse_script, voice_signature



def checkpoint(state):
    temp = OUT / '本地配音制作状态.tmp'
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(OUT / '本地配音制作状态.json')


def ellipsis_pause(text):
    """A line containing only a written ellipsis is a pause, not spoken words."""
    stripped = re.sub(r'[\s“”‘’「」『』]', '', text)
    return bool(re.fullmatch(r'(?:…+|⋯+|\.{3,}|。{3,})', stripped))


def synthesis_text(text):
    # Some printed chants stretch every character with two em dashes. Supply
    # audible commas instead; retain the exact printed text in scripts/captions.
    if re.fullmatch(r'(?:——[\u3400-\u9fff])+——', text):
        return '，'.join(re.findall(r'[\u3400-\u9fff]', text)) + '。'
    return text


def validate(path, chars=1, pause=False):
    audio, sr = sf.read(str(path), dtype='float32')
    assert audio.ndim == 1 and sr > 0
    duration = len(audio) / sr
    if pause:
        assert np.isfinite(audio).all() and abs(duration - 0.65) <= 1 / sr
        assert np.count_nonzero(audio) == 0, 'Written ellipsis must be an explicit silent pause'
        return duration
    assert np.isfinite(audio).all() and duration > max(0.3, chars / 12)
    if chars > 1:
        assert duration < max(12, chars / 2 + 6), 'Unusually long speech; possible repetition'
    assert np.sqrt(np.mean(audio.astype(np.float64) ** 2)) > 0.0005
    return duration


def archive_invalid(path):
    folder = path.parent / '_需重配'
    folder.mkdir(exist_ok=True)
    path.rename(folder / (path.stem + '_' + str(time.time_ns()) + path.suffix))


def load_model(kind):
    from qwen_tts import Qwen3TTSModel
    name = 'Qwen3-TTS-12Hz-1.7B-' + kind
    print('Loading local model:', name, flush=True)
    return Qwen3TTSModel.from_pretrained(str(MODELS / name), device_map='cuda:0', dtype=torch.bfloat16, attn_implementation='sdpa', local_files_only=True)


def create_references(state):
    state['references_ready'] = [key for key in VOICES if (REFS / (key + '.wav')).exists()]
    checkpoint(state)
    missing = [key for key in VOICES if not (REFS / (key + '.wav')).exists()]
    if not missing:
        return
    model = load_model('VoiceDesign')
    for index, (key, config) in enumerate(VOICES.items()):
        target = REFS / (key + '.wav')
        if target.exists():
            validate(target, len(config['reference_text']))
            continue
        print('Designing fixed voice:', key, flush=True)
        torch.manual_seed(71000 + index)
        started = time.monotonic()
        with torch.inference_mode():
            waves, sr = model.generate_voice_design(text=config['reference_text'], language='Chinese', instruct=config['description'], max_new_tokens=1024)
        sf.write(str(target), waves[0], sr, subtype='PCM_16')
        duration = validate(target, len(config['reference_text']))
        config['reference_duration_seconds'] = round(duration, 3)
        config['generation_seconds'] = round(time.monotonic() - started, 2)
        (REFS / (key + '.txt')).write_text(config['reference_text'], encoding='utf-8')
        (REFS / '声线模板.json').write_text(json.dumps(VOICES, ensure_ascii=False, indent=2), encoding='utf-8')
        state['references_ready'] = [key for key in VOICES if (REFS / (key + '.wav')).exists()]
        checkpoint(state)
        print('Reference ready:', key, round(duration, 1), 'seconds', flush=True)
    del model
    gc.collect()
    torch.cuda.empty_cache()


def parse_turns():
    text = SOURCE.read_text(encoding='utf-8')
    result = parse_script(text, VOICES)
    signature = voice_signature(REFS, VOICES, MODELS)
    for turn in result:
        digest = hashlib.sha256((signature + '\n' + turn['speaker'] + '\n' + turn['text']).encode('utf-8')).hexdigest()[:20]
        turn['file'] = str(CLIPS / f"{turn['speaker']}_{digest}.wav")
        if ellipsis_pause(turn['text']):
            turn['delivery'] = 'written_ellipsis_pause'
    return text, result


def encode_mp3(wav, mp3):
    run = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin', '-y', '-i', str(wav), '-af', 'loudnorm=I=-18:TP=-1.5:LRA=11', '-codec:a', 'libmp3lame', '-b:a', '128k', str(mp3)], capture_output=True)
    if run.returncode:
        raise RuntimeError(run.stderr.decode('utf-8', errors='replace'))
    check = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-i', str(mp3), '-f', 'null', '-'], capture_output=True)
    assert check.returncode == 0


def combine(turns, name):
    result = []
    chapters = []
    elapsed = 0.0
    sample_rate = None
    previous_chapter = None
    for index, turn in enumerate(turns):
        audio, sr = sf.read(turn['file'], dtype='float32')
        if sample_rate is None:
            sample_rate = sr
        assert sr == sample_rate
        # Very short fades prevent clicks without cutting speech.
        fade = min(round(sr * 0.004), len(audio) // 4)
        if fade:
            audio[:fade] *= np.linspace(0, 1, fade)
            audio[-fade:] *= np.linspace(1, 0, fade)
        if turn['chapter'] != previous_chapter:
            chapters.append({'title': turn['chapter'], 'seconds': round(elapsed, 3)})
            previous_chapter = turn['chapter']
        turn['start_seconds'] = round(elapsed, 3)
        result.append(audio)
        elapsed += len(audio) / sr
        if index < len(turns) - 1:
            gap = 0.2 if len(turn['text']) < 30 else 0.32
            result.append(np.zeros(round(sr * gap), dtype='float32'))
            elapsed += gap
    wav = OUT / (name + '.wav')
    sf.write(str(wav), np.concatenate(result), sample_rate, subtype='PCM_16')
    validate(wav)
    mp3 = OUT / (name + '.mp3')
    encode_mp3(wav, mp3)
    def subtitle_time(seconds):
        millis = round(seconds * 1000)
        return f'{millis // 3600000:02d}:{millis // 60000 % 60:02d}:{millis // 1000 % 60:02d},{millis % 1000:03d}'
    subtitles = []
    for i, turn in enumerate(turns, 1):
        speaker = VOICES[turn['speaker']].get('label', turn['speaker'])
        begin = turn['start_seconds']
        end = begin + turn['duration_seconds']
        subtitles += [str(i), subtitle_time(begin) + ' --> ' + subtitle_time(end), speaker + '：' + turn['text'], '']
    subtitle_path = OUT / (name + '.srt')
    subtitle_path.write_text('\n'.join(subtitles), encoding='utf-8')
    return {'path': mp3.name, 'subtitle': subtitle_path.name, 'duration_seconds': round(elapsed, 3), 'chapters': chapters, 'turns': turns}


def main():
    global SOURCE, OUT, REFS, CLIPS, MODELS, VOICES
    parser = argparse.ArgumentParser()
    parser.add_argument('--references-only', action='store_true')
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--script', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--references', type=Path, default=ASSETS / 'voices')
    parser.add_argument('--voices', type=Path, default=ASSETS / 'voices/声线模板.json')
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--assemble-only', action='store_true')
    parser.add_argument('--design-missing', action='store_true')
    parser.add_argument('--name', default=None)
    args = parser.parse_args()
    SOURCE, OUT, REFS = args.script.resolve(), args.output.resolve(), args.references.resolve()
    MODELS = args.models.resolve()
    VOICES = json.loads(args.voices.read_text(encoding='utf-8'))
    CLIPS = OUT / '本地配音分句'
    if args.design_missing:
        assert REFS != (ASSETS / 'voices').resolve(), 'Design new voices in a project folder, not installed skill assets'
        REFS.mkdir(parents=True, exist_ok=True)
    missing = [k for k in VOICES if not (REFS / (k + '.wav')).exists()]
    assert not missing or args.design_missing, f'Missing approved reference voices: {missing}'
    if missing:
        OUT.mkdir(parents=True, exist_ok=True)
        assert torch.cuda.is_available(), 'CUDA is unavailable'
        create_references({'status': 'designing_voices'})
    for key, config in VOICES.items():
        validate(REFS / (key + '.wav'), len(config['reference_text']))
    source_text, turns = parse_turns()
    if args.plan:
        print(json.dumps({'turns': turns, 'voice_signature': voice_signature(REFS, VOICES, MODELS)}, ensure_ascii=False, indent=2))
        return
    for folder in [OUT, CLIPS]:
        folder.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    state = {'voice_signature': voice_signature(REFS, VOICES, MODELS), 'status': 'preparing', 'engine': 'Qwen3-TTS 1.7B, local CUDA, VoiceDesign then Base voice reuse', 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU assembly', 'torch': torch.__version__, 'script_sha256': hashlib.sha256(source_text.encode('utf-8')).hexdigest(), 'references_ready': [], 'completed_turns': []}
    checkpoint(state)
    create_references(state)
    if args.references_only:
        state['status'] = 'references_ready'
        checkpoint(state)
        return
    selected = turns
    state.update(status='rendering', total_turns=len(selected))
    checkpoint(state)
    pending = []
    for index, turn in enumerate(selected, 1):
        target = Path(turn['file'])
        if target.exists():
            try:
                duration = validate(target, len(turn['text']), pause=ellipsis_pause(turn['text']))
            except AssertionError:
                archive_invalid(target)
                pending.append((index, turn))
            else:
                turn['duration_seconds'] = round(duration, 3)
                state['completed_turns'].append({'speaker': turn['speaker'], 'file': target.name, 'duration_seconds': round(duration, 3)})
        else:
            pending.append((index, turn))
    if not args.assemble_only:
        speech_pending = []
        for index, turn in pending:
            if not ellipsis_pause(turn['text']):
                speech_pending.append((index, turn))
                continue
            target = Path(turn['file'])
            rate = 24000
            sf.write(str(target), np.zeros(round(rate * 0.65), dtype='float32'), rate, subtype='PCM_16')
            duration = validate(target, len(turn['text']), pause=True)
            turn['duration_seconds'] = round(duration, 3)
            state['completed_turns'].append({'speaker': turn['speaker'], 'file': target.name,
                                             'duration_seconds': round(duration, 3),
                                             'delivery': 'written_ellipsis_pause'})
            print(f'Written ellipsis pause: {index}/{len(selected)}', flush=True)
        pending = speech_pending
    checkpoint(state)
    assert not (args.assemble_only and pending), f'Missing or invalid cached turns: {len(pending)}'
    if pending:
        assert torch.cuda.is_available(), 'CUDA is unavailable'
    model = load_model('Base') if pending else None
    prompts = {}
    batch_size = max(1, min(args.batch_size, 8))
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        for index, turn in batch:
            key = turn['speaker']
            if key not in prompts:
                reference, rate = sf.read(str(REFS / (key + '.wav')), dtype='float32')
                prompts[key] = model.create_voice_clone_prompt(ref_audio=(reference, rate), ref_text=VOICES[key]['reference_text'], x_vector_only_mode=False)
        print('Rendering batch:', [(index, turn['speaker']) for index, turn in batch], flush=True)
        for index, turn in batch:
            spoken = synthesis_text(turn['text'])
            if spoken != turn['text']:
                state.setdefault('synthesis_normalizations', []).append({'turn': index,
                    'original_text': turn['text'], 'synthesis_text': spoken,
                    'reason': 'Decorative chant dashes rendered as audible spacing; words unchanged'})
        checkpoint(state)
        torch.manual_seed(82000 + sum(int(hashlib.sha256(turn['text'].encode('utf-8')).hexdigest()[:6], 16) for _, turn in batch))
        with torch.inference_mode():
            waves, sr = model.generate_voice_clone(text=[synthesis_text(turn['text']) for _, turn in batch], language=['Chinese'] * len(batch), voice_clone_prompt=[prompts[turn['speaker']][0] for _, turn in batch], max_new_tokens=1024)
        assert len(waves) == len(batch)
        for (index, turn), audio in zip(batch, waves):
            target = Path(turn['file'])
            for attempt in range(3):
                sf.write(str(target), audio, sr, subtype='PCM_16')
                try:
                    duration = validate(target, len(turn['text']))
                    break
                except AssertionError:
                    archive_invalid(target)
                    state.setdefault('retakes', []).append({'turn': index, 'attempt': attempt + 1, 'reason': 'Audio validation failed; saved separate rejected take'})
                    checkpoint(state)
                    if attempt == 2:
                        raise
                    print('Retaking single turn:', index, 'attempt', attempt + 1, flush=True)
                    torch.manual_seed(92000 + index * 31 + attempt)
                    with torch.inference_mode():
                        retry, retry_sr = model.generate_voice_clone(text=synthesis_text(turn['text']), language='Chinese', voice_clone_prompt=prompts[turn['speaker']], max_new_tokens=1024)
                    audio, sr = retry[0], retry_sr
            turn['duration_seconds'] = round(duration, 3)
            state['completed_turns'].append({'speaker': turn['speaker'], 'file': target.name, 'duration_seconds': round(duration, 3)})
            checkpoint(state)
            print(f'Saved {index}/{len(selected)}: {duration:.1f}s', flush=True)
    state['status'] = 'assembling'
    checkpoint(state)
    name = args.name or SOURCE.stem
    assert name and not re.search(r'[<>:\\/?*|]', name) and name not in ['.', '..'], 'Use a plain output basename'
    output = combine(selected, name)
    state.update(status='complete', output=output)
    checkpoint(state)
    navigation = ['AI合成配音。按手册阅读门槛编排的穿插对话改编；非原始逐字桌录。', '', f'音频：{output["path"]}', f'时长：{output["duration_seconds"]:.1f}秒', '']
    for chapter in output['chapters']:
        seconds = int(chapter['seconds'])
        navigation.append(f'{seconds // 60:02d}:{seconds % 60:02d}  {chapter["title"]}')
    (OUT / (name + '_说明.txt')).write_text('\n'.join(navigation), encoding='utf-8')
    print(json.dumps({'status': state['status'], 'file': output['path'], 'seconds': output['duration_seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
