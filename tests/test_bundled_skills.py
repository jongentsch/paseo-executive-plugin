import json
import tempfile
import unittest
from pathlib import Path

from paseo_executive.core import Store
from paseo_executive.runtime import Runtime
from paseo_executive.skills import BUNDLED_SKILLS, register_skills
from paseo_executive.tools import TOOLS, execute

ROOT = Path(__file__).resolve().parents[1]


class BundledSkillTests(unittest.TestCase):
    def test_registration_uses_package_files_and_discovery_descriptions(self):
        registered = {}
        class Context:
            def register_skill(self, name, path, description=''):
                registered[name] = (path, description)
        register_skills(Context())
        self.assertEqual(set(registered), {'hosts','monitoring','orchestrate','permissions','review'})
        for name, (path, description) in registered.items():
            self.assertTrue(path.is_file())
            self.assertEqual(path.parent.name,name)
            self.assertTrue(path.is_relative_to(ROOT/'skills'))
            self.assertTrue(description)

    def test_recipe_arguments_match_tools_and_execute_without_live_daemons(self):
        recipes = [recipe for path in sorted((ROOT/'skills').glob('*/references/tool-recipes.json')) for recipe in json.loads(path.read_text())]
        schemas = {tool['name']:tool['parameters'] for tool in TOOLS}
        calls = []
        class CLI:
            def call(self, host, *args):
                calls.append((host['id'],args))
                if args[0]=='ls': return [{'id':'ACTUAL_FULL_AGENT_ID','status':'running'}]
                if args[0] in {'run','inspect'}: return {'id':'ACTUAL_FULL_AGENT_ID','status':'running','pendingPermissions':[]}
                return {'ok':True}
            def activity(self,host,agent_id,tail):
                return {'source':'paseo_cli_logs','text':'Worker-reported completion','scope':'recent_activity'}
        with tempfile.TemporaryDirectory() as directory:
            store=Store(directory)
            store.save_host({'id':'linux','target':'ssh://user@example.invalid'})
            runtime=Runtime(store,CLI())
            for recipe in recipes:
                schema=schemas[recipe['tool']]
                args=recipe['arguments']
                self.assertFalse(set(schema['required'])-args.keys())
                self.assertFalse(args.keys()-schema['properties'].keys())
                for key,value in args.items():
                    if 'enum' in schema['properties'][key]:
                        self.assertIn(value,schema['properties'][key]['enum'])
                execute(runtime,recipe['tool'],args)
            self.assertTrue(calls)
            self.assertTrue(all(host in {'linux','remote'} for host,args in calls))
            self.assertTrue(store.host('remote')['enabled'])
            self.assertNotIn('local-extra', [host['id'] for host in store.hosts()])
            self.assertTrue(store.setting('monitor_enabled'))
