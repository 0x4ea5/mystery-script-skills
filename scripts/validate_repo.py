"""Validate the portable skill package without models, GPU, or third-party modules."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SKILLS = (
    'mystery-script-ocr', 'mystery-script-workflow', 'mystery-dm',
    'mystery-player', 'local-dialogue-audio',
)


def main():
    errors = []
    files = [p for p in ROOT.rglob('*') if p.is_file()
             and not any(part in {'.git', '__pycache__', '.venv'}
                         for part in p.relative_to(ROOT).parts)]
    for name in SKILLS:
        path = ROOT / 'skills' / name / 'SKILL.md'
        if not path.is_file():
            errors.append(f'Missing skill entrypoint: {name}')
            continue
        text = path.read_text(encoding='utf-8')
        header = re.match(r'\A---\n(.*?)\n---(?:\n|$)', text, re.S)
        if not header:
            errors.append(f'Invalid skill frontmatter: {name}')
        elif (not re.search(r'^name: ' + re.escape(name) + r'\s*$', header[1], re.M)
              or not re.search(r'^description: .+', header[1], re.M)):
            errors.append(f'Missing or inconsistent skill metadata: {name}')
    for path in files:
        if path.suffix.lower() not in {'.md', '.py', '.json', '.yaml', '.yml', '.html', '.txt'}:
            continue
        rel = path.relative_to(ROOT)
        try:
            text = path.read_text(encoding='utf-8')
            if '\ufffd' in text:
                errors.append(f'Replacement character in {rel}')
            if path.suffix == '.py':
                ast.parse(text, filename=str(rel))
            elif path.suffix == '.json':
                json.loads(text)
            elif path.suffix == '.md':
                # Local Markdown links must resolve inside the distributed package.
                for raw in re.findall(r'\[[^\]]*\]\(([^\n)]+)\)', text):
                    target = raw.strip().split(' "', 1)[0].strip('<>')
                    if target.startswith('#') or re.match(r'[a-zA-Z][\w+.-]*:', target):
                        continue
                    target = unquote(target.split('#', 1)[0])
                    dest = (path.parent / target).resolve()
                    if not dest.is_relative_to(ROOT) or not dest.exists():
                        errors.append(f'Broken or external local link in {rel}: {target}')
            if ('skills' in rel.parts and path.suffix != '.py'
                    and re.search(r'(?i)\b[a-z]:[\\/]|\\\\[a-z0-9.-]+\\[^\s\\]', text)):
                errors.append(f'Machine-specific path in {rel}')
        except (ValueError, SyntaxError, UnicodeError) as error:
            errors.append(f'{rel}: {error}')
    # The sample and bundled voice configuration must agree on speaker IDs.
    audio = ROOT / 'skills' / 'local-dialogue-audio'
    common_path = audio / 'scripts' / 'common.py'
    if common_path.is_file():
        try:
            spec = importlib.util.spec_from_file_location('audio_common', common_path)
            common = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(common)
            voices = json.loads((audio / 'assets' / 'voices' / '声线模板.json').read_text(encoding='utf-8'))
            if any(not voice.get('reference_text') or not voice.get('description')
                   for voice in voices.values()):
                errors.append('Voice templates need reference text and design descriptions')
            turns = common.parse_script((audio / 'assets' / 'example-dialogue.txt').read_text(encoding='utf-8'), voices)
            print(f'Example dialogue: {len(turns)} turns, {len(voices)} voice templates')
        except (OSError, ValueError, KeyError) as error:
            errors.append(f'Audio sample/configuration: {error}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Validated {len(SKILLS)} skills, local links, Python syntax, JSON, and dialogue sample.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
