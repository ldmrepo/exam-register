import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

def check(workspace):
    packages={}
    for name in ['PyMuPDF','Pillow','jsonschema']:
        try: packages[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name]=None
    return {'python':sys.version.split()[0],'executable':sys.executable,'packages':packages,
            'workspace':str(Path(workspace).resolve()),'workspace_exists':Path(workspace).is_dir(),
            'local_dependencies_ready':sys.version_info >= (3,10) and all(packages.values()),
            'mcp':'not_tested_use_teamsword_ping_in_Codex',
            'visual_tools':'not_tested_check_actual_browser_inventory_in_Codex'}

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--workspace',type=Path,required=True); a=p.parse_args()
    result=check(a.workspace); print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['local_dependencies_ready'] else 1)
