import unittest
from pipeline.build import doi, normalize

def row(**kw):
    d={'Record ID':'1','OriginalPaperDOI':'10.1234/example','RetractionNature':'Retraction','RetractionDate':'6/1/2020 0:00','OriginalPaperDate':'6/1/2019 0:00','Subject':'Medicine;Medicine;Biology;','Author':'A;A;B;'}
    d.update(kw); return d
class ResearchRules(unittest.TestCase):
    def test_doi(self):
        self.assertEqual(doi('https://doi.org/10.1234/ABC'), '10.1234/abc')
        self.assertIsNone(doi('Unavailable'))
    def test_dedup_and_leap_year(self):
        p,n,q=normalize([row(),row(**{'Record ID':'2'})],'2026-09-09')
        self.assertEqual(len(p),1);self.assertEqual(len(n),2)
        self.assertEqual(p[0]['lag_days'],366)
        self.assertEqual(p[0]['authors'],['A','B'])
        self.assertEqual(q['duplicate_paper_rows'],1)
    def test_earliest_retraction(self):
        p,_,_=normalize([row(),row(RetractionDate='1/1/2020')],'2026-09-09')
        self.assertEqual(p[0]['retracted'],'2020-01-01')
    def test_exclude_corrections_and_future(self):
        p,_,q=normalize([row(RetractionNature='Correction'),row(RetractionDate='1/1/2027')],'2026-09-09')
        self.assertEqual(p,[]);self.assertEqual(q['future_retraction_rows'],1)
    def test_missing_and_negative_lag(self):
        p,_,q=normalize([row(OriginalPaperDate='1/1/2021')],'2026-09-09')
        self.assertIsNone(p[0]['lag_days']);self.assertEqual(q['negative_lag_papers'],1)
        p,_,_=normalize([row(RetractionDate='')],'2026-09-09')
        self.assertIsNone(p[0]['retracted'])
    def test_missing_doi_keeps_distinct_records(self):
        p,_,_=normalize([row(OriginalPaperDOI=''),row(**{'Record ID':'2','OriginalPaperDOI':''})],'2026-09-09')
        self.assertEqual(len(p),2)
if __name__=='__main__':unittest.main()
