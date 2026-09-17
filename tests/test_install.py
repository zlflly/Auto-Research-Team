import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'tools/install.py')
i=importlib.util.module_from_spec(spec); spec.loader.exec_module(i)

class InstallTests(unittest.TestCase):
    def setUp(self): self.temp=tempfile.TemporaryDirectory(); self.repo=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def test_dry_run_does_not_write(self):
        p=i.plan_install(self.repo); self.assertTrue(p['copy_needed']); self.assertEqual(list(self.repo.iterdir()),[])
    def test_plugin_install_is_idempotent(self):
        i.apply_plan(i.plan_install(self.repo)); p=i.plan_install(self.repo)
        self.assertFalse(p['copy_needed']); self.assertEqual(p['writes'],[])
        c=tomllib.loads((self.repo/'.codex/config.toml').read_text()); self.assertTrue(c['plugins']['auto-research-team@personal-research']['enabled'])
    def test_preserves_marketplace_name_and_other_config(self):
        m=self.repo/'.agents/plugins/marketplace.json'; m.parent.mkdir(parents=True)
        original={'name':'my-lab','interface':{'displayName':'Existing'},'plugins':[{'name':'other','source':{'source':'local','path':'./other'}}]}
        m.write_text(json.dumps(original)); c=self.repo/'.codex/config.toml'; c.parent.mkdir(); c.write_text('# keep this\nmodel = "existing-model"\n')
        i.apply_plan(i.plan_install(self.repo)); new=json.loads(m.read_text()); self.assertEqual(new['name'],'my-lab'); self.assertEqual(new['plugins'][0],original['plugins'][0])
        self.assertTrue(c.read_text().startswith('# keep this')); self.assertIn('auto-research-team@my-lab',tomllib.loads(c.read_text())['plugins'])
        self.assertEqual(len(list(m.parent.glob('*.backup-*'))),1); self.assertEqual(len(list(c.parent.glob('*.backup-*'))),1)
    def test_skill_only_self_contained(self):
        i.apply_plan(i.plan_install(self.repo,skill_only=True)); root=self.repo/'.agents/skills/auto-research'
        self.assertTrue((root/'SKILL.md').exists()); self.assertTrue((root/'scripts/researchctl.py').exists()); self.assertFalse((self.repo/'.codex').exists())
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)
    def test_plugin_prevents_duplicate_skill(self):
        i.apply_plan(i.plan_install(self.repo))
        with self.assertRaises(i.InstallError): i.plan_install(self.repo,skill_only=True)
    def test_different_installed_content_not_overwritten(self):
        i.apply_plan(i.plan_install(self.repo)); f=self.repo/'plugins/auto-research-team/plugin.json'; f.write_text('{}')
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)
        self.assertEqual(f.read_text(),'{}')
    def test_disabled_existing_config_not_overwritten(self):
        c=self.repo/'.codex/config.toml'; c.parent.mkdir(); c.write_text('[plugins."auto-research-team@personal-research"]\nenabled=false\n')
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)
        self.assertFalse((self.repo/'plugins').exists())
    def test_conflicting_catalog_not_overwritten(self):
        m=self.repo/'.agents/plugins/marketplace.json'; m.parent.mkdir(parents=True); m.write_text(json.dumps({'name':'lab','plugins':[{'name':i.NAME,'source':{'source':'local','path':'./different'}}]}))
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)
    def test_invalid_config_preflight_leaves_no_plugin(self):
        c=self.repo/'.codex/config.toml'; c.parent.mkdir(); c.write_text('[broken')
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)
        self.assertFalse((self.repo/'plugins').exists())
    def test_portable_manifest_and_skill_structure(self):
        p=ROOT/'plugins/auto-research-team'; manifest=json.loads((p/'plugin.json').read_text())
        self.assertEqual(manifest['$schema'],'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json')
        self.assertEqual(manifest['name'],i.NAME); self.assertIn('com.openai',manifest['extensions'])
        self.assertNotIn('agents',manifest); self.assertNotIn('mcpServers',manifest)
        fallback=json.loads((p/'.codex-plugin/plugin.json').read_text()); self.assertEqual(fallback['skills'],'./skills/')
        s=p/'skills/auto-research'; self.assertTrue((s/'SKILL.md').read_text().startswith('---\nname: auto-research\n'))
        for role in ['researcher','engineer','analyst','verifier']: self.assertTrue((s/f'references/roles/{role}.md').exists())
    def test_symlink_install_target_rejected(self):
        external=self.repo/'other'; external.mkdir(); (self.repo/'plugins').symlink_to(external,target_is_directory=True)
        with self.assertRaises(i.InstallError): i.plan_install(self.repo)

if __name__=='__main__': unittest.main()
