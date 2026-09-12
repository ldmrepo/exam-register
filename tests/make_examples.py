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

def generate():
    font_path=Path('C:/Windows/Fonts/malgun.ttf')
    if not font_path.exists():raise RuntimeError('Use a Korean-capable font on this environment')
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
            q['elements'].append(el('material',2,kind,'image',[60,190,841,651],a={'path':rel(folder/'material.png'),'sha256':asset['sha256'],'size':asset['size']},alt=desc))
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
            '\n\nsource.png와 question.json을 원본 대조에 사용한다. 파일 경로는 스킬 폴더를 작업 루트로 해석한 예시다. 실제 작업에는 작업 폴더로 복사하고 경로를 맞춘다.\n',encoding='utf-8')
    print('Generated four original visual cases')
if __name__=='__main__':generate()
