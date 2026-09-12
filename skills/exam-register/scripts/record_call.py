"""Record one MCP call (request before, response after) atomically and track it in manifest.operations.

The script never calls the remote MCP. Codex saves the request JSON it is about to send,
runs this once (status: intent), performs the call, saves the response JSON, and runs this
again with --response (status: succeeded | failed | uncertain). Authorization headers and
image bytes (dataBase64) are redacted before anything is written.
"""
import argparse
import json
import re
from pathlib import Path
from common import atomic_json, local_path, read_json

STEPS = ['create', 'upload', 'write', 'read', 'verify', 'update']
REDACT_KEYS = {'authorization', 'database64'}
SEQ = re.compile(r'^(\d{4})-')


def redact(value):
    if isinstance(value, dict):
        return {k: (f'<redacted:{len(v) if isinstance(v, str) else 0} bytes>' if k.lower() in REDACT_KEYS else redact(v))
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def classify(response):
    """intent | succeeded | failed | uncertain from a tool result (envelope or bare structuredContent)."""
    if response is None:
        return 'intent'
    if not isinstance(response, dict):
        return 'uncertain'
    if response.get('isError'):
        return 'failed'
    body = response.get('structuredContent', response)
    if not isinstance(body, dict):
        return 'uncertain'
    if 'code' in body and 'message' in body and 'results' not in body:
        return 'failed'  # tool error payload without the envelope flag
    results = body.get('results')
    if isinstance(results, list):
        if not results:
            return 'uncertain'
        return 'succeeded' if all(r.get('applied') is True for r in results) else 'failed'
    return 'succeeded'


def next_sequence(mcp_dir):
    numbers = [int(m.group(1)) for f in mcp_dir.glob('*.json') if (m := SEQ.match(f.name))]
    return max(numbers, default=0) + 1


def record(manifest, root, question, step, key, request, response=None, document_id=None):
    root = Path(root).resolve()
    manifest = Path(manifest).resolve()
    if not manifest.is_relative_to(root):
        raise ValueError('manifest must be inside the workspace')
    if step not in STEPS:
        raise ValueError('step must be one of ' + ', '.join(STEPS))
    run = read_json(manifest)
    request_body = redact(read_json(local_path(root, request)))
    response_body = None
    status = 'intent'
    if response is not None:
        response_path = local_path(root, response)
        try:
            response_body = redact(read_json(response_path))
            status = classify(response_body)
        except (OSError, ValueError):
            status = 'uncertain'
    mcp_dir = manifest.parent / 'mcp'
    mcp_dir.mkdir(parents=True, exist_ok=True)
    ops = run.setdefault('operations', [])
    existing = next((op for op in ops if op['key'] == key), None)
    rel = lambda p: p.relative_to(root).as_posix()

    request_file = None
    if existing and existing.get('request'):
        previous = local_path(root, existing['request'])
        if previous.is_file() and read_json(previous) == request_body:
            request_file = previous
    if request_file is None:
        request_file = mcp_dir / f'{next_sequence(mcp_dir):04d}-{step}-{question}.request.json'
        atomic_json(request_file, request_body)
    response_file = None
    if response is not None:
        response_file = request_file.with_name(request_file.name.replace('.request.json', '.response.json'))
        atomic_json(response_file, response_body if response_body is not None else {'unparsed': True})

    if document_id is None:
        if existing and existing.get('document_id'):
            document_id = existing['document_id']
        elif isinstance(response_body, dict):
            body = response_body.get('structuredContent', response_body)
            if isinstance(body, dict):
                document_id = body.get('documentId') or (body.get('id') if step == 'create' else None)
    entry = {'key': key, 'question_id': question, 'step': step, 'status': status, 'document_id': document_id,
             'evidence': rel(response_file or request_file), 'request': rel(request_file),
             'response': rel(response_file) if response_file else None}
    if existing:
        index = ops.index(existing)
        ops[index] = entry
    else:
        ops.append(entry)
        index = len(ops) - 1
    atomic_json(manifest, run)
    return {'status': status, 'index': index, 'request': entry['request'], 'response': entry['response'],
            'document_id': document_id}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--question', required=True)
    p.add_argument('--step', required=True, choices=STEPS)
    p.add_argument('--key', required=True)
    p.add_argument('--request', required=True, help='request JSON, path relative to the workspace')
    p.add_argument('--response', help='response JSON, path relative to the workspace')
    p.add_argument('--document-id')
    a = p.parse_args()
    print(json.dumps(record(a.manifest, a.workspace, a.question, a.step, a.key, a.request, a.response, a.document_id),
                     ensure_ascii=False, indent=2))
