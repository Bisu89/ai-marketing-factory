"""Replace two corrected narration beats before their motion stage completes.

Keeps all existing beat windows and synchronizes the whole voice track,
per-beat assets, caption word timings, saved plan and voice cache metadata.
"""
import json
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import recap
from app.modules.voice.providers import EdgeTTSProvider
from app.api.v1.endpoints.voice_generate import voice_fingerprint, voice_runs, build_narration_text
from app.modules.beat.schemas import Beat, VoiceProjectConfig

SERIES=ROOT/'manhua-series/chang-re-manh-nhat-lich-su'
V=ROOT/'backend/data/library/_voice/project_306'
MARKER=SERIES/'long_121_130/voice_corrections.json'

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if MARKER.exists():raise SystemExit('Corrections already applied.')
while True:
    run=recap.call('GET','/factory-runs/356')
    print('WAIT',run['status'],flush=True)
    if run['status']=='GENERATING_MOTION':break
    if run['status'] not in {'PREPARING','GENERATING_VOICE'}:raise RuntimeError(run)
    time.sleep(20)

plan=recap.call('GET','/projects/306')
final=read(SERIES/'long_121_130/script.json')
changes=[(b,new) for b,new in zip(plan['beats'],final['beats']) if b['narration']!=new['narration']]
if len(changes)!=2:raise RuntimeError(f'Expected 2 corrections, got {len(changes)}')
write(V/'editorial_plan_before.json',plan)
source=V/'narration.wav'
shutil.copy2(source,V/'narration.before_editorial.wav')
metadata=read(V/'narration.meta.json')
write(V/'narration.meta.before_editorial.json',metadata)
voice=VoiceProjectConfig.model_validate(plan['config']['voice'])
edits=[]
for b,new in changes:
    target_text=new['narration'];bid=b['id']
    print('CORRECT',bid,flush=True)
    raw=V/f'editorial_{bid}.raw.wav'
    result=EdgeTTSProvider().synthesize(target_text,b.get('voice_id') or voice.voice_id,voice.language,voice.speed,raw,sentence_pause_sec=voice.sentence_pause_sec)
    duration=b['end']-b['start']
    ratio=result.duration_sec/duration
    if not 0.5<=ratio<=2:raise RuntimeError(f'Unexpected correction duration ratio {ratio}')
    replacement=V/f'editorial_{bid}.wav'
    subprocess.run(['ffmpeg','-y','-v','error','-i',str(raw),'-af',f'atempo={ratio},apad,atrim=duration={duration}','-ar','48000','-ac','1','-c:a','pcm_s16le',str(replacement)],check=True,capture_output=True)
    with wave.open(str(source),'rb') as f:
        params=f.getparams();pcm=f.readframes(f.getnframes())
    stride=params.nchannels*params.sampwidth
    begin=round(b['start']*params.framerate);end=round(b['end']*params.framerate)
    with wave.open(str(replacement),'rb') as f:segment=f.readframes(f.getnframes())
    target_bytes=(end-begin)*stride
    segment=(segment+bytes(max(0,target_bytes-len(segment))))[:target_bytes]
    tmp=V/'editorial_combined.tmp.wav'
    with wave.open(str(tmp),'wb') as f:
        f.setparams(params);f.writeframes(pcm[:begin*stride]+segment+pcm[end*stride:])
    tmp.replace(source)
    beatfile=V/f'beat_{bid}.wav'
    shutil.copy2(beatfile,V/f'beat_{bid}.before_editorial.wav')
    with wave.open(str(beatfile),'wb') as f:f.setparams(params);f.writeframes(segment)
    words=metadata.get('word_timestamps') or []
    words=[w for w in words if not (w['start']<b['end'] and w['end']>b['start'])]
    words.extend({'text':w.text,'start':b['start']+w.start/ratio,'end':min(b['end'],b['start']+w.end/ratio)} for w in result.word_timestamps or [])
    metadata['word_timestamps']=sorted(words,key=lambda w:w['start']) or None
    edits.append({'beat_id':bid,'before':b['narration'],'after':target_text,'duration':duration,'tempo_ratio':ratio})
    plan['script_text']=plan['script_text'].replace(b['narration'],target_text)
    b['narration']=target_text

current=recap.call('GET','/factory-runs/356')
if current['status']!='GENERATING_MOTION':raise RuntimeError('Motion finished before voice correction could be persisted; check audio/caption caches.')
recap.call('PUT','/projects/306/beat-plan',{'project_name':plan['project_name'],'script_text':plan['script_text'],'script_locked':True,'beats':plan['beats'],'config':plan['config']})
beats=[Beat.model_validate(b) for b in plan['beats']]
metadata['fingerprint']=voice_fingerprint(build_narration_text(beats),voice,voice_runs(beats,voice.voice_id))
metadata['editorial_corrections']=edits
write(V/'narration.meta.json',metadata)
write(MARKER,{'project_id':306,'edits':edits,'voice':'edge_tts','timing':'Existing beat windows preserved; whole track, beat audio, plan and word timing updated together.'})
print('CORRECTED',len(edits),'beats',flush=True)
