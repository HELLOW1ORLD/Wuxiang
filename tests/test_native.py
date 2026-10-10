import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from wuxiang.build import ROOT,load_config,protect,verify

class NativeTests(unittest.TestCase):
    def test_mixed_cpp_abi_and_protected_behavior(self):
        result=protect(ROOT/'examples/compat.json')
        self.assertTrue(result['ok'])
        check=verify(ROOT/'examples/compat.json')
        self.assertTrue(check['behavior_equivalent'],check)
        self.assertTrue(check['ok'],check['limits'])
        header=ROOT/'examples/compat/constants.inc'
        original=header.read_bytes()
        try:
            header.write_bytes(original.replace(b'128',b'129'))
            with self.assertRaisesRegex(ValueError,'Stale build'):verify(ROOT/'examples/compat.json')
        finally:header.write_bytes(original)

if __name__=='__main__':unittest.main()
