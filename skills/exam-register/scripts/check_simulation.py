"""Mechanical checks on a simulation asset file and its specification block.

Reads the HTML as bytes and text; it never runs the document. Conformance requirements
that need execution (1 ready timing, 2 response timing, 4 determinism, 9 change events,
12 restore) are outside its reach — the editor's handshake covers 1, 2, 3, 6, 10 and the
author checks the rest by operating the simulation. Passing here is not conformance.
"""
import argparse
import json
import re
from pathlib import Path
from common import read_json, local_path, digest

DEFAULT_ASSET_MAX_BYTES = 5242880  # 서버 ASSET_MAX_BYTES 기본값
VALUE_MAX_CHARS = 16 * 1024  # 계약 요건 3 — config · initial · 정답 공통
PROLOGUE_SCAN_BYTES = 4096  # 서버가 루트 이름을 찾는 범위와 같다

# 루트가 html 이 아닐 때 HTML 문서로 인정받는 표식 (서버 asset-validation.ts 와 같은 목록)
HTML_MARKERS = re.compile(r'<(?:html|head|body|meta|script|style|title|link)[\s>/]', re.I)

# 서빙 CSP 가 default-src 'none' 이라 바깥을 가리키는 것은 모두 조용히 차단된다.
EXTERNAL_ATTR = re.compile(r'''\b(?:src|href)\s*=\s*["']\s*(https?:)?//[^"']+''', re.I)
EXTERNAL_CSS = re.compile(r'@import\s+(?:url\()?\s*["\']?\s*(?:https?:)?//', re.I)
NETWORK_CALL = re.compile(r'\b(?:fetch\s*\(|XMLHttpRequest|new\s+WebSocket|navigator\.sendBeacon|EventSource)')

# 규약 문자열은 그대로 쓰여야 한다 — 이름을 바꿔 부를 수 있는 것이 아니다.
PROTOCOL = [
    ('qtiSim', r'\bqtiSim\b'),
    ('contract', r'\bcontract\b'),
    ("ready", r'["\']ready["\']'),
    ('response.get', r'response\.get'),
    ('requestId', r'\brequestId\b'),
    ('response.set', r'response\.set'),
    ('reset', r'["\']reset["\']'),
    ('mode', r'["\']mode["\']'),
    ('message listener', r'addEventListener\s*\(\s*["\']message["\']'),
    ('parent.postMessage', r'parent\.postMessage'),
]


def document_root_name(head):
    """DOCTYPE 이름, 없으면 첫 요소 이름. 마크업이 아니면 None. 서버 판정과 같은 규칙이다."""
    s = head
    while True:
        s = s.lstrip()
        if s.startswith('<?'):
            end = s.find('?>')
            if end < 0:
                return None
            s = s[end + 2:]
            continue
        if s.startswith('<!--'):
            end = s.find('-->')
            if end < 0:
                return None
            s = s[end + 3:]
            continue
        if re.match(r'^<!doctype', s, re.I):
            named = re.match(r'^<!doctype\s+([a-z][\w:.-]*)', s, re.I)
            if named:
                return named.group(1).lower()
            end = s.find('>')
            if end < 0:
                return None
            s = s[end + 1:]
            continue
        element = re.match(r'^<([a-z][\w:.-]*)', s, re.I)
        return element.group(1).lower() if element else None


def _check_asset_file(errors, checked, root, record, asset_max):
    try:
        path = local_path(root, record['path'])
        raw = path.read_bytes()
    except (OSError, ValueError) as e:
        errors.append(str(e))
        return None
    if digest(path) != record['sha256']:
        errors.append('Hash mismatch: ' + record['path'])
    if len(raw) != record['bytes']:
        errors.append('Byte size mismatch: ' + record['path'])
    if len(raw) > asset_max:
        errors.append(f'Asset exceeds server limit ({len(raw)} > {asset_max} bytes): ' + record['path'])

    head = raw[:PROLOGUE_SCAN_BYTES].decode('utf-8', 'replace').lstrip('﻿')
    name = document_root_name(head)
    checked['root_element'] = name
    if name is None:
        errors.append('Not a markup document — the server cannot classify it as a simulation')
    elif name == 'svg':
        errors.append('Root element is <svg>: the server classifies this as an image, not a simulation')
    elif name != 'html' and not HTML_MARKERS.search(head):
        errors.append('Root is <' + name + '> and no html/head/body/script marker in the first 4KB')
    return raw.decode('utf-8', 'replace')


def _check_self_contained(errors, checked, text):
    external = [m.group(0)[:80] for m in EXTERNAL_ATTR.finditer(text)]
    external += [m.group(0)[:80] for m in EXTERNAL_CSS.finditer(text)]
    calls = sorted({m.group(0).rstrip('( ') for m in NETWORK_CALL.finditer(text)})
    checked['external_references'] = external
    checked['network_calls'] = calls
    for ref in external:
        errors.append('External reference is blocked by the serving CSP: ' + ref)
    for call in calls:
        errors.append('Network call is blocked by the serving CSP: ' + call)


def _check_protocol(errors, checked, text):
    missing = [name for name, pattern in PROTOCOL if not re.search(pattern, text)]
    checked['protocol_missing'] = missing
    for name in missing:
        errors.append('Handshake string not found: ' + name)


def _contains(node, needle):
    """config 안 어딘가에 정답과 같은 값이 들어 있는가. 중첩과 이스케이프를 넘어 본다."""
    if node == needle:
        return True
    if isinstance(node, dict):
        return any(_contains(v, needle) for v in node.values())
    if isinstance(node, list):
        return any(_contains(v, needle) for v in node)
    return False


def _json_value(errors, checked, label, raw):
    if raw is None:
        checked[label] = None
        return None
    if len(raw) > VALUE_MAX_CHARS:
        errors.append(f'{label} exceeds {VALUE_MAX_CHARS} characters ({len(raw)})')
    try:
        parsed = json.loads(raw)
    except ValueError as e:
        errors.append(f'{label} is not JSON: {e}')
        return None
    checked[label] = raw
    return parsed


def check_simulation(question, root, settings=None):
    errors, checked = [], {}
    sim = question.get('simulation')
    if question['interaction'] != 'simulation':
        return {'simulation_pass': not sim, 'errors': [] if not sim else
                ['Non-simulation interaction carries a simulation block'], 'checked': {}, 'not_checked': []}
    if not sim:
        return {'simulation_pass': False, 'errors': ['Simulation item has no simulation block'],
                'checked': {}, 'not_checked': []}

    asset_max = int((settings or {}).get('asset_max_bytes', DEFAULT_ASSET_MAX_BYTES))
    text = _check_asset_file(errors, checked, root, sim['asset'], asset_max)
    if text is not None:
        _check_self_contained(errors, checked, text)
        _check_protocol(errors, checked, text)

    config = _json_value(errors, checked, 'config', sim['config'])
    _json_value(errors, checked, 'initial', sim['initial'])

    answer = question['answer']
    value = parsed_answer = None
    if answer['status'] == 'confirmed':
        if len(answer['values']) != 1:
            errors.append('A simulation answer is exactly one value string')
        else:
            value = answer['values'][0]
            parsed_answer = _json_value(errors, checked, 'answer', value)
    checked['answer_status'] = answer['status']

    # 정답과 출발 상태가 같으면 응시자가 아무것도 하지 않고 맞는다. 편집기는 경고하지 않는다.
    if value is not None and sim['initial'] is not None and value == sim['initial']:
        errors.append('Answer equals the starting state — the examinee passes without operating anything')
    # config 는 저장 HTML 에 그대로 나가 응시자가 읽는다 (요건 11).
    if value is not None and sim['config'] and (
            value in sim['config'] or (parsed_answer is not None and _contains(config, parsed_answer))):
        errors.append('The answer appears inside config, which the examinee can read')

    conf = sim['conformance']
    checked['editor_handshake'] = conf['editor_handshake']
    checked['author_checked'] = conf['author_checked']
    if question['state'] == 'verified':
        if conf['editor_handshake'] != 'passed':
            errors.append('Verified simulation needs a passed editor handshake')
        unchecked = [n for n in (4, 9, 12) if n not in conf['author_checked']]
        if unchecked:
            errors.append('Requirements the editor cannot check are unconfirmed: ' +
                          ', '.join(str(n) for n in unchecked))

    return {'simulation_pass': not errors, 'errors': errors, 'checked': checked,
            'not_checked': ['1 ready within 3s', '2 response within 1s', '4 determinism',
                            '9 response on every change', '12 restore from response.set',
                            'screen matches the source', 'the answer state is actually correct',
                            'keyboard operation works']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('question', type=Path)
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    settings_path = a.workspace / 'config/settings.local.json'
    settings = read_json(settings_path) if settings_path.is_file() else {}
    result = check_simulation(read_json(a.question), a.workspace, settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['simulation_pass'] else 1)
