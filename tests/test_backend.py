import base64
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from server import validate_input


class ValidationTests(unittest.TestCase):
    IMAGE = base64.b64encode(b'\xff\xd8\xff' + b'0'*200).decode()

    def test_valid_payload_projection(self):
        image, model, scan = validate_input({
            'image': self.IMAGE, 'model': 'qwen3-vl:4b',
            'scan': {'site': 'example.test', 'secret': 'should not be forwarded',
                     'controls': [{'label': 'Ouvir áudio', 'kind': 'audio', 'password': 'not forwarded'}]}
        })
        self.assertEqual(image, self.IMAGE)
        self.assertEqual(model, 'qwen3-vl:4b')
        self.assertEqual(scan['controls'][0], {'label': 'Ouvir áudio', 'kind': 'audio'})
        self.assertNotIn('secret', scan)

    def test_reject_invalid_model(self):
        with self.assertRaises(ValueError):
            validate_input({'image': self.IMAGE, 'model': '../../bad space'})

    def test_reject_invalid_image(self):
        with self.assertRaises(ValueError):
            validate_input({'image': base64.b64encode(b'wrong'*50).decode()})

    def test_reject_bad_shapes(self):
        with self.assertRaises(ValueError):
            validate_input({'image': self.IMAGE, 'scan': ['bad']})


if __name__ == '__main__':
    unittest.main()
