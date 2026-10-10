import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))


class BenchTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec('wuxiang.bench')
        self.assertIsNotNone(spec, 'benchmark implementation must exist')
        from wuxiang import bench
        self.bench = bench
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def manifest(self):
        artifact = self.path / 'sample.exe'
        artifact.write_bytes(b'MZ' + bytes(range(128)))
        tasks = []
        for category in self.bench.CATEGORIES:
            for seed in (11, 23, 47):
                for variant in ('baseline', 'protected', 'msvc'):
                    tasks.append(dict(id=category, category=category, seed=seed,
                                      variant=variant, artifact_path=str(artifact),
                                      sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                      verified=True))
        manifest = dict(schema_version=1, tasks=tasks, toolchain={}, balanced_caps_all_pass=True)
        p = self.path / 'build.json'
        p.write_text(json.dumps(manifest), encoding='utf-8')
        return p, manifest

    def test_prepare_excludes_source_and_private_mapping(self):
        manifest, _ = self.manifest()
        report = self.bench.prepare({'benchmark': {'build_manifest_path': str(manifest),
                                                   'output_dir': str(self.path / 'packs')}}, self.path / 'config.json')
        self.assertEqual(report['pack_count'], 54)
        attacker = Path(report['attacker_dir'])
        files = list(attacker.rglob('*'))
        self.assertTrue(any(p.suffix == '.exe' for p in files))
        self.assertFalse(any(p.suffix in ('.cpp', '.pdb') for p in files))
        text = '\n'.join(p.read_text(encoding='utf-8') for p in files if p.suffix in ('.json', '.md', '.h'))
        self.assertNotIn('hidden_cases', text)
        self.assertNotIn('artifact_path', text)
        self.assertNotIn('protected', text)
        self.assertTrue(Path(report['scoring_manifest']).is_file())
        self.assertIn('adaptive_dir', report, 'Adaptive known-design task packs must be exported separately')
        adaptive = Path(report['adaptive_dir'])
        self.assertEqual(len(list(adaptive.glob('*/protection-design.md'))), 54)
        self.assertFalse(list(attacker.rglob('protection-design.md')))

    def test_prepare_rejects_changed_and_unverified_binary(self):
        p, manifest = self.manifest()
        manifest['tasks'][0]['sha256'] = '0' * 64
        p.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.bench.prepare({'benchmark': {'build_manifest_path': str(p), 'output_dir': str(self.path / 'packs')}}, self.path / 'config.json')
        manifest['tasks'][0]['sha256'] = manifest['tasks'][1]['sha256']
        manifest['tasks'][0]['verified'] = False
        p.write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'verified'):
            self.bench.prepare({'benchmark': {'build_manifest_path': str(p), 'output_dir': str(self.path / 'packs')}}, self.path / 'config.json')

    def test_reference_literals_include_memory_side_effects(self):
        self.assertEqual(self.bench.reference('branch', 0, b'', 0), (0x19, b''))
        self.assertEqual(self.bench.reference('parser', 0, b'123', 0), (123, b''))
        self.assertEqual(self.bench.reference('parser', 0, b'12x', 0), (2**64 - 1, b''))
        self.assertEqual(self.bench.reference('buffer', 1, b'\x00\x01', 1)[1], b'\x01')

    def test_caps_evidence_cannot_be_missing_or_truthy(self):
        p,manifest=self.manifest()
        for value in (None,1,'true'):
            manifest['balanced_caps_all_pass']=value
            p.write_text(json.dumps(manifest),encoding='utf-8')
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'caps'):
                self.bench.prepare({'benchmark':{'build_manifest_path':str(p),'output_dir':str(self.path/'packs')}},self.path/'config.json')

    def test_submission_cannot_forge_score_or_execute_a_command(self):
        p = self.path / 'submission.json'
        p.write_text(json.dumps({'schema_version': 1, 'score': 1.0,
                                 'command': ['echo', 'forged']}), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.bench.score(p)

    def test_prepare_does_not_copy_ambient_credentials(self):
        p, manifest = self.manifest()
        manifest['toolchain'] = {'compiler': 'cl.exe', 'compiler_environment':
                                {'INCLUDE': 'sdk', 'OPENAI_API_KEY': 'do-not-copy', 'PATH': 'tools'}}
        p.write_text(json.dumps(manifest), encoding='utf-8')
        report = self.bench.prepare({'benchmark': {'build_manifest_path': str(p),
                                      'output_dir': str(self.path / 'packs')}}, self.path / 'config.json')
        content = Path(report['scoring_manifest']).read_text(encoding='utf-8')
        self.assertFalse('do-not-copy' in content, 'Ambient credential copied to scoring pack')
        self.assertTrue('sdk' in content)

    def test_pair_summary_requires_three_fresh_sessions_same_environment(self):
        rows = []
        for repeat in range(3):
            for variant, elapsed in (('baseline', 10), ('protected', 20)):
                rows.append({'category':'parser', 'seed':11, 'mode':'blind',
                             'variant':variant, 'pair_id':str(repeat),
                             'session_id':f'{variant}-{repeat}',
                             'status':'semantic_success', 'elapsed_seconds':elapsed,
                             'environment':{'model':'same', 'tools':['same']}})
        summary = self.bench.summarize_records(rows)
        self.assertEqual(summary['eligible_group_count'], 1)
        self.assertEqual(summary['groups'][0]['median_time_ratio'], 2)
        self.assertFalse(summary['effectiveness_claim'])
        rows[-1]['environment']['model'] = 'different'
        self.assertEqual(self.bench.summarize_records(rows)['eligible_group_count'], 0)
        rows[-1]['environment']['model'] = 'same'
        rows[-1]['session_id'] = rows[1]['session_id']
        self.assertEqual(self.bench.summarize_records(rows)['eligible_group_count'], 0)

    def test_real_candidates_are_compiled_and_scored(self):
        from wuxiang.build import msvc_environment
        try:
            env, _ = msvc_environment()
        except (ValueError, OSError, RuntimeError) as error:
            self.skipTest('MSVC environment unavailable: ' + str(error))
        compiler = shutil.which('cl.exe', path=env.get('Path', env.get('PATH', '')))
        self.assertIsNotNone(compiler)
        manifest_path, manifest = self.manifest()
        manifest['toolchain'] = dict(compiler=str(compiler), compiler_environment=env)
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
        report = self.bench.prepare({'benchmark': {'build_manifest_path': str(manifest_path),
                                                   'output_dir': str(self.path / 'packs')}}, self.path / 'config.json')
        scoring = json.loads(Path(report['scoring_manifest']).read_text(encoding='utf-8'))
        task = next(t for t in scoring['tasks'] if t['category'] == 'parser')
        transcript = self.path / 'transcript.json'
        transcript.write_text(json.dumps({'schema_version':1, 'events': [{'kind':'tool_call','tool':'analysis'}]}), encoding='utf-8')
        correct = self.path / 'candidate.cpp'
        correct.write_text('#include <cstdint>\n#include <cstddef>\nextern "C" uint64_t wuxiang_task(uint64_t,const uint8_t*p,size_t n,uint8_t*,size_t){ if(!n)return ~uint64_t(0); uint64_t v=0;for(size_t i=0;i<n;++i){if(p[i]<48||p[i]>57)return ~uint64_t(0); if(v>(~uint64_t(0)-(p[i]-48))/10)return ~uint64_t(0);v=v*10+p[i]-48;}return v;}\n', encoding='utf-8')
        submission = dict(schema_version=1, scoring_manifest=report['scoring_manifest'],
                          pack_id=task['pack_id'], artifact_sha256=task['sha256'],
                          candidate_source=str(correct), transcript_path=str(transcript),
                          elapsed_seconds=12, mode='blind', session_id='test-real',
                          environment={'model':'test', 'rea_version':'test', 'tools':['native'], 'dynamic_available':False})
        p = self.path / 'submission.json'
        p.write_text(json.dumps(submission), encoding='utf-8')
        result = self.bench.score(p)
        self.assertEqual(result['status'], 'semantic_success', result)
        self.assertEqual(result['passed_cases'], result['total_cases'])
        self.assertFalse(result['effectiveness_claim'])
        self.assertEqual(result['dynamic_analysis'], 'unevaluated')
        correct.write_text('#include <cstdint>\n#include <cstddef>\nextern "C" uint64_t wuxiang_task(uint64_t,const uint8_t*,size_t,uint8_t*,size_t){return 0;}\n', encoding='utf-8')
        result = self.bench.score(p)
        self.assertEqual(result['status'], 'semantic_failure')
        correct.write_text('invalid C++', encoding='utf-8')
        self.assertEqual(self.bench.score(p)['status'], 'compilation_error')
        submission['elapsed_seconds'] = 1801
        p.write_text(json.dumps(submission), encoding='utf-8')
        self.assertEqual(self.bench.score(p)['status'], 'budget_exceeded')


if __name__ == '__main__':
    unittest.main()
