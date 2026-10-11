import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'python'))
from wuxiang.artifact_surface import prepare_surface, inspect_surface


def pe_fixture(payload, section=b'.wxhint', flags=0x40000040):
    data = bytearray(512 + len(payload))
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1)
    struct.pack_into('<H', data, 0x94, 0xf0)
    struct.pack_into('<H', data, 0x98, 0x20b)
    table = 0x98 + 0xf0
    data[table:table+8] = section.ljust(8, b'\0')
    struct.pack_into('<IIII', data, table+8, len(payload), 0x1000, len(payload), 512)
    struct.pack_into('<I', data, table+36, flags)
    data[512:] = payload
    return bytes(data)


class SurfaceTests(unittest.TestCase):
    def test_disabled_surface_does_not_generate_a_payload(self):
        self.assertIsNone(prepare_surface(None, 11))
        self.assertIsNone(prepare_surface({}, 11))

    def test_deterministic_payload_offsets_and_cpp_anchor(self):
        config = {'experimental': True, 'prompt_injection': 'marker',
                  'semantic_decoy': 'utf8_parser'}
        first = prepare_surface(config, 11)
        self.assertEqual(first.payload, prepare_surface(config, 11).payload)
        self.assertNotEqual(first.payload, prepare_surface(config, 23).payload)
        self.assertEqual({e['kind'] for e in first.entries}, {'prompt_injection', 'semantic_decoy'})
        for entry in first.entries:
            self.assertTrue(first.payload[entry['offset']:].startswith(entry['text'].encode('utf-8')))
        source = first.cpp_source()
        self.assertIn(first.symbol, source)
        self.assertIn('.wxhint', source)
        self.assertIn('extern "C"', source)
        self.assertIn('const unsigned char', source)
        self.assertIn(first.symbol + '_read', source)
        self.assertIn('__declspec(noinline)', source)
        self.assertIn('const volatile unsigned char', source)

    def test_invalid_options_and_unapproved_prompt_are_rejected(self):
        bad = [{'prompt_injection': 'marker'}, {'prompt_injection': 'delete'},
               {'semantic_decoy': 'anything'}, {'payload': 'arbitrary command'},
               {'experimental': 'true'}, {'max_bytes': True},
               {'experimental': True, 'max_bytes': 65537},
               {'semantic_decoy': 'utf8_parser', 'max_bytes': 1}]
        for options in bad:
            with self.subTest(options=options), self.assertRaises(ValueError):
                prepare_surface(options, 11)

    def test_inspection_checks_pe_section_and_framing(self):
        surface = prepare_surface({'semantic_decoy': 'checksum'}, 11)
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'fixture.exe'
            path.write_bytes(pe_fixture(surface.payload))
            result = inspect_surface(path)
            self.assertTrue(result['present'])
            self.assertEqual(result['payload_sha256'], surface.sha256)
            self.assertEqual(result['entries'], surface.entries)
            self.assertEqual(result['exposure_status'], 'not_evaluated')
            path.write_bytes(pe_fixture(surface.payload, section=b'.rdata'))
            self.assertFalse(inspect_surface(path)['present'])
            path.write_bytes(pe_fixture(surface.payload, flags=0xc0000040))
            with self.assertRaises(ValueError):
                inspect_surface(path)
            path.write_bytes(pe_fixture(surface.payload[:-3]))
            with self.assertRaises(ValueError):
                inspect_surface(path)

    def test_unsupported_input_and_forged_offsets_are_rejected(self):
        surface = prepare_surface({'semantic_decoy': 'packet_codec'}, 11)
        payload = surface.payload
        length = struct.unpack_from('<I', payload, 8)[0]
        meta = json.loads(payload[12:12+length])
        meta['entries'][0]['offset'] = 0
        body = json.dumps(meta, separators=(',', ':'), sort_keys=True).encode()
        forged = payload[:8] + struct.pack('<I', len(body)) + body + b'\0'
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'fixture.exe'
            for data in (b'not a PE', pe_fixture(forged)):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    inspect_surface(path)

    def test_truncated_optional_header_is_rejected(self):
        surface = prepare_surface({'semantic_decoy': 'checksum'}, 11)
        original = bytearray(pe_fixture(surface.payload))
        table = bytes(original[0x188:0x188+40])
        struct.pack_into('<H', original, 0x94, 2)
        original[0x9a:0x9a+40] = table
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder:
            path = Path(folder) / 'fixture.exe'
            path.write_bytes(original)
            with self.assertRaises(ValueError):
                inspect_surface(path)


if __name__ == '__main__':
    unittest.main()
