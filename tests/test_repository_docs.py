"""Packaging checks; they do not test native-host instruction adherence."""
from pathlib import Path
import importlib.util
import json
import re
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=ROOT/'plugins/auto-research-team/skills/auto-research'

class RepositoryPackagingTests(unittest.TestCase):
    def test_policy_and_agents_asset_are_identical(self):
        self.assertEqual((S/'references/repository-policy.md').read_bytes(),(S/'assets/AGENTS.md').read_bytes())
    def test_owner_loads_policy_and_examples_exist(self):
        skill=(S/'SKILL.md').read_text()
        self.assertIn('[repository policy](references/repository-policy.md)',skill)
        self.assertTrue((S/'references/repository-examples.md').is_file())
    def test_templates_enable_required_profile(self):
        self.assertEqual(json.loads((S/'assets/protocol.template.json').read_text())['source_snapshot_policy'],'required')
        node=json.loads((S/'assets/node.template.json').read_text())
        for key in ['source_commit_or_snapshot','source_hash','snapshot_manifest_sha256']:
            self.assertIsNone(node[key])
        self.assertIn('workspaces',json.loads((S/'assets/team.template.json').read_text()))
    def test_standalone_install_copies_policy_scripts_without_editing_agents(self):
        spec=importlib.util.spec_from_file_location('fixture_installer',ROOT/'tools/install.py')
        installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as d:
            project=Path(d); policy=project/'AGENTS.md'; policy.write_text('Existing user instructions\n')
            installer.apply_plan(installer.plan_install(project,skill_only=True))
            dest=project/'.agents/skills/auto-research'
            for f in ['scripts/repoctl.py','scripts/researchctl.py','references/repository-policy.md',
                      'references/repository-examples.md','assets/AGENTS.md']:
                self.assertEqual((dest/f).read_bytes(),(S/f).read_bytes())
            self.assertEqual(policy.read_text(),'Existing user instructions\n')
    def test_relative_markdown_links_resolve(self):
        # Local markdown links only; URLs and runtime placeholders are excluded.
        for file in ROOT.rglob('*.md'):
            for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',file.read_text()):
                if '://' in target or target.startswith('#') or '<' in target:
                    continue
                target=target.split('#',1)[0]
                if target:
                    with self.subTest(file=str(file.relative_to(ROOT)),target=target):
                        self.assertTrue((file.parent/target).exists())
    def test_manifest_versions_match(self):
        for p in [ROOT/'plugins/auto-research-team/plugin.json',ROOT/'plugins/auto-research-team/.codex-plugin/plugin.json']:
            self.assertEqual(json.loads(p.read_text())['version'],'0.1.1')

if __name__=='__main__': unittest.main()
