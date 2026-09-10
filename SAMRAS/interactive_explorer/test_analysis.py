"""Checks for filtering, denominators, drilling and saved input provenance."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

try:
    from . import analysis as a
except ImportError:
    import analysis as a


def example_data():
    return pd.DataFrame({
        "record_id": list("abcdef"),
        "year": [2020, 2020, 2021, 2021, 2020, 2022],
        "commodity": ["AU", "CL", "CL", "AU", "AU", "CL"],
        "location_group": ["Production", "Production", "Access", "Access", "", "Access"],
        "location_text": ["Face", "Face", "Road", "Road", "", "Other"],
        "hazard_mechanism": ["Rock", "Rock", "Transport", "Other", "", "Other"],
        "activity_text": ["", "Drilling (electrical)", "", "", "", ""],
        "persons_injured": [1, 2, 0, 3, 0, 0],
        "persons_killed": [0, 1, 2, 0, 0, 0],
        "persons_disabled": [0, 0, 0, 1, 0, 0],
        "confirmed_or_probable": [True, False, True, False, False, False],
        "illumination_candidate": [True, True, True, False, False, False],
        "evidence_tier": ["Tier A - assigned", "Tier C - contextual", "Tier B - narrative", "No evidence", "No evidence", "No evidence"],
        "accident_description": ["While drilling the face.", "A.B", "N/A", "transporting a drill", "", "Other"],
        "age_years": [25, 35, 45, np.nan, 0, 60],
    }, index=[10, 20, 30, 40, 50, 60])


class RuleAndGroupTests(unittest.TestCase):
    def setUp(self):
        self.df = example_data()

    def test_boolean_logic_numeric_and_literal_contains(self):
        rules = [{"field": "commodity", "op": "in", "value": ["CL"]},
                 {"field": "age_years", "op": "between", "value": [20, 40]}]
        self.assertEqual(self.df.index[a.apply_rules(self.df, rules)].tolist(), [20])
        self.assertEqual(int(a.apply_rules(self.df, rules, "OR").sum()), 4)
        literal = a.apply_rules(self.df, [{"field": "accident_description", "op": "contains", "value": "."}])
        self.assertEqual(self.df.index[literal].tolist(), [10, 20])
        self.assertTrue(a.apply_rules(self.df, [], "OR").all())
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "age_years", "op": "gte", "value": 40}]).sum()), 2)
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "age_years", "op": "lte", "value": 25}]).sum()), 2)

    def test_missing_categories_and_inverse_rules(self):
        missing = a.apply_rules(self.df, [{"field": "location_group", "op": "in", "value": [a.MISSING]}])
        self.assertEqual(self.df.index[missing].tolist(), [50])
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "age_years", "op": "is_missing"}]).sum()), 1)
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "age_years", "op": "not_missing"}]).sum()), 5)
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "commodity", "op": "not_in", "value": ["CL"]}]).sum()), 3)
        self.assertEqual(int(a.apply_rules(self.df, [{"field": "accident_description", "op": "not_contains", "value": "DRILL"}]).sum()), 4)

    def test_nested_groups_stay_inside_reference_and_detect_cycle(self):
        groups = {
            "Production": {"parent": "Reference population", "rules": [{"field": "location_group", "op": "in", "value": ["Production"]}]},
            "Coal production": {"parent": "Production", "rules": [{"field": "commodity", "op": "in", "value": ["CL"]}]},
            "Injuries": {"parent": "Reference population", "rules": [{"field": "persons_injured", "op": "gte", "value": 1}]},
        }
        reference = self.df.year.eq(2020)
        coal = a.resolve_group_mask(self.df, "Coal production", groups, reference)
        self.assertEqual(self.df.index[coal].tolist(), [20])
        overlap = coal & a.resolve_group_mask(self.df, "Injuries", groups, reference)
        self.assertEqual(int(overlap.sum()), 1)
        self.assertEqual(int(a.resolve_group_mask(self.df, "All SAMRASS", groups, reference).sum()), 6)
        groups["Production"]["parent"] = "Coal production"
        with self.assertRaisesRegex(ValueError, "cycle"):
            a.resolve_group_mask(self.df, "Production", groups, reference)

    def test_invalid_conditions_raise(self):
        with self.assertRaises(ValueError):
            a.apply_rules(self.df, [{"field": "age_years", "op": "between", "value": [50, 20]}])
        with self.assertRaises(ValueError):
            a.apply_rules(self.df, [{"field": "unknown", "op": "in", "value": [1]}])


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.df = example_data()
        self.all = pd.Series(True, index=self.df.index)

    def test_people_records_and_outcomes_are_distinct(self):
        selected = self.df.index.isin([10, 20, 30])
        self.assertEqual(a.calculate_metric(self.df, selected, "fatalities")["value"], 3)
        self.assertEqual(a.calculate_metric(self.df, selected, "fatal_records")["value"], 2)
        metric = a.calculate_metric(self.df, selected, mode="outcome_pct", outcome="fatal")
        self.assertEqual((metric["numerator"], metric["denominator"]), (2, 3))
        self.assertAlmostEqual(metric["value"], 200 / 3)
        self.assertEqual(a.calculate_metric(self.df, selected, mode="fatalities_per_1000")["value"], 1000)

    def test_share_uses_same_measure_and_fixed_denominator(self):
        selected = self.df.location_group.eq("Production")
        metric = a.calculate_metric(self.df, selected, "injured", "share", denominator_mask=self.all)
        self.assertEqual((metric["numerator"], metric["denominator"], metric["value"]), (3, 6, 50))
        table = a.summarize_by(self.df, self.all, ["commodity"], "injured", "share", denominator_mask=self.all)
        self.assertTrue(table.denominator.eq(6).all())
        self.assertAlmostEqual(table.value.sum(), 100)

    def test_custom_group_outcome_keeps_reference_denominator(self):
        outcome = self.df.commodity.eq("CL")
        metric = a.calculate_metric(self.df, self.all, mode="outcome_pct", outcome=outcome)
        self.assertEqual((metric["numerator"], metric["denominator"]), (3, 6))
        table = a.summarize_by(self.df, self.all, ["location_group"], mode="outcome_pct", outcome=outcome)
        production = table.loc[table.location_group.eq("Production")].iloc[0]
        self.assertEqual((production.numerator, production.denominator), (1, 2))
        self.assertIn(a.MISSING, set(table.location_group))

    def test_empty_selection_is_zero_total_and_undefined_rate(self):
        empty = ~self.all
        self.assertEqual(a.calculate_metric(self.df, empty)["value"], 0)
        self.assertTrue(np.isnan(a.calculate_metric(self.df, empty, mode="outcome_pct")["value"]))
        self.assertTrue(np.isnan(a.calculate_metric(self.df, empty, mode="share", denominator_mask=empty)["value"]))
        self.assertTrue(a.summarize_by(self.df, empty, ["commodity"]).empty)
        self.assertTrue(np.isnan(a.coverage(self.df, empty, ["age_years"]).iloc[0].percent))

    def test_numeric_nonfinite_and_missing_do_not_create_rates(self):
        df = self.df.copy()
        df["persons_injured"] = df["persons_injured"].astype(float)
        df.loc[10, "persons_injured"] = np.inf
        df.loc[20, "persons_injured"] = np.nan
        self.assertEqual(a.measure_total(df, "injured"), 3)
        self.assertEqual(a.coverage(df, self.all, ["persons_injured"]).iloc[0].missing, 2)


class AnnualSummaryTests(unittest.TestCase):
    def setUp(self):
        self.df = example_data()
        self.all = pd.Series(True, index=self.df.index)

    def test_category_totals_reconcile_and_complete_missing_years(self):
        table = a.summarize_annual(self.df, self.all, (2020, 2023), "injured",
                                   category_field="commodity", categories=["CL", "AU"])
        self.assertEqual(len(table), 8)
        self.assertEqual(table.loc[table.year.eq(2020), "commodity"].tolist(), ["CL", "AU"])
        self.assertEqual(table.groupby("commodity").numerator.sum().to_dict(), {"AU": 4, "CL": 2})
        total = a.summarize_annual(self.df, self.all, (2020, 2023), "injured")
        self.assertEqual(table.groupby("year").value.sum().tolist(), total.value.tolist())
        self.assertEqual(total.value.tolist(), [3, 3, 0, 0])
        self.assertTrue(pd.api.types.is_integer_dtype(table.year))

    def test_outcomes_do_not_filter_category_year_denominators(self):
        table = a.summarize_annual(self.df, self.all, (2020, 2023), mode="outcome_pct",
                                   outcome="fatal", category_field="commodity", categories=["AU", "CL"])
        au_2020 = table.loc[table.year.eq(2020) & table.commodity.eq("AU")].iloc[0]
        self.assertEqual((au_2020.numerator, au_2020.denominator, au_2020.value), (0, 2, 0))
        cl_2021 = table.loc[table.year.eq(2021) & table.commodity.eq("CL")].iloc[0]
        self.assertEqual((cl_2021.numerator, cl_2021.denominator, cl_2021.value), (1, 1, 100))
        absent = table.loc[table.year.eq(2023)]
        self.assertTrue(absent.value.isna().all())
        self.assertTrue(absent.denominator.eq(0).all())
        severity = a.summarize_annual(self.df, self.all, (2020, 2023), mode="fatalities_per_1000",
                                      category_field="commodity", categories=["CL"])
        self.assertEqual(severity.value.iloc[1], 2000)
        self.assertTrue(pd.isna(severity.value.iloc[-1]))

    def test_share_denominator_stays_fixed_when_categories_are_limited(self):
        table = a.summarize_annual(self.df, self.all, (2020, 2023), "injured", "share",
                                   denominator_mask=self.all, category_field="commodity", categories=["CL"])
        self.assertTrue(table.denominator.eq(6).all())
        self.assertAlmostEqual(table.value.sum(), 100 / 3)
        self.assertEqual(table.value.iloc[-1], 0)
        empty = a.summarize_annual(self.df, self.all, (2020, 2023), "injured", "share",
                                   denominator_mask=~self.all, category_field="commodity", categories=["CL"])
        self.assertTrue(empty.value.isna().all())

    def test_missing_categories_empty_selection_and_filtered_years(self):
        table = a.summarize_annual(self.df, self.all, (2020, 2021), category_field="location_group",
                                   categories=[a.MISSING])
        self.assertEqual(table.value.tolist(), [1, 0])
        empty = a.summarize_annual(self.df, ~self.all, (2020, 2021), category_field="commodity", categories=["CL"])
        self.assertEqual(empty.value.tolist(), [0, 0])
        self.assertTrue(a.summarize_annual(self.df, self.all, (2020, 2021),
                                          category_field="commodity", categories=[]).empty)
        clipped = a.summarize_annual(self.df, self.all, (2021, 2021))
        self.assertEqual(clipped.year.tolist(), [2021])
        self.assertEqual(clipped.value.tolist(), [2])


class LoadingAndDrillingTests(unittest.TestCase):
    def test_loading_preserves_literal_na_and_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory(prefix="samrass-explorer-test-") as temporary:
            path = Path(temporary) / "fixture.csv"
            df = example_data()
            df.to_csv(path, index=False)
            loaded = a.load_data(path)
            self.assertEqual(loaded.loc[2, "accident_description"], "N/A")
            self.assertTrue(pd.api.types.is_bool_dtype(loaded.confirmed_or_probable))
            self.assertEqual(loaded.loc[0, "drilling_context"], a.DRILLING_NARRATIVE)
            df.loc[20, "record_id"] = "a"
            df.to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "unique record_id"):
                a.load_data(path)

    def test_drilling_excludes_transport_preparation_and_completed_task(self):
        narratives = [
            "While drilling the face he was struck by a rock.",
            "He was carrying a drill machine to the workplace.",
            "The driller was walking towards the face.",
            "He was preparing for drilling.",
            "After drilling the bottom hole and pulling out the jumper he sprained his back.",
            "He was not drilling when the rock fell.",
            "The injured was collaring a hole when a rock fell.",
            "He was repairing the drill during drilling operations.",
        ]
        df = pd.DataFrame({"accident_description": narratives, "activity_text": ["", "", "", "", "Drilling (pneomatic)", "", "Collaring hole", ""],
                           "commodity": "AU", "location_text": "Stope working face", "location_group": "Stope, face, or production area"})
        result = a._add_exploratory_context(df)
        self.assertEqual(result.index[result.active_drilling_in_production].tolist(), [0, 6])
        self.assertEqual(result.loc[1, "drilling_context"], a.DRILLING_RELATED)
        self.assertEqual(result.loc[4, "drilling_context"], a.DRILLING_UNCERTAIN)


class WorkforceTests(unittest.TestCase):
    def test_explicit_zero_years_and_pooling_use_employee_years(self):
        df = example_data()
        workforce = pd.DataFrame({"commodity": ["AU", "AU"], "year": [2020, 2023],
                                  "commodity_label": ["Gold", "Gold"], "employees": [100, 300],
                                  "source": ["Fixture", "Fixture"], "source_detail": ["", ""], "notes": ["", ""]})
        with patch.object(a, "load_workforce", return_value=workforce):
            annual = a.workforce_rates(df, [2020, 2023], ["AU"], "records")
            self.assertEqual(annual.numerator.tolist(), [2, 0])
            self.assertEqual(annual.denominator.tolist(), [100, 300])
            pooled = a.workforce_rates(df, [2020, 2023], ["AU"], "records", pooled=True).iloc[0]
            self.assertEqual((pooled.numerator, pooled.denominator, pooled.value), (2, 400, 5))
            self.assertEqual(pooled.years, 2)
            self.assertNotEqual(pooled.value, annual.value.mean())

    def test_unavailable_exposure_and_unsupported_commodities_raise(self):
        with self.assertRaisesRegex(ValueError, "seven disjoint"):
            a.workforce_rates(example_data(), [2020], ["LS"], "records")
        workforce = pd.DataFrame({"commodity": ["AU"], "year": [2020], "employees": [0],
                                  "commodity_label": ["Gold"], "source": ["Fixture"], "source_detail": [""], "notes": [""]})
        with patch.object(a, "load_workforce", return_value=workforce):
            with self.assertRaisesRegex(ValueError, "positive workforce"):
                a.workforce_rates(example_data(), [2020], ["AU"], "records")


@unittest.skipUnless(a.INPUT_CSV.exists(), "Saved SAMRASS master is not present")
class SavedBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = a.load_data()

    def test_saved_cohorts_and_outcomes(self):
        df = self.df
        self.assertEqual((len(df), df.record_id.nunique()), (67223, 67223))
        self.assertEqual(a.measure_total(df, "injured"), 59784)
        self.assertEqual(a.measure_total(df, "fatalities"), 2180)
        self.assertEqual(a.measure_total(df, "disabled"), 64)
        self.assertEqual(a.measure_total(df, "fatal_records"), 1987)
        self.assertEqual(a.measure_total(df, "core_records"), 123)
        groups, reference = a.preset_groups(), pd.Series(True, index=df.index)
        self.assertEqual(int(a.resolve_group_mask(df, "Production areas", groups, reference).sum()), 24247)
        self.assertEqual(int(a.resolve_group_mask(df, "Stope working face", groups, reference).sum()), 11912)

    def test_activity_and_narrative_coverage(self):
        df = self.df
        available = df.activity_text.str.strip().ne("")
        self.assertEqual(int(available.sum()), 5568)
        self.assertEqual(set(df.loc[available, "year"]), {2010, 2024})
        self.assertEqual(int(df.accident_description.str.strip().ne("").sum()), 67052)

    def test_major_workforce_series_are_complete_and_disjoint(self):
        workforce = a.load_workforce()
        self.assertEqual(len(workforce), 140)
        self.assertFalse(workforce.duplicated(["commodity", "year"]).any())
        self.assertTrue(workforce.employees.gt(0).all())
        rates = a.workforce_rates(self.df, range(2005, 2025), list(a.WORKFORCE_COMMODITIES), "fatalities", pooled=True)
        self.assertEqual(len(rates), 7)
        self.assertTrue(rates.years.eq(20).all())


if __name__ == "__main__":
    unittest.main(verbosity=2)
