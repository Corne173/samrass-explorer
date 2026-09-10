"""Interface integration checks; no result files are written."""
from pathlib import Path
import json
import unittest

from streamlit.testing.v1 import AppTest

APP = Path(__file__).with_name("app.py")


class InterfaceTests(unittest.TestCase):
    def make_app(self):
        app = AppTest.from_file(str(APP), default_timeout=60).run()
        self.assert_clean(app)
        return app

    def assert_clean(self, app):
        self.assertFalse(app.exception, [e.message for e in app.exception])
        self.assertFalse(app.error, [e.value for e in app.error])

    def test_initial_view_and_explicit_face(self):
        app = self.make_app()
        self.assertEqual([m.value for m in app.metric], ["67,223", "67,223", "24,247", "24,247"])
        self.assertEqual(len(app.get("plotly_chart")), 4)
        app.selectbox(key="active_group").set_value("Stope working face").run()
        self.assert_clean(app)
        self.assertEqual(app.metric[2].value, "11,912")
        self.assertTrue(any("11,502" in m.value for m in app.markdown))

    def test_chart_gestures_and_empty_years(self):
        app = self.make_app()
        for chart in app.get("plotly_chart")[:3]:
            self.assertEqual(json.loads(chart.proto.spec)["layout"]["dragmode"], "pan")
            self.assertEqual(list(chart.proto.selection_mode), [0])
        app.selectbox(key="selection_tool").set_value("Drag a selection box").run()
        self.assert_clean(app)
        for chart in app.get("plotly_chart")[:3]:
            self.assertEqual(json.loads(chart.proto.spec)["layout"]["dragmode"], "select")
            self.assertEqual(list(chart.proto.selection_mode), [1])
        app.session_state["drill"] = [{"description": "Year: 2005", "alternatives": [[
            {"field": "year", "op": "in", "value": [2005]}
        ]]}]
        app.run()
        self.assert_clean(app)
        self.assertEqual(app.metric[1].value, "67,223")
        self.assertEqual(app.metric[2].value, "24,247")
        annual = json.loads(app.get("plotly_chart")[1].proto.spec)["data"][0]
        self.assertEqual(annual["x"], list(range(2005, 2025)))
        self.assertEqual(annual["y"][1:], [0] * 19)
        app.selectbox(key="metric_mode").set_value("outcome_pct").run()
        self.assert_clean(app)
        annual = json.loads(app.get("plotly_chart")[1].proto.spec)["data"][0]
        self.assertEqual(annual["y"][1:], [None] * 19)

    def test_category_trends_follow_ranking_and_restore_total(self):
        app = self.make_app()
        initial = json.loads(app.get("plotly_chart")[1].proto.spec)["data"][0]
        self.assertEqual(app.radio(key="trend_mode").value, "Total")
        app.radio(key="trend_mode").set_value("Displayed categories").run()
        app.slider(key="top_n").set_value(5).run()
        self.assert_clean(app)
        bar = json.loads(app.get("plotly_chart")[0].proto.spec)["data"][0]
        series = json.loads(app.get("plotly_chart")[1].proto.spec)["data"]
        self.assertEqual(len(series), 5)
        self.assertEqual([s["customdata"][0][1] for s in series], [c[0] for c in bar["customdata"]])
        for line, total in zip(series, bar["x"]):
            self.assertEqual(sum(line["y"]), total)
            self.assertEqual(line["x"], list(range(2005, 2025)))
            self.assertEqual([c[0] for c in line["customdata"]], line["x"])
            self.assertFalse(line["connectgaps"])
        app.selectbox(key="bar_dimension").set_value("commodity").run()
        self.assert_clean(app)
        series = json.loads(app.get("plotly_chart")[1].proto.spec)["data"]
        self.assertTrue(all(len(s["customdata"][0][1]) == 2 for s in series))
        self.assertEqual(app.metric[1].value, "67,223")
        self.assertEqual(app.metric[3].value, "24,247")
        app.radio(key="trend_mode").set_value("Total").run()
        self.assert_clean(app)
        total = json.loads(app.get("plotly_chart")[1].proto.spec)["data"]
        self.assertEqual(len(total), 1)
        self.assertEqual(total[0]["y"], initial["y"])

    def test_outcome_denominator_and_named_outcome(self):
        app = self.make_app()
        app.selectbox(key="metric_mode").set_value("outcome_pct").run()
        self.assert_clean(app)
        self.assertIn("Denominator: all 24,247 records", "\n".join(c.value for c in app.caption))
        app.selectbox(key="outcome").set_value("core").run()
        self.assert_clean(app)
        text = "\n".join(c.value for c in app.caption)
        self.assertIn("Numerator: 14 records", text)
        self.assertIn("Denominator: all 24,247 records", text)
        app.selectbox(key="outcome").set_value("group:Stope working face").run()
        self.assert_clean(app)
        text = "\n".join(c.value for c in app.caption)
        self.assertIn("Numerator: 11,912 records", text)
        self.assertIn("Denominator: all 24,247 records", text)

    def test_create_subgroup_through_controls(self):
        app = self.make_app()
        app.text_input(key="draft_name").set_value("Gold production")
        app.button(key="groupdraft_add").click().run()
        ident = app.session_state["groupdraft_rows"][0]["_id"]
        app.selectbox(key=f"groupdraft_{ident}_field").set_value("commodity").run()
        app.multiselect(key=f"groupdraft_{ident}_commodity_in_value").set_value(["AU"]).run()
        next(b for b in app.button if b.label == "Save group in this session").click().run()
        self.assert_clean(app)
        self.assertEqual(app.selectbox(key="active_group").value, "Gold production")
        self.assertEqual(app.metric[2].value, "12,131")
        self.assertEqual(app.session_state["groups"]["Gold production"]["parent"], "Production areas")

    def test_empty_group_and_reference_reset(self):
        app = self.make_app()
        app.multiselect(key="reference_commodities").set_value(["FE"]).run()
        app.selectbox(key="active_group").set_value("Stope working face").run()
        self.assert_clean(app)
        self.assertEqual(app.metric[3].value, "0")
        self.assertTrue(any("No records match" in x.value for x in app.info))
        next(b for b in app.button if b.label == "Reset reference filters").click().run()
        self.assert_clean(app)
        self.assertEqual(app.metric[3].value, "11,912")


if __name__ == "__main__":
    unittest.main()
