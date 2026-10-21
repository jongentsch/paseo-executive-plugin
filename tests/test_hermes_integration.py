"""Run through `hermes --run-module unittest discover -s tests -p test_hermes_integration.py -v`."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from hermes_cli.plugins import PluginContext, PluginManager
    from hermes_cli.plugins_manifest import PluginManifest
    HERMES=True
except ImportError:
    HERMES=False


@unittest.skipUnless(HERMES,'Run with the Hermes runtime for integration tests')
class HermesIntegration(unittest.TestCase):
    def test_real_injection_api_accepts_route_and_acknowledges_outbox(self):
        from paseo_executive.core import Store
        from paseo_executive.runtime import Runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'config.yaml').write_text('plugins:\n  entries:\n    paseo-executive:\n      allow_gateway_injection: true\n')
            manager=PluginManager(scope_key=directory)
            received=[]
            manager.set_tui_message_injector(self,lambda **kw: received.append(kw) or True)
            context=PluginContext(PluginManifest(name='paseo-executive',source='user'),manager)
            store=Store(root/'data')
            store.set_setting('notification_session_key','test-durable-session-key')
            store.event('local','worker','completed',{'status':'idle'})
            runtime=Runtime(store)
            runtime.context=context
            with patch('hermes_cli.plugin_events.broadcast_plugin_event'):
                runtime.deliver()
            self.assertEqual(received[0]['session_key'],'test-durable-session-key')
            self.assertIn('completed',received[0]['content'])
            self.assertTrue(store.events()[0]['delivered'])
            manager.clear_tui_message_injector(self)

    def test_api_state_and_confirmation_gate(self):
        from paseo_executive import api
        from paseo_executive.core import Store
        from paseo_executive.runtime import Runtime
        with tempfile.TemporaryDirectory() as directory:
            runtime=Runtime(Store(directory))
            runtime.start=lambda:None
            app=FastAPI();app.include_router(api.router)
            with patch.object(api,'get_runtime',return_value=runtime),TestClient(app) as client:
                self.assertEqual(client.get('/state').json()['hosts'][0]['id'],'local')
                response=client.post('/action',json={'name':'paseo_decide_permission','args':{}})
                self.assertEqual(response.status_code,403)
                self.assertEqual(client.post('/action',json={'name':'unknown'}).status_code,422)
                response=client.post('/action',json={'name':'paseo_hosts','args':{'action':'add','host_id':'test-remote','target':'worker:6767'}})
                self.assertEqual(response.status_code,200)
                self.assertEqual(len(client.get('/state').json()['hosts']),2)
                response=client.post('/action',json={'name':'paseo_hosts','args':{'action':'remove','host_id':'test-remote'}})
                self.assertEqual(response.status_code,200)

    def test_native_host_settings_and_http_editor_share_the_real_config(self):
        from hermes_constants import set_hermes_home_override, reset_hermes_home_override
        from paseo_executive import api
        from paseo_executive.runtime import bind_context, get_runtime
        with tempfile.TemporaryDirectory() as directory:
            token = set_hermes_home_override(directory)
            unbind = None
            try:
                manager = PluginManager(scope_key=directory)
                context = PluginContext(PluginManifest(name='paseo-executive',source='user'), manager)
                context.set_config('hosts', [
                    {'id':'local','home':'~/.paseo'},
                    {'id':'ssh','target':'ssh://user@worker'},
                ])
                unbind = bind_context(context)
                runtime = get_runtime()
                self.assertIs(runtime.context, context)
                app = FastAPI()
                app.include_router(api.router)
                with patch.object(runtime,'start'), TestClient(app) as client:
                    self.assertEqual(len(client.get('/state').json()['hosts']),2)
                    response = client.post('/action',json={'name':'paseo_hosts','args':{
                        'action':'add','host_id':'remote','target':'192.0.2.1:6767'}})
                    self.assertEqual(response.status_code,200)
                    self.assertEqual({h['id'] for h in context.get_config('hosts')},{'local','ssh','remote'})
                    context.set_config('hosts',[{'id':'only','target':'new:6767'}])
                    state = client.get('/state').json()
                    self.assertEqual([h['id'] for h in state['hosts']],['only'])
            finally:
                if unbind: unbind()
                reset_hermes_home_override(token)
