from evals import saathi_eval as se


def test_the_golden_set_covers_several_languages_and_every_case_expects_all_three_fields():
    g = se.load()
    assert len(g["cases"]) >= 12 and {c["language"] for c in g["cases"]} >= {"English", "Hindi", "Hinglish", "Marathi", "Tamil", "Bengali"}
    assert all(set(c["expect"]) == set(se.FIELDS) for c in g["cases"])


def test_scoring_uses_the_apps_own_normalisation_and_demands_the_exact_name():
    r = se.score_case({"full_name": "Meera Iyer", "state": "kerala", "sector": "science"}, {"full_name": "Meera Iyer", "state": "Kerala", "sector": "Science"})
    assert all(r.values())
    r = se.score_case({"full_name": "Meera Iyar", "state": "Goa", "sector": None}, {"full_name": "Meera Iyer", "state": "Kerala", "sector": "Science"})
    assert r == {"full_name": False, "state": False, "sector": False}


def test_summary_is_per_language_and_overall():
    s = se.summarise([("English", {"full_name": True, "state": True, "sector": False}), ("Hindi", {"full_name": False, "state": True, "sector": True})])
    assert s["English"]["sector"] == 0.0 and s["Hindi"]["full_name"] == 0.0 and s["all"]["state"] == 1.0 and s["all"]["n"] == 2


async def test_the_offline_mock_runs_end_to_end(client):
    res = await se.run(live=False)
    assert res["all"]["n"] >= 12 and res["api_errors"] == 0
