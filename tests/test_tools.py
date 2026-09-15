import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
import fitz
from PIL import Image

SKILL=Path(__file__).resolve().parents[1]/'skills/exam-register'
sys.path.insert(0,str(SKILL/'scripts'))
from render_pdf import render
from crop_image import crop
from common import digest,atomic_json,read_json,local_path
from check_manifest import check_question
from record_state import transition
from record_call import record, classify
from check_manifest import check_run
from prepare_registration import prepare
from check_readback import compare
from check_simulation import check_simulation, document_root_name
FIX=Path(__file__).resolve().parent/'fixtures'

class MechanicalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.pdf=self.root/'source.pdf'
        doc=fitz.open();page=doc.new_page(width=300,height=400);page.insert_text((30,40),'Source fixture');doc.save(self.pdf);doc.close()
    def tearDown(self):self.temp.cleanup()
    def question(self):
        record=render(self.pdf,1,2,self.root/'cache')
        q=read_json(SKILL/'templates/question.json')
        q['source']['path']='source.pdf';q['source']['sha256']=digest(self.pdf)
        q['pages']=[{k:record[k] for k in ['sha256','size','source_sha256','page','scale']} | {'path':str(Path(record['path']).relative_to(self.root))}]
        q['regions']=[{'page':1,'bbox':[0,0,500,700]}]
        q['elements'][0]['regions']=[{'page':1,'bbox':[10,10,500,100]}]
        for i in range(2):
            e=copy.deepcopy(q['elements'][0]);e.update(id=f'c{i}',order=i+2,semantic_type='choice',text=str(i));q['elements'].append(e)
            q['choices'].append({'id':f'c{i}','label':str(i+1),'element_ids':[f'c{i}']})
        return q
    def test_cache_and_corruption_recovery(self):
        first=render(self.pdf,1,2,self.root/'cache');second=render(self.pdf,1,2,self.root/'cache')
        self.assertFalse(first['cache_hit']);self.assertTrue(second['cache_hit'])
        Image.new('RGB',(600,800),'black').save(first['path'])
        third=render(self.pdf,1,2,self.root/'cache');self.assertFalse(third['cache_hit']);self.assertEqual(third['sha256'],first['sha256'])
        Path(first['path']).write_bytes(b'corrupted')
        self.assertFalse(render(self.pdf,1,2,self.root/'cache')['cache_hit'])
        self.assertNotEqual(render(self.pdf,1,3,self.root/'cache')['path'],first['path'])
    def test_invalid_page_and_crop(self):
        with self.assertRaises(ValueError):render(self.pdf,0,2,self.root/'cache')
        r=render(self.pdf,1,2,self.root/'cache')
        for box in [[0,0,601,50],[10,10,5,20],[0,0,0,0]]:
            with self.assertRaises(ValueError):crop(r['path'],box,self.root/'bad.png')
        c=crop(r['path'],[20,30,120,230],self.root/'crop.png');self.assertEqual(c['size'],[100,200])
    def test_reject_false_completion_and_tamper(self):
        q=self.question();self.assertEqual(check_question(q,self.root),[])
        q['state']='verified';self.assertTrue(check_question(q,self.root))
        q=self.question();q['source']['sha256']='f'*64;self.assertTrue(check_question(q,self.root))
        q=self.question();q['choices'][0]['element_ids']=['missing'];self.assertTrue(check_question(q,self.root))
    def test_revision_and_failed_transition_preserve_record(self):
        q=self.question();p=self.root/'q.json';atomic_json(p,q)
        self.assertEqual(transition(p,self.root,'extracted',1,'local extraction'),2)
        with self.assertRaises(ValueError):transition(p,self.root,'reviewed',1,'stale revision')
        with self.assertRaises(ValueError):transition(p,self.root,'reviewed',2,'no actual review')
        self.assertEqual(read_json(p)['revision'],2)
        self.assertFalse(p.with_suffix('.json.lock').exists())
        self.assertEqual(transition(p,self.root,'blocked',2,'upload failed','upload'),3)
        self.assertEqual(read_json(p)['resume_from'],'upload')
    def test_path_escape(self):
        with self.assertRaises(ValueError):local_path(self.root,'../secret.txt')
    def image_question(self):
        q=self.question();source=self.root/q['pages'][0]['path']
        record=crop(source,[0,0,100,100],self.root/'asset.png')
        e=copy.deepcopy(q['elements'][0]);e.update(id='image',order=4,representation='image',semantic_type='image',text='',alt='source crop',regions=[{'page':1,'bbox':[0,0,100,100]}],asset={'path':'asset.png','sha256':record['sha256'],'size':[100,100],'bytes':record['bytes']})
        q['elements'].append(e);return q,record
    def test_asset_bytes_recorded_and_server_limit(self):
        q,record=self.image_question()
        self.assertEqual(record['bytes'],(self.root/'asset.png').stat().st_size);self.assertEqual(record['content_type'],'image/png')
        self.assertEqual(check_question(q,self.root),[])
        wrong=copy.deepcopy(q);wrong['elements'][-1]['asset']['bytes']=record['bytes']+1
        self.assertTrue(any('Byte size mismatch' in x for x in check_question(wrong,self.root)))
        self.assertTrue(any('exceeds server limit' in x for x in check_question(q,self.root,{'asset_max_bytes':10})))
        (self.root/'config').mkdir();atomic_json(self.root/'config/settings.local.json',{'asset_max_bytes':10})
        self.assertTrue(any('exceeds server limit' in x for x in check_question(q,self.root)))
    def manifest(self):
        m=read_json(SKILL/'templates/run.json');m['run_id']='r1';p=self.root/'runs/r1/manifest.json';atomic_json(p,m);return p
    def test_record_call_intent_then_response(self):
        m=self.manifest();req=self.root/'runs/r1/req.json'
        atomic_json(req,{'documentId':'d1','operations':[{'command':'item.prompt.set','payload':{'text':'q'}}],'headers':{'Authorization':'Bearer secret-token'}})
        first=record(m,self.root,'q1','write','k1','runs/r1/req.json')
        self.assertEqual(first['status'],'intent');self.assertIsNone(first['response'])
        saved=read_json(self.root/first['request']);self.assertNotIn('secret-token',json.dumps(saved));self.assertIn('redacted',saved['headers']['Authorization'])
        atomic_json(self.root/'runs/r1/res.json',{'structuredContent':{'status':'applied','results':[{'index':0,'applied':True}],'version':'v2'}})
        second=record(m,self.root,'q1','write','k1','runs/r1/req.json','runs/r1/res.json')
        ops=read_json(m)['operations']
        self.assertEqual(len(ops),1);self.assertEqual(ops[0]['status'],'succeeded');self.assertEqual(second['request'],first['request'])
        self.assertTrue((self.root/ops[0]['response']).is_file());self.assertEqual(check_run(read_json(m),self.root),[])
    def test_record_call_failure_uncertain_and_sequence(self):
        m=self.manifest();atomic_json(self.root/'runs/r1/req.json',{'documentId':'d1','operations':[]})
        atomic_json(self.root/'runs/r1/bad.json',{'isError':True,'structuredContent':{'code':'SCHEMA_MISMATCH','message':'x'}})
        self.assertEqual(record(m,self.root,'q1','write','k1','runs/r1/req.json','runs/r1/bad.json')['status'],'failed')
        atomic_json(self.root/'runs/r1/partial.json',{'results':[{'applied':True},{'applied':False,'status':'skipped'}]})
        self.assertEqual(record(m,self.root,'q1','write','k2','runs/r1/req.json','runs/r1/partial.json')['status'],'failed')
        (self.root/'runs/r1/broken.json').write_text('{not json',encoding='utf-8')
        self.assertEqual(record(m,self.root,'q2','upload','k3','runs/r1/req.json','runs/r1/broken.json')['status'],'uncertain')
        atomic_json(self.root/'runs/r1/created.json',{'structuredContent':{'id':'doc-9','title':'t'}})
        created=record(m,self.root,'q2','create','k4','runs/r1/req.json','runs/r1/created.json')
        self.assertEqual(created['document_id'],'doc-9')
        names=sorted(f.name for f in (self.root/'runs/r1/mcp').glob('*.request.json'))
        self.assertEqual([n[:4] for n in names],['0001','0002','0003','0004'])
        with self.assertRaises(ValueError):record(m,self.root,'q1','write','k5','../outside.json')
        with self.assertRaises(ValueError):record(m,self.root,'q1','delete','k6','runs/r1/req.json')
        self.assertEqual(classify(None),'intent');self.assertEqual(classify({'structuredContent':{'results':[]}}),'uncertain')
    def reviewed_question(self):
        q=self.question();(self.root/'runs').mkdir(exist_ok=True);(self.root/'runs/review.md').write_text('reviewed',encoding='utf-8')
        q['state']='reviewed';q['verification']['source']={'status':'passed','evidence':['runs/review.md'],'notes':''}
        for s in ['planned','extracted']: q['history'].append({'from':s,'to':'x','at':'2026-09-12T00:00:00+00:00','evidence':'e'})
        p=self.root/'q.json';atomic_json(p,q);return p
    def test_prepare_registration_gate(self):
        p=self.reviewed_question();q=read_json(p)
        q['state']='extracted';atomic_json(p,q);r=prepare(p,self.root);self.assertFalse(r['ok']);self.assertTrue(any('reviewed' in e for e in r['errors']))
        q=read_json(self.reviewed_question());q['verification']['source']['status']='pending';q['state']='extracted';atomic_json(p,q)
        self.assertTrue(any('source comparison' in e for e in prepare(p,self.root)['errors']))
        p=self.reviewed_question();before=read_json(p)['revision']
        r=prepare(p,self.root);self.assertTrue(r['ok']);after=read_json(p)
        self.assertEqual(after['registration']['creation_status'],'intent_recorded');self.assertEqual(after['revision'],before)
        r=prepare(p,self.root);self.assertFalse(r['ok']);self.assertTrue(any('previous creation intent' in e for e in r['errors']))
        after['registration']['document_id']='doc-1';after['registration']['creation_status']='confirmed';atomic_json(p,after)
        r=prepare(p,self.root);self.assertFalse(r['ok']);self.assertTrue(any('--resume' in e for e in r['errors']))
        snapshot=p.read_text(encoding='utf-8');r=prepare(p,self.root,resume=True)
        self.assertTrue(r['ok']);self.assertEqual(r['document_id'],'doc-1');self.assertEqual(p.read_text(encoding='utf-8'),snapshot)
    def test_visual_pass_requires_capture_file(self):
        q=self.question();(self.root/'runs').mkdir(exist_ok=True)
        (self.root/'runs/notes.md').write_text('seen in chat',encoding='utf-8');Image.new('RGB',(4,4),'white').save(self.root/'runs/shot.png')
        q['verification']['visual']={'status':'passed','evidence':['runs/notes.md'],'notes':''}
        self.assertTrue(any('screen capture' in e for e in check_question(q,self.root)))
        q['verification']['visual']['evidence'].append('runs/shot.png')
        self.assertFalse(any('screen capture' in e for e in check_question(q,self.root)))
    def readback_spec(self,image=False):
        q=self.question();q['elements']=[q['elements'][0]];q['choices']=[]
        def el(id,order,sem,rep,text='',**extra):
            e={'id':id,'order':order,'semantic_type':sem,'representation':rep,'reason':'fixture','regions':[{'page':1,'bbox':[0,0,10,10]}],'text':text,'asset':None,'alt':''};e.update(extra);return e
        if image:
            q['elements']=[el('prompt',1,'prompt','text','다음 창작 자료에 대한 설명으로 옳은 것은?'),el('img',2,'map','image','',alt='창작 지도 자료'),el('vb',3,'viewbox','text','○ 제목이 있는 창작 보기.',viewbox_title='<보기>')]
            texts=['자료의 구조를 보존한다.','자료를 임의의 표로 바꾼다.'];q['registration']['asset_ids']={'img':'asset-0001'}
        else:
            q['elements']=[el('prompt',1,'prompt','text','밑줄 친 <u>낱말</u>의 쓰임으로 알맞은 것은?'),el('vb',2,'viewbox','text','○ 창작 보기의 첫 문장이다.\n○ 창작 보기의 둘째 문장이다.',viewbox_title=None)]
            texts=['첫째 창작 선택지','둘째 창작 선택지','셋째 창작 선택지']
        n=len(q['elements'])
        for i,t in enumerate(texts,1):
            q['elements'].append(el(f'c{i}',n+i,'choice','text',t));q['choices'].append({'id':f'c{i}','label':str(i),'element_ids':[f'c{i}']})
        q['answer']={'status':'confirmed','values':['c1' if image else 'c3'],'evidence':'fixture'}
        return q
    def test_readback_matches_and_detects_differences(self):
        read=read_json(FIX/'readback-choice.json');q=self.readback_spec()
        self.assertEqual(compare(q,read)['errors'],[])
        swapped=copy.deepcopy(q);swapped['choices'][0],swapped['choices'][1]=swapped['choices'][1],swapped['choices'][0]
        self.assertTrue(any('Choice 1 text differs' in e for e in compare(swapped,read)['errors']))
        wrong=copy.deepcopy(q);wrong['answer']['values']=['c2'];self.assertTrue(any('Checked answers differ' in e for e in compare(wrong,read)['errors']))
        nou=copy.deepcopy(q);nou['elements'][0]['text']='밑줄 친 <u>쓰임</u>의 쓰임으로 알맞은 것은?'
        errs=compare(nou,read)['errors'];self.assertTrue(any('Underline missing' in e for e in errs))
        titled=copy.deepcopy(q);titled['elements'][1]['viewbox_title']='<보기>';self.assertTrue(any('Viewbox heading differs' in e for e in compare(titled,read)['errors']))
        self.assertFalse(compare(q,{'html':''})['structure_pass'])
        self.assertEqual(check_question(q,self.root),[])  # viewbox_title 은 스키마가 받는 선택 필드
    def test_readback_images_and_default_heading(self):
        read=read_json(FIX/'readback-image.json');q=self.readback_spec(image=True)
        self.assertEqual(compare(q,read)['errors'],[])
        missing=copy.deepcopy(q);missing['registration']['asset_ids']={'img':'asset-9999'};self.assertTrue(any('asset ids differ' in e for e in compare(missing,read)['errors']))
        untitled=copy.deepcopy(q);untitled['elements'][2]['viewbox_title']=None
        self.assertTrue(any("expected '', saved '<보기>'" in e for e in compare(untitled,read)['errors']))
    def test_check_run_duplicates(self):
        m=self.manifest();run=read_json(m)
        for name in ['a','b']:
            q=self.question();q['id']='same';atomic_json(self.root/f'runs/r1/{name}.json',q)
        run['questions']=['runs/r1/a.json','runs/r1/b.json'];self.assertIn('Duplicate question IDs in run',check_run(run,self.root))
        for name in ['a','b']:
            q=read_json(self.root/f'runs/r1/{name}.json');q['id']=name;q['registration'].update(document_id='doc-x',creation_status='confirmed');atomic_json(self.root/f'runs/r1/{name}.json',q)
        self.assertIn('Multiple questions target the same document',check_run(run,self.root))
        q=read_json(self.root/'runs/r1/b.json');q['registration']['document_id']='doc-y';atomic_json(self.root/'runs/r1/b.json',q)
        self.assertEqual(check_run(run,self.root),[])
        run['operations']=[{'key':'k','question_id':'a','step':'write','status':'succeeded','document_id':'doc-x','evidence':'runs/r1/a.json','request':None,'response':None}]
        self.assertTrue(any('no recorded response' in e for e in check_run(run,self.root)))
    def test_valid_hash_but_wrong_crop_pixels(self):
        q=self.question();source=self.root/q['pages'][0]['path']
        record=crop(source,[0,0,100,100],self.root/'asset.png')
        e=copy.deepcopy(q['elements'][0]);e.update(id='image',order=4,representation='image',semantic_type='image',text='',alt='source crop',regions=[{'page':1,'bbox':[0,0,100,100]}],asset={'path':'asset.png','sha256':record['sha256'],'size':[100,100],'bytes':record['bytes']})
        q['elements'].append(e);self.assertEqual(check_question(q,self.root),[])
        Image.new('RGB',(100,100),'black').save(self.root/'asset.png');e['asset']['sha256']=digest(self.root/'asset.png');e['asset']['bytes']=(self.root/'asset.png').stat().st_size
        self.assertTrue(any('Crop pixels differ' in x for x in check_question(q,self.root)))

    SIM_HTML=('<!DOCTYPE html><html><head><meta charset="utf-8"><title>t</title></head><body>'
        '<input id="d" type="range"><script>'
        'function send(t,e){var m={qtiSim:1,type:t};for(var k in e)m[k]=e[k];window.parent.postMessage(m,"*");}'
        'window.addEventListener("message",function(ev){var m=ev.data;if(!m||m.qtiSim!==1)return;'
        'if(m.type==="init"){}else if(m.type==="mode"){}else if(m.type==="response.set"){}'
        'else if(m.type==="response.get"){send("response",{value:{d:1},requestId:m.requestId});}'
        'else if(m.type==="reset"){}});'
        'send("ready",{contract:1,a11y:{description:"설명"}});</script></body></html>')
    def simulation(self,html=None):
        q=self.question();q.update(interaction='simulation',choices=[])
        q['elements']=[q['elements'][0],{'id':'stage','order':2,'semantic_type':'simulation','representation':'simulation',
            'reason':'답이 조작 결과의 상태다','regions':[{'page':1,'bbox':[10,110,500,400]}],'text':'','asset':None,'alt':'지레'}]
        path=self.root/'sim.html';path.write_text(html if html is not None else self.SIM_HTML,encoding='utf-8',newline='\n')
        q['answer']={'status':'confirmed','values':['{"d":2}'],'evidence':'author 모드에서 만든 상태'}
        q['simulation']={'asset':{'path':'sim.html','sha256':digest(path),'bytes':path.stat().st_size},
            'alt':'지레 균형','config':'{"m1":2}','seed':None,'initial':'{"d":5}','width':480,'height':None,
            'align':'center','conformance':{'editor_handshake':'pending','author_checked':[],'notes':''}}
        return q
    def test_simulation_asset_is_html_and_self_contained(self):
        q=self.simulation();self.assertEqual(check_question(q,self.root),[])
        self.assertEqual(check_simulation(q,self.root)['errors'],[])
        svg=self.simulation('<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><script>send("ready")</script></svg>')
        self.assertTrue(any('classifies this as an image' in e for e in check_simulation(svg,self.root)['errors']))
        cdn=self.simulation(self.SIM_HTML.replace('<body>','<body><script src="https://cdn.example/x.js"></script>'))
        self.assertTrue(any('External reference' in e for e in check_simulation(cdn,self.root)['errors']))
        net=self.simulation(self.SIM_HTML.replace('send("ready"','fetch("/x");send("ready"'))
        self.assertTrue(any('Network call' in e for e in check_simulation(net,self.root)['errors']))
        # 본문 안 인라인 svg 는 루트가 아니므로 시뮬레이션으로 남는다
        inline=self.simulation(self.SIM_HTML.replace('<body>','<body><svg width="10" height="10"></svg>'))
        self.assertEqual(check_simulation(inline,self.root)['checked']['root_element'],'html')
        self.assertEqual(document_root_name('<!-- c --><!doctype html><html>'),'html')
        self.assertIsNone(document_root_name('   plain text'))
    def test_simulation_handshake_strings_and_values(self):
        gone=self.simulation(self.SIM_HTML.replace('m.type==="response.set"','m.type==="nope"'))
        self.assertIn('Handshake string not found: response.set',check_simulation(gone,self.root)['errors'])
        same=self.simulation();same['simulation']['initial']='{"d":2}'
        self.assertTrue(any('Answer equals the starting state' in e for e in check_simulation(same,self.root)['errors']))
        leak=self.simulation();leak['simulation']['config']='{"m1":2,"target":{"d":2}}'
        self.assertTrue(any('appears inside config' in e for e in check_simulation(leak,self.root)['errors']))
        bad=self.simulation();bad['simulation']['initial']='d=5'
        self.assertTrue(any('initial is not JSON' in e for e in check_simulation(bad,self.root)['errors']))
        two=self.simulation();two['answer']['values']=['{"d":2}','{"d":3}']
        self.assertTrue(any('exactly one value string' in e for e in check_simulation(two,self.root)['errors']))
        self.assertTrue(any('exactly one value string' in e for e in check_question(two,self.root)))
    def test_simulation_block_matches_interaction_and_state(self):
        q=self.simulation();q['interaction']='choice'
        self.assertTrue(any('Only a simulation item' in e for e in check_question(q,self.root)))
        q=self.simulation();q['simulation']=None
        self.assertTrue(any('no simulation block' in e for e in check_question(q,self.root)))
        q=self.simulation();q['choices']=[{'id':'c','label':'1','element_ids':['prompt']}]
        self.assertTrue(any('Simulation has no choices' in e for e in check_question(q,self.root)))
        q=self.simulation();q['elements'][1]['representation']='text'
        self.assertTrue(any('Exactly one element represents' in e for e in check_question(q,self.root)))
        q=self.simulation();q['simulation']['asset']['sha256']='f'*64
        self.assertTrue(any('Hash mismatch' in e for e in check_question(q,self.root)))
        # 편집기가 못 보는 요건 4·9·12 는 저자가 확인해야 verified 다
        done=self.simulation();done['state']='verified'
        errs=check_simulation(done,self.root)['errors']
        self.assertTrue(any('passed editor handshake' in e for e in errs))
        self.assertTrue(any('4, 9, 12' in e for e in errs))
        done['simulation']['conformance'].update(editor_handshake='passed',author_checked=[4,9,12])
        self.assertEqual(check_simulation(done,self.root)['errors'],[])

if __name__=='__main__':unittest.main()
