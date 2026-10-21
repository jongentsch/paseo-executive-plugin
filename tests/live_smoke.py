"""Opt-in local smoke: a no-tools worker, real SDK snapshots, completion delivery."""
import json
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paseo_executive.core import Executive, Store


def main():
    with tempfile.TemporaryDirectory(prefix='paseo-executive-smoke-') as directory:
        store=Store(directory)
        executive=Executive(store)
        proc=subprocess.Popen(['node','bridge/watch.mjs'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        proc.stdin.write(json.dumps({'url':'ws://127.0.0.1:6767/ws','home':str(Path.home()/'.paseo')})+'\n')
        proc.stdin.close()
        selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
        worker=None
        deadline=time.time()+100
        ready=False
        observed=0
        try:
            while time.time()<deadline:
                if not selector.select(1):
                    if proc.poll() is not None:break
                    continue
                line=proc.stdout.readline()
                if not line:break
                frame=json.loads(line)
                if frame['type']=='error':raise RuntimeError(frame['message'])
                if frame['type']=='snapshot':
                    observed+=1
                    store.observe('local',frame['agent'])
                if frame['type']=='ready' and not ready:
                    ready=True
                    worker=executive.spawn('local','Reply exactly PASEO_EXECUTIVE_SMOKE_OK. Do not call tools, read or modify files, or spawn other agents.',
                                           str(Path.cwd()),'codex',title='Paseo Executive plugin smoke test')['agent']['id']
                    print(json.dumps({'sdk_subscription_ready':True,'spawned_worker':worker}),flush=True)
                events=[e for e in store.events() if e['agent']==worker and e['kind'] in {'completed','failed'}]
                if events:
                    print(json.dumps({'observed_snapshots':observed,'worker_event':events[-1]}),flush=True)
                    assert events[-1]['kind']=='completed'
                    return worker
            raise RuntimeError(f'Smoke timed out: sdk_ready={ready}, worker={worker}, snapshots={observed}')
        finally:
            proc.terminate()
            try:proc.wait(timeout=4)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            errors=proc.stderr.read()
            if errors: print(errors[:1500],file=sys.stderr)
            if worker:
                try:executive.cli.call(store.host('local'),'archive',worker)
                except Exception as exc:print(f'Smoke worker cleanup: {exc}',file=sys.stderr)


if __name__=='__main__': main()
