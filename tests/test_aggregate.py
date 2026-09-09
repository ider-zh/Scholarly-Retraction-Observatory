import unittest
from pipeline.aggregate import aggregate, leaders, percentile

def paper(id='a', **kw):
    p={'id':id,'doi':None,'title':'sample','published':'2020-01-01','retracted':'2025-01-01','lag_days':1827,'subjects':['X','Y'],'authors':['A','B'],'institutions':['I'],'rw_ids':[id],'oa':None}
    p.update(kw); return p
META={'partial_year':2026,'paper_count':2}
class Aggregates(unittest.TestCase):
    def test_membership_and_fractional_mass(self):
        rows=[paper(),paper('b',subjects=['Y'])]
        r=leaders(rows,'rw','subjects')
        self.assertEqual(r['full'][0]['count'],2)
        self.assertEqual(r['fractional'][0]['count'],1.5)
        self.assertEqual(sum(x['count'] for x in r['fractional']),2)
    def test_zero_baseline_and_missing_lag(self):
        r,_=aggregate([paper(lag_days=None)],META)
        self.assertIsNone(r['taxonomies']['rw']['disciplines'][0]['growth']['percent'])
        self.assertEqual(r['summary']['lag']['n'],0)
    def test_growth_and_observation_evidence(self):
        rows=[paper('a',retracted='2024-01-01'),paper('b'),paper('c')]
        r,_=aggregate(rows,META)
        self.assertEqual(r['taxonomies']['rw']['disciplines'][0]['growth']['percent'],100)
        self.assertEqual(r['insights'][1]['evidence']['percent'],100)
        self.assertEqual(sum(t['count'] for t in r['trend']['retracted']),3)
    def test_samples_are_bounded_and_not_corpus(self):
        r,s=aggregate([paper(str(i)) for i in range(70)],META)
        self.assertEqual(len(s['items']),36)
        self.assertEqual(r['summary']['paper_count'],70)
        self.assertNotIn('papers',r)
        self.assertNotIn('authors',s['items'][0])
    def test_hierarchy_deduplicates_parents_and_weights_each_level(self):
        r,_=aggregate([paper(subjects=['(HSC) A','(HSC) B','(BLS) A'])],META)
        g=r['taxonomies']['rw']
        self.assertEqual({x['id']:x['count'] for x in g['domains']},{'HSC':1,'BLS':1})
        self.assertEqual([x['fractional_count'] for x in g['domains']],[.5,.5])
        self.assertEqual(len(g['disciplines']),3)
        # Published fractional values are rounded to three decimal places.
        self.assertAlmostEqual(sum(x['fractional_count'] for x in g['disciplines']),1,delta=.0015)
        self.assertEqual({x['parent_id'] for x in g['disciplines']},{'HSC','BLS'})
    def test_unknown_subject_is_retained(self):
        r,_=aggregate([paper(subjects=[]),paper('b',subjects=['Unrecognized'])],META)
        self.assertEqual(r['taxonomies']['rw']['unclassified_papers'],2)
        self.assertEqual(r['taxonomies']['rw']['domains'][0]['count'],2)
    def test_openalex_cannot_change_statistics(self):
        a,_=aggregate([paper()],META)
        b,_=aggregate([paper(oa={'field':{'id':'fake','name':'fake'},'authors':['fake']})],META)
        for key in ['summary','trend','taxonomies','insights']:
            self.assertEqual(a[key],b[key])
        self.assertEqual(set(b['taxonomies']),{'rw'})
    def test_percentile(self):
        self.assertEqual(percentile([0,10],.25),2.5)
        self.assertIsNone(percentile([],.5))
if __name__=='__main__': unittest.main()
