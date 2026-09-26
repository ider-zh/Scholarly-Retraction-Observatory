"""Deliberately small, exact correctness oracle; never a production graph engine."""

import argparse
from datetime import date
import json
import re


POLICIES = ("exclude_publication_year", "include_publication_year")
COUNTS = ("NF", "NB", "NR", "citation_count", "future_related_count")


def work_id(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(?:https://openalex.org/)?W([1-9][0-9]*)", value)
    return f"https://openalex.org/W{match.group(1)}" if match else None


def valid_year(value):
    return type(value) is int and 1 <= value <= 9999


def consistency(counts):
    citation_delta = counts["citation_count"] - counts["NF"] - counts["NB"]
    neighborhood_delta = counts["future_related_count"] - sum(
        counts[key] for key in ("NF", "NB", "NR")
    )
    return {
        "citation_partition_delta": citation_delta,
        "citation_count_consistent": citation_delta == 0,
        "neighborhood_partition_delta": neighborhood_delta,
        "neighborhood_count_consistent": neighborhood_delta == 0,
    }


class ReferenceGraph:
    def __init__(self, works, snapshot_date):
        self.snapshot_date = date.fromisoformat(snapshot_date)
        self.works = {}
        for record in works:
            identifier = work_id(record["id"])
            if identifier is None or identifier in self.works:
                raise ValueError("Invalid or duplicate Work ID")
            self.works[identifier] = dict(record)
        self.outgoing = {identifier: set() for identifier in self.works}
        self.incoming = {identifier: set() for identifier in self.works}
        self.audit = {}
        for identifier, record in self.works.items():
            references = record.get("referenced_works")
            if references is not None and not isinstance(references, list):
                raise ValueError("referenced_works must be a list or null")
            counts = dict.fromkeys(("duplicate", "invalid", "dangling", "self_loop",
                                    "same_year", "future_year", "unknown_year"), 0)
            seen = set()
            for raw_reference in references or []:
                reference = work_id(raw_reference)
                if reference is None:
                    counts["invalid"] += 1
                    continue
                if reference in seen:
                    counts["duplicate"] += 1
                seen.add(reference)
                if reference == identifier:
                    counts["self_loop"] += 1
                    continue
                if reference not in self.works:
                    counts["dangling"] += 1
                    continue
                self.outgoing[identifier].add(reference)
                self.incoming[reference].add(identifier)
            focal_year = record.get("year")
            for reference in self.outgoing[identifier]:
                reference_year = self.works[reference].get("year")
                if not valid_year(focal_year) or not valid_year(reference_year):
                    counts["unknown_year"] += 1
                elif reference_year == focal_year:
                    counts["same_year"] += 1
                elif reference_year > focal_year:
                    counts["future_year"] += 1
            self.audit[identifier] = counts

    def annual(self, identifier):
        identifier = work_id(identifier)
        record = self.works[identifier]
        focal_year = record.get("year")
        year_known = valid_year(focal_year)
        references = {
            reference for reference in self.outgoing[identifier]
            if year_known and valid_year(self.works[reference].get("year"))
            and self.works[reference]["year"] < focal_year
        }
        raw_references = record.get("referenced_works")
        cited_by = record.get("cited_by_count")
        incoming_years = [self.works[citing].get("year")
                          for citing in self.incoming[identifier]]
        result = {
            "work_id": identifier,
            "publication_year": focal_year,
            "reference_count_raw": len(raw_references) if raw_references is not None else None,
            "reference_count_resolved_unique": len(self.outgoing[identifier]),
            "reference_count_valid": len(references) if year_known else None,
            "reference_count": len(references) if year_known else None,
            "has_references": bool(references) if year_known else None,
            "reference_quality_counts": self.audit[identifier],
            "reference_list_unknown": raw_references is None,
            "graph_indegree_all": len(incoming_years),
            "openalex_cited_by_count": cited_by,
            "openalex_graph_citation_count_delta": (
                len(incoming_years) - cited_by if type(cited_by) is int else None
            ),
            "incoming_same_year_count": sum(
                valid_year(year) and year == focal_year for year in incoming_years
            ) if year_known else None,
            "incoming_earlier_year_count": sum(
                valid_year(year) and year < focal_year for year in incoming_years
            ) if year_known else None,
            "incoming_unknown_year_count": sum(
                not valid_year(year) for year in incoming_years
            ) if year_known else None,
            "computation_status": "complete" if year_known else "unknown_publication_year",
            "annual_counts": [],
        }
        if not year_known:
            return result
        for citing_year in range(focal_year, self.snapshot_date.year + 1):
            candidates = {
                citing for citing, candidate in self.works.items()
                if citing != identifier and valid_year(candidate.get("year"))
                and candidate["year"] == citing_year
            }
            counts = dict.fromkeys(COUNTS, 0)
            for citing in candidates:
                cites_focal = identifier in self.outgoing[citing]
                cites_references = bool(references & self.outgoing[citing])
                if cites_focal:
                    counts["NB" if cites_references else "NF"] += 1
                elif cites_references:
                    counts["NR"] += 1
            counts["citation_count"] = len(candidates & self.incoming[identifier])
            related = set(self.incoming[identifier])
            for reference in references:
                related.update(self.incoming[reference])
            counts["future_related_count"] = len(candidates & related)
            result["annual_counts"].append({
                "age_year": citing_year - focal_year,
                **counts,
                **consistency(counts),
                "is_partial_calendar_year": date(citing_year, 12, 31) > self.snapshot_date,
            })
        return result

    def window(self, annual, policy, years):
        if policy not in POLICIES:
            raise ValueError("Unknown window policy")
        lifetime = years == "lifetime"
        if not lifetime and (type(years) is not int or years < 1):
            raise ValueError("Window must be a positive whole year count or lifetime")
        start_age = 1 if policy == POLICIES[0] else 0
        focal_year = annual["publication_year"]
        year_known = valid_year(focal_year)
        start_year = focal_year + start_age if year_known else None
        end_year = focal_year + start_age + years - 1 if year_known and not lifetime else None
        unrepresentable_bounds = year_known and (
            start_year > 9999 or (end_year is not None and end_year > 9999)
        )
        planned_start = date(start_year, 1, 1) if start_year is not None and start_year <= 9999 else None
        planned_end = date(end_year, 12, 31) if end_year is not None and end_year <= 9999 else None
        observable = planned_start is not None and planned_start <= self.snapshot_date
        observed_end = min(planned_end or self.snapshot_date, self.snapshot_date) if observable else None
        mature = (planned_end is not None and planned_end <= self.snapshot_date) if year_known and not lifetime else None
        selected = [row for row in annual["annual_counts"]
                    if row["age_year"] >= start_age
                    and (lifetime or row["age_year"] < start_age + years)]
        counts = {key: sum(row[key] for row in selected) if observable else None for key in COUNTS}
        flags = []
        if unrepresentable_bounds:
            flags.append("unrepresentable_window_bounds")
        if annual["reference_count_valid"] == 0:
            flags.append("no_references")
        if annual["reference_list_unknown"] or not year_known:
            flags.append("incomplete_record")
        if mature is False:
            flags.append("insufficient_observation_window")
        if lifetime:
            flags.append("snapshot_limited")
        if annual["openalex_graph_citation_count_delta"] not in (None, 0):
            flags.append("openalex_graph_citation_count_warning")
        raw_cd = raw_no_nr = None
        checks = {}
        if observable:
            checks = consistency(counts)
            direct = counts["NF"] + counts["NB"]
            denominator = direct + counts["NR"]
            numerator = counts["NF"] - counts["NB"]
            raw_cd = numerator / denominator if denominator else None
            raw_no_nr = numerator / direct if direct else None
            if counts["citation_count"] == 0:
                flags.append("no_future_citations")
            if not denominator:
                flags.append("empty_denominator_cd")
            if not direct:
                flags.append("empty_denominator_no_nr")
            if not checks["citation_count_consistent"]:
                flags.append("citation_partition_warning")
            if not checks["neighborhood_count_consistent"]:
                flags.append("neighborhood_partition_warning")
        standard_available = observable and annual["has_references"] and (lifetime or mature)
        return {
            "work_id": annual["work_id"], "window_policy": policy,
            "window": "lifetime" if lifetime else f"{years}y",
            "planned_start_date": planned_start.isoformat() if planned_start else None,
            "planned_end_date": planned_end.isoformat() if planned_end else None,
            "observed_end_date": observed_end.isoformat() if observed_end else None,
            "observed_age_start": start_age if observable else None,
            "observed_age_end": observed_end.year - focal_year if observable else None,
            "is_mature": mature, "snapshot_limited": lifetime,
            "computation_status": annual["computation_status"] if observable else "unobservable",
            **counts, **checks,
            "disruption_cd_raw_observed": raw_cd,
            "disruption_no_nr_raw_observed": raw_no_nr,
            "disruption_cd": raw_cd if standard_available else None,
            "disruption_no_nr": raw_no_nr if standard_available else None,
            "flags": flags,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Tiny JSON array of works with id/year/referenced_works")
    parser.add_argument("--snapshot-date", required=True)
    args = parser.parse_args()
    with open(args.input, encoding="utf-8") as handle:
        works = json.load(handle)
    if len(works) > 10000:
        parser.error("Oracle refuses more than 10,000 nodes; use the production engine")
    graph = ReferenceGraph(works, args.snapshot_date)
    result = []
    for identifier in graph.works:
        annual = graph.annual(identifier)
        result.append({**annual, "windows": [graph.window(annual, policy, years)
                                             for policy in POLICIES
                                             for years in (3, 5, 10, "lifetime")]})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
