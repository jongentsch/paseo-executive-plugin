import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from paseo_executive.core import Executive, ExecutiveError, Store, event_message


def activity(text='Completed the scoped fix', turn='turn-1'):
    return {'source':'paseo_sdk_timeline','scope':'turn','format':'timeline','observed_at':120,
            'entries':[{'type':'assistant_message','text':text,'turn_id':turn,'timestamp':'2026-10-21T12:00:00Z'}]}


class EventFixture:
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name)

    def completed(self):
        self.store.record_assignment('local','worker','Fix the login redirect',title='Login fix',cwd='/project',provider='codex',recorded=90)
        self.store.observe('local',{'id':'worker','status':'running','provider':'codex','cwd':'/project',
            'name':'Login fix','model':'chosen-model','worktree':{'branch':'fix/login'},
            'activeTurn':{'turnId':'turn-1','startedAt':100},'_executive_observed_at':101},source='sdk')
        report=json.dumps({'summary':'Fixed the redirect','tests':['pytest tests/login: passed'],
                           'changed_files':['login.py'],'artifacts':['reports/login.txt'],'passed':True})
        ids=self.store.observe('local',{'id':'worker','status':'idle','activeTurn':None,'updatedAt':'version-1',
            '_executive_observed_at':120,'_executive_activity':activity(report)},source='sdk')
        return self.store.get_event(ids[0])


class EventContextTests(EventFixture, unittest.TestCase):
    def test_completion_has_context_unverified_report_and_followup(self):
        event=self.completed()
        self.assertEqual(event['schema_version'],1)
        self.assertEqual(event['data'],{'status':'idle','name':'Login fix'})
        self.assertEqual(event['context']['assignment']['prompt'],'Fix the login redirect')
        self.assertEqual(event['context']['worker']['branch'],'fix/login')
        self.assertEqual(event['context']['worker']['cwd'],'/project')
        self.assertEqual(event['context']['timing']['elapsed_seconds'],20)
        self.assertEqual(event['context']['observation']['source'],'sdk')
        self.assertEqual(event['result']['summary'],'Fixed the redirect')
        self.assertEqual(event['result']['attribution'],'worker_reported')
        self.assertEqual(event['result']['verification'],'not_verified')
        self.assertTrue(event['result']['reported_evidence']['reported_passed'])
        self.assertEqual(event['follow_up']['arguments']['event_id'],event['id'])

    def test_tool_only_completion_reaches_notification_and_durable_event(self):
        self.store.observe('local', {'id':'worker', 'status':'running'})
        report=activity()
        report['entries']=[{'type':'tool_call','name':'shell','status':'completed',
                            'detail':{'type':'shell','output':'3 tests passed','exitCode':0}},
                           {'type':'tool_call','name':'edit','status':'completed',
                            'detail':{'type':'edit','filePath':'login.py','unifiedDiff':'-old\n+new'}}]
        ids=self.store.observe('local', {'id':'worker','status':'idle','_executive_activity':report})
        event=self.store.get_event(ids[0])
        self.assertEqual(event['result']['tool_results'], report['entries'])
        self.assertIn('3 tests passed', event_message(event))
        self.assertIn('login.py', event_message(event))
        self.assertEqual(self.store.get_event(ids[0]), event)

    def test_completed_context_is_immutable_after_followup_and_new_turn(self):
        old=self.completed()
        self.store.record_assignment('local','worker','A different task',recorded=125)
        self.store.observe('local',{'id':'worker','status':'running','activeTurn':{'turnId':'turn-2'},'_executive_observed_at':130})
        self.store.observe('local',{'id':'worker','status':'idle','_executive_observed_at':140})
        self.assertEqual(self.store.get_event(old['id']),old)
        new=self.store.events()[-1]
        self.assertEqual(new['context']['assignment']['prompt'],'A different task')
        self.assertIsNone(new['result']['summary'])

    def test_permission_payload_remains_exact_with_assignment_context(self):
        self.store.record_assignment('local','worker','Run a check',recorded=10)
        request={'id':'permission-1','kind':'tool','input':{'command':'true'}}
        self.store.observe('local',{'id':'worker','status':'running','pendingPermissions':[request],'_executive_observed_at':20})
        event=self.store.events()[0]
        self.assertEqual(event['data'],request)
        self.assertEqual(event['context']['assignment']['prompt'],'Run a check')

    def test_new_audit_records_also_capture_connection_identity(self):
        event_id=self.store.event('local','worker','spawned',{'title':'Example'})
        event=self.store.get_event(event_id)
        self.assertTrue(event['context']['connection_key'])
        self.assertEqual(event['context']['observation']['source'],'plugin_action')
        self.assertIsNone(event['result']['summary'])

    def test_context_bounded_message_keeps_valid_json_and_followup(self):
        event=self.completed()
        event['data']={'input':{'command':'x'*50000}}
        event['context']['assignment']['prompt']='y'*50000
        message=event_message(event)
        json.loads(message.splitlines()[1])
        self.assertLess(len(message),18000)
        self.assertIn('paseo_worker_details',message)
        self.assertIn('not verified',message)

    def test_legacy_database_migrates_without_losing_events(self):
        with tempfile.TemporaryDirectory() as directory:
            connection=sqlite3.connect(Path(directory)/'executive.sqlite3')
            connection.execute('CREATE TABLE events(id INTEGER PRIMARY KEY,host TEXT,agent TEXT,kind TEXT,data TEXT,created REAL,delivered INTEGER DEFAULT 0,claimed_until REAL DEFAULT 0)')
            connection.execute("INSERT INTO events VALUES(1,'local','old-worker','completed','{}',1,0,0)")
            connection.commit();connection.close()
            store=Store(directory)
            event=store.get_event(1)
            self.assertEqual(event['agent'],'old-worker')
            self.assertIsNone(event['context'])
            self.assertEqual(Store(directory).get_event(1)['id'],1)


class DetailsTests(EventFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.calls=[]
        self.snapshot={'id':'worker','status':'idle','updatedAt':'version-1','pendingPermissions':[]}
        owner=self
        class CLI:
            def call(self,host,*args):
                owner.calls.append((host['id'],args))
                if args[0]!='inspect': raise AssertionError('Read-only details attempted a mutation')
                return copy.deepcopy(owner.snapshot)
            def activity(self,host,agent_id,tail):
                owner.calls.append((host['id'],('logs',agent_id,tail)))
                return activity()
        self.executive=Executive(self.store,CLI())

    def test_read_only_details_returns_fresh_state_and_report_without_events(self):
        event=self.completed()
        before=self.store.events()
        details=self.executive.details('local','worker',event_id=event['id'])
        self.assertEqual(details['event_correlation'],'same_snapshot')
        self.assertEqual(details['result']['summary'],'Completed the scoped fix')
        self.assertEqual(details['verification'],'not_verified')
        self.assertEqual(self.store.events(),before)
        self.assertEqual([args[0] for host,args in self.calls],['inspect','logs','inspect'])

    def test_event_identity_and_connection_are_checked_before_reads(self):
        event=self.completed()
        with self.assertRaises(ExecutiveError):
            self.executive.details('local','other',event_id=event['id'])
        self.store.save_host({'id':'local','target':'different:6767'})
        with self.assertRaisesRegex(ExecutiveError,'connection changed'):
            self.executive.details('local','worker',event_id=event['id'])
        self.assertEqual(self.calls,[])

    def test_newer_worker_state_is_labeled_separately_from_captured_event(self):
        event=self.completed()
        self.snapshot['updatedAt']='version-2'
        details=self.executive.details('local','worker',event_id=event['id'])
        self.assertEqual(details['event_correlation'],'newer_snapshot')
        self.assertEqual(details['event']['context']['observation']['snapshot_updated_at'],'version-1')

    def test_unavailable_activity_does_not_lose_worker_state(self):
        def unavailable(*args): raise ExecutiveError('timeline unavailable')
        self.executive.activity_reader=unavailable
        details=self.executive.details('local','worker')
        self.assertEqual(details['snapshot']['status'],'idle')
        self.assertIsNone(details['result']['summary'])
        self.assertIn('timeline unavailable',details['result']['unavailable_reason'])

    def test_changing_worker_discards_potentially_misattributed_report(self):
        def change(*args):
            self.snapshot.update(status='running',updatedAt='version-2')
            return activity()
        self.executive.activity_reader=change
        details=self.executive.details('local','worker')
        self.assertIsNone(details['result']['summary'])
        self.assertEqual(details['snapshot']['status'],'running')

    def test_full_id_and_bounded_tail_required(self):
        with self.assertRaises(ExecutiveError): self.executive.details('local','prefix')
        for tail in [0,51,True]:
            with self.assertRaises(ExecutiveError): self.executive.details('local','worker',tail=tail)

    def test_secondary_refresh_failure_returns_partial_details_honestly(self):
        event=self.completed()
        original=self.executive.cli.call
        count=0
        def call(*args):
            nonlocal count
            count+=1
            if count==2: raise ExecutiveError('connection lost')
            return original(*args)
        self.executive.cli.call=call
        details=self.executive.details('local','worker',event_id=event['id'])
        self.assertEqual(details['state_freshness'],'second_read_failed')
        self.assertEqual(details['event_correlation'],'unknown')
        self.assertIsNone(details['result']['summary'])
        self.assertEqual(details['snapshot']['status'],'idle')

    def test_followup_records_full_identity_and_new_assignment(self):
        original=self.executive.cli.call
        def call(host,*args):
            if args[0]=='send':
                self.calls.append((host['id'],args))
                return {'ok':True}
            return original(host,*args)
        self.executive.cli.call=call
        self.executive.send('local','prefix','Review the test failure')
        assignment=self.store.assignment('local','worker')
        self.assertEqual(assignment['prompt'],'Review the test failure')
        self.assertEqual(self.calls[-1][1][2],'worker')
        self.assertIsNone(self.store.assignment('local','prefix'))


class PollContextTests(EventFixture, unittest.TestCase):
    def test_activity_failure_does_not_suppress_completion(self):
        self.store.observe('local',{'id':'worker','status':'running'})
        class CLI:
            def call(self,host,*args):
                if args[0]=='ls': return [{'id':'worker','status':'idle'}]
                return {'id':'worker','status':'idle','updatedAt':'v1'}
            def activity(self,*args): raise ExecutiveError('logs unavailable')
        Executive(self.store,CLI()).poll('local')
        event=self.store.events()[0]
        self.assertEqual(event['kind'],'completed')
        self.assertIsNone(event['result']['summary'])
        self.assertEqual(event['context']['observation']['source'],'poll')

    def test_plain_cli_logs_are_not_claimed_as_a_final_assistant_report(self):
        self.store.observe('local',{'id':'worker','status':'running'})
        class CLI:
            def call(self,host,*args):
                if args[0]=='ls': return [{'id':'worker','status':'idle'}]
                return {'id':'worker','status':'idle'}
            def activity(self,*args):
                return {'source':'paseo_cli_logs','scope':'recent_activity','text':'[User] check tests\nSome worker text'}
        Executive(self.store,CLI()).poll('local')
        event=self.store.events()[0]
        self.assertEqual(event['result']['attribution'],'unclassified_activity')
        self.assertNotIn('reported_evidence',event['result'])


    def test_sdk_staleness_is_not_replaced_with_unrelated_cli_activity(self):
        import subprocess
        from unittest.mock import patch
        from paseo_executive.runtime import Runtime
        runtime=Runtime(self.store)
        stale={'source':'paseo_sdk_timeline','scope':'newer_snapshot','error':'Worker changed'}
        result=subprocess.CompletedProcess([],0,json.dumps(stale),'')
        with patch.object(runtime,'stream_config',return_value={'url':'ws://example.invalid/ws'}), \
             patch('paseo_executive.runtime.shutil.which',return_value='/node'), \
             patch('paseo_executive.runtime.subprocess.run',return_value=result), \
             patch.object(runtime.executive.cli,'activity',side_effect=AssertionError('Stale data must not fall back')):
            self.assertEqual(runtime.read_activity(self.store.host('local'),{'id':'worker','updatedAt':'old'}),stale)
