import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paseo_executive.core import Executive, ExecutiveError, PaseoCLI, Store
from paseo_executive.runtime import Runtime
from paseo_executive.tools import execute, register


class FakeCLI:
    def __init__(self):
        self.calls = []
        self.snapshots = {}

    def call(self, host, *args):
        self.calls.append((host["id"], args))
        if args[0] == 'inspect':
            return self.snapshots[(host['id'], args[1])]
        if args[0] == 'run':
            return {'id': 'worker-full-id', 'status': 'running'}
        return {'ok': True}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.cli = FakeCLI()
        self.executive = Executive(self.store, self.cli)

    def observe(self, status, **kwargs):
        return self.store.observe('local', dict(id='a', status=status, **kwargs))

    def test_hosts_persist_and_remove_does_not_stop_workers(self):
        self.store.save_host({'id':'ssh-worker', 'target':'ssh://user@worker'})
        self.store.save_host({'id':'remote', 'target':'10.0.0.4:6767'})
        self.assertEqual(len(Store(self.temp.name).hosts()), 3)
        self.store.remove_host('ssh-worker')
        self.assertEqual(len(self.store.hosts()), 2)
        self.store.remove_host('local')
        self.assertNotIn('local', [h['id'] for h in Store(self.temp.name).hosts()])
        self.assertEqual(self.cli.calls, [])

    def test_invalid_host_and_credential_urls_rejected(self):
        for config in [{'id':'../bad','home':'/x'}, {'id':'bad','target':'--help'},
                       {'id':'bad','target':'ws://user:password@host/ws'},
                       {'id':'bad','home':'/x','target':'worker:6767'}]:
            with self.assertRaises(ExecutiveError):
                self.store.save_host(config)

    def test_events_deduplicate_across_restart_and_allow_new_turn(self):
        self.observe('idle')
        self.assertEqual(self.store.events(), [])
        self.observe('running')
        self.observe('idle')
        Store(self.temp.name).observe('local', {'id':'a','status':'idle'})
        self.assertEqual([e['kind'] for e in self.store.events()], ['completed'])
        self.observe('running')
        self.observe('idle')
        self.assertEqual(len(self.store.events()), 2)

    def test_pending_permission_and_failure_event_exact_scope(self):
        request = {'id':'req1','kind':'tool','input':{'command':'true'}}
        self.observe('running', pendingPermissions=[request])
        self.observe('running', pendingPermissions=[request])
        self.observe('error', lastError='failed', pendingPermissions=[])
        self.observe('error', lastError='failed', pendingPermissions=[])
        events=self.store.events()
        self.assertEqual([e['kind'] for e in events], ['permission','failed'])
        self.assertEqual(events[0]['data'],request)
        self.assertEqual(events[0]['host'],'local')

    def test_removed_host_rejects_late_stream_events(self):
        self.store.remove_host('local')
        self.assertEqual(self.observe('error'), [])

    def test_permission_revalidation_rejects_wrong_host_or_stale_request(self):
        self.cli.snapshots[('local','full-id')]={'Id':'full-id','Status':'running','PendingPermissions':[{'id':'r'}]}
        self.executive.decide('local','full-id','r','deny')
        self.assertEqual(self.cli.calls[-1], ('local',('permit','deny','full-id','r')))
        for agent, request in [('full-id','stale'), ('prefix','r')]:
            if agent == 'prefix':
                self.cli.snapshots[('local','prefix')]=self.cli.snapshots[('local','full-id')]
            with self.assertRaises(ExecutiveError):
                self.executive.decide('local',agent,request,'allow')
        with self.assertRaises(ExecutiveError):
            self.executive.decide('unknown','full-id','r','allow')
        self.assertEqual(sum(c[1][0]=='permit' for c in self.cli.calls),1)

    def test_async_spawn_and_no_shell_interpolation(self):
        prompt='--hello $(touch /tmp/should-not-exist)'
        result=self.executive.spawn('local',prompt,'/project with spaces')
        self.assertEqual(result['agent']['id'],'worker-full-id')
        args=self.cli.calls[0][1]
        self.assertIn('--no-wait',args)
        self.assertEqual(args[-2:],('--',prompt))

    @patch('paseo_executive.core.subprocess.run')
    def test_cli_passes_json_before_positional_separator(self, run):
        run.return_value=subprocess.CompletedProcess([],0,'{"ok":true}','')
        PaseoCLI('/paseo').call({'home':'/local/home'},'run','--','--prompt')
        command=run.call_args.args[0]
        self.assertLess(command.index('--json'),command.index('--'))
        self.assertEqual(command[-1],'--prompt')
        self.assertNotIn('shell',run.call_args.kwargs)

    @patch('paseo_executive.core.subprocess.run')
    def test_cli_timeout_marks_outcome_unknown(self, run):
        run.side_effect=subprocess.TimeoutExpired('paseo',25)
        with self.assertRaisesRegex(ExecutiveError,'outcome may be unknown'):
            PaseoCLI('/paseo').call({'home':'/local/home'},'run','task')

    def test_leases_and_delivery_claims_are_process_safe(self):
        other=Store(self.temp.name)
        self.assertTrue(self.store.lease('host:local','owner1'))
        self.assertFalse(other.lease('host:local','owner2'))
        self.store.release('host:local','owner1')
        self.assertTrue(other.lease('host:local','owner2'))
        event_id=self.store.event('local','a','completed',{})
        self.assertTrue(self.store.claim_event(event_id))
        self.assertFalse(other.claim_event(event_id))

    def test_failed_notification_retained_until_accepted(self):
        class Context:
            accepted=False
            def get_config(self,key): return None
            def emit(self,*args): pass
            def inject_message(self,*args,**kwargs): return self.accepted
        runtime=Runtime(self.store,self.cli)
        runtime.context=Context()
        event_id=self.store.event('local','a','completed',{})
        # Avoid importing Hermes in the standalone test; use a public bridge stub.
        import types,sys
        bridge=types.ModuleType('hermes_cli.plugin_events')
        bridge.broadcast_plugin_event=lambda *args:None
        with patch.dict(sys.modules, {'hermes_cli.plugin_events':bridge}):
            runtime.deliver()
            self.assertFalse(self.store.events()[0]['delivered'])
            with self.store.db() as db:
                db.execute('UPDATE events SET claimed_until=0')
            runtime.context.accepted=True
            runtime.deliver()
        self.assertTrue(self.store.events()[0]['delivered'])

    def test_hook_requires_human_decision_and_registration_is_inert(self):
        class Context:
            def __init__(self): self.tools={}; self.hooks={}
            def register_tool(self,**kwargs): self.tools[kwargs['name']]=kwargs
            def register_hook(self,name,callback): self.hooks[name]=callback
            def register_skill(self,name,path,**kwargs): pass
            def on_unload(self,callback): self.unload=callback
        ctx=Context()
        with patch('paseo_executive.tools.bind_context', return_value=lambda: None):
            register(ctx)
        directive=ctx.hooks['pre_tool_call']('paseo_decide_permission',{'decision':'allow'})
        self.assertEqual(directive['action'],'approve')
        self.assertIsNone(ctx.hooks['pre_tool_call']('paseo_hosts',{'action':'list'}))
        self.assertEqual(len(ctx.tools),7)


if __name__=='__main__':
    unittest.main()
