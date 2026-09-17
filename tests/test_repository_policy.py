"""Local source-management fixtures; IDs do not represent actual native agents."""
from __future__ import annotations
import copy
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
S = ROOT / 'plugins/auto-research-team/skills/auto-research'
sys.path.insert(0, str(S / 'scripts'))
r = importlib.import_module('researchctl')
g = importlib.import_module('repoctl')

EVALUATOR = '''import argparse, json, pathlib
p=argparse.ArgumentParser()
for k in ['workspace','output','seed','stage']: p.add_argument('--'+k,required=True)
a=p.parse_args(); w=pathlib.Path(a.workspace)
c=json.loads((w/'candidate.json').read_text())
if c.get('edit'): (w/'candidate.json').write_text('{}')
if c.get('chmod'): (w/'candidate.json').chmod(0o755)
out={'valid':True,'checks':{'correct':True},'metrics':{'score':c['score']}}
(pathlib.Path(a.output)/'metrics.json').write_text(json.dumps(out))
'''

@unittest.skipUnless(os.name == 'posix', 'POSIX task locks')
class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project'; self.project.mkdir()
        self.base = self.root / 'baseline'; self.a = self.root / 'A'; self.b = self.root / 'B'
        for path, score in [(self.base, 10), (self.a, 8), (self.b, 9)]:
            path.mkdir(); (path/'candidate.json').write_text(json.dumps({'score':score}))
        self.task = r.init_task(self.project, 'T001', 'Fixture only', [])
        self.evaluator = self.task / 'evaluator.py'; self.evaluator.write_text(EVALUATOR)
        self.p = {'schema_version':1,'mode':'algorithm','source_snapshot_policy':'required',
                  'allowed_workspaces':list(map(str,[self.base,self.a,self.b])),
                  'baseline_workspace':str(self.base), 'tracked_paths':['candidate.json'],
                  'protected_files':[str(self.evaluator)], 'required_checks':['correct'],
                  'evaluation_command':[sys.executable,str(self.evaluator),'--workspace','{workspace}',
                     '--output','{output}','--seed','{seed}','--stage','{stage}'],
                  'primary_metric':{'name':'score','direction':'min','minimum_improvement':0},
                  'confirmation_seeds':[11],
                  'budget':{'max_runs':12,'max_run_seconds':3,'max_total_seconds':30,
                            'confirmation_reserve_fraction':.3}}
        r.write_json(self.task/'protocol.json',self.p)
        self.frozen = r.freeze(self.task,self.task/'protocol.json')
        self.node('baseline',self.base)
        self.node('N001',self.a,parent='baseline')
        self.node('N002',self.b,parent='baseline')
    def tearDown(self): self.tmp.cleanup()
    def node(self,name,workspace,**extra):
        n={'id':name,'parent':None,'reference_nodes':[], 'hypothesis':'Fixture hypothesis',
           'author_agent_id':'fixture-owner' if name=='baseline' else 'fixture-engineer',
           'workspace':str(workspace),'status':'implemented','reason':'Fixture only',
           'operator':'draft','source_commit_or_snapshot':None,'run_ids':[]}
        n.update(extra); r.write_json(self.task/'nodes'/f'{name}.json',n)
    def run_node(self,name='N001',workspace=None,stage='search'):
        return r.run_evaluation(self.task,name,workspace or self.a,11,stage,
                                'fixture-verifier' if stage=='confirm' else 'fixture-engineer')
    def seal_all(self):
        for n in ['baseline','N001','N002']: g.seal(self.task,n)
    def test_profile_rejects_unsealed_run_without_spending_budget(self):
        with self.assertRaises(r.ResearchError): self.run_node()
        self.assertEqual(r.records(self.task),[])
    def test_seal_copies_source_and_binds_run(self):
        g.seal(self.task,'N001'); x=self.run_node()
        self.assertTrue(x['valid']); self.assertIn('source_snapshot_manifest_sha256',x)
        self.assertEqual((self.task/'snapshots/N001/source/candidate.json').read_bytes(),
                         (self.a/'candidate.json').read_bytes())
        self.assertTrue(g.check(self.task,'N001',True)['valid'])
    def test_no_overwrite_of_sealed_node(self):
        g.seal(self.task,'N001')
        with self.assertRaises(r.ResearchError): g.seal(self.task,'N001')
    def test_old_node_cannot_run_modified_code(self):
        g.seal(self.task,'N001'); (self.a/'candidate.json').write_text('{"score":7}')
        with self.assertRaises(r.ResearchError): self.run_node()
    def test_new_node_in_reused_slot_preserves_old_evidence(self):
        self.seal_all(); base=self.run_node('baseline',self.base); old=self.run_node()
        (self.a/'candidate.json').write_text('{"score":7}')
        self.node('N003',self.a,parent='N001'); g.seal(self.task,'N003')
        self.assertTrue(self.run_node('N003')['valid'])
        self.assertEqual(r.compare(self.task,base['run_id'],old['run_id'])['gain'],2)
        self.assertTrue(g.check(self.task,'N001')['valid'])
        with self.assertRaises(r.ResearchError): g.check(self.task,'N001',True)
    def test_snapshot_damage_blocks_old_evidence(self):
        g.seal(self.task,'N001'); run=self.run_node()
        (self.task/'snapshots/N001/source/candidate.json').write_text('{}')
        with self.assertRaises(r.ResearchError): r.verify_record(self.task,run['run_id'])
    def test_manifest_damage_blocks_old_evidence(self):
        g.seal(self.task,'N001'); run=self.run_node()
        manifest=self.task/'snapshots/N001/manifest.json'; manifest.write_text('{}')
        with self.assertRaises(r.ResearchError): r.verify_record(self.task,run['run_id'])
    def test_node_binding_damage_is_rejected(self):
        g.seal(self.task,'N001'); node=r.read_json(self.task/'nodes/N001.json')
        node['source_commit_or_snapshot']='snapshots/N002/source'
        r.write_json(self.task/'nodes/N001.json',node)
        with self.assertRaises(r.ResearchError): self.run_node()
    def test_node_status_and_run_id_updates_are_allowed(self):
        g.seal(self.task,'N001'); node=r.read_json(self.task/'nodes/N001.json')
        node.update(status='screened',run_ids=['informational'],reason='Observation')
        r.write_json(self.task/'nodes/N001.json',node)
        self.assertTrue(self.run_node()['valid'])
    def test_wrong_workspace_is_rejected(self):
        g.seal(self.task,'N001'); shutil.copy2(self.a/'candidate.json',self.b/'candidate.json')
        with self.assertRaises(r.ResearchError): self.run_node(workspace=self.b)
    def test_source_change_during_evaluation_invalidates(self):
        (self.a/'candidate.json').write_text('{"score":8,"edit":true}')
        g.seal(self.task,'N001'); self.assertFalse(self.run_node()['valid'])
    def test_mode_change_before_run_is_rejected(self):
        g.seal(self.task,'N001'); (self.a/'candidate.json').chmod(0o755)
        with self.assertRaises(r.ResearchError): self.run_node()
    def test_mode_change_during_run_is_rejected(self):
        (self.a/'candidate.json').write_text('{"score":8,"chmod":true}')
        (self.a/'candidate.json').chmod(0o644)
        g.seal(self.task,'N001'); self.assertFalse(self.run_node()['valid'])
    def test_changed_baseline_cannot_be_sealed(self):
        (self.base/'candidate.json').write_text('{"score":9}')
        with self.assertRaises(r.ResearchError): g.seal(self.task,'baseline')
    def test_baseline_mode_change_before_seal_is_rejected(self):
        (self.base/'candidate.json').chmod(0o755)
        with self.assertRaises(r.ResearchError): g.seal(self.task,'baseline')
    def test_snapshot_handles_binary_declared_source(self):
        # Binary source bytes are copied, not represented as an incomplete text diff.
        (self.a/'candidate.json').write_bytes(b'\x00\xff\x01')
        g.seal(self.task,'N001')
        self.assertEqual((self.task/'snapshots/N001/source/candidate.json').read_bytes(),b'\x00\xff\x01')
        self.assertTrue(g.check(self.task,'N001',True)['valid'])
    def test_symlinked_source_is_rejected(self):
        file=self.a/'candidate.json'; file.unlink(); file.symlink_to(self.b/'candidate.json')
        with self.assertRaises(r.ResearchError): g.seal(self.task,'N001')
    def test_nonbaseline_node_cannot_bind_baseline(self):
        self.node('BAD',self.base)
        with self.assertRaises(r.ResearchError): g.seal(self.task,'BAD')
    def test_unknown_parent_is_rejected(self):
        self.node('BAD',self.a,parent='UNKNOWN')
        with self.assertRaises(r.ResearchError): g.seal(self.task,'BAD')
    def test_unsafe_id_is_rejected(self):
        with self.assertRaises(r.ResearchError): g.seal(self.task,'../bad')
    def test_seal_respects_run_lock(self):
        with r.lock(self.task,'.run.lock'):
            with self.assertRaises(r.ResearchError): g.seal(self.task,'N001')
    def test_seal_refuses_orphan_running_record(self):
        r.write_json(self.task/'runs/orphan/record.json',{'status':'running'})
        with self.assertRaises(r.ResearchError): g.seal(self.task,'N001')
    def test_saved_source_survives_workspace_removal(self):
        g.seal(self.task,'N001'); run=self.run_node(); shutil.rmtree(self.a)
        self.assertTrue(g.check(self.task,'N001')['valid'])
        self.assertTrue(r.verify_record(self.task,run['run_id'])['valid'])
    def test_catalog_uses_run_records_not_manual_run_index(self):
        g.seal(self.task,'N001'); run=self.run_node(); data=g.catalog(self.task)
        row=next(n for n in data['nodes'] if n['id']=='N001')
        self.assertEqual(row['run_ids'],[run['run_id']])
    def test_source_profile_rejects_dot(self):
        p=copy.deepcopy(self.p); p['tracked_paths']=['.']
        with self.assertRaises(r.ResearchError): r.validate_protocol(p)
    def test_source_profile_rejects_evaluator_in_workspace(self):
        f=self.a/'eval.py'; f.write_text(EVALUATOR)
        p=copy.deepcopy(self.p); p['protected_files']=[str(f)]
        with self.assertRaises(r.ResearchError): r.validate_protocol(p)
    def test_source_profile_rejects_duplicate_roots(self):
        p=copy.deepcopy(self.p); p['allowed_workspaces'].append(str(self.a))
        with self.assertRaises(r.ResearchError): r.validate_protocol(p)
    def test_source_profile_rejects_nested_roots(self):
        f=self.a/'nested'; f.mkdir()
        p=copy.deepcopy(self.p); p['allowed_workspaces'].append(str(f))
        with self.assertRaises(r.ResearchError): r.validate_protocol(p)
    def test_legacy_protocol_keeps_original_behavior(self):
        # New task; never mutate an existing protocol lock to downgrade its checks.
        t=r.init_task(self.project,'T002','Legacy fixture',[])
        p=copy.deepcopy(self.p); p.pop('source_snapshot_policy')
        r.write_json(t/'protocol.json',p); r.freeze(t,t/'protocol.json')
        self.assertTrue(r.run_evaluation(t,'N001',self.a,11,'search','fixture-engineer')['valid'])
    def test_independent_confirmation_and_finish_with_sealed_nodes(self):
        self.seal_all(); a=self.run_node('baseline',self.base,'confirm'); b=self.run_node(stage='confirm')
        review={'verdict':'pass','reviewer_agent_id':'fixture-verifier',
                'builder_agent_ids':['fixture-engineer'],'protocol_hash':self.frozen['protocol_hash'],
                'candidate_node_id':'N001','evidence_run_ids':[a['run_id'],b['run_id']],
                'summary':'Fixture only','claim_scope':'local fixture','blocking_issues':[],
                'limitations':['No native host test']}
        path=self.task/'reviews/input.json';r.write_json(path,review)
        self.assertEqual(r.finish(self.task,path)['phase'],'completed')
    def test_cli_seal_check_catalog(self):
        for command in [['seal','--node','N001'],['check','--node','N001','--live'],['catalog']]:
            p=subprocess.run([sys.executable,str(S/'scripts/repoctl.py'),*command,'--task-dir',str(self.task)],
                              capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr); self.assertIsInstance(json.loads(p.stdout),dict)


@unittest.skipUnless(os.name=='posix' and shutil.which('git'),'Git/POSIX required')
class WorktreeFixtureTests(unittest.TestCase):
    def test_two_worktrees_edit_independently_without_switching_user_checkout(self):
        import concurrent.futures
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); repo=root/'project'; repo.mkdir()
            def git(*args):
                return subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True,text=True).stdout.strip()
            git('init','-b','main'); (repo/'method.py').write_text('BASE\n')
            git('add','method.py'); git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                                       'commit','-m','fixture baseline')
            original=git('rev-parse','HEAD')
            a=root/'A';b=root/'B'
            git('worktree','add','-b','art/T001/A-shuffle',str(a),original)
            git('worktree','add','-b','art/T001/B-schedule',str(b),original)
            def edit(path,label):
                for i in range(20): (path/'method.py').write_text(f'{label}:{i}\n')
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                fa=ex.submit(edit,a,'A');fb=ex.submit(edit,b,'B'); fa.result();fb.result()
            self.assertEqual((repo/'method.py').read_text(),'BASE\n')
            self.assertEqual((a/'method.py').read_text(),'A:19\n')
            self.assertEqual((b/'method.py').read_text(),'B:19\n')
            self.assertEqual(git('branch','--show-current'),'main')
            self.assertEqual(git('rev-parse','HEAD'),original)
            self.assertEqual(g.git_metadata(a)['branch'],'art/T001/A-shuffle')
            self.assertEqual(g.git_metadata(b)['branch'],'art/T001/B-schedule')

if __name__=='__main__': unittest.main()
