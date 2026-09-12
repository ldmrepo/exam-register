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
    def test_valid_hash_but_wrong_crop_pixels(self):
        q=self.question();source=self.root/q['pages'][0]['path']
        record=crop(source,[0,0,100,100],self.root/'asset.png')
        e=copy.deepcopy(q['elements'][0]);e.update(id='image',order=4,representation='image',semantic_type='image',text='',alt='source crop',regions=[{'page':1,'bbox':[0,0,100,100]}],asset={'path':'asset.png','sha256':record['sha256'],'size':[100,100],'bytes':record['bytes']})
        q['elements'].append(e);self.assertEqual(check_question(q,self.root),[])
        Image.new('RGB',(100,100),'black').save(self.root/'asset.png');e['asset']['sha256']=digest(self.root/'asset.png');e['asset']['bytes']=(self.root/'asset.png').stat().st_size
        self.assertTrue(any('Crop pixels differ' in x for x in check_question(q,self.root)))

if __name__=='__main__':unittest.main()
