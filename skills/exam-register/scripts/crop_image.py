"""Crop only agent-supplied integer coordinates. Never infer boundaries or resize."""
import argparse
import json
from pathlib import Path
from PIL import Image
from common import atomic_json, digest, valid_box

def crop(source, bbox, output):
    source,output=Path(source),Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Cannot overwrite source image')
    if output.suffix.lower() != '.png':
        raise ValueError('Output must be a lossless PNG')
    if any(type(v) is not int for v in bbox):
        raise ValueError('Crop coordinates must be integers')
    with Image.open(source) as im:
        valid_box(bbox,im.size)
        out=im.crop(bbox)
        output.parent.mkdir(parents=True,exist_ok=True)
        temp=output.with_suffix('.tmp.png'); out.save(temp); temp.replace(output)
        record={'path':str(output.resolve()),'sha256':digest(output),'size':list(out.size),
                'source_image':str(source.resolve()),'source_sha256':digest(source),'source_size':list(im.size),
                'bbox':bbox,'visual_review':'pending'}
    atomic_json(output.with_suffix('.json'),record)
    return record

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('source',type=Path)
    p.add_argument('--bbox',type=int,nargs=4,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(crop(a.source,a.bbox,a.output),ensure_ascii=False,indent=2))
