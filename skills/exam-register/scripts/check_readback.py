"""Compare a saved item (item_read html) with the local question specification.

Mechanical only: prompt text, choice order and text, checked answers, image asset ids,
underlined strings, viewbox count and headings. It does not read the source PDF and it is
not a visual verification.
"""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from common import read_json

WS = re.compile(r'\s+')
TAG = re.compile(r'<[^>]+>')


def norm(text):
    return WS.sub(' ', text).strip()


def plain(spec_text):
    """Specification text without inline markup such as <u>…</u>."""
    return norm(TAG.sub('', spec_text))


class ItemHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.prompt_parts, self.choices, self.checked = [], {}, set()
        self.images, self.underlined, self.viewboxes = [], [], []
        self._prompt = self._fieldset = self._p = self._u = self._heading = 0
        self._choice = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'prompt':
            self._prompt += 1
        elif tag == 'fieldset':
            self._fieldset += 1
            if 'qti-viewbox' in (a.get('class') or ''):
                self.viewboxes.append({'heading': ''})
        elif tag == 'div' and 'qti-viewbox-heading' in (a.get('class') or ''):
            self._heading += 1
            self._buf.append('')
        elif tag == 'simplechoice':
            self._choice = {'identifier': a.get('identifier'), 'order': int(a.get('order') or 0), 'text': ''}
            if a.get('checked') is not None:
                self.checked.add(a.get('identifier'))
        elif tag == 'img':
            self.images.append((a.get('src') or '').rsplit('/', 1)[-1])
        elif tag == 'u':
            self._u += 1
            self._buf.append('')
        elif tag == 'p':
            self._p += 1
            self._buf.append('')

    def handle_endtag(self, tag):
        if tag == 'prompt':
            self._prompt -= 1
        elif tag == 'fieldset':
            self._fieldset -= 1
        elif tag == 'div' and self._heading:
            self._heading -= 1
            if self.viewboxes:
                self.viewboxes[-1]['heading'] = norm(self._buf.pop())
        elif tag == 'simplechoice' and self._choice is not None:
            self.choices[self._choice['identifier']] = self._choice
            self._choice = None
        elif tag == 'u' and self._u:
            self._u -= 1
            text = self._buf.pop()
            self.underlined.append(norm(text))
            self._append(text)
        elif tag == 'p' and self._p:
            self._p -= 1
            text = self._buf.pop()
            if self._choice is not None:
                self._choice['text'] += text
            elif self._prompt and not self._fieldset:
                self.prompt_parts.append(norm(text))

    def _append(self, text):
        if self._buf:
            self._buf[-1] += text

    def handle_data(self, data):
        self._append(data)


def parse(html):
    parser = ItemHTML()
    parser.feed(html)
    return parser


def compare(question, read):
    body = read.get('structuredContent', read) if isinstance(read, dict) else {}
    html = body.get('html') if isinstance(body, dict) else None
    if not html:
        return {'structure_pass': False, 'errors': ['read response has no html; use item_read {format:"html"}'],
                'compared': {}}
    doc = parse(html)
    errors, compared = [], {}
    by_id = {e['id']: e for e in question['elements']}

    prompts = [e for e in question['elements'] if e['semantic_type'] == 'prompt']
    expected_prompt = ' '.join(plain(e['text']) for e in prompts)
    actual_prompt = ' '.join(doc.prompt_parts)
    compared['prompt'] = {'expected': expected_prompt, 'actual': actual_prompt}
    if expected_prompt != actual_prompt:
        errors.append('Prompt text differs from specification')

    expected_choices = [plain(' '.join(by_id[i]['text'] for i in c['element_ids'])) for c in question['choices']]
    actual = sorted(doc.choices.values(), key=lambda c: c['order'])
    actual_choices = [norm(c['text']) for c in actual]
    compared['choices'] = {'expected': expected_choices, 'actual': actual_choices}
    if len(expected_choices) != len(actual_choices):
        errors.append(f'Choice count differs: spec {len(expected_choices)}, saved {len(actual_choices)}')
    else:
        for i, (e, a) in enumerate(zip(expected_choices, actual_choices), 1):
            if e != a:
                errors.append(f'Choice {i} text differs')

    answer = question['answer']
    if answer['status'] == 'confirmed' and question['interaction'] == 'choice':
        ids = [c['id'] for c in question['choices']]
        expected_checked = {actual[ids.index(v)]['identifier'] for v in answer['values']
                            if v in ids and ids.index(v) < len(actual)}
        compared['answer'] = {'expected': sorted(expected_checked), 'actual': sorted(doc.checked)}
        if expected_checked != doc.checked:
            errors.append('Checked answers differ from specification')

    image_elements = [e for e in question['elements'] if e['representation'] == 'image']
    expected_assets = set(question['registration']['asset_ids'].values())
    compared['images'] = {'expected_assets': sorted(expected_assets), 'actual_assets': sorted(doc.images),
                          'expected_count': len(image_elements)}
    if len(doc.images) != len(image_elements):
        errors.append(f'Image count differs: spec {len(image_elements)}, saved {len(doc.images)}')
    if expected_assets and set(doc.images) != expected_assets:
        errors.append('Image asset ids differ from registration.asset_ids')

    expected_marks = [norm(m) for e in question['elements'] for m in re.findall(r'<u>(.*?)</u>', e['text'])]
    compared['underlines'] = {'expected': expected_marks, 'actual': doc.underlined}
    for m in expected_marks:
        if m not in doc.underlined:
            errors.append('Underline missing: ' + m)

    viewbox_elements = [e for e in question['elements'] if e['semantic_type'] == 'viewbox']
    compared['viewboxes'] = {'expected_count': len(viewbox_elements), 'actual': doc.viewboxes}
    if len(viewbox_elements) != len(doc.viewboxes):
        errors.append(f'Viewbox count differs: spec {len(viewbox_elements)}, saved {len(doc.viewboxes)}')
    else:
        for e, v in zip(viewbox_elements, doc.viewboxes):
            if 'viewbox_title' in e:
                expected = norm(e['viewbox_title'] or '')
                if expected != v['heading']:
                    errors.append(f"Viewbox heading differs for {e['id']}: expected '{expected}', saved '{v['heading']}'")
    return {'structure_pass': not errors, 'errors': errors, 'compared': compared,
            'visual_verification': 'not_performed'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('question', type=Path)
    p.add_argument('--read', type=Path, required=True, help='saved item_read response JSON')
    p.add_argument('--workspace', type=Path, required=True)
    a = p.parse_args()
    result = compare(read_json(a.question), read_json(a.read))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['structure_pass'] else 1)
