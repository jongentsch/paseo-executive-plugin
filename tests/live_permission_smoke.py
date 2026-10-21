"""Opt-in smoke: request elevation for /usr/bin/true, then deny that exact request."""
import json
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paseo_executive.core import Executive,Store

with tempfile.TemporaryDirectory(prefix='paseo-permission-smoke-') as directory:
    store=Store(directory)
    executive=Executive(store)
    worker=executive.spawn('local',
        'This is a permission integration test. Use the exec_command tool to run /usr/bin/true with sandbox_permissions=require_escalated and justification="Paseo Executive permission smoke test". Request elevation explicitly even though true needs no privileges. Do not run any other commands, read or modify files, or spawn agents. If elevation is denied, stop and report that the test was denied as expected.',
        str(Path.cwd()),'codex',title='Paseo Executive permission smoke test')['agent']['id']
    print(json.dumps({'worker':worker}),flush=True)
    try:
        deadline=time.time()+100
        while time.time()<deadline:
            snapshot=executive.inspect('local',worker)
            store.observe('local',snapshot)
            pending=snapshot.get('pendingPermissions',[])
            if pending:
                request=pending[0]
                print(json.dumps({'permission_surfaced':True,'request_id':request['id'],'kind':request.get('kind')}),flush=True)
                result=executive.decide('local',worker,request['id'],'deny')
                print(json.dumps({'exact_request_denied':result['ok']}),flush=True)
                assert any(e['kind']=='permission' for e in store.events())
                break
            if snapshot['status'] in {'idle','error','closed'}:
                raise RuntimeError('Worker ended before emitting a permission; inspect provider availability or approval policy')
            time.sleep(1)
        else: raise RuntimeError('Permission smoke timed out')
    finally:
        executive.cli.call(store.host('local'),'stop',worker)
        executive.cli.call(store.host('local'),'archive',worker)
