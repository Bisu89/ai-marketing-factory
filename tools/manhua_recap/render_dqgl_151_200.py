"""Build, render, and export DQGL chapters 151-200 in five 10-chapter batches.

Uses existing panel images, the local manhua recap API, Edge TTS, and library
visual mode. No image generation is invoked.
"""
import contextlib
import io
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

import recap

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / 'manhua-series/dai-quan-gia-la-ma-hoang'
STATE = SERIES / 'RENDER_151_200.json'
OUT = SERIES / 'renders_151_200'
TAGS = ['#DaiQuanGiaLaMaHoang', '#ReviewManhua', '#Manhua', '#TuTien', '#XuyenKhong', '#ReviewTruyen']
SHORT_IDS = ['aq','ar','as','at','au','av','aw','ax','ay','az','ba','bb','bc','bd','be']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compose_scripts():
    short_groups=[]
    for start in range(151, 201, 10):
        end=start+9
        eps=[read(SERIES/f'ep{n}/script.json') for n in range(start,end+1)]
        long_beats=[]
        for ep in eps:
            n=int(ep['chapters'])
            title=ep['title']
            for i, beat in enumerate(ep['beats']):
                item=dict(beat)
                item['panel']=f'dqgl_ep{n}/{item["panel"]}.jpg'
                item['kind']='recap'
                item['type']='HOOK' if not long_beats else 'ENDING' if n==end and i==len(ep['beats'])-1 else 'BUILD'
                if i==0: item['section']=f'Tập {n}: {title}'
                long_beats.append(item)
        long_title=f'Đại Quản Gia Là Ma Hoàng | Tập {start}–{end}'
        long_obj={'template':'manhua_recap_long_vi','title':long_title,'chapters':f'{start}-{end}',
                  'source_dir':f'manhua-recap/dqgl_ep{start}','written_by':'OpenAI, biên tập từ script từng tập, 2026-10-21',
                  'description':f'Tóm tắt Đại Quản Gia Là Ma Hoàng từ tập {start} đến {end}, nối tiếp cuộc chiến và những bước đột phá của Trác Phàm.',
                  'hashtags':TAGS,'thumbnail':eps[0]['thumbnail'],'beats':long_beats}
        write(SERIES/f'long_{start}_{end}/script.json',long_obj)
        idx=(start-151)//10*3
        groups=[(start,start+3),(start+4,start+6),(start+7,end)]
        for offset,(a,b) in enumerate(groups):
            selected=[]
            for n in range(a,b+1):
                ep=eps[n-start]
                for i,beat in enumerate(ep['beats']):
                    item=dict(beat);item['panel']=f'dqgl_ep{n}/{item["panel"]}.jpg';item['kind']='recap'
                    item['type']='HOOK' if not selected else 'ENDING' if n==b and i==len(ep['beats'])-1 else 'BUILD'
                    selected.append(item)
            sid=SHORT_IDS[idx+offset]
            title=f'Đại Quản Gia Là Ma Hoàng | Tập {a}–{b}: Trác Phàm nghịch chuyển!?'
            obj={'template':'manhua_recap_vi','title':title,'chapters':f'{a}-{b}',
                 'source_dir':f'manhua-recap/dqgl_ep{a}','written_by':'OpenAI, biên tập từ script từng tập, 2026-10-21',
                 'description':f'Tóm tắt tập {a} đến {b} Đại Quản Gia Là Ma Hoàng. Trác Phàm đối đầu cao thủ và tìm cách xoay chuyển cục diện.',
                 'hashtags':TAGS,'thumbnail':eps[a-start]['thumbnail'],'beats':selected}
            write(SERIES/f'short_{sid}/script.json',obj)
            short_groups.append({'name':f'Short {sid.upper()} ({a}-{b})','range':f'{a}-{b}',
                                 'script':f'manhua-series/dai-quan-gia-la-ma-hoang/short_{sid}/script.json','source':a,'kind':'short'})
        print(f'PREPARED {start}-{end}: 1 Long, 3 Shorts',flush=True)
    videos=[]
    for i,start in enumerate(range(151,201,10)):
        end=start+9
        videos.append({'name':f'DQGL - Long {start}-{end}','range':f'{start}-{end}',
                       'script':f'manhua-series/dai-quan-gia-la-ma-hoang/long_{start}_{end}/script.json',
                       'source':start,'kind':'long'})
        videos.extend(v for v in short_groups if int(v['range'].split('-')[0])>=start and int(v['range'].split('-')[1])<=end)
    write(STATE,{'series':'dai-quan-gia-la-ma-hoang','batches':{},'videos':videos})


def build_batch(state,start,end):
    for v in state['videos']:
        if int(v['range'].split('-')[0])<start or int(v['range'].split('-')[1])>end or v.get('project_id'):continue
        script_path=ROOT/v['script'];script=read(script_path)
        for beat in script['beats']:
            sub,_,fname=beat['panel'].rpartition('/')
            panel=ROOT/'manhua-recap'/sub/'_recap/panels'/fname
            if not panel.is_file():raise RuntimeError(f'Missing panel: {panel}')
        source=ROOT/'manhua-recap'/f'dqgl_ep{v["source"]}'
        cap=io.StringIO()
        dbpath=(ROOT/'backend/data/library.db').resolve()
        found=None
        if dbpath.exists():
            with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
                found=db.execute('select id from project where name=? order by id desc limit 1',(v['name'],)).fetchone()
        original=recap.call
        def reuse_call(method,path,body=None,timeout=300):
            if found and method=='POST' and path=='/projects':return original('GET',f'/projects/{found[0]}')
            return original(method,path,body,timeout)
        recap.call=reuse_call
        try:
            with contextlib.redirect_stdout(cap):
                recap.cmd_build(source,v['name'],False,recap.COMMENTARY_VOICE,script_path=script_path)
        finally:recap.call=original
        match=re.search(r'project (\d+)',cap.getvalue())
        if not match:raise RuntimeError(cap.getvalue())
        v['project_id']=int(match.group(1));write(STATE,state)
        project=recap.call('GET',f'/projects/{v["project_id"]}')
        cfg=project['config'];cfg['voice']['provider']='edge_tts';cfg['visual_generation']['mode']='library';cfg['package']['ai_metadata_enabled']=False
        recap.call('PUT',f'/projects/{v["project_id"]}/beat-plan',{'project_name':project['project_name'],'script_text':project['script_text'],
                    'script_locked':True,'beats':project['beats'],'config':cfg})
        print('BUILT',v['project_id'],v['name'],len(project['beats']),flush=True)


def export(state):
    count=0
    for v in state['videos']:
        pkg=v.get('package') or {};rel=pkg.get('video_path')
        if not rel:continue
        source=ROOT/'backend'/rel
        if not source.is_file():continue
        folder=OUT/v['range'];folder.mkdir(parents=True,exist_ok=True)
        suffix=('long_'+v['range']) if v['kind']=='long' else Path(v['script']).parent.name
        target=folder/(suffix+'.mp4')
        if not target.exists():
            try:os.link(source,target)
            except OSError:shutil.copy2(source,target)
            print('EXPORTED',target.relative_to(ROOT),flush=True)
        thumb=pkg.get('thumbnail_path')
        if thumb:
            src=ROOT/'backend'/thumb;dst=folder/(suffix+'_thumbnail.jpg')
            if src.is_file() and not dst.exists():shutil.copy2(src,dst)
        meta={'project_id':v['project_id'],'factory_run_id':v['run_id'],'render_job_id':v.get('render_job_id'),
              'range':v['range'],'script':v['script'],'package':pkg,'final_qa':v.get('final_qa'),
              'video':target.relative_to(SERIES).as_posix()}
        write(folder/(suffix+'.json'),meta);count+=1
    OUT.mkdir(exist_ok=True)
    rows=[]
    for v in state['videos']:
        if v.get('package',{}).get('video_path'):
            name=('Long' if v['kind']=='long' else Path(v['script']).parent.name)
            d=round(v['package'].get('duration') or 0);rows.append((v['range'],name,f'{d//60}:{d%60:02d}'))
    lines=['# Đại Quản Gia Là Ma Hoàng — tập 151–200','','Mỗi 10 tập: 1 Long và 3 Short. Giọng đọc Edge TTS, ảnh truyện đã có sẵn.','','| Cụm tập | Video | Thời lượng |','|---|---|---|']
    lines += [f'| {r} | {n} | {d} |' for r,n,d in rows]
    lines += ['',f'Đã xuất: {count}/20 video.','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')


def run_batch(state,start,end):
    build_batch(state,start,end)
    terminal={'COMPLETED','FAILED','CANCELLED'}
    while True:
        state=read(STATE);active=[]
        for v in state['videos']:
            a,b=map(int,v['range'].split('-'))
            if a<start or b>end or not v.get('run_id'):continue
            if v.get('status')=='COMPLETED' and v.get('final_qa'):continue
            status=recap.call('GET',f'/factory-runs/{v["run_id"]}')
            v['status']=status['status'];v['render_job_id']=status.get('render_job_id')
            if status.get('error_message'):v['error']=status['error_message']
            if v['status']=='FAILED' and 'edge_tts synthesis failed' in (v.get('error') or '') and v.get('retry_count',0)<2:
                retried=recap.call('POST',f'/factory-runs/{v["run_id"]}/retry')
                v['retry_count']=v.get('retry_count',0)+1;v['status']=retried['status'];v['error']=None
                print('RETRIED_VOICE',v['name'],v['retry_count'],flush=True)
            if v['status']=='NEEDS_REVIEW':
                report=recap.call('POST',f'/projects/{v["project_id"]}/quality-check');v['review_report']=report
                allowed={'LOW_RESOLUTION_ASSET','LOW_PURPOSE_DIVERSITY','PURPOSE_DUPLICATION','PACING_OUTLIER'}
                okay=(not report.get('issues') and report.get('visual',{}).get('coverage')==1.0 and all(w['code'] in allowed for w in report.get('warnings',[])))
                if okay:
                    recap.call('POST',f'/factory-runs/{v["run_id"]}/continue?force=true');v['status']='CONTINUING'
                    print('CONTINUED',v['project_id'],flush=True)
                else:
                    write(STATE,state)
                    raise RuntimeError(f'Quality review blocked {v["name"]}: {report}')
            if v['status']=='COMPLETED' and not v.get('final_qa'):
                v['final_qa']=recap.call('GET',f'/projects/{v["project_id"]}/final-qa')
                v['package']=recap.call('GET',f'/projects/{v["project_id"]}/package')
                print('DONE',v['project_id'],v['name'],flush=True)
            if v['status'] not in terminal:active.append(v)
        write(STATE,state)
        for v in state['videos']:
            a,b=map(int,v['range'].split('-'))
            if a<start or b>end or not v.get('project_id') or v.get('run_id'):continue
            run=recap.call('POST',f'/projects/{v["project_id"]}/factory-run')
            v['run_id']=run['id'];v['status']=run['status'];active.append(v);write(STATE,state)
            print('STARTED',v['project_id'],run['id'],v['name'],flush=True)
            break
        remaining=[v for v in state['videos'] if int(v['range'].split('-')[0])>=start and int(v['range'].split('-')[1])<=end and v.get('status') not in terminal]
        export(state)
        print('STATUS',f'{start}-{end}',[(v.get('project_id'),v.get('status')) for v in remaining],flush=True)
        if not remaining:break
        time.sleep(15)
    failures=[v for v in read(STATE)['videos'] if int(v['range'].split('-')[0])>=start and int(v['range'].split('-')[1])<=end and v.get('status') in {'FAILED','CANCELLED'}]
    if failures:raise RuntimeError(f'Batch {start}-{end} failed: '+', '.join(v['name'] for v in failures))


if __name__=='__main__':
    action=sys.argv[1] if len(sys.argv)>1 else 'all'
    if action in {'all','prepare'}:compose_scripts()
    if action in {'all','run'}:
        for start in range(151,201,10):
            print('BATCH',f'{start}-{start+9}',flush=True)
            run_batch(read(STATE),start,start+9)
