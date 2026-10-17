import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('deviation', Path(__file__).resolve().parents[1]/'operator-plugins/sieans-deviation/deviation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def run(points, reference, **overrides):
    params = dict(referencePoints=[dict(zip(('x', 'y', 'z'), row)) for row in reference], referenceUnit='mm',
                  maximumDistance=.1, maximumOutsidePercent=0, bidirectional=True, colorize=True)
    params.update(overrides)
    return module.run(dict(params=params, cloud=dict(points=points, unit='mm', frame='fixture')))


class Deviation(unittest.TestCase):
    def test_exact_and_displaced(self):
        reference = [[0, 0, 0], [10, 0, 0]]
        self.assertTrue(run(reference, reference)['result']['passed'])
        out = run([[0, 0, 2], [10, 0, 2]], reference)
        self.assertEqual(out['result']['outsideCount'], 4)
        self.assertEqual(out['result']['maximumDistance'], 2)
        self.assertEqual(out['result']['rmsDistance'], 2)
        self.assertEqual(out['cloud']['frame'], 'fixture')
        self.assertEqual(out['cloud']['colors'], [[1, .15, .1]]*2)

    def test_missing_reference_requires_reverse_check(self):
        source, target = [[0, 0, 0]], [[0, 0, 0], [10, 0, 0]]
        out = run(source, target)['result']
        self.assertEqual(out['forwardOutsideCount'], 0)
        self.assertEqual(out['reverseOutsideCount'], 1)
        self.assertFalse(out['passed'])
        self.assertEqual(out['items'][0]['direction'], '参考→输入')
        self.assertTrue(run(source, target, bidirectional=False)['result']['passed'])

    def test_inclusive_limits_and_no_color_output(self):
        out = run([[0, 0, 1]], [[0, 0, 0]], maximumDistance=1, colorize=False)
        self.assertTrue(out['result']['passed'])
        self.assertNotIn('cloud', out)
        self.assertTrue(run([[0, 0, 1]], [[0, 0, 0]], maximumOutsidePercent=100)['result']['passed'])

    def test_invalid_clouds_units_and_bounded_details(self):
        for source, target in [([], [[0, 0, 0]]), ([[0, 0, 0]], []), ([[float('nan'), 0, 0]], [[0, 0, 0]])]:
            with self.assertRaises(ValueError):
                run(source, target)
        with self.assertRaisesRegex(ValueError, '单位'):
            run([[0, 0, 0]], [[0, 0, 0]], referenceUnit='m')
        result = run([[0, 0, 5]]*600, [[0, 0, 0]])['result']
        self.assertEqual(result['outsideCount'], 601)
        self.assertEqual(len(result['items']), 500)
        self.assertTrue(result['detailsTruncated'])


if __name__ == '__main__':
    unittest.main()
