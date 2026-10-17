import importlib.util
import json
import math
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('records',ROOT/'operator-plugins/sieans-records/records.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
manifest=json.loads((ROOT/'operator-plugins/sieans-records/operator-plugin.json').read_text(encoding='utf-8'))


def run(task,**overrides):
    definition=next(op for op in manifest['operators'] if op['id']==task)
    p=json.loads(json.dumps({f['key']:f['default'] for f in definition['parameters']}));p.update(overrides)
    return r.run(dict(params=p))['result']


class RecordsTests(unittest.TestCase):
    def test_build_keeps_nested_types_and_copies_data(self):
        data=dict(x=1,enabled=True,empty=None,values=[1,'1'],nested=dict(y=2))
        result=run('build',fields=data);self.assertEqual(result['record'],data)
        result['record']['nested']['y']=9;self.assertEqual(data['nested']['y'],2)
        self.assertEqual(result['fieldCount'],5)

    def test_append_capacity_and_copy_on_success_and_failure(self):
        rows=[dict(id=1),dict(id=2)]
        out=run('append',records=rows,record=dict(id=3),capacity=2,overflow='drop-oldest')
        self.assertEqual(out['records'],[dict(id=2),dict(id=3)]);self.assertEqual(out['discarded'],1);self.assertEqual(rows,[dict(id=1),dict(id=2)])
        with self.assertRaisesRegex(ValueError,'已满'):run('append',records=rows,record=dict(id=3),capacity=2)
        with self.assertRaisesRegex(ValueError,'超出容量'):run('append',records=rows,record=dict(id=3),capacity=1,overflow='drop-oldest')

    def test_typed_duplicate_keys_ignore_replace_and_invalid_existing_keys(self):
        rows=[dict(id=1,value='old')]
        with self.assertRaisesRegex(ValueError,'已存在'):run('append',records=rows,record=dict(id=1.,value='new'),keyField='id')
        out=run('append',records=rows,record=dict(id=1.,value='new'),keyField='id',duplicate='ignore');self.assertFalse(out['accepted']);self.assertEqual(out['records'],rows)
        out=run('append',records=rows,record=dict(id=1,value='new'),keyField='id',duplicate='replace');self.assertTrue(out['replaced']);self.assertEqual(out['records'][0]['value'],'new')
        for value in ['1',True]:self.assertEqual(run('append',records=rows,record=dict(id=value),keyField='id')['count'],2)
        for bad in [[dict(id=1),dict(id=1.)],[dict(id=None)],[dict(other=1)]]:
            with self.assertRaises(ValueError):run('append',records=bad,record=dict(id=2),keyField='id')

    def test_filter_strict_types_presence_and_missing_policies(self):
        rows=[dict(value=1),dict(value='1'),dict(value=True),dict(value=None),dict(other=1)]
        out=run('filter',records=rows,operand=dict(value=1),missing='skip');self.assertEqual(out['records'],[dict(value=1)]);self.assertEqual(out['missingCount'],1)
        self.assertEqual(run('filter',records=rows,comparison='exists')['count'],4)
        self.assertEqual(run('filter',records=rows,comparison='missing')['records'],[dict(other=1)])
        with self.assertRaisesRegex(ValueError,'缺少'):run('filter',records=[{}])
        with self.assertRaisesRegex(ValueError,'数值'):run('filter',records=[dict(value=True)],comparison='gte',operand=dict(value=1))
        with self.assertRaisesRegex(ValueError,'布尔'):run('filter',records=[dict(value=1)],comparison='is_true')
        self.assertEqual(run('filter',records=[dict(value='ABC'),dict(value='abc')],comparison='contains',operand=dict(value='A'))['count'],1)
        with self.assertRaises(ValueError):run('filter',records=[],comparison='gte',operand=dict(value='1'))

    def test_inverse_filter_does_not_retain_skipped_rows(self):
        rows=[dict(value=1),dict(value=2),dict(other=1)]
        out=run('filter',records=rows,operand=dict(value=1),keepMatches=False,missing='skip');self.assertEqual(out['records'],[dict(value=2)]);self.assertEqual(out['matchedCount'],1)

    def test_stable_sort_and_missing_bucket_in_both_directions(self):
        rows=[dict(id='a',value=2),dict(id='b'),dict(id='c',value=2),dict(id='d',value=1),dict(id='e',value=None)]
        self.assertEqual([r['id'] for r in run('sort',records=rows,direction='descending',missing='last')['records']],['a','c','d','b','e'])
        self.assertEqual([r['id'] for r in run('sort',records=rows,missing='first')['records']],['b','e','d','a','c'])
        for values in [[1,'2'],[1,True],[{},{}]]:
            with self.assertRaises(ValueError):run('sort',records=[dict(value=v) for v in values])

    def test_select_last_empty_and_out_of_range(self):
        self.assertEqual(run('select',records=[dict(a=1),dict(a=2)],index=-1)['record'],dict(a=2))
        self.assertFalse(run('select',records=[],index=-1,outOfRange='empty')['found'])
        with self.assertRaisesRegex(ValueError,'越界'):run('select',records=[],index=0)
        with self.assertRaises(ValueError):run('select',records=[],index=True)

    def test_projection_renames_flattens_arrays_and_skips_whole_row(self):
        rows=[dict(data=dict(points=[dict(x=7)]),id=1),dict(id=2)]
        columns=[dict(output='x',source='data.points.0.x')]
        out=run('project',records=rows,columns=columns,missing='skip-row');self.assertEqual(out['records'],[dict(x=7)]);self.assertEqual(out['skippedCount'],1)
        with self.assertRaises(ValueError):run('project',records=rows,columns=columns)
        with self.assertRaisesRegex(ValueError,'重名'):run('project',records=[],columns=columns+columns)
        with self.assertRaises(ValueError):run('project',records=[],columns=[dict(output='x',source='__proto__.x')])

    def test_numeric_summary_missing_and_empty_are_explicit(self):
        out=run('summary',records=[dict(value=v) for v in [1,2,3,None]],missing='skip')
        self.assertEqual((out['valueCount'],out['missingCount']),(3,1));self.assertEqual(out['summary']['sum'],6);self.assertEqual(out['summary']['mean'],2);self.assertAlmostEqual(out['summary']['populationStddev'],math.sqrt(2/3))
        out=run('summary',records=[{}],missing='skip');self.assertFalse(out['hasValues']);self.assertEqual(out['summary'],{})
        for value in [True,'2']:
            with self.assertRaises(ValueError):run('summary',records=[dict(value=value)])
        with self.assertRaisesRegex(ValueError,'溢出'):run('summary',records=[dict(value=1e308),dict(value=1e308)])

    def test_bounds_and_reserved_fields_reject_before_creating_outputs(self):
        for value in [dict(a=float('nan')),dict(constructor=1),{'bad.key':1},dict(a='x'*50000)]:
            with self.assertRaises(ValueError):run('build',fields=value)
        with self.assertRaises(ValueError):run('select',records=[{}]*1001)
        deep=0
        for _ in range(14):deep=dict(a=deep)
        with self.assertRaisesRegex(ValueError,'嵌套'):run('build',fields=deep)


if __name__=='__main__':unittest.main()
