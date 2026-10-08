#!/usr/bin/env python3
"""使用已安裝 MiniMax Music 3 Q8 原生歌手；JSON 調參、離線推論、拒絕覆寫。"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
from opencc import OpenCC

BASE = Path(os.environ.get('MINIMAX_MUSIC3_HOME', str(Path.home()/'.local/share/minimax-music3'))).expanduser()
DEFAULT = Path(__file__).resolve().parents[1]/'references/minimax-default.json'
FIELDS = {'caption','lyrics','duration','steps','seed','lm_seed','lm_batch_size','synth_batch_size','lm_cfg','lm_top_k','dit_cfg','peak_clip','output_format','lm_model','depth_model','cond_model','dit_model','vae_model','mp3_bitrate'}


def prepare(request, lyrics):
    r = dict(request)
    if set(r)-FIELDS:
        raise ValueError(f'未支援的參數：{sorted(set(r)-FIELDS)}')
    if not isinstance(r.get('caption'), str) or not r['caption'].strip():
        raise ValueError('caption 不可空白')
    lines = [x.strip() for x in re.sub(r'\[[^\]\n]+\]', '', lyrics).splitlines() if x.strip()]
    if not lines:
        raise ValueError('歌詞不可只有段落標籤')
    for field, lo, hi in [('duration',10,300),('steps',1,100),('lm_cfg',0,10),('dit_cfg',0,10),('lm_top_k',1,16384),('seed',-1,4294967295),('lm_seed',-1,4294967295)]:
        value = r.get(field)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'{field} 需在 {lo}–{hi}，這是本機 helper 的防誤用範圍')
        if field in ('steps','lm_top_k','seed','lm_seed') and not isinstance(value,int):
            raise ValueError(f'{field} 需為整數')
    if r.get('lm_batch_size') != 1 or r.get('synth_batch_size') != 1 or r.get('output_format') != 'wav32':
        raise ValueError('本機 helper 固定 batch 1、原始 wav32；完成後另轉 MP3')
    for field in ('lm_model','depth_model','cond_model','dit_model','vae_model'):
        name = r.get(field)
        if not isinstance(name,str) or Path(name).name != name or not (BASE/'models'/name).is_file():
            raise ValueError(f'缺少／非法的本機權重：{field}')
    r['lyrics'] = OpenCC('t2s').convert(lyrics)
    return r, lines


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lyrics',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--request',type=Path,default=DEFAULT)
    p.add_argument('--duration',type=float)
    p.add_argument('--check',action='store_true')
    a = p.parse_args()
    try:
        r = json.loads(a.request.read_text());lyrics = a.lyrics.read_text(encoding='utf-8-sig').strip()
        if a.duration is not None:r['duration'] = a.duration
        r, lines = prepare(r,lyrics)
        if a.out.exists() and (not a.out.is_dir() or any(a.out.iterdir())):raise ValueError('請使用新目錄或空目錄，避免覆寫')
        if not (BASE/'source/build/mm-synth').is_file() or not (BASE/'gpu_library_paths.txt').is_file():raise ValueError('缺少已安裝本機執行器')
    except (ValueError,OSError) as e:p.error(str(e))
    if a.check:
        print(f'輸入核對通過：{len(lines)} 句，時長上限 {r["duration"]} 秒；未載入模型、未寫輸出。')
        return
    a.out.mkdir(parents=True,exist_ok=True);out=a.out.resolve()
    (out/'生成請求.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    (out/'採用歌詞.txt').write_text(lyrics+'\n')
    manifest={'original_lines':lines,'lyrics':lyrics,'model_lyrics':r['lyrics'],'model':'MiniMax-Music3 Q8 GGUF','reference_audio':None,'local_inference':True,'human_listening_verified':False,'quality_status':'not_checked','request':r,'source_commit':subprocess.check_output(['git','-C',str(BASE/'source'),'rev-parse','HEAD'],text=True).strip()}
    (out/'生成設定.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    env=dict(os.environ,OMP_NUM_THREADS='4',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_IMPLICIT_TOKEN='1',HF_HUB_DISABLE_TELEMETRY='1')
    env['LD_LIBRARY_PATH']=(BASE/'gpu_library_paths.txt').read_text().strip()
    # ponytail: context estimate reserves 2048 text tokens; longer captions need a tokenizer budget check.
    context=min(10240,max(4096,math.ceil(r['duration']*25)+2048))
    with (out/'生成日誌.log').open('w') as log:
        subprocess.run([str(BASE/'source/build/mm-synth'),'--models',str(BASE/'models'),'--request',str(out/'生成請求.json'),'--max-seq',str(context),'--out',str(out/'song.wav')],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(f'已生成原生歌曲，待音訊、歌詞與自然度檢查：{out/"song.wav"}')


if __name__ == '__main__':main()
