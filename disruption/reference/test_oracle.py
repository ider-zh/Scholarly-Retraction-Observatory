import unittest

from disruption.reference.oracle import POLICIES, ReferenceGraph, consistency


def record(number, year, references=(), **extra):
    return {"id": f"W{number}", "year": year,
            "referenced_works": [f"W{target}" for target in references], **extra}


def fixture():
    return [
        record(1, 2020, [2, 2, 3, 4, 5, 6, 999, 1], cited_by_count=9),
        record(2, 2018), record(3, 2019), record(4, 2020),
        record(5, 2021), record(6, None), record(7, 2020, [1]),
        record(8, 2021, [1]), record(9, 2022, [1, 2, 3, 1, 2]),
        record(10, 2023, [2, 3, 3]), record(11, 2024, [1]),
        record(12, 2025, [1, 2]), record(13, 2026, [3]),
        record(14, 2019, [1]), record(15, None, [1]),
    ]


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.graph = ReferenceGraph(fixture(), "2026-06-26")
        self.annual = self.graph.annual("W1")

    def test_acceptance_windows(self):
        expected = {
            (0, 3): (1, 1, 1), (1, 3): (2, 1, 0),
            (0, 5): (2, 2, 1), (1, 5): (3, 1, 1),
            (0, "lifetime"): (2, 2, 2), (1, "lifetime"): (3, 2, 2),
        }
        for (policy_index, years), counts in expected.items():
            with self.subTest(policy=policy_index, years=years):
                result = self.graph.window(self.annual, POLICIES[policy_index], years)
                self.assertEqual(tuple(result[key] for key in ("NF", "NB", "NR")), counts)
                self.assertEqual(result["citation_count"], counts[0] + counts[1])
                self.assertEqual(result["future_related_count"], sum(counts))
                self.assertTrue(result["citation_count_consistent"])
                self.assertAlmostEqual(result["disruption_cd"], (counts[0] - counts[1]) / sum(counts))
                self.assertAlmostEqual(result["disruption_no_nr"], (counts[0] - counts[1]) / (counts[0] + counts[1]))
                self.assertEqual(result["is_mature"], None if years == "lifetime" else True)

    def test_references_and_all_indegree(self):
        self.assertEqual(self.annual["reference_count_raw"], 8)
        self.assertEqual(self.annual["reference_count_valid"], 2)
        self.assertEqual(self.annual["reference_count_resolved_unique"], 5)
        self.assertEqual(self.annual["reference_quality_counts"], {
            "duplicate": 1, "invalid": 0, "dangling": 1, "self_loop": 1,
            "same_year": 1, "future_year": 1, "unknown_year": 1,
        })
        self.assertEqual(self.annual["graph_indegree_all"], 7)
        self.assertEqual(self.annual["openalex_graph_citation_count_delta"], -2)
        self.assertEqual(self.annual["incoming_same_year_count"], 1)
        self.assertEqual(self.annual["incoming_earlier_year_count"], 1)
        self.assertEqual(self.annual["incoming_unknown_year_count"], 1)
        self.assertIn("openalex_graph_citation_count_warning",
                      self.graph.window(self.annual, POLICIES[0], 5)["flags"])

    def test_immature_retains_observed_counts(self):
        for policy in POLICIES:
            result = self.graph.window(self.annual, policy, 10)
            lifetime = self.graph.window(self.annual, policy, "lifetime")
            self.assertFalse(result["is_mature"])
            self.assertIsNone(result["disruption_cd"])
            self.assertEqual(result["disruption_cd_raw_observed"], lifetime["disruption_cd"])
            self.assertEqual(result["observed_end_date"], "2026-06-26")
            self.assertIn("insufficient_observation_window", result["flags"])
        self.assertEqual(self.graph.window(self.annual, POLICIES[0], 5)["planned_end_date"], "2025-12-31")
        self.assertEqual(self.graph.window(self.annual, POLICIES[1], 5)["planned_end_date"], "2024-12-31")

    def test_arbitrary_range_from_annual(self):
        selected = [row for row in self.annual["annual_counts"] if 2 <= row["age_year"] <= 5]
        self.assertEqual(tuple(sum(row[key] for row in selected) for key in ("NF", "NB", "NR")), (1, 2, 1))
        self.assertTrue(self.annual["annual_counts"][-1]["is_partial_calendar_year"])
        self.assertFalse(self.annual["annual_counts"][0]["is_partial_calendar_year"])

    def test_unknown_and_invalid_year_not_zero(self):
        for year in (None, 0, True, "2020"):
            graph = ReferenceGraph([record(1, year, [2]), record(2, 2010), record(3, 2021, [1])], "2026-06-26")
            annual = graph.annual("W1")
            self.assertIsNone(annual["reference_count_valid"])
            self.assertEqual(annual["graph_indegree_all"], 1)
            self.assertEqual(annual["annual_counts"], [])
            result = graph.window(annual, POLICIES[0], 5)
            self.assertIsNone(result["NF"])
            self.assertIsNone(result["is_mature"])

    def test_no_references_raw_one_standard_null(self):
        graph = ReferenceGraph([record(1, 2020), record(2, 2021, [1])], "2026-06-26")
        result = graph.window(graph.annual("W1"), POLICIES[0], 5)
        self.assertEqual(result["disruption_cd_raw_observed"], 1)
        self.assertIsNone(result["disruption_cd"])
        self.assertIn("no_references", result["flags"])

    def test_only_reference_citations_cd_zero_no_nr_null(self):
        graph = ReferenceGraph([record(1, 2020, [2]), record(2, 2018), record(3, 2021, [2])], "2026-06-26")
        result = graph.window(graph.annual("W1"), POLICIES[0], 5)
        self.assertEqual(result["disruption_cd"], 0)
        self.assertIsNone(result["disruption_no_nr"])
        self.assertIn("no_future_citations", result["flags"])
        self.assertNotIn("empty_denominator_cd", result["flags"])

    def test_empty_completed_and_unobservable_differ(self):
        graph = ReferenceGraph([record(1, 2026)], "2026-06-26")
        annual = graph.annual("W1")
        self.assertIsNone(graph.window(annual, POLICIES[0], 3)["NF"])
        observed = graph.window(annual, POLICIES[1], 3)
        self.assertEqual(observed["NF"], 0)
        self.assertIsNone(observed["disruption_cd_raw_observed"])

    def test_invalid_reference_and_missing_list(self):
        graph = ReferenceGraph([{"id": "W1", "year": 2020, "referenced_works": [None, "bad", "W999"]},
                                {"id": "W2", "year": 2021}], "2026-06-26")
        self.assertEqual(graph.annual("W1")["reference_quality_counts"]["invalid"], 2)
        self.assertEqual(graph.annual("W1")["reference_quality_counts"]["dangling"], 1)
        self.assertIsNone(graph.annual("W2")["reference_count_raw"])

    def test_mismatch_warns_preserves_counts_and_score(self):
        self.annual["annual_counts"][1]["citation_count"] += 7
        result = self.graph.window(self.annual, POLICIES[0], 3)
        self.assertEqual(result["citation_count"], 9)
        self.assertEqual(result["citation_partition_delta"], 7)
        self.assertIn("citation_partition_warning", result["flags"])
        self.assertEqual(result["disruption_cd"], 0)
        self.assertFalse(consistency({"NF": 0, "NB": 0, "NR": 0, "citation_count": 0,
                                      "future_related_count": 1})["neighborhood_count_consistent"])

    def test_input_permutation_invariant(self):
        reversed_graph = ReferenceGraph(list(reversed(fixture())), "2026-06-26")
        self.assertEqual(self.annual, reversed_graph.annual("W1"))

    def test_duplicate_nodes_fail(self):
        with self.assertRaises(ValueError):
            ReferenceGraph([record(1, 2020), record(1, 2021)], "2026-06-26")

    def test_unrepresentable_bounds_do_not_overflow(self):
        graph = ReferenceGraph([record(1, 9999, [2]), record(2, 9998),
                                record(3, 9999, [1])], "9999-06-26")
        annual = graph.annual("W1")
        for policy in POLICIES:
            result = graph.window(annual, policy, 10)
            self.assertIn("unrepresentable_window_bounds", result["flags"])
            self.assertIsNone(result["planned_end_date"])
            self.assertFalse(result["is_mature"])
            self.assertIsNone(result["disruption_cd"])
        included = graph.window(annual, POLICIES[1], 10)
        self.assertEqual(included["NF"], 1)
        self.assertEqual(included["disruption_cd_raw_observed"], 1)
        excluded = graph.window(annual, POLICIES[0], "lifetime")
        self.assertIn("unrepresentable_window_bounds", excluded["flags"])
        self.assertIsNone(excluded["NF"])
        self.assertIsNone(excluded["is_mature"])

    def test_boolean_citing_year_does_not_enter_age_zero(self):
        graph = ReferenceGraph([record(1, 1), record(2, True, [1])], "0001-06-26")
        annual = graph.annual("W1")
        self.assertEqual(annual["graph_indegree_all"], 1)
        self.assertEqual(annual["incoming_unknown_year_count"], 1)
        self.assertEqual(annual["annual_counts"][0]["NF"], 0)
        self.assertEqual(annual["annual_counts"][0]["citation_count"], 0)


if __name__ == "__main__":
    unittest.main()
