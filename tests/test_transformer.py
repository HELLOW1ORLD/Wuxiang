"""Native transformer behavior tests; requires the pinned local LLVM SDK."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'python'))
from wuxiang.build import tool_paths, function_code


class TransformerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools, cls.env = tool_paths()
        cls.transform = Path(os.environ.get('WUXIANG_IR_EXE', cls.tools['transform']))
        if not cls.transform.is_file():
            raise RuntimeError('Build wuxiang-ir before native transformer tests')
        cls.out = ROOT / 'build/tests/transformer'
        cls.out.mkdir(parents=True, exist_ok=True)

    def run_tool(self, args):
        result = subprocess.run(list(map(str, args)), env=self.env, cwd=self.out,
                                text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def transform_file(self, source, symbol, seed, stem, expect_success=True):
        bc, report = self.out / (stem + '.bc'), self.out / (stem + '.json')
        if bc.exists():
            bc.unlink()
        result = subprocess.run([str(self.transform), str(source), '-o', str(bc),
                                '--report', str(report), '--functions', symbol,
                                '--seed', str(seed)], env=self.env, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=180)
        self.assertEqual(result.returncode == 0, expect_success, result.stderr)
        data = json.loads(report.read_text(encoding='utf-8'))
        self.assertEqual(data['ok'], expect_success)
        self.assertEqual(bc.exists(), expect_success)
        return bc, data

    def native(self, bc, stem):
        obj, exe = self.out / (stem + '.obj'), self.out / (stem + '.exe')
        self.run_tool([self.tools['llc'], '-O=2', '-filetype=obj', bc, '-o', obj])
        self.run_tool([self.tools['link'], '/nologo', obj, '/out:' + str(exe),
                       '/subsystem:console', '/defaultlib:msvcrt',
                       '/defaultlib:vcruntime', '/defaultlib:ucrt', '/defaultlib:kernel32'])
        self.run_tool([exe])
        return obj

    def test_exhaustive_arithmetic_and_loop_memory_semantics(self):
        for fixture, symbol in [('arithmetic', 'kernel'), ('loop', 'loop_kernel')]:
            source = ROOT / 'tests/ir' / (fixture + '.ll')
            reference = self.native(source, fixture + '-reference')
            baseline = function_code(self.tools, reference, self.env)[symbol]
            for seed in (1, 7, 19):
                with self.subTest(fixture=fixture, seed=seed):
                    stem = fixture + '-' + str(seed)
                    bc, report = self.transform_file(source, symbol, seed, stem)
                    obj = self.native(bc, stem)
                    self.assertTrue(report['verified'])
                    self.assertNotEqual(function_code(self.tools, obj, self.env)[symbol], baseline)

    def test_missing_and_untransformable_functions_fail_explicitly(self):
        for fixture, symbol in [('arithmetic', 'absent'), ('identity', 'identity'),
                                ('boolean', 'boolean'), ('poison', 'flagged')]:
            with self.subTest(symbol=symbol):
                _, report = self.transform_file(ROOT / 'tests/ir' / (fixture + '.ll'),
                                                symbol, 7, 'reject-' + symbol, False)
                self.assertTrue(report['errors'])
                self.assertEqual(report['functions'][0]['status'], 'unsupported')

    def test_exception_unwind_and_destructors_remain_valid(self):
        source = ROOT / 'tests/native/eh.cpp'
        original = self.out / 'eh-original.bc'
        self.run_tool([self.tools['clang'], '/nologo', '/O2', '/MD', '/EHsc', '/GR',
                       '/std:c++20', '/c', '/I' + str(ROOT / 'include'),
                       '/clang:-emit-llvm', '/clang:-o', '/clang:' + str(original), source])
        ref = self.native(original, 'eh-reference')
        symbol = '?guarded@@YAII@Z'
        bc, report = self.transform_file(original, symbol, 11, 'eh-protected')
        row = report['functions'][0]
        self.assertEqual(row['status'], 'partial')
        self.assertEqual(row['transformations']['control_regions'], 0)
        protected = self.native(bc, 'eh-protected')
        self.assertNotEqual(function_code(self.tools, ref, self.env)[symbol],
                            function_code(self.tools, protected, self.env)[symbol])

    def test_volatile_effects_invalidate_callsite_and_function_attributes(self):
        bc, _ = self.transform_file(ROOT / 'tests/ir/attributes.ll', 'effect', 7, 'attributes')
        dis = Path(self.tools['llc']).with_name('llvm-dis.exe')
        ir = self.run_tool([dis, bc, '-o', '-'])
        self.assertNotIn('nosync', ir)
        self.assertNotIn('speculatable', ir)
        self.assertNotIn('memory(none)', ir)
        optimized = self.out / 'attributes.optimized.bc'
        opt = Path(self.tools['llc']).with_name('opt.exe')
        self.run_tool([opt, '-passes=default<O2>', bc, '-o', optimized])
        obj = self.native(optimized, 'attributes')
        # If the old memory(none)/speculatable facts remain at the callsite,
        # optimization discards this unused call despite new volatile accesses.
        assembly = self.run_tool([self.tools['objdump'], '--disassemble', obj])
        main_code = assembly.split('<main>:', 1)[1]
        self.assertIn('call', main_code)

    def test_cmake_msvc_main_and_protected_static_library(self):
        source_dir = self.out / 'cmake-source'
        build_dir = self.out / 'cmake-build'
        source_dir.mkdir(exist_ok=True)
        text = '''cmake_minimum_required(VERSION 3.25)
project(WuxiangAdapterTest LANGUAGES CXX)
if(DEFINED WUXIANG_TEST_CRT)
  set(CMAKE_MSVC_RUNTIME_LIBRARY "${WUXIANG_TEST_CRT}")
endif()
set(WUXIANG_CLANG_CL "@CLANG@")
set(WUXIANG_LLC "@LLC@")
set(WUXIANG_IR "@TRANSFORM@")
include("@ROOT@/cmake/Wuxiang.cmake")
wuxiang_add_protected_library(protected_module SOURCES "@ROOT@/examples/compat/module.cpp" INCLUDE_DIRECTORIES "@ROOT@/examples/compat" COMPILE_OPTIONS ${WUXIANG_TEST_FLAG})
add_executable(adapter "@ROOT@/examples/compat/main.cpp")
target_compile_features(adapter PRIVATE cxx_std_20)
wuxiang_link_protected_library(adapter protected_module)
'''
        for name, value in {'ROOT': ROOT, 'CLANG': self.tools['clang'],
                            'LLC': self.tools['llc'], 'TRANSFORM': self.transform}.items():
            text = text.replace('@' + name + '@', Path(value).as_posix())
        (source_dir / 'CMakeLists.txt').write_text(text, encoding='utf-8')
        self.run_tool([self.tools['cmake'], '-S', source_dir, '-B', build_dir,
                       '-G', 'Visual Studio 17 2022', '-A', 'x64'])
        self.run_tool([self.tools['cmake'], '--build', build_dir, '--config', 'Debug', '--parallel', '1'])
        self.run_tool([build_dir / 'Debug/adapter.exe'])
        coverage = json.loads((build_dir / 'wuxiang/protected_module/1.coverage.json').read_text())
        self.assertTrue(coverage['ok'])
        rejected = subprocess.run([self.tools['cmake'], '-S', str(source_dir),
                                   '-B', str(self.out / 'cmake-reject'), '-G',
                                   'Visual Studio 17 2022', '-A', 'x64',
                                   '-DWUXIANG_TEST_CRT=MultiThreaded'], env=self.env,
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
        self.assertIn('MultiThreadedDLL', rejected.stdout + rejected.stderr)
        for index, flag in enumerate(('/Faoutside.asm', '@injected.rsp', '/clang:-fno-exceptions')):
            with self.subTest(flag=flag):
                rejected = subprocess.run([self.tools['cmake'], '-S', str(source_dir),
                    '-B', str(self.out / ('cmake-reject-flag-' + str(index))), '-G',
                    'Visual Studio 17 2022', '-A', 'x64', '-DWUXIANG_TEST_FLAG=' + flag],
                    env=self.env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
                self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                self.assertIn('output/ABI overrides forbidden', rejected.stdout + rejected.stderr)

    def test_optimized_parser_keeps_protection_in_machine_code(self):
        original = self.out / 'parser-original.bc'
        self.run_tool([self.tools['clang'], '/nologo', '/O2', '/MD', '/EHsc', '/GR',
                       '/std:c++20', '/DTASK_ID=2', '/c', '/clang:-emit-llvm',
                       '/clang:-o', '/clang:' + str(original), ROOT / 'bench/tasks.cpp'])
        reference = self.out / 'parser-reference.obj'
        self.run_tool([self.tools['llc'], '-O=2', '-filetype=obj', original, '-o', reference])
        baseline = function_code(self.tools, reference, self.env)['wuxiang_task']
        for seed in (11, 29, 47):
            with self.subTest(seed=seed):
                bc, report = self.transform_file(original, 'wuxiang_task', seed, 'parser-' + str(seed))
                obj = self.out / ('parser-' + str(seed) + '.obj')
                self.run_tool([self.tools['llc'], '-O=2', '-filetype=obj', bc, '-o', obj])
                self.assertNotEqual(function_code(self.tools, obj, self.env)['wuxiang_task'], baseline)


if __name__ == '__main__':
    unittest.main()
