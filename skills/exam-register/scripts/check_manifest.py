"""Schema, file, hash, coordinate, reference, and state checks. Not semantic validation.

Passing here means the specification is internally consistent and its files are intact.
It says nothing about transcription accuracy, crop completeness, or what the editor shows.
"""
import argparse
import json
from pathlib import Path
from PIL import Image
from jsonschema import Draft202012Validator
from common import read_json, local_path, digest, valid_box

SKILL = Path(__file__).resolve().parents[1]
DEFAULT_ASSET_MAX_BYTES = 5242880  # 서버 ASSET_MAX_BYTES 기본값. 배포마다 config/settings.local.json 의 asset_max_bytes 로 맞춘다.
CAPTURE_SUFFIXES = ('.png', '.jpg', '.jpeg')
FINAL_STATES = ('reviewed', 'registered', 'verified')


def load_settings(root):
    path = Path(root) / 'config/settings.local.json'
    return read_json(path) if path.is_file() else {}


def schema_errors(name, value):
    schema = read_json(SKILL / 'schemas' / name)
    return [f'{list(e.path)}: {e.message}' for e in Draft202012Validator(schema).iter_errors(value)]


def _check_file_record(errors, root, record, asset_max, image=False):
    """Hash, image size, and byte size of one recorded file."""
    try:
        path = local_path(root, record['path'])
        if digest(path) != record['sha256']:
            errors.append('Hash mismatch: ' + record['path'])
        if image:
            with Image.open(path) as im:
                if list(im.size) != record['size']:
                    errors.append('Image size mismatch: ' + record['path'])
        if 'bytes' in record:
            actual = path.stat().st_size
            if actual != record['bytes']:
                errors.append('Byte size mismatch: ' + record['path'])
            if actual > asset_max:
                errors.append(f'Asset exceeds server limit ({actual} > {asset_max} bytes): ' + record['path'])
    except (OSError, ValueError) as e:
        errors.append(str(e))


def _check_pages(errors, q, root, asset_max):
    pages = {}
    for page in q['pages']:
        if page['page'] in pages:
            errors.append('Duplicate page number')
        pages[page['page']] = page
        _check_file_record(errors, root, page, asset_max, image=True)
        if page['source_sha256'] != q['source']['sha256']:
            errors.append('Page source hash mismatch')
    return pages


def _check_image_element(errors, e, root, pages, asset_max):
    if e['asset'] is None:
        errors.append('Image lacks asset: ' + e['id'])
        return
    _check_file_record(errors, root, e['asset'], asset_max, image=True)
    if len(e['regions']) != 1:
        errors.append('Use one image element per page/crop')
    else:
        b = e['regions'][0]['bbox']
        if e['asset']['size'] != [b[2] - b[0], b[3] - b[1]]:
            errors.append('Crop dimensions mismatch: ' + e['id'])
        try:
            page = pages[e['regions'][0]['page']]
            with Image.open(local_path(root, page['path'])) as original, \
                    Image.open(local_path(root, e['asset']['path'])) as actual:
                valid_box(b, original.size)
                if original.crop(b).convert('RGBA').tobytes() != actual.convert('RGBA').tobytes():
                    errors.append('Crop pixels differ from recorded source: ' + e['id'])
        except (OSError, ValueError, KeyError) as ex:
            errors.append(str(ex))
    if e['text']:
        errors.append('Image must not be replaced with text: ' + e['id'])
    if not e['alt']:
        errors.append('Image lacks alt description: ' + e['id'])


def _check_elements(errors, q, root, pages, asset_max):
    ids = []
    for e in q['elements']:
        ids.append(e['id'])
        for r in e['regions']:
            try:
                valid_box(r['bbox'], pages[r['page']]['size'])
            except (KeyError, ValueError) as ex:
                errors.append('Invalid region for ' + e['id'] + ': ' + str(ex))
        if e['representation'] == 'image':
            _check_image_element(errors, e, root, pages, asset_max)
        elif e['asset'] is not None:
            errors.append('Non-image element has asset')
    if len(ids) != len(set(ids)):
        errors.append('Duplicate element ID')
    if [e['order'] for e in q['elements']] != list(range(1, len(ids) + 1)):
        errors.append('Element order must be contiguous from 1')
    for r in q['regions']:
        try:
            valid_box(r['bbox'], pages[r['page']]['size'])
        except (KeyError, ValueError) as ex:
            errors.append('Invalid question region: ' + str(ex))
    return ids


def _check_choices_and_answer(errors, q, ids):
    choices = [c['id'] for c in q['choices']]
    if len(choices) != len(set(choices)):
        errors.append('Duplicate choice ID')
    if any(not set(c['element_ids']).issubset(ids) for c in q['choices']):
        errors.append('Unresolved choice element reference')
    if q['interaction'] == 'choice' and (len(choices) < 2 or q['max_choices'] > len(choices)):
        errors.append('Invalid choice count')
    if q['interaction'] == 'short_answer' and choices:
        errors.append('Short answer cannot have choices')
    answer = q['answer']
    if answer['status'] == 'confirmed':
        if not answer['evidence']:
            errors.append('Confirmed answer lacks evidence')
        if q['interaction'] == 'choice':
            if not answer['values'] or not set(answer['values']).issubset(choices):
                errors.append('Invalid answer choice references')
            if len(answer['values']) > q['max_choices']:
                errors.append('More answers than allowed selections')
    if answer['status'] == 'unknown' and q['registration']['answer_application'] == 'applied':
        errors.append('Unknown answer cannot be applied')


def _check_simulation_block(errors, q, root, asset_max):
    """명세 안의 앞뒤. 자산 HTML 자체는 check_simulation.py 가 본다."""
    sim = q['simulation']
    if q['interaction'] != 'simulation':
        if sim is not None:
            errors.append('Only a simulation item carries a simulation block')
        return
    if sim is None:
        errors.append('Simulation item has no simulation block')
        return
    if q['choices']:
        errors.append('Simulation has no choices')
    holders = [e for e in q['elements'] if e['representation'] == 'simulation']
    if len(holders) != 1:
        errors.append('Exactly one element represents the simulation')
    for e in holders:
        if e['semantic_type'] != 'simulation':
            errors.append('Simulation element needs semantic_type simulation: ' + e['id'])
        if e['asset'] is not None:
            errors.append('The simulation file is recorded in the simulation block, not element.asset')
    _check_file_record(errors, root, sim['asset'], asset_max)
    answer = q['answer']
    if answer['status'] == 'confirmed' and len(answer['values']) != 1:
        errors.append('A simulation answer is exactly one value string')


def _check_verification(errors, q, root):
    for kind, v in q['verification'].items():
        if v['status'] == 'passed' and not v['evidence']:
            errors.append('Passed verification needs evidence: ' + kind)
        if kind == 'visual' and v['status'] == 'passed' and \
                not any(f.lower().endswith(CAPTURE_SUFFIXES) for f in v['evidence']):
            errors.append('Visual pass needs a screen capture file (.png/.jpg) in evidence')
        for f in v['evidence']:
            try:
                if not local_path(root, f).is_file():
                    errors.append('Missing evidence: ' + f)
            except ValueError as ex:
                errors.append(str(ex))


def _check_registration_and_state(errors, q):
    reg = q['registration']
    if reg['document_id'] and reg['creation_status'] != 'confirmed':
        errors.append('Document ID needs confirmed creation status')
    state = q['state']
    if state in FINAL_STATES and q['verification']['source']['status'] != 'passed':
        errors.append('Source comparison must pass before reviewed/registered/verified')
    if state in ('registered', 'verified') and not reg['document_id']:
        errors.append('Missing registered document ID')
    if state == 'verified':
        if any(v['status'] != 'passed' for v in q['verification'].values()):
            errors.append('All verification stages must pass')
        if q['issues']:
            errors.append('Verified question has unresolved issues')
        if any(reg[k] in ('pending', 'unsupported', 'failed') for k in ('answer_application', 'points_application')):
            errors.append('Required answer/points application is incomplete')
    if state in ('blocked', 'needs_revision') and not q['resume_from']:
        errors.append('Missing resume step')


def check_question(q, root, settings=None):
    if settings is None:
        settings = load_settings(root)
    asset_max = int(settings.get('asset_max_bytes', DEFAULT_ASSET_MAX_BYTES))
    errors = schema_errors('question.schema.json', q)
    if errors:
        return errors
    _check_file_record(errors, root, q['source'], asset_max)
    pages = _check_pages(errors, q, root, asset_max)
    ids = _check_elements(errors, q, root, pages, asset_max)
    _check_choices_and_answer(errors, q, ids)
    _check_simulation_block(errors, q, root, asset_max)
    _check_verification(errors, q, root)
    _check_registration_and_state(errors, q)
    return errors


def _check_operations(errors, run, root):
    for op in run['operations']:
        for k in ('request', 'response'):
            if op.get(k):
                try:
                    if not local_path(root, op[k]).is_file():
                        errors.append('Missing operation file: ' + op[k])
                except ValueError as ex:
                    errors.append(str(ex))
        if op['status'] in ('succeeded', 'failed') and not op.get('response'):
            errors.append('Operation ' + op['key'] + ' has a final status but no recorded response')


def check_run(run, root, settings=None):
    if settings is None:
        settings = load_settings(root)
    errors = schema_errors('run.schema.json', run)
    if errors:
        return errors
    ids, docs = [], []
    for relative in run['questions']:
        try:
            q = read_json(local_path(root, relative))
            ids.append(q['id'])
            errors.extend(relative + ': ' + e for e in check_question(q, root, settings))
            if q['registration']['document_id']:
                docs.append(q['registration']['document_id'])
            if not set(q['shared_material_ids']).issubset(run['shared_material_ids']):
                errors.append('Unknown shared material ID')
        except (OSError, ValueError, KeyError) as e:
            errors.append(str(e))
    _check_operations(errors, run, root)
    if len(ids) != len(set(ids)):
        errors.append('Duplicate question IDs in run')
    if len(docs) != len(set(docs)):
        errors.append('Multiple questions target the same document')
    return errors


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--kind', choices=['question', 'run'], default='question')
    a = p.parse_args()
    check = check_run if a.kind == 'run' else check_question
    errors = check(read_json(a.file), a.workspace)
    print(json.dumps({'mechanical_pass': not errors, 'errors': errors, 'semantic_validation': 'not_performed'},
                     ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))
