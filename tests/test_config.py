import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from wuxiang.build import load_config, within_output, evaluate_limits, validate_options, make_dependencies

class ConfigTests(unittest.TestCase):
    def test_output_must_be_inside_project(self):
        with self.assertRaises(ValueError):
            within_output(Path('F:/outside'), Path(__file__).resolve().parents[1])

    def test_performance_cap_not_silently_relaxed(self):
        report = evaluate_limits([1.0]*31, [1.21]*31, 100, 190)
        self.assertFalse(report['ok'])
        self.assertFalse(report['performance_pass'])
        self.assertTrue(report['size_pass'])

    def test_size_cap_and_zero_baseline(self):
        self.assertFalse(evaluate_limits([1]*31,[1]*31,100,201)['ok'])
        with self.assertRaises(ValueError):
            evaluate_limits([0]*31,[1]*31,100,100)

    def test_compiler_flags_cannot_redirect_outputs_or_override_contract(self):
        for flag in ('/FaF:/outside/a.asm','/Zi','@outside.rsp','/clang:-flto','/GL','/MDd','/EHa','/interface'):
            with self.subTest(flag=flag), self.assertRaises(ValueError):validate_options([flag])
        validate_options(['/fp:precise','/utf-8','/W4','/wd4100'])

    def test_windows_depfile_preserves_directory_backslashes(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            p=Path(folder)/'module.d'
            p.write_text('out.bc: F:\\src\\main.cpp D:\\ProgramFiles\\Microsoft\\ VS\\include\\vector\n')
            self.assertEqual(make_dependencies(p),[str(Path('F:/src/main.cpp').resolve()),str(Path('D:/ProgramFiles/Microsoft VS/include/vector').resolve())])

    def test_nonfinite_or_negative_measurements_never_pass(self):
        for b,p in (([float('inf')],[1]),([1],[-1]),([1],[float('nan')]),([],[1])):
            with self.subTest(b=b,p=p),self.assertRaises(ValueError):evaluate_limits(b,p,100,100)
        with self.assertRaises(ValueError):evaluate_limits([1],[1],100,-1)

if __name__ == '__main__':
    unittest.main()
