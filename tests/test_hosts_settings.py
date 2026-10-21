import copy
import tempfile
import unittest
from unittest.mock import patch

from paseo_executive.core import ExecutiveError, PaseoCLI, Store
from paseo_executive.runtime import Runtime
from paseo_executive.tools import execute


class SettingsContext:
    def __init__(self, **settings):
        self.settings = copy.deepcopy(settings)

    def get_config(self, key, default=None):
        return copy.deepcopy(self.settings.get(key, default))

    def set_config(self, key, value):
        self.settings[key] = copy.deepcopy(value)


class HostSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.runtime = Runtime(self.store)
        self.context = self.runtime.context = SettingsContext()

    def test_native_settings_configures_all_connection_types(self):
        self.context.settings['hosts'] = [
            {'id':'local','home':'~/.paseo'},
            {'id':'linux','target':'ssh://jon@linux'},
            {'id':'windows','target':'192.0.2.20:6767'},
        ]
        self.runtime.refresh_settings()
        self.assertEqual(len(self.store.hosts()), 3)
        self.assertEqual(self.store.host('linux')['target'], 'ssh://jon@linux')
        self.assertTrue(self.store.host('local')['home'].startswith('/'))
        self.assertIsNone(self.runtime.config_error)

    def test_add_edit_pause_remove_write_same_settings_value(self):
        execute(self.runtime,'paseo_hosts',{'action':'add','host_id':'remote','target':'old:6767','label':'Old'})
        execute(self.runtime,'paseo_hosts',{'action':'update','host_id':'remote','target':'new:6767','label':'New'})
        execute(self.runtime,'paseo_hosts',{'action':'update','host_id':'remote','enabled':False})
        configured = next(h for h in self.context.settings['hosts'] if h['id']=='remote')
        self.assertEqual(configured['target'], 'new:6767')
        self.assertEqual(configured['label'], 'New')
        self.assertFalse(configured['enabled'])
        self.runtime.refresh_settings()
        self.assertFalse(self.store.host('remote')['enabled'])
        execute(self.runtime,'paseo_hosts',{'action':'remove','host_id':'remote'})
        self.assertNotIn('remote', [h['id'] for h in self.context.settings['hosts']])
        self.runtime.refresh_settings()
        self.assertEqual(len(self.store.hosts()), 1)

    def test_generic_editor_changes_reconcile_without_restart(self):
        self.context.settings['hosts'] = [{'id':'worker','target':'before:6767'}]
        self.runtime.refresh_settings()
        old = self.store.host('worker')
        self.context.settings['hosts'] = [{'id':'worker','target':'after:6767'}]
        self.runtime.refresh_settings()
        self.assertFalse(self.runtime.active(old))
        self.assertEqual(self.store.host('worker')['target'], 'after:6767')
        self.context.settings['hosts'] = []
        self.runtime.refresh_settings()
        self.assertEqual(self.store.hosts(), [])

    def test_invalid_or_duplicate_config_preserves_last_working_hosts(self):
        for invalid in [[{'id':'x','home':'/tmp/x'},{'id':'x','target':'remote:6767'}],
                        [{'id':'x','target':'ssh://'}], [{'id':'x','enabled':'false','target':'x:6767'}]]:
            self.context.settings['hosts'] = invalid
            self.runtime.refresh_settings()
            self.assertIsNotNone(self.runtime.config_error)
            self.assertEqual([h['id'] for h in self.store.hosts()], ['local'])

    def test_failed_settings_write_does_not_change_registry(self):
        with patch.object(self.context,'set_config',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):
                self.runtime.save_host({'id':'remote','target':'worker:6767'})
        self.assertEqual([h['id'] for h in self.store.hosts()], ['local'])

    def test_upgrade_keeps_existing_hosts_until_user_sets_host_list(self):
        self.store.save_host({'id':'existing','target':'worker:6767'})
        self.runtime.refresh_settings()
        self.assertEqual(len(self.store.hosts()), 2)
        self.runtime.save_host({'id':'new','target':'new:6767'})
        self.assertEqual({h['id'] for h in self.context.settings['hosts']},{'local','existing','new'})

    def test_each_spawn_uses_selected_host_even_with_same_worker_id(self):
        captured = []
        class CLI:
            def call(self, host, *args):
                captured.append((host['target'],args))
                return {'id':'same-id','status':'running'}
        self.runtime.executive.cli = CLI()
        for name in ['one','two']:
            self.runtime.save_host({'id':name,'target':name+':6767'})
            execute(self.runtime,'paseo_spawn',{'host_id':name,'prompt':'test','cwd':'/project'})
        self.assertEqual([c[0] for c in captured],['one:6767','two:6767'])
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM snapshots WHERE agent=?',('same-id',)).fetchone()[0],2)

    def test_changed_endpoint_rejects_late_events_from_old_monitor(self):
        old = self.store.host('local')
        self.store.observe('local',{'id':'a','status':'running'},expected_host=old)
        self.runtime.save_host({'id':'local','target':'different:6767'})
        self.assertEqual(self.store.observe('local',{'id':'a','status':'error'},expected_host=old),[])
        self.assertEqual(self.store.events(),[])

    @patch('paseo_executive.core.subprocess.run')
    def test_cli_remote_and_ssh_targets_never_use_shell(self, run):
        import subprocess
        run.return_value = subprocess.CompletedProcess([],0,'[]','')
        for target in ['192.0.2.1:6767','ssh://user@devbox']:
            PaseoCLI('/paseo').call({'target':target},'ls','-g')
            command = run.call_args.args[0]
            self.assertEqual(command[1:3],['--host',target])
            self.assertNotIn('shell',run.call_args.kwargs)

    def test_audit_events_cannot_starve_worker_notifications(self):
        for i in range(60):
            self.store.event('local',str(i),'spawned',{})
        self.store.event('local','worker','completed',{})
        events = self.store.events(limit=20,unread=True,notifications_only=True)
        self.assertEqual([event['kind'] for event in events],['completed'])

    def test_probe_updates_only_selected_hosts_health(self):
        class CLI:
            def call(self, host, *args):
                if host['id']=='bad': raise ExecutiveError('unreachable')
                return {'connectedDaemon':'reachable'}
        self.runtime.executive.cli=CLI()
        self.runtime.save_host({'id':'good','target':'good:6767'})
        self.runtime.save_host({'id':'bad','target':'bad:6767'})
        self.assertTrue(execute(self.runtime,'paseo_hosts',{'action':'probe','host_id':'good'})['ok'])
        with self.assertRaises(ExecutiveError):
            execute(self.runtime,'paseo_hosts',{'action':'probe','host_id':'bad'})
        self.assertTrue(self.store.host('good')['health']['connected'])
        self.assertFalse(self.store.host('bad')['health']['connected'])
        self.assertIsNone(self.store.host('local')['health'])
