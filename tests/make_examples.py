"""Original CC0 fixtures for visual registration checks, not real exam questions."""
import copy
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'skills/exam-register'
sys.path.insert(0,str(S/'scripts'))
from common import atomic_json,digest,read_json
from crop_image import crop

def generate(font_path=Path('C:/Windows/Fonts/malgun.ttf')):
    font_path=Path(font_path)
    if not font_path.exists():raise RuntimeError('Korean-capable TrueType font not found: '+str(font_path)+' (pass --font)')
    font=ImageFont.truetype(str(font_path),26);small=ImageFont.truetype(str(font_path),22)
    cases=[('image-stimulus','지도와 범례가 결합된 창작 자료','map'),('text-viewbox','일반 텍스트 보기','viewbox'),
           ('timeline-image','표 형태의 창작 연표 자료','timeline'),('composite-letter','편지와 해설이 결합된 창작 자료','image')]
    for i,(name,desc,kind) in enumerate(cases,1):
        folder=S/'examples'/name;folder.mkdir(parents=True,exist_ok=True)
        im=Image.new('RGB',(900,1000),'white');d=ImageDraw.Draw(im)
        d.text((40,30),'창작 검증용 문항 · 실제 수능 아님',fill='black',font=font)
        prompt='다음 자료의 보존 방식으로 적절한 것은?'
        d.text((40,100),f'{i}. '+prompt,fill='black',font=font)
        d.rectangle((60,190,840,650),outline='#28374a',width=3)
        d.text((90,210),desc,fill='black',font=font)
        if name=='image-stimulus':
            d.polygon([(150,330),(340,280),(500,380),(350,540),(170,510)],fill='#dae8d7',outline='black')
            d.ellipse((260,380,284,404),fill='#bf4030');d.text((300,380),'가 마을',fill='black',font=small)
            d.text((540,330),'범례',fill='black',font=font);d.text((540,380),'● 마을 위치',fill='black',font=small)
            d.text((90,600),'설명: 지도와 범례를 함께 보존한다.',fill='black',font=small)
        elif name=='text-viewbox':
            d.text((90,300),'○ 원문의 문단과 기호를 보존한다.',fill='black',font=font)
            d.text((90,390),'○ 밑줄 친 핵심어를 확인한다.',fill='black',font=font)
            d.line((248,427,326,427),fill='black',width=2)
        elif name=='timeline-image':
            for y in [285,365,445,525]:d.line((90,y,810,y),fill='black',width=2)
            d.line((250,285,250,585),fill='black',width=2)
            for y,year,text in [(305,'100년','첫 기록'),(385,'120년','마을 설립'),(465,'150년','자료 보존')]:
                d.text((110,y),year,fill='black',font=font);d.text((285,y),text,fill='black',font=font)
            d.line([(90,595),(230,620),(400,595),(590,620),(810,595)],fill='#28374a',width=4)
        else:
            d.rounded_rectangle((90,280,810,520),radius=25,outline='#735631',width=4)
            d.text((120,310),'친구에게 보내는 글',fill='black',font=font)
            d.text((120,375),'오랜만에 소식을 전한다.',fill='black',font=font)
            d.text((120,430),'자료를 온전히 보존해 주기 바란다.',fill='black',font=font)
            d.text((90,570),'[해설] 편지와 설명은 하나의 자료이다.',fill='black',font=small)
        choices=['자료의 구조와 내용을 함께 보존한다.','모든 자료를 임의의 표로 바꾼다.']
        for j,text in enumerate(choices):d.text((60,730+j*80),f'{j+1}. '+text,fill='black',font=font)
        source=folder/'source.png';im.save(source)
        asset=crop(source,[60,190,841,651],folder/'material.png') if kind!='viewbox' else None
        q=read_json(S/'templates/question.json');q.update(id=name,number=str(i))
        rel=lambda p:p.relative_to(S).as_posix()
        q['source'].update(path=rel(source),sha256=digest(source),subject='창작 검증',variant='단일형',provenance='이 패키지를 위해 작성한 CC0 예시')
        q['pages']=[{'path':rel(source),'sha256':digest(source),'source_sha256':digest(source),'size':[900,1000],'page':1,'scale':1}]
        q['regions']=[{'page':1,'bbox':[40,100,860,920]}]
        def el(id,order,semantic,rep,bbox,text='',a=None,alt=''):
            return {'id':id,'order':order,'semantic_type':semantic,'representation':rep,'reason':desc if semantic!='choice' else '선택지는 편집 가능한 텍스트',
                    'regions':[{'page':1,'bbox':bbox}],'text':text,'asset':a,'alt':alt}
        q['elements']=[el('prompt',1,'prompt','text',[40,100,860,160],prompt)]
        if asset:
            q['elements'].append(el('material',2,kind,'image',[60,190,841,651],a={'path':rel(folder/'material.png'),'sha256':asset['sha256'],'size':asset['size'],'bytes':asset['bytes']},alt=desc))
        else:q['elements'].append(el('material',2,'viewbox','text',[60,190,841,651],'일반 텍스트 보기\n○ 원문의 문단과 기호를 보존한다.\n○ 밑줄 친 <u>핵심어</u>를 확인한다.'))
        q['choices']=[]
        for j,text in enumerate(choices):
            q['elements'].append(el(f'c{j+1}',j+3,'choice','text',[60,730+j*80,840,790+j*80],text))
            q['choices'].append({'id':f'c{j+1}','label':str(j+1),'element_ids':[f'c{j+1}']})
        q['answer']={'status':'confirmed','values':['c1'],'evidence':'창작 문항 작성자가 지정한 정답. 공식 시험 정답 아님.'}
        q['registration']['operation_key']='example-'+name
        atomic_json(folder/'question.json',q)
        if asset:
            asset['path']='material.png';asset['source_image']='source.png'
            atomic_json(folder/'material.json',asset)
        (folder/'decision.md').write_text(f'# {desc}\n\n이 사례는 직접 작성한 CC0 자료다. 실제 수능 문제의 대체 정답 자료가 아니다.\n\nsemantic_type={kind}; representation={"text" if kind=="viewbox" else "image"}. '+
            ('일반 보기의 텍스트·문단·밑줄을 편집 가능하게 유지한다.' if kind=='viewbox' else '제목·자료·범례·설명·장식 전체를 이미지로 보존한다. 표 모양이어도 자동으로 표 노드로 바꾸지 않는다.')+
            '\n\nsource.png와 question.json을 원본 대조에 사용한다. 파일 경로는 스킬 폴더를 작업 루트로 해석한 예시다. 실제 작업에는 작업 폴더로 복사하고 경로를 맞춘다.\n',encoding='utf-8',newline='\n')
    print('Generated four original visual cases')

def generate_simulation(font_path=Path('C:/Windows/Fonts/malgun.ttf')):
    """조작으로 답하는 사례. simulation.html 은 손으로 쓴 자산이므로 다시 만들지 않는다."""
    font_path=Path(font_path)
    if not font_path.exists():raise RuntimeError('Korean-capable TrueType font not found: '+str(font_path)+' (pass --font)')
    font=ImageFont.truetype(str(font_path),26);small=ImageFont.truetype(str(font_path),22)
    folder=S/'examples/simulation-balance';folder.mkdir(parents=True,exist_ok=True)
    html=folder/'simulation.html'
    if not html.is_file():raise RuntimeError('simulation.html is part of the example and must exist: '+str(html))
    prompt='받침점 왼쪽 3 m 자리에 2 kg 추가 있다. 오른쪽 3 kg 추를 어느 자리에 두어야 지레가 수평이 되는가? 화면에서 직접 맞추시오.'
    im=Image.new('RGB',(900,700),'white');d=ImageDraw.Draw(im)
    d.text((40,30),'창작 검증용 문항 · 실제 수능 아님',fill='black',font=font)
    d.text((40,100),'5. '+prompt[:34],fill='black',font=font);d.text((70,140),prompt[34:],fill='black',font=font)
    d.rectangle((60,210,840,600),outline='#28374a',width=3)
    d.text((90,230),'조작 화면 자리 · 지레 균형 실험',fill='black',font=font)
    d.line((120,470,780,470),fill='#c9c9c9',width=3);d.polygon([(450,468),(426,520),(474,520)],fill='#8a8a8a')
    d.line((170,430,730,430),fill='#5a5a5a',width=8)
    d.rectangle((318,398,354,434),fill='#b4462f');d.rectangle((558,398,594,434),fill='#1d6fd0')
    d.text((90,540),'응시자가 오른쪽 추를 끌어 수평을 맞춘다.',fill='black',font=small)
    source=folder/'source.png';im.save(source)
    rel=lambda p:p.relative_to(S).as_posix()
    q=read_json(S/'templates/question.json');q.update(id='simulation-balance',number='5',interaction='simulation',max_choices=1)
    q['source'].update(path=rel(source),sha256=digest(source),subject='창작 검증',variant='단일형',provenance='이 패키지를 위해 작성한 CC0 예시')
    q['pages']=[{'path':rel(source),'sha256':digest(source),'source_sha256':digest(source),'size':[900,700],'page':1,'scale':1}]
    q['regions']=[{'page':1,'bbox':[40,100,860,620]}]
    q['elements']=[
        {'id':'prompt','order':1,'semantic_type':'prompt','representation':'text','reason':'질문은 편집 가능한 텍스트',
         'regions':[{'page':1,'bbox':[40,100,860,180]}],'text':prompt,'asset':None,'alt':''},
        {'id':'stage','order':2,'semantic_type':'simulation','representation':'simulation',
         'reason':'답이 보기 중 하나가 아니라 조작 결과의 상태다','regions':[{'page':1,'bbox':[60,210,841,601]}],
         'text':'','asset':None,'alt':'지레 균형 실험. 오른쪽 추의 거리를 옮겨 수평을 맞춘다.'}]
    q['choices']=[]
    q['answer']={'status':'confirmed','values':['{"d":2}'],
                 'evidence':'2 kg × 3 m = 3 kg × 2 m. author 모드에서 수평을 만든 뒤 시뮬레이션이 낸 문자열.'}
    q['simulation']={
        'asset':{'path':rel(html),'sha256':digest(html),'bytes':html.stat().st_size},
        'alt':'지레 균형 실험. 받침점 왼쪽 3 m 에 2 kg, 오른쪽에 3 kg 추가 있고 오른쪽 추의 거리를 옮길 수 있다.',
        'config':'{"m1":2,"x1":3,"m2":3}','seed':None,'initial':'{"d":5}',
        'width':480,'height':None,'align':'center',
        'conformance':{'editor_handshake':'pending','author_checked':[],
                       'notes':'이 사례는 파일만 제공한다. 요건 4·9·12 는 편집기에 넣고 조작해 확인한다.'}}
    q['registration']['operation_key']='example-simulation-balance'
    atomic_json(folder/'question.json',q)
    (folder/'decision.md').write_text(
        '# 조작으로 답하는 사례 · 지레 균형\n\n'
        '이 사례는 직접 작성한 CC0 자료다. 실제 수능 문제가 아니다.\n\n'
        'interaction=simulation; semantic_type=simulation; representation=simulation. '
        '답이 보기 중 하나도, 글자 하나도 아니고 **조작 결과의 상태**라서 시뮬레이션이다. '
        '같은 내용을 「수평이 되는 거리는?」 으로 묻고 보기 다섯을 준다면 그것은 선다형이다.\n\n'
        '## 값이 사는 자리\n\n'
        '- `config` `{"m1":2,"x1":3,"m2":3}` — 화면에 이미 보이는 값뿐이다. 응시자가 읽는다.\n'
        '- `initial` `{"d":5}` — 출발 자리. 정답과 다르므로 가만히 제출하면 틀린다.\n'
        '- 정답 `{"d":2}` — 2 kg × 3 m = 3 kg × 2 m. `author` 모드에서 수평을 만든 뒤 '
        '시뮬레이션이 낸 문자열을 **바이트 그대로** 옮긴 것이다. `{ "d": 2 }` 로 다시 쓰면 다른 답이 된다.\n'
        '- `seed` 없음 — 무작위가 없다.\n\n'
        '## 자산\n\n'
        '`simulation.html` 은 자족 HTML 한 파일이다. 외부 주소를 하나도 참조하지 않고(서빙 CSP 가 '
        '`default-src \'none\'` 이다) 규약 문자열을 모두 갖췄다. `scripts/check_simulation.py` 로 그 두 가지를 '
        '기계 검사할 수 있다. 다만 **요건 4·9·12 는 돌려 봐야 안다** — 이 사례의 `conformance.author_checked` 가 '
        '빈 것은 그래서다.\n\n'
        'source.png 와 question.json 을 원본 대조에 사용한다. 파일 경로는 스킬 폴더를 작업 루트로 해석한 '
        '예시다. 실제 작업에는 작업 폴더로 복사하고 경로를 맞춘다.\n',
        encoding='utf-8',newline='\n')
    print('Generated the simulation case')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--font',default='C:/Windows/Fonts/malgun.ttf',help='Korean-capable TrueType font path')
    p.add_argument('--only',choices=['all','visual','simulation'],default='all')
    a=p.parse_args()
    if a.only in ('all','visual'):generate(a.font)
    if a.only in ('all','simulation'):generate_simulation(a.font)
