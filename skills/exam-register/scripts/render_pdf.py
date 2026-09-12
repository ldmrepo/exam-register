"""Render specified one-based pages with content-addressed cache and integrity checks."""
import argparse
from pathlib import Path
import fitz
from PIL import Image
from common import atomic_json, digest, read_json

def render(pdf, page, scale, cache):
    if scale <= 0 or scale > 8:
        raise ValueError('scale must be >0 and <=8')
    sha = digest(pdf)
    with fitz.open(pdf) as doc:
        if not 1 <= page <= len(doc):
            raise ValueError('page must be between 1 and '+str(len(doc)))
        key = f'{sha}/p{page:04d}-s{scale:g}-fitz{fitz.VersionBind}-rgb'
        image = Path(cache) / (key+'.png')
        meta = image.with_suffix('.json')
        if meta.exists() and image.exists():
            try:
                record = read_json(meta)
                with Image.open(image) as im:
                    intact = list(im.size) == record['size']
                if intact and digest(image) == record['sha256']:
                    return {**record, 'cache_hit': True}
            except (OSError, ValueError, KeyError):
                pass  # Regenerate a damaged cache; never modify the source.
        image.parent.mkdir(parents=True, exist_ok=True)
        pix = doc[page-1].get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        temporary = image.with_suffix('.tmp.png')
        pix.save(temporary)
        temporary.replace(image)
        record = {'path': str(image.resolve()), 'sha256': digest(image), 'size': [pix.width,pix.height],
                  'source_sha256': sha, 'page':page, 'scale':scale, 'renderer':'PyMuPDF '+fitz.VersionBind}
        atomic_json(meta, record)
        return {**record, 'cache_hit':False}

if __name__ == '__main__':
    import json
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf',type=Path); p.add_argument('--pages',type=int,nargs='+',required=True)
    p.add_argument('--scale',type=float,default=2); p.add_argument('--cache',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps([render(a.pdf,n,a.scale,a.cache) for n in a.pages],ensure_ascii=False,indent=2))
