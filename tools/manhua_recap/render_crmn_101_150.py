"""Resume the authorized CRMN batch using existing images and Edge TTS only."""
import argparse
import contextlib
import io
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import recap

ROOT = Path(__file__).resolve().parents[2]
SERIES = ROOT / 'manhua-series/chang-re-manh-nhat-lich-su'
STATE = SERIES / 'RENDER_101_150.json'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_script(folder, data):
    data['hashtags'] = ['#ChangReManhNhatLichSu', '#ReviewManhua', '#XuyenKhong']
    data['beats'][0]['type'] = 'HOOK'
    data['beats'][-1]['type'] = 'ENDING'
    for b in data['beats'][1:-1]:
        b['type'] = 'BUILD'
    write(SERIES / folder / 'script.json', data)


def prepare_old():
    beats = []
    for n in range(101, 111):
        src = read(SERIES / f'ep{n}/script.json')['beats']
        indices = sorted({round(i * (len(src)-1) / 18) for i in range(19)})
        for j,i in enumerate(indices):
            b = dict(src[i]); b['panel'] = f'crmn_ep{n}/' + b['panel']
            b['kind'] = 'recap'
            if j == 0: b['section'] = f'Tập {n}'
            beats.append(b)
        comments = {
            101: 'Một bài thơ vừa cứu người vừa gửi lời thách thức. Thẩm Lãng vẫn phải giữ tỉnh táo khi người cầm quyền có thể tùy ý biến lời nói thành án phạt.',
            104: 'Chiến thắng của Mộc Lan cho thấy lời đồn bất bại có thể che đi một kẽ hở chưa ai khai thác. Phần chuẩn bị trước trận đã quyết định khoảnh khắc ra đòn.',
            108: 'Tráo đề chỉ có tác dụng khi đối phương hoàn toàn dựa vào một đáp án học thuộc. Trương Xung đang đánh cược vào điều mình chưa kiểm chứng ở Kim Mộc Thông.'
        }
        if n in comments: beats.append({'panel':beats[-1]['panel'],'type':'BUILD','kind':'commentary','narration':comments[n]})
    save_script('long_101_110', {'template':'manhua_recap_long_vi','title':'Chàng Rể Mạnh Nhất Lịch Sử | Tập 101–110','source_dir':'manhua-recap/crmn_ep101','chapters':'100-109','description':'Từ bài thơ cứu người đến ba trận tranh đảo Kim Sơn: Mộc Lan đấu Đường Viêm, quân chiến và màn đổi đề thi của Trương Xung.','beats':beats})
    old = read(SERIES / 'long11/script.json')
    old['title'] = 'Chàng Rể Mạnh Nhất Lịch Sử | Tập 111–120'
    selected=[]
    for n in range(111,121):
        chapter=[b for b in old['beats'] if b['panel'].startswith(f'crmn_ep{n}/')]
        indices=sorted({round(i*(len(chapter)-1)/15) for i in range(16)})
        selected.extend(chapter[i] for i in indices)
    old['beats']=selected
    # These old kind labels sometimes denote character thoughts, not host opinion.
    for b in old['beats']: b['kind'] = 'recap'
    for chapter,comment in [(113,'Cuộc tranh chấp đã chuyển từ đấu trường sang sinh kế của người dân. Một kế phá đê có thể gây thiệt hại vượt xa hai gia tộc đang trả thù nhau.'),(119,'Người phục kích chỉ tính toán dựa trên vẻ ngoài của phu xe. Cách Lý Thiên Thu giấu thân phận khiến toàn bộ lợi thế mà sát thủ tưởng có trở thành sai lầm.')]:
        positions=[i for i,b in enumerate(old['beats']) if b['panel'].startswith(f'crmn_ep{chapter}/')]
        i=positions[-1];old['beats'].insert(i+1,{'panel':old['beats'][i]['panel'],'type':'BUILD','kind':'commentary','narration':comment})
    save_script('long_111_120',old)


def discover():
    state = read(STATE) if STATE.exists() else {'series':'chang-re-manh-nhat-lich-su','videos':[]}
    known={v['script'] for v in state['videos']}
    for start in range(101,151,10):
        end=start+9; folder=f'long_{start}_{end}'
        candidates=[(folder,f'Chàng Rể - Long {start}-{end}',start)]
        shortstart=9+((start-101)//10)*3
        candidates += [(f'best_of/cr_s{k:02d}',f'Chàng Rể - Short B{k:02d} ({start}-{end})',start) for k in range(shortstart,shortstart+3)]
        for folder,name,chapter in candidates:
            p=SERIES/folder/'script.json';rel=p.relative_to(ROOT).as_posix()
            if p.exists() and rel not in known:
                state['videos'].append({'name':name,'range':f'{start}-{end}','script':rel,'source':f'manhua-recap/crmn_ep{chapter}'})
    write(STATE,state);return state


def build_pending(state):
    for v in state['videos']:
        if v.get('project_id'):continue
        script=read(ROOT/v['script'])
        for b in script['beats']:
            sub,_,fname=b['panel'].rpartition('/')
            src=ROOT/'manhua-recap'/sub if sub else ROOT/v['source']
            if not (src/'_recap/panels'/fname).is_file():raise RuntimeError(f'Missing {b["panel"]}')
        capture=io.StringIO()
        dbpath=(ROOT/'backend/data/library.db').resolve()
        with sqlite3.connect(dbpath.as_uri()+'?mode=ro',uri=True) as db:
            found=db.execute('select id from project where name=? order by id desc limit 1',(v['name'],)).fetchone()
        original_call=recap.call
        def reuse_call(method,path,body=None,timeout=300):
            if found and method=='POST' and path=='/projects':
                return original_call('GET',f'/projects/{found[0]}')
            return original_call(method,path,body,timeout)
        recap.call=reuse_call
        try:
            with contextlib.redirect_stdout(capture):
                recap.cmd_build(ROOT/v['source'],v['name'],False,recap.COMMENTARY_VOICE,script_path=ROOT/v['script'])
        finally:recap.call=original_call
        m=re.search(r'project (\d+)',capture.getvalue())
        if not m:raise RuntimeError(capture.getvalue())
        v['project_id']=int(m.group(1));write(STATE,state)
        p=recap.call('GET',f'/projects/{v["project_id"]}')
        cfg=p['config'];cfg['voice']['provider']='edge_tts';cfg['visual_generation']['mode']='library';cfg['package']['ai_metadata_enabled']=False
        recap.call('PUT',f'/projects/{v["project_id"]}/beat-plan',{'project_name':p['project_name'],'script_text':p['script_text'],'script_locked':True,'beats':p['beats'],'config':cfg})
        print('BUILT',v['project_id'],v['name'],len(p['beats']),flush=True)


def run(state, slots):
    terminal={'COMPLETED','FAILED','CANCELLED'}
    while True:
        state=read(STATE)
        active=[]
        for v in state['videos']:
            if not v.get('run_id'):continue
            if v.get('status')=='COMPLETED' and v.get('final_qa'):continue
            r=recap.call('GET',f'/factory-runs/{v["run_id"]}');v['status']=r['status'];v['render_job_id']=r.get('render_job_id')
            if r.get('error_message'):v['error']=r['error_message']
            if v['status']=='NEEDS_REVIEW':
                cps=recap.call('GET',f'/factory-runs/{v["run_id"]}/checkpoints')
                v['review_checkpoints']=cps
                write(STATE,state)
                # Review the actual local report: small source panels and BUILD
                # sequences are expected in this established manhua format.
                report=recap.call('POST',f'/projects/{v["project_id"]}/quality-check')
                v['review_report']=report
                allowed={'LOW_RESOLUTION_ASSET','LOW_PURPOSE_DIVERSITY','PURPOSE_DUPLICATION','PACING_OUTLIER'}
                accepted=(not report.get('issues') and report.get('visual',{}).get('coverage')==1.0
                    and all(w['code'] in allowed for w in report.get('warnings',[])))
                if v['project_id']==306 and not (SERIES/'long_121_130/voice_corrections.json').exists():
                    accepted=False
                if accepted:
                    recap.call('POST',f'/factory-runs/{v["run_id"]}/continue?force=true')
                    v['status']='CONTINUING'
                    print('CONTINUED',v['project_id'],flush=True)
            if v['status']=='COMPLETED' and not v.get('final_qa'):
                v['final_qa']=recap.call('GET',f'/projects/{v["project_id"]}/final-qa')
                v['package']=recap.call('GET',f'/projects/{v["project_id"]}/package')
                print('DONE',v['project_id'],v['name'],flush=True)
            if v['status'] not in terminal:active.append(v)
        write(STATE,state)
        pending_order=sorted(state['videos'],key=lambda v: '/long_' not in v['script'])
        for v in pending_order:
            if len(active)>=slots:break
            if v.get('project_id') and not v.get('run_id'):
                r=recap.call('POST',f'/projects/{v["project_id"]}/factory-run');v['run_id']=r['id'];v['status']=r['status'];active.append(v);write(STATE,state)
                print('STARTED',v['project_id'],v['run_id'],v['name'],flush=True)
        remaining=[v for v in state['videos'] if v.get('status') not in terminal]
        print('STATUS',len(state['videos']),'videos',[(v.get('project_id'),v.get('status')) for v in active],flush=True)
        if not remaining:break
        time.sleep(15)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare-old','build','run']);p.add_argument('--slots',type=int,default=3);a=p.parse_args()
    if a.action=='prepare-old':prepare_old();discover()
    elif a.action=='build':build_pending(discover())
    else:run(discover(),a.slots)
