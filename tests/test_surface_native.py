"""Real COFF/PE and ABI tests for opt-in target text, not anti-agent efficacy."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from wuxiang.artifact_surface import inspect_surface
from wuxiang.build import protect, verify, tool_paths, run


class SurfaceNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = ROOT / 'build/tests/surface-native'
        cls.out.mkdir(parents=True, exist_ok=True)
        original = json.loads((ROOT / 'examples/compat-surfaces.json').read_text())
        original['module']['sources'] = [str(ROOT / 'examples/compat/module.cpp')]
        original['main']['sources'] = [str(ROOT / 'examples/compat/main.cpp')]
        original['include_dirs'] = [str(ROOT / 'examples/compat')]
        original['output_dir'] = str(cls.out / 'artifacts')
        cls.config = cls.out / 'config.json'
        cls.config.write_text(json.dumps(original))
        cls.manifest = protect(cls.config)

    def test_linked_controls_behavior_and_relocations(self):
        manifest = self.manifest
        self.assertTrue(manifest['ok'])
        self.assertEqual(manifest['agent_surface']['function_references'], 2)
        surface = inspect_surface(manifest['binaries']['protected']['path'])
        for variant, binary in manifest['binaries'].items():
            self.assertEqual(run([binary['path']]).strip(), 'WUXIANG_ABI_OK')
            self.assertEqual(inspect_surface(binary['path'])['present'], variant == 'protected')
        self.assertFalse(surface['effectiveness_verified'])
        self.assertEqual(surface['exposure_status'], 'not_evaluated')
        tools, env = tool_paths()
        relocs = run([tools['objdump'], '--reloc', self.out / 'artifacts/module0.protected.obj'], env)
        self.assertEqual(sum(line.rstrip().endswith(surface['symbol']) for line in relocs.splitlines()), 2)
        self.assertEqual(sum(line.rstrip().endswith(surface['symbol'] + '_read') for line in relocs.splitlines()), 2)
        cli = subprocess.run([sys.executable, str(ROOT/'wuxiang.py'), 'surface', 'inspect',
                              '--artifact', manifest['binaries']['protected']['path']],
                             capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(cli.stdout)['payload_sha256'], surface['payload_sha256'])

    def test_surface_config_change_rejects_stale_build(self):
        original = self.config.read_bytes()
        try:
            config = json.loads(original)
            config['agent_surface']['semantic_decoy'] = 'checksum'
            self.config.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Stale build'):
                verify(self.config)
        finally:
            self.config.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
