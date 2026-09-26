import math
from collections import Counter
from pathlib import Path
import tempfile
import unittest
import subprocess

import pyarrow as pa

from taxonomy_ngd import core
from taxonomy_ngd.engine import connect, count_sql, project
from taxonomy_ngd.publish import count_key, make_matrix
from taxonomy_ngd.run import worker


class NumericalTests(unittest.TestCase):
    def test_defined_and_degenerate(self):
        self.assertAlmostEqual(core.metrics(8, 4, 2, 2)['ngd'], .5)
        self.assertEqual(core.metrics(100, 10, 10, 1)['ngd'], 1)
        self.assertAlmostEqual(core.metrics(100, 20, 20, 1)['ngd'], math.log(20)/math.log(5))
        self.assertEqual(core.metrics(8, 4, 4, 4)['ngd'], 0)
        self.assertEqual(core.metrics(8, 8, 8, 8)['ngd_status'], 'zero_denominator')
        self.assertEqual(core.metrics(8, 0, 2, 0)['ngd_status'], 'zero_marginal')
        self.assertEqual(core.metrics(8, 4, 2, 0)['ngd_status'], 'zero_cooccurrence')
        self.assertEqual(core.metrics(8, 4, 2, 0)['jaccard'], 0)
        for values in [(0,0,0,0), (8,9,2,2), (8,7,7,0), (8,2,2,3), (8,-1,2,0)]:
            with self.assertRaises(ValueError):
                core.metrics(*values)

    def test_independent_eight_work_oracle(self):
        sets = {'A': {1,2,3,4}, 'B': {3,4,5,6}, 'C': set(), 'X': {1,2}, 'Y': {3,4}, 'Z': set()}
        parents = {'X':['A'], 'Y':['A','B'], 'Z':['B']}
        nodes = [{'taxonomy':'concepts', 'level':0 if identifier in 'ABC' else 1, 'id':identifier, 'name':identifier,
                  'parent_l0_ids':parents.get(identifier,[]), 'parent_relationship_source':'test'} for identifier in sets]
        counts = Counter()
        for left in 'ABC':
            counts[('concepts','l0',left,None)] = len(sets[left])
        for right in 'XYZ':
            counts[('concepts','l1',None,right)] = len(sets[right])
            for left in 'ABC':
                counts[('concepts','joint',left,right)] = len(sets[left] & sets[right])
        rows = make_matrix(nodes, counts, 8, 'concepts', 'test', 'test')
        self.assertEqual(len(rows),9)
        for row in rows:
            if row['l1_id']=='Y' and row['l0_id'] in 'AB':
                self.assertEqual(row['ngd_rank_for_l1'],1)
                self.assertIsNone(row['ngd_rank_excluding_parent'])
            if row['l1_id']=='Z':
                self.assertIsNone(row['ngd'])


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.entities = {'concepts':{'C0':{'id':'C0','level':0}, 'C1':{'id':'C1','level':1}},
                         'topics':{identifier:{'id':identifier,'subfield':{'id':subfield},'field':{'id':field},'domain':{'id':'D'}}
                                   for identifier,subfield,field in [('T1','S1','F1'),('T2','S2','F2')]}}
        self.connection = connect(self.entities)
        self.topics = [{'id':identifier,'subfield':{'id':subfield},'field':{'id':field},'domain':{'id':'D'}}
                       for identifier,subfield,field in [('T1','S1','F1'),('T2','S2','F2')]]

    def tearDown(self):
        self.connection.close()

    def table(self, duplicate=False, corrupt=False):
        rows=[]
        for index in range(3):
            topics = self.topics + [self.topics[0]] if index==0 else ([] if index==1 else None)
            if corrupt and index==0:
                topics = [dict(self.topics[0], field={'id':'BAD'})]
            rows.append({'id':f'https://openalex.org/W{1 if duplicate else index+1}', 'publication_year':2020 if index==0 else None,
                         'type':'review', 'is_retracted':False, 'is_xpac':index==2,
                         'concepts':[{'id':'C1','level':1,'score':0.0},{'id':'C1','level':1,'score':0.0}] if index==0 else [],
                         'topics':topics})
        return pa.Table.from_pylist(rows)

    def test_multilabel_and_no_ancestor_imputation(self):
        summary=project(self.connection,self.table())
        self.assertEqual(summary['rows'],3)
        self.assertFalse(summary['audit'])
        counts={count_key(row):row['count'] for row in count_sql(self.connection)}
        for left in ('F1','F2'):
            for right in ('S1','S2'):
                self.assertEqual(counts[('topics','joint',left,right)],1)
        self.assertNotIn(('concepts','l0','C0',None),counts)
        self.assertEqual(counts[('concepts','l1',None,'C1')],1)
        self.assertEqual(summary['coverage']['topics']['null'],1)
        self.assertEqual(summary['coverage']['topics']['empty'],1)

    def test_structural_anomalies(self):
        summary=project(self.connection,self.table(duplicate=True,corrupt=True))
        kinds={audit['kind'] for audit in summary['audit'] if audit['blocking']}
        self.assertIn('duplicate_work_id',kinds)
        self.assertIn('topic_field_conflict',kinds)

    def test_gzip_atomic_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'example.json.gz'
            core.save_json(path,{'value':None})
            self.assertEqual(core.read_json(path),{'value':None})

    def test_checkpoint_resume_corruption_and_source_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            source=run/'source.parquet'
            core.parquet(source,self.table())
            core.save_json(run/'lookups.json.gz',self.entities)
            task={'run':str(run),'source':{'path':str(source),'rows':3,'identity':core.source_identity(source)},
                  'destination':str(run/'output'),'definition_hash':'test','engine':'duckdb'}
            (run/'output').mkdir()
            (run/'output/membership.parquet.tmp').write_bytes(b'interrupted initial attempt')
            result=worker(task)
            self.assertEqual(worker(task),result)
            with self.assertRaises(ValueError):
                worker(dict(task,definition_hash='changed'))
            partial=run/'output/membership.parquet.tmp'
            partial.write_bytes(b'interrupted output')
            self.assertEqual(worker(task),result)
            (run/'output/membership.parquet').write_bytes(b'corrupt')
            with self.assertRaises(Exception):
                worker(task)
            task['source']['identity']['bytes']+=1
            with self.assertRaises(ValueError):
                worker(task)

    def test_native_count_equivalence(self):
        from taxonomy_ngd.engine import count_native
        nodes=[{'taxonomy':taxonomy,'level':level,'id':identifier} for taxonomy,level,identifiers in
               [('concepts',0,['C0']),('concepts',1,['C1']),('topics',0,['F1','F2']),('topics',1,['S1','S2'])] for identifier in identifiers]
        project(self.connection,self.table())
        expected=sorted(count_sql(self.connection),key=str)
        with tempfile.TemporaryDirectory() as directory:
            for language,command in [('go',['go','build','-o',str(Path(directory)/'go'),'taxonomy_ngd/count.go']),
                                     ('rust',['rustc','--edition=2021','-O','taxonomy_ngd/count.rs','-o',str(Path(directory)/'rust')])]:
                subprocess.run(command,check=True,capture_output=True)
                actual=count_native(self.connection,nodes,Path(directory)/language)
                self.assertEqual(sorted(actual,key=str),expected)


if __name__ == '__main__':
    unittest.main()
