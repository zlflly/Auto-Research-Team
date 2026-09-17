"""Local fixtures only: actor labels below do NOT represent real Codex subagents."""
import copy
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'plugins/auto-research-team/skills/auto-research/scripts/researchctl.py'
spec = importlib.util.spec_from_file_location('researchctl', SCRIPT)
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

EVALUATOR = r'''
import argparse, json, pathlib, sys, time
p=argparse.ArgumentParser()
for key in ['workspace','output','seed','stage']: p.add_argument('--'+key, required=True)
a=p.parse_args(); w=pathlib.Path(a.workspace); out=pathlib.Path(a.output)
c=json.loads((w/'candidate.json').read_text())
mode=c.get('mode','normal')
if mode=='sleep': time.sleep(10)
if mode=='crash': sys.exit(7)
if mode=='missing': sys.exit(0)
if mode=='source_edit': (w/'candidate.json').write_text('{}')
if mode=='evaluator_edit': pathlib.Path(__file__).write_text('# changed')
result={'valid': c.get('valid',True), 'checks':{'correct':c.get('correct',True),'feature':c.get('feature',True)}, 'metrics':{'score':c.get('score',10)}}
if mode=='nan': result['metrics']['score']=float('nan')
if mode=='bool_metric': result['metrics']['score']=True
if mode=='missing_metric': result['metrics']={}
(out/'metrics.json').write_text(json.dumps(result))
'''

@unittest.skipUnless(os.name=='posix','Managed evaluation requires POSIX')
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.base=self.root/'baseline'; self.cand=self.root/'candidate'
        self.base.mkdir(); self.cand.mkdir()
        self.write_candidate(self.base, score=10); self.write_candidate(self.cand, score=8)
        self.evaluator=self.root/'eval.py'; self.evaluator.write_text(EVALUATOR)
        self.task=r.init_task(self.root,'T001','Fixture only',[])
        self.p={'schema_version':1,'mode':'algorithm',
          'allowed_workspaces':[str(self.base),str(self.cand)],'baseline_workspace':str(self.base),
          'baseline_expected_failures':[], 'tracked_paths':['candidate.json'],
          'protected_files':[str(self.evaluator)],
          'evaluation_command':[sys.executable,str(self.evaluator),'--workspace','{workspace}','--output','{output}','--seed','{seed}','--stage','{stage}'],
          'required_checks':['correct'],'confirmation_seeds':[11],
          'primary_metric':{'name':'score','direction':'min','minimum_improvement':1,'target':None},
          'budget':{'max_runs':8,'max_run_seconds':2,'max_total_seconds':30,'confirmation_reserve_fraction':.3}}
        self.protocol=self.task/'protocol.json'
    def tearDown(self): self.temp.cleanup()
    def write_candidate(self, where=None, **kwargs):
        (where or self.cand).joinpath('candidate.json').write_text(json.dumps(kwargs))
    def freeze(self):
        r.write_json(self.protocol,self.p); self.sealed=r.freeze(self.task,self.protocol); return self.sealed
    def evaluate(self,node='A1',workspace=None,seed=11,stage='search',actor='fixture-engineer'):
        return r.run_evaluation(self.task,node,workspace or self.cand,seed,stage,actor)
    def confirmations(self):
        a=self.evaluate('baseline',self.base,stage='confirm',actor='fixture-verifier')
        b=self.evaluate(stage='confirm',actor='fixture-verifier')
        self.assertTrue(a['valid']); self.assertTrue(b['valid']); return [a,b]
    def review(self, runs, **kwargs):
        obj={'verdict':'pass','reviewer_agent_id':'fixture-verifier','builder_agent_ids':['fixture-engineer'],
             'protocol_hash':self.sealed['protocol_hash'],'candidate_node_id':'A1',
             'evidence_run_ids':[x['run_id'] for x in runs], 'summary':'Fixture result, not a research claim.',
             'claim_scope':'fixture only','blocking_issues':[],'limitations':['No live Codex test.']}
        obj.update(kwargs); path=self.task/'reviews/input.json'; r.write_json(path,obj); return path
    def test_init_preserves_insight(self):
        insight=self.root/'idea.md'; payload='假设\nα\n'.encode(); insight.write_bytes(payload)
        t=r.init_task(self.root,'T002','口述 insight',[insight])
        self.assertEqual((t/'input/insight-01.md').read_bytes(),payload)
        self.assertEqual(r.read_json(t/'input/sources.json')['sources'][1]['sha256'],r.digest_file(insight))
    def test_init_refuses_duplicate_and_traversal(self):
        for name in ['T001','../escape','/tmp/escape']:
            with self.subTest(name=name),self.assertRaises(r.ResearchError): r.init_task(self.root,name,'goal',[])
    def test_init_missing_insight_is_nonmutating(self):
        with self.assertRaises(r.ResearchError): r.init_task(self.root,'T002','goal',[self.root/'missing.md'])
        self.assertFalse((self.root/'.autoresearch/T002').exists())
    def test_freeze_and_refreeze(self):
        self.freeze(); self.assertEqual(r.status(self.task)['state']['phase'],'baseline')
        with self.assertRaises(r.ResearchError): r.freeze(self.task,self.protocol)
    def test_protocol_rejects_bad_values(self):
        bads=[('schema_version',2),('evaluation_command','python eval.py'),('confirmation_seeds',[True]),('tracked_paths',['../escape']),('baseline_workspace','/missing')]
        for key,val in bads:
            with self.subTest(key=key):
                p=copy.deepcopy(self.p); p[key]=val
                with self.assertRaises(r.ResearchError): r.validate_protocol(p)
    def test_valid_run_and_result_artifact(self):
        self.freeze(); x=self.evaluate(); self.assertTrue(x['valid']); self.assertEqual(x['status'],'finished')
        self.assertEqual(r.verify_record(self.task,x['run_id'])['result']['metrics']['score'],8)
    def test_failed_correctness_is_not_success(self):
        self.write_candidate(correct=False,score=1); self.freeze(); x=self.evaluate()
        self.assertFalse(x['valid']); self.assertEqual(x['status'],'invalid')
    def test_false_procedure_valid_is_rejected(self):
        self.write_candidate(valid=False,score=1); self.freeze(); self.assertFalse(self.evaluate()['valid'])
    def test_malformed_results_fail_closed(self):
        self.freeze()
        for mode in ['missing','missing_metric','nan','bool_metric']:
            with self.subTest(mode=mode):
                self.write_candidate(mode=mode,score=8); x=self.evaluate(); self.assertFalse(x['valid'])
    def test_crash_consumes_budget(self):
        self.write_candidate(mode='crash'); self.freeze(); x=self.evaluate()
        self.assertEqual(x['status'],'failed'); self.assertEqual(r.status(self.task)['run_count'],1)
    def test_timeout_stops_process(self):
        self.p['budget']['max_run_seconds']=.1; self.write_candidate(mode='sleep'); self.freeze(); x=self.evaluate()
        self.assertEqual(x['status'],'timeout'); self.assertFalse(x['valid'])
        with self.assertRaises(ProcessLookupError): os.killpg(x['process_group_id'],0)
    def test_source_change_during_run_invalidates(self):
        self.write_candidate(mode='source_edit',score=8); self.freeze(); x=self.evaluate()
        self.assertFalse(x['valid']); self.assertIn('DURING',x['error'])
    def test_evaluator_change_before_run_blocks(self):
        self.freeze(); self.evaluator.write_text('# changed')
        with self.assertRaises(r.ResearchError): self.evaluate()
        self.assertEqual(r.status(self.task)['run_count'],0)
    def test_evaluator_change_during_run_invalidates(self):
        self.write_candidate(mode='evaluator_edit',score=8); self.freeze(); x=self.evaluate()
        self.assertFalse(x['valid']); self.assertIn('Protected',x['error'])
    def test_baseline_source_is_fixed(self):
        self.freeze(); self.write_candidate(self.base,score=9)
        with self.assertRaises(r.ResearchError): self.evaluate('baseline',self.base)
    def test_cannot_claim_candidate_as_baseline(self):
        self.freeze()
        with self.assertRaises(r.ResearchError): self.evaluate('baseline',self.cand)
        with self.assertRaises(r.ResearchError): self.evaluate('A1',self.base)
    def test_allowlist_enforced(self):
        self.freeze()
        with self.assertRaises(r.ResearchError): self.evaluate(workspace=self.root)
    def test_task_lock_prevents_two_runners(self):
        self.freeze()
        with r.lock(self.task,'.run.lock'):
            with self.assertRaises(r.ResearchError): self.evaluate()
    def test_confirmation_slots_reserved(self):
        self.p['budget']['max_runs']=3; self.freeze(); self.evaluate()
        with self.assertRaisesRegex(r.ResearchError,'reserved'): self.evaluate()
        self.assertTrue(self.evaluate(stage='confirm')['valid'])
    def test_total_run_budget_includes_failures(self):
        self.p['budget']['max_runs']=1; self.write_candidate(mode='crash'); self.freeze(); self.evaluate(stage='confirm')
        with self.assertRaisesRegex(r.ResearchError,'count'): self.evaluate(stage='confirm')
    def test_time_budget_reserved(self):
        self.freeze(); x=self.evaluate(); x['elapsed_seconds']=25
        r.write_json(self.task/'runs'/x['run_id']/'record.json',x)
        with self.assertRaisesRegex(r.ResearchError,'time allowance'): self.evaluate()
    def test_compare_matched_pairs(self):
        self.freeze(); a=self.evaluate('baseline',self.base); b=self.evaluate(); result=r.compare(self.task,a['run_id'],b['run_id'])
        self.assertEqual(result['decision'],'promising'); self.assertEqual(result['gain'],2)
        c=self.evaluate(seed=99)
        with self.assertRaises(r.ResearchError): r.compare(self.task,a['run_id'],c['run_id'])
    def test_max_direction(self):
        self.p['primary_metric']['direction']='max'; self.write_candidate(score=12); self.freeze()
        a=self.evaluate('baseline',self.base); b=self.evaluate(); self.assertEqual(r.compare(self.task,a['run_id'],b['run_id'])['gain'],2)
    def test_modified_artifact_or_cached_metrics_rejected(self):
        self.freeze(); x=self.evaluate(); folder=self.task/'runs'/x['run_id']
        x['result']['metrics']['score']=0; r.write_json(folder/'record.json',x)
        with self.assertRaisesRegex(r.ResearchError,'Stored metrics'): r.verify_record(self.task,x['run_id'])
        (folder/'output/metrics.json').write_text('{}')
        with self.assertRaisesRegex(r.ResearchError,'modified'): r.verify_record(self.task,x['run_id'])
    def test_independent_confirmations_can_finish(self):
        self.freeze(); runs=self.confirmations(); state=r.finish(self.task,self.review(runs))
        self.assertEqual(state['phase'],'completed')
        with self.assertRaises(r.ResearchError): r.finish(self.task,self.review(runs))
        with self.assertRaises(r.ResearchError): self.evaluate()
        with self.assertRaises(r.ResearchError): r.checkpoint(self.task,'search','retry','fixture-owner')
    def test_author_cannot_self_review(self):
        self.freeze(); runs=self.confirmations()
        with self.assertRaisesRegex(r.ResearchError,'distinct'): r.finish(self.task,self.review(runs,reviewer_agent_id='fixture-engineer'))
    def test_confirmation_actor_must_be_reviewer(self):
        self.freeze(); a=self.evaluate('baseline',self.base,stage='confirm'); b=self.evaluate(stage='confirm')
        with self.assertRaisesRegex(r.ResearchError,'independent reviewer'): r.finish(self.task,self.review([a,b]))
    def test_search_only_runs_cannot_finish(self):
        self.freeze(); a=self.evaluate('baseline',self.base); b=self.evaluate()
        with self.assertRaisesRegex(r.ResearchError,'confirmation'): r.finish(self.task,self.review([a,b]))
    def test_blockers_prevent_pass(self):
        self.freeze(); runs=self.confirmations()
        with self.assertRaisesRegex(r.ResearchError,'blocking'): r.finish(self.task,self.review(runs,blocking_issues=['unresolved']))
    def test_candidate_change_after_verification_blocks(self):
        self.freeze(); runs=self.confirmations(); self.write_candidate(score=7)
        with self.assertRaisesRegex(r.ResearchError,'changed after'): r.finish(self.task,self.review(runs))
    def test_target_not_met_blocks_pass(self):
        self.p['primary_metric']['target']=5; self.freeze(); runs=self.confirmations()
        with self.assertRaisesRegex(r.ResearchError,'target'): r.finish(self.task,self.review(runs))
    def test_no_improvement_blocks_pass(self):
        self.write_candidate(score=11); self.freeze(); runs=self.confirmations()
        with self.assertRaisesRegex(r.ResearchError,'improvement'): r.finish(self.task,self.review(runs))
    def test_negative_and_inconclusive_are_separate(self):
        self.freeze()
        with self.assertRaisesRegex(r.ResearchError,'observed'): r.finish(self.task,self.review([],verdict='no_gain'))
        state=r.finish(self.task,self.review([],verdict='inconclusive')); self.assertEqual(state['phase'],'inconclusive')
    def test_observed_no_gain_can_close(self):
        self.write_candidate(score=11); self.freeze(); a=self.evaluate('baseline',self.base); b=self.evaluate()
        state=r.finish(self.task,self.review([a,b],verdict='no_gain')); self.assertEqual(state['phase'],'no_gain')
    def test_engineering_baseline_expected_failure(self):
        self.p.update(mode='engineering',primary_metric=None,required_checks=['correct','feature'],baseline_expected_failures=['feature'])
        self.write_candidate(self.base,score=10,feature=False); self.write_candidate(score=8,feature=True)
        self.freeze(); runs=self.confirmations(); self.assertFalse(runs[0]['result']['checks']['feature'])
        self.assertEqual(r.finish(self.task,self.review(runs))['phase'],'completed')
    def test_expected_failure_does_not_exempt_candidate(self):
        self.p.update(mode='engineering',primary_metric=None,required_checks=['correct','feature'],baseline_expected_failures=['feature'])
        self.write_candidate(self.base,feature=False); self.write_candidate(feature=False); self.freeze()
        self.assertTrue(self.evaluate('baseline',self.base)['valid']); self.assertFalse(self.evaluate()['valid'])
    def test_algorithm_cannot_exempt_baseline_correctness(self):
        self.p['baseline_expected_failures']=['correct']
        with self.assertRaises(r.ResearchError): self.freeze()
    def test_engineering_baseline_cannot_be_candidate(self):
        self.p.update(mode='engineering',primary_metric=None); self.freeze(); a=self.evaluate('baseline',self.base,stage='confirm',actor='fixture-verifier')
        with self.assertRaisesRegex(r.ResearchError,'distinct candidate'): r.finish(self.task,self.review([a],candidate_node_id='baseline'))
    def test_blocked_task_does_not_run(self):
        self.freeze(); r.checkpoint(self.task,'blocked','Need permission','fixture-owner')
        with self.assertRaises(r.ResearchError): self.evaluate()
        r.checkpoint(self.task,'search','Resumed','fixture-owner'); self.assertTrue(self.evaluate()['valid'])
    def test_recover_orphan_needs_explicit_confirmation(self):
        self.freeze(); x={'run_id':'orphan','status':'running','timeout_seconds':1,'node_id':'A1'}
        r.write_json(self.task/'runs/orphan/record.json',x)
        with self.assertRaises(r.ResearchError): self.evaluate()
        with self.assertRaises(r.ResearchError): r.recover(self.task,False)
        self.assertEqual(r.recover(self.task,True)['recovered_runs'],1)
        self.assertEqual(r.records(self.task)[0]['elapsed_seconds'],1)
    def test_recover_does_not_override_live_process(self):
        self.freeze(); x={'run_id':'orphan','status':'running','timeout_seconds':1,'process_group_id':os.getpgrp()}
        r.write_json(self.task/'runs/orphan/record.json',x)
        with self.assertRaisesRegex(r.ResearchError,'still exists'): r.recover(self.task,True)

if __name__=='__main__': unittest.main()
