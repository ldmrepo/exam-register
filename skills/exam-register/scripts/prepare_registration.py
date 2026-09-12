"""Gate before item_create: state, mechanical checks, source comparison, and creation intent in one step.

Passes only when the question is `reviewed`, `check_manifest` reports no errors and the source
comparison passed. On pass it records `registration.creation_status = intent_recorded` atomically
(no state transition, revision unchanged). A question that already has a document_id needs
--resume, which leaves the file untouched. It never calls the remote MCP.
"""
import argparse
import json
from pathlib import Path
from check_manifest import check_question, load_settings
from common import atomic_json, read_json


def prepare(path, root, resume=False):
    path = Path(path)
    q = read_json(path)
    errors = []
    if q['state'] != 'reviewed':
        errors.append(f"state must be reviewed before registration (is {q['state']})")
    if q['verification']['source']['status'] != 'passed':
        errors.append('source comparison must be passed before registration')
    errors.extend(check_question(q, root, load_settings(root)))
    reg = q['registration']
    if reg['document_id'] and not resume:
        errors.append('document_id already recorded; use --resume to continue an existing registration')
    if not reg['document_id'] and reg['creation_status'] in ('intent_recorded', 'uncertain') and not resume:
        errors.append('a previous creation intent has no document_id: check item_list for the document '
                      'before creating again, then rerun with --resume')
    if errors:
        return {'ok': False, 'errors': errors}
    if not resume:
        reg['creation_status'] = 'intent_recorded'
        atomic_json(path, q)
    return {'ok': True, 'operation_key': reg['operation_key'], 'document_id': reg['document_id'],
            'creation_status': reg['creation_status'], 'resume': resume}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('file', type=Path)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    result = prepare(a.file, a.workspace, a.resume)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
