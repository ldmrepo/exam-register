"""Atomic, version-checked local state transitions; never sends a remote write."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
from common import read_json,atomic_json
from check_manifest import check_question

NEXT={'planned':{'extracted'},'extracted':{'reviewed'},'reviewed':{'registered'},'registered':{'verified'},
      'needs_revision':{'extracted','reviewed','registered'},'blocked':{'planned','extracted','reviewed','registered'},'verified':set()}

def transition(path,root,state,expected,evidence,resume=None):
    path=Path(path);lock=path.with_suffix(path.suffix+'.lock')
    # One writer per question. A stale lock must be inspected before recovery.
    handle=lock.open('x')
    try:
        with handle:
            q=read_json(path)
            if q['revision']!=expected: raise ValueError('Local revision conflict')
            if state not in NEXT[q['state']] | {'blocked','needs_revision'}: raise ValueError('Invalid state transition')
            previous=q['state'];q['state']=state;q['resume_from']=resume
            q['revision']+=1
            q['history'].append({'from':previous,'to':state,'at':datetime.now(timezone.utc).isoformat(),'evidence':evidence})
            errors=check_question(q,root)
            if errors:raise ValueError('; '.join(errors))
            atomic_json(path,q)
    finally:
        lock.unlink()
    return q['revision']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--state',required=True);p.add_argument('--expected-revision',type=int,required=True)
    p.add_argument('--evidence',required=True);p.add_argument('--resume-from');a=p.parse_args()
    print(transition(a.file,a.workspace,a.state,a.expected_revision,a.evidence,a.resume_from))
