"""Phase 3: every archetype generates a runnable MVP whose own tests pass."""
import json

import pytest

from agents import builder
from agents.intake import parse_brief
from models import CanvasBlock, Critique, KillAssumption, LeanCanvas

CANVAS = LeanCanvas(**{k: CanvasBlock(block=k, content=f"{k} content") for k in (
    "problem", "customer_segments", "unique_value_proposition", "solution", "channels", "revenue_streams",
    "cost_structure", "key_metrics", "unfair_advantage")})
CRITIQUE = Critique(summary="s", riskiest_assumptions=[KillAssumption(assumption="Users will pay", kill_criterion="k")])

IDEAS = {
    "spaced_repetition": "AI flashcard and spaced-repetition tool for university students in Egypt, Arabic and English",
    "booking": "Booking app for yoga tutors in Kenya",
    "habit_tracker": "Habit tracker for nurses in India",
    "directory": "Marketplace to find freelance designers in Jordan",
    "course": "Online course with Excel templates for accountants in Nigeria",
}


UNRELATED = [
    "AI resume feedback tool for job seekers in Egypt",
    "Arabic podcast transcription service",
    "AI tutor chatbot for high-school math",
    "Meal planner for students on a budget",
    "Invoice generator for freelancers in Nigeria",
]


def test_classifier_picks_expected_archetype():
    for archetype, idea in IDEAS.items():
        sel = builder.select_template(idea)
        assert sel["supported"] and sel["archetype"] == archetype, (idea, sel["reason"])
        assert builder.classify(idea)[0] == archetype


def test_clearly_supported_idea_is_selected_with_reason():
    sel = builder.select_template("Appointment booking for physiotherapy clinics in Jordan")
    assert sel["archetype"] == "booking" and sel["supported"]
    assert "appointment" in sel["matched"]["booking"] and "booking" in sel["reason"]


@pytest.mark.parametrize("idea", UNRELATED)
def test_unrelated_idea_is_rejected_not_forced_into_course(idea):
    sel = builder.select_template(idea)
    assert sel["archetype"] is None and not sel["supported"]
    assert "No tested template fits" in sel["reason"]
    assert builder.classify(idea)[0] is None


def test_ambiguous_idea_is_not_confidently_misclassified():
    sel = builder.select_template("Schedule study sessions and follow an online course")
    assert sel["scores"]["booking"] == sel["scores"]["course"] == 2
    assert sel["archetype"] is None and "Ambiguous" in sel["reason"]


def test_single_weak_keyword_is_not_enough():
    sel = builder.select_template("Mood journal for teenagers")   # only 'journal' (weight 1)
    assert sel["archetype"] is None


def test_unsupported_idea_builds_nothing():
    report = builder.run("t-unsupported", parse_brief(UNRELATED[2]), CANVAS, CRITIQUE)
    assert report["supported"] is False and report["files"] == 0 and report["app_dir"] is None
    assert report["tests"]["ran"] == 0 and not report["smoke_ok"]
    assert not (builder.GENERATED / "t-unsupported").exists()
    from gates import evaluate_gate_3
    from models import GateOutcome
    g = evaluate_gate_3(report, attempt=1)
    assert g.outcome == GateOutcome.STOP and "no MVP was built" in g.reason
    assert g.checks["tested_template_fits_idea"] is False


@pytest.mark.parametrize("archetype", list(IDEAS))
def test_generated_mvp_passes_its_own_tests(archetype):
    report = builder.run(f"t-{archetype}", parse_brief(IDEAS[archetype]), CANVAS, CRITIQUE)
    assert report["spec"].archetype == archetype
    t = report["tests"]
    assert t["ok"], t["output"][-2000:]
    assert t["ran"] >= 18 and t["failed"] == 0 and t["errors"] == 0
    assert report["smoke_ok"], report["smoke_msg"]
    assert report["features_traced"]
    assert {"server.py", "core.py", "config.json", "tests/test_spec.py"} <= set(report["file_list"])


def test_generated_app_is_idea_specific():
    report = builder.run("t-specific", parse_brief(IDEAS["spaced_repetition"]), CANVAS, CRITIQUE)
    cfg = json.loads((report["app_dir"] / "config.json").read_text(encoding="utf-8"))
    assert cfg["product_name"] == "STEM Recall" or "Recall" in cfg["product_name"]
    assert "ar" in cfg["languages"]                        # Arabic requested in the brief
    assert any("التسارع" in i["back"] for i in cfg["seed_items"])  # bilingual seed card
    assert cfg["target_user"] == "university students"
    spec_test = (report["app_dir"] / "tests" / "test_spec.py").read_text(encoding="utf-8")
    assert "test_feature_sm_2_adaptive_scheduling" in spec_test


def test_broken_build_is_detected(monkeypatch):
    """If generated code is wrong, the real test run must report failures (Gate 3 cannot pass)."""
    original = builder.render

    def sabotaged(run_id, spec):
        d = original(run_id, spec)
        core = d / "core.py"
        core.write_text(core.read_text(encoding="utf-8").replace("interval = 1 if reps == 0", "interval = 2 if reps == 0"),
                        encoding="utf-8")
        return d

    monkeypatch.setattr(builder, "render", sabotaged)
    report = builder.run("t-broken", parse_brief(IDEAS["spaced_repetition"]), CANVAS, CRITIQUE)
    assert not report["tests"]["ok"] and report["tests"]["failed"] >= 1
