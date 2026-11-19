#!/usr/bin/env python3
"""Build local sing-box 1.13.x SRS rule sets for the Momo Geph profile."""
import argparse, json, pathlib, shutil, subprocess, sys, tarfile, tempfile, urllib.request
from collections import defaultdict

BASE = pathlib.Path(__file__).resolve().parent
LOYAL = 'https://raw.githubusercontent.com/Loyalsoldier/v2ray-rules-dat/release/'
GEOIP = 'https://raw.githubusercontent.com/Loyalsoldier/geoip/release/srs/'
FAKEIP = 'https://raw.githubusercontent.com/qichiyuhub/rule/refs/heads/main/rules/fakeipfilter.json'
DLC = 'https://github.com/v2fly/domain-list-community/archive/refs/heads/master.tar.gz'
FILES = ['direct-list.txt','proxy-list.txt','china-list.txt','apple-cn.txt','google-cn.txt','gfw.txt']

def download(url, dest):
    dest=pathlib.Path(dest); dest.parent.mkdir(parents=True,exist_ok=True)
    candidates=[url]
    if 'raw.githubusercontent.com/' in url:
        candidates.append(url.replace('https://raw.githubusercontent.com/','https://cdn.jsdelivr.net/gh/').replace('/release/','@release/').replace('/refs/heads/main/','@main/'))
    errors=[]
    for candidate in candidates:
        try:
            req=urllib.request.Request(candidate,headers={'User-Agent':'momo-geph-rule-builder/1.1'})
            with urllib.request.urlopen(req,timeout=120) as r, open(dest,'wb') as f: shutil.copyfileobj(r,f)
            if dest.stat().st_size < 16: raise RuntimeError('download too small')
            return
        except Exception as e: errors.append(f'{candidate}: {e}')
    raise RuntimeError('download failed:\n'+'\n'.join(errors))

def parse_line(raw):
    line=raw.split('#',1)[0].strip()
    if not line: return None
    parts=line.split(); head=parts[0]; attrs={x[1:] for x in parts[1:] if x.startswith('@')}
    if head.startswith('include:'): return ('include',head[8:],attrs)
    if ':' in head:
        typ,value=head.split(':',1)
        if typ not in ('domain','full','keyword','regexp'): return None
    else: typ,value='domain',head
    value=value.strip().rstrip('.')
    return (typ,value,attrs) if value else None

class Lists:
    def __init__(self,root): self.root=pathlib.Path(root)
    def read(self,name,exclude=(),require=(),stack=None):
        stack=set() if stack is None else stack
        name=name.replace('@','_')
        if name in stack: return []
        p=self.root/name
        if not p.is_file(): raise FileNotFoundError(f'missing V2Fly list: {p}')
        stack.add(name); result=[]
        for raw in p.read_text(encoding='utf-8').splitlines():
            item=parse_line(raw)
            if not item: continue
            typ,value,attrs=item
            if attrs.intersection(exclude) or (require and not attrs.intersection(require)): continue
            if typ=='include': result.extend(self.read(value,exclude,require,stack))
            else: result.append((typ,value))
        stack.remove(name); return result

def plain(path):
    out=[]
    for raw in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        item=parse_line(raw)
        if item and item[0]!='include': out.append((item[0],item[1]))
    return out

def compile_domain(tag,items,outdir,binary):
    fields=defaultdict(set); mapping={'domain':'domain_suffix','full':'domain','keyword':'domain_keyword','regexp':'domain_regex'}
    for typ,value in items:
        if typ in mapping: fields[mapping[typ]].add(value)
    rules=[{k:sorted(fields[k])} for k in ('domain','domain_suffix','domain_keyword','domain_regex') if fields[k]]
    if not rules: raise RuntimeError(f'{tag}: empty generated rule set')
    source=outdir/(tag+'.json'); target=outdir/(tag+'.srs')
    source.write_text(json.dumps({'version':4,'rules':rules},ensure_ascii=False),encoding='utf-8')
    subprocess.run([binary,'rule-set','compile','--output',str(target),str(source)],check=True)
    source.unlink(); print(f'{tag}: {sum(map(len,fields.values()))} domains')

def safe_extract(tar,root):
    root=pathlib.Path(root).resolve()
    for m in tar.getmembers():
        target=(root/m.name).resolve()
        if target!=root and root not in target.parents: raise RuntimeError('unsafe path in source archive')
    tar.extractall(root)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out-dir',default=str(BASE/'rule_set'))
    ap.add_argument('--sing-box',default='sing-box')
    a=ap.parse_args(); out=pathlib.Path(a.out_dir).resolve(); out.mkdir(parents=True,exist_ok=True)
    v=subprocess.run([a.sing_box,'version'],check=True,text=True,capture_output=True).stdout.strip()
    if '1.13.' not in v: raise RuntimeError(f'Need sing-box 1.13.x to generate rule-set version 4; got: {v}')
    with tempfile.TemporaryDirectory(prefix='momo-geph-rules-') as td:
        td=pathlib.Path(td); archive=td/'dlc.tar.gz'
        print('Downloading V2Fly domain-list-community source...'); download(DLC,archive)
        with tarfile.open(archive,'r:gz') as t: safe_extract(t,td)
        roots=list(td.glob('domain-list-community-*/data'))
        if not roots: raise RuntimeError('V2Fly data directory not found')
        dl=Lists(roots[0])
        for f in FILES: print('Downloading Loyalsoldier',f); download(LOYAL+f,td/f)
        fake=td/'fakeipfilter.json'; print('Downloading custom FakeIP filter...'); download(FAKEIP,fake)
        obj=json.loads(fake.read_text(encoding='utf-8'))
        if not isinstance(obj,dict) or obj.get('version') not in (1,2,3,4) or 'rules' not in obj: raise RuntimeError('fakeipfilter is not a sing-box source rule-set')
        subprocess.run([a.sing_box,'rule-set','compile','--output',str(out/'geosite-fakeipfilter.srs'),str(fake)],check=True)
        p={f:plain(td/f) for f in FILES}
        groups={
          'geosite-ai':dl.read('category-ai-!cn',exclude=('cn',)),
          'geosite-youtube':dl.read('youtube'),
          'geosite-google':dl.read('google')+p['google-cn.txt'],
          'geosite-github':dl.read('github'),
          'geosite-onedrive':dl.read('onedrive'),
          'geosite-microsoft':dl.read('microsoft'),
          'geosite-apple':dl.read('apple')+p['apple-cn.txt'],
          'geosite-telegram':dl.read('telegram'),
          'geosite-tiktok':dl.read('tiktok'),
          'geosite-netflix':dl.read('netflix'),
          'geosite-paypal':dl.read('paypal'),
          'geosite-steam':dl.read('steam'),
          'geosite-steamcn':dl.read('steam',require=('cn',)),
          'geosite-!cn':dl.read('geolocation-!cn',exclude=('cn','ads'))+p['proxy-list.txt']+p['gfw.txt'],
          'geosite-cn':dl.read('cn')+p['direct-list.txt']+p['china-list.txt']
        }
        for tag,items in groups.items(): compile_domain(tag,items,out,a.sing_box)
        for name in ('cn','google','telegram','netflix'):
            print('Downloading Loyalsoldier GeoIP',name)
            download(GEOIP+name+'.srs',out/f'geoip-{name}.srs')
    expected={'geosite-fakeipfilter','geosite-ai','geosite-youtube','geosite-google','geosite-github','geosite-onedrive','geosite-microsoft','geosite-apple','geosite-telegram','geosite-tiktok','geosite-netflix','geosite-paypal','geosite-steam','geosite-steamcn','geosite-!cn','geosite-cn','geoip-cn','geoip-google','geoip-telegram','geoip-netflix'}
    missing=[x for x in expected if not (out/(x+'.srs')).is_file() or (out/(x+'.srs')).stat().st_size==0]
    if missing: raise RuntimeError('missing output rule sets: '+', '.join(sorted(missing)))
    print(f'\nSUCCESS: {len(expected)} rule sets compiled into {out}')

if __name__=='__main__':
    try: main()
    except Exception as e: print('ERROR:',e,file=sys.stderr); sys.exit(1)
