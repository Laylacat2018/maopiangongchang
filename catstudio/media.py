"""本地媒体适配器。只检测与抽帧，不代替剪映剪辑转码。"""
import json, subprocess, shutil, re
from fractions import Fraction
from pathlib import Path
from PIL import Image

def run(args, timeout=240):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        raise ValueError('媒体读取失败，请确认文件完整、编码可读并已安装 FFmpeg。')
    return result

def probe(path):
    if not shutil.which('ffprobe'): raise ValueError('未安装 ffprobe，请安装 FFmpeg 后重试')
    result = run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)],60)
    payload=json.loads(result.stdout)
    video=next((x for x in payload.get('streams',[]) if x.get('codec_type')=='video'),{})
    audio=next((x for x in payload.get('streams',[]) if x.get('codec_type')=='audio'),{})
    return {'duration':float(payload.get('format',{}).get('duration',0)), 'width':int(video.get('width',0)), 'height':int(video.get('height',0)), 'fps':float(Fraction(video.get('avg_frame_rate','0/1') or '0/1')), 'codec':video.get('codec_name'), 'has_audio':bool(audio),'audio_codec':audio.get('codec_name')}

def frames(path, directory):
    directory.mkdir(parents=True, exist_ok=True)
    # 60s/120 frames bounds prevent accidental multi-hour decoding.
    run(['ffmpeg','-y','-v','error','-i',str(path),'-t','60','-vf','fps=2,scale=320:-2','-frames:v','120',str(directory/'frame-%03d.jpg')])
    return sorted(x.name for x in directory.glob('frame-*.jpg'))

def inspect_final(path, brief):
    meta=probe(path)
    result=run(['ffmpeg','-hide_banner','-i',str(path),'-vf','blackdetect=d=0.15:pix_th=0.10','-af','silencedetect=n=-45dB:d=0.5','-f','null','-'],600)
    log=result.stderr.decode('utf-8',errors='replace')
    black=[{'start':float(a),'end':float(b)} for a,b in re.findall(r'black_start:([\d.]+) black_end:([\d.]+)',log)]
    silence=[float(x) for x in re.findall(r'silence_start: ([\d.]+)',log)]
    ratio=meta['width']/max(meta['height'],1)
    wanted=9/16 if brief.get('aspect_ratio','9:16')=='9:16' else 16/9
    checks={'ratio':abs(ratio-wanted)<.03,'resolution':meta['width']>=brief.get('min_width',1080) and meta['height']>=brief.get('min_height',1920 if wanted<1 else 1080),'duration':brief.get('duration_min_s',20)-.2<=meta['duration']<=brief.get('duration_max_s',30)+.2,'audio':meta['has_audio'],'black':not black,'silence':not silence}
    return {'meta':meta,'checks':checks,'black_segments':black,'silence_starts':silence,'passed':all(checks.values())}
