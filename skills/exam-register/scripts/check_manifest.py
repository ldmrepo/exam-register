"""Schema, file, hash, coordinate, reference, and state checks. Not semantic validation."""
import argparse
import json
from pathlib import Path
from PIL import Image
from jsonschema import Draft202012Validator
from common import read_json, local_path, digest, valid_box

SKILL=Path(__file__).resolve().parents[1]
DEFAULT_ASSET_MAX_BYTES=5242880  # 서버 ASSET_MAX_BYTES 기본값. 배포마다 config/settings.local.json 의 asset_max_bytes 로 맞춘다.

def load_settings(root):
    path=Path(root)/'config/settings.local.json'
    return read_json(path) if path.is_file() else {}

def check_question(q,root,settings=None):
    if settings is None: settings=load_settings(root)
    asset_max=int(settings.get('asset_max_bytes',DEFAULT_ASSET_MAX_BYTES))
    errors=[f'{list(e.path)}: {e.message}' for e in Draft202012Validator(read_json(SKILL/'schemas/question.schema.json')).iter_errors(q)]
    if errors: return errors
    def file_record(record,image=False):
        try:
            path=local_path(root,record['path'])
            if digest(path)!=record['sha256']: errors.append('Hash mismatch: '+record['path'])
            if image:
                with Image.open(path) as im:
                    if list(im.size)!=record['size']: errors.append('Image size mismatch: '+record['path'])
            if 'bytes' in record:
                actual=path.stat().st_size
                if actual!=record['bytes']: errors.append('Byte size mismatch: '+record['path'])
                if actual>asset_max: errors.append(f'Asset exceeds server limit ({actual} > {asset_max} bytes): '+record['path'])
        except (OSError,ValueError) as e: errors.append(str(e))
    file_record(q['source'])
    pages={}
    for page in q['pages']:
        if page['page'] in pages: errors.append('Duplicate page number')
        pages[page['page']]=page
        file_record(page,True)
        if page['source_sha256']!=q['source']['sha256']: errors.append('Page source hash mismatch')
    ids=[]
    for e in q['elements']:
        ids.append(e['id'])
        for r in e['regions']:
            try: valid_box(r['bbox'],pages[r['page']]['size'])
            except (KeyError,ValueError) as ex: errors.append('Invalid region for '+e['id']+': '+str(ex))
        if e['representation']=='image':
            if e['asset'] is None: errors.append('Image lacks asset: '+e['id']); continue
            file_record(e['asset'],True)
            if len(e['regions'])!=1: errors.append('Use one image element per page/crop')
            else:
                b=e['regions'][0]['bbox']
                if e['asset']['size'] != [b[2]-b[0],b[3]-b[1]]: errors.append('Crop dimensions mismatch: '+e['id'])
                try:
                    with Image.open(local_path(root,pages[e['regions'][0]['page']]['path'])) as original, Image.open(local_path(root,e['asset']['path'])) as actual:
                        valid_box(b,original.size)
                        if original.crop(b).convert('RGBA').tobytes()!=actual.convert('RGBA').tobytes():
                            errors.append('Crop pixels differ from recorded source: '+e['id'])
                except (OSError,ValueError,KeyError) as ex: errors.append(str(ex))
            if e['text']: errors.append('Image must not be replaced with text: '+e['id'])
            if not e['alt']: errors.append('Image lacks alt description: '+e['id'])
        elif e['asset'] is not None: errors.append('Non-image element has asset')
    if len(ids)!=len(set(ids)): errors.append('Duplicate element ID')
    if [e['order'] for e in q['elements']]!=list(range(1,len(ids)+1)): errors.append('Element order must be contiguous from 1')
    for r in q['regions']:
        try: valid_box(r['bbox'],pages[r['page']]['size'])
        except (KeyError,ValueError) as ex: errors.append('Invalid question region: '+str(ex))
    choices=[c['id'] for c in q['choices']]
    if len(choices)!=len(set(choices)): errors.append('Duplicate choice ID')
    if any(not set(c['element_ids']).issubset(ids) for c in q['choices']): errors.append('Unresolved choice element reference')
    if q['interaction']=='choice' and (len(choices)<2 or q['max_choices']>len(choices)): errors.append('Invalid choice count')
    if q['interaction']=='short_answer' and choices: errors.append('Short answer cannot have choices')
    if q['answer']['status']=='confirmed':
        if not q['answer']['evidence']: errors.append('Confirmed answer lacks evidence')
        if q['interaction']=='choice' and (not q['answer']['values'] or not set(q['answer']['values']).issubset(choices)):
            errors.append('Invalid answer choice references')
        if q['interaction']=='choice' and len(q['answer']['values'])>q['max_choices']: errors.append('More answers than allowed selections')
    if q['answer']['status']=='unknown' and q['registration']['answer_application']=='applied': errors.append('Unknown answer cannot be applied')
    if q['registration']['document_id'] and q['registration']['creation_status']!='confirmed': errors.append('Document ID needs confirmed creation status')
    for kind,v in q['verification'].items():
        if v['status']=='passed' and not v['evidence']: errors.append('Passed verification needs evidence: '+kind)
        for f in v['evidence']:
            try:
                if not local_path(root,f).is_file(): errors.append('Missing evidence: '+f)
            except ValueError as ex: errors.append(str(ex))
    if q['state'] in ['reviewed','registered','verified'] and q['verification']['source']['status']!='passed':
        errors.append('Source comparison must pass before reviewed/registered/verified')
    if q['state'] in ['registered','verified'] and not q['registration']['document_id']: errors.append('Missing registered document ID')
    if q['state']=='verified':
        if any(v['status']!='passed' for v in q['verification'].values()): errors.append('All verification stages must pass')
        if q['issues']: errors.append('Verified question has unresolved issues')
        if any(q['registration'][k] in ['pending','unsupported','failed'] for k in ['answer_application','points_application']):
            errors.append('Required answer/points application is incomplete')
    if q['state'] in ['blocked','needs_revision'] and not q['resume_from']: errors.append('Missing resume step')
    return errors

def check_run(run,root,settings=None):
    if settings is None: settings=load_settings(root)
    errors=[str(e.message) for e in Draft202012Validator(read_json(SKILL/'schemas/run.schema.json')).iter_errors(run)]
    if errors:return errors
    ids=[]; docs=[]
    for relative in run['questions']:
        try:
            q=read_json(local_path(root,relative)); ids.append(q['id'])
            errors.extend(relative+': '+e for e in check_question(q,root,settings))
            if q['registration']['document_id']: docs.append(q['registration']['document_id'])
            if not set(q['shared_material_ids']).issubset(run['shared_material_ids']): errors.append('Unknown shared material ID')
        except (OSError,ValueError,KeyError) as e: errors.append(str(e))
    for op in run['operations']:
        for k in ('request','response'):
            if op.get(k):
                try:
                    if not local_path(root,op[k]).is_file(): errors.append('Missing operation file: '+op[k])
                except ValueError as ex: errors.append(str(ex))
        if op['status'] in ('succeeded','failed') and not op.get('response'): errors.append('Operation '+op['key']+' has a final status but no recorded response')
    if len(ids)!=len(set(ids)): errors.append('Duplicate question IDs in run')
    if len(docs)!=len(set(docs)): errors.append('Multiple questions target the same document')
    return errors

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('file',type=Path);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--kind',choices=['question','run'],default='question');a=p.parse_args()
    errors=(check_run if a.kind=='run' else check_question)(read_json(a.file),a.workspace)
    print(json.dumps({'mechanical_pass':not errors,'errors':errors,'semantic_validation':'not_performed'},ensure_ascii=False,indent=2))
    raise SystemExit(bool(errors))
