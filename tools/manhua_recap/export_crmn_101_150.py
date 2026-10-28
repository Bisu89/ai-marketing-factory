"""Collect finished batch outputs without duplicating large MP4 data."""
import json
import os
import shutil
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SERIES=ROOT/'manhua-series/chang-re-manh-nhat-lich-su'
DEST=SERIES/'renders_101_150'

def export():
    state=json.loads((SERIES/'RENDER_101_150.json').read_text(encoding='utf-8'))
    rows=[]
    count=0
    for v in state['videos']:
        pkg=v.get('package') or {}
        rel=pkg.get('video_path')
        if not rel:continue
        source=ROOT/'backend'/rel
        if not source.is_file():continue
        is_long='/long_' in v['script']
        folder=DEST/v['range'];folder.mkdir(parents=True,exist_ok=True)
        suffix='long_'+v['range'] if is_long else 'short_'+Path(v['script']).parent.name
        target=folder/(suffix+'.mp4')
        if not target.exists():
            try:os.link(source,target)
            except OSError:shutil.copy2(source,target)
            print('EXPORTED',target.relative_to(ROOT),flush=True)
        thumb=pkg.get('thumbnail_path')
        if thumb:
            src=ROOT/'backend'/thumb;dst=folder/(suffix+'_thumbnail.jpg')
            if src.is_file() and not dst.exists():shutil.copy2(src,dst)
        meta={'project_id':v['project_id'],'factory_run_id':v['run_id'],'render_job_id':v.get('render_job_id'),'range':v['range'],'script':v['script'],'package':pkg,'final_qa':v.get('final_qa'),'video':target.relative_to(SERIES).as_posix()}
        (folder/(suffix+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        rows.append((v['range'],'Long' if is_long else suffix,pkg.get('duration'),target.relative_to(DEST).as_posix()))
        count+=1
    DEST.mkdir(exist_ok=True)
    lines=['# Chàng Rể Mạnh Nhất Lịch Sử — tập 101–150','','Mỗi 10 tập: 1 Long và 3 Short. Giọng đọc Edge TTS, ảnh truyện có sẵn.','','| Cụm tập | Video | Thời lượng |','|---|---|---|']
    for r,kind,duration,link in rows:
        duration=round(duration or 0);m,s=divmod(duration,60)
        lines.append(f'| {r} | [{kind}]({link}) | {m}:{s:02d} |')
    lines+=['',f'Đã xuất: {count}/20 video.','']
    (DEST/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return count

if __name__=='__main__':
    import sys
    while True:
        count=export()
        if '--watch' not in sys.argv or count==20:break
        time.sleep(30)
