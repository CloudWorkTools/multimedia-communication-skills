"""不載入模型：dry-run 無副作用、拒絕覆寫及無效參數。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
script = Path(__file__).with_name('generate_local_song.py')
default = script.parents[1]/'references/minimax-default.json'
with tempfile.TemporaryDirectory() as temp:
    p = Path(temp)
    base = p/'runtime'
    (base/'models').mkdir(parents=True)
    (base/'source/build').mkdir(parents=True)
    (base/'source/build/mm-synth').touch()
    (base/'gpu_library_paths.txt').write_text('')
    for key, value in json.loads(default.read_text()).items():
        if key.endswith('_model'):
            (base/'models'/value).touch()
    env = dict(os.environ, MINIMAX_MUSIC3_HOME=str(base))
    lyrics = p/'lyrics.txt'
    lyrics.write_text('[Verse]\n不懂就問人工智慧\n')
    out = p/'out'
    args = [sys.executable, str(script), '--lyrics', str(lyrics), '--out', str(out), '--check']
    def run(extra=()):
        return subprocess.run(args+list(extra), env=env, capture_output=True)
    result = run()
    assert result.returncode == 0, result.stderr.decode()
    assert not out.exists()
    out.mkdir()
    (out/'keep').write_text('preserve')
    assert run().returncode != 0
    assert (out/'keep').read_text() == 'preserve'
    (out/'keep').unlink()
    request = p/'request.json'
    r = json.loads(default.read_text())
    r['duration'] = float('nan')
    request.write_text(json.dumps(r))
    assert run(['--request', str(request)]).returncode != 0
    r = json.loads(default.read_text())
    r['temperature'] = .7
    request.write_text(json.dumps(r))
    assert run(['--request', str(request)]).returncode != 0
    (base/'models'/r['lm_model']).unlink()
    assert run().returncode != 0
print('通過：dry-run 無寫入、既有成品保留、無效參數與缺少模型皆拒絕；未載入模型。')
