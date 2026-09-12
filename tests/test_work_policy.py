import unittest

from pipeline.work_policy import classify, notice_links


class BroadWorkPolicyTests(unittest.TestCase):
    def test_title_and_type_are_not_exclusion_evidence(self):
        for kind in ('article', 'review', 'retraction', 'book-chapter'):
            work = dict(type=kind, doi='10.1234/original', pmid=None, original_evidence=False, notice_evidence=True, title_suspected=True)
            role, uncertain, originals = classify(work, {})
            self.assertEqual(role, 'unresolved')
            self.assertTrue(uncertain)
            self.assertEqual(originals, [])

    def test_distinct_original_required_and_conflict_is_retained(self):
        links = notice_links([dict(doi='10.1234/notice', pmid=None, original_ids=['doi:10.1234/original'])])
        work = dict(type='retraction', doi='10.1234/notice', pmid=None, original_evidence=False, notice_evidence=True, title_suspected=True)
        self.assertEqual(classify(work, links)[0], 'known_notice')
        work['original_evidence'] = True
        self.assertEqual(classify(work, links)[:2], ('original_supported', True))

    def test_same_identifier_or_missing_comparable_identifier_is_not_proof(self):
        work = dict(type='article', doi='10.1234/same', pmid=None, original_evidence=False, notice_evidence=True, title_suspected=False)
        for original in ('doi:10.1234/same', 'pmid:123', 'rw:123'):
            links = notice_links([dict(doi=work['doi'], pmid=None, original_ids=[original])])
            self.assertEqual(classify(work, links)[0], 'unresolved')
