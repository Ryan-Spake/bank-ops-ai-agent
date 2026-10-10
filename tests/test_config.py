"""Consistency checks on hand-maintained config: seeds and the eval question set."""

import csv

import pytest
import yaml
from conftest import ROOT

SEEDS = ROOT / "dbt" / "seeds"


def _rows(name):
    with (SEEDS / name).open(newline="") as f:
        return list(csv.DictReader(f))


def test_exactly_one_focal_bank():
    focal = [r["bank_id"] for r in _rows("bank_dim.csv") if r["is_focal"] == "true"]
    assert focal == ["jpm"]


@pytest.mark.parametrize("col", ["bank_id", "fdic_cert", "cfpb_company", "sec_cik"])
def test_bank_ids_unique(col):
    values = [r[col] for r in _rows("bank_dim.csv")]
    assert len(values) == len(set(values))


def test_sec_ciks_keep_leading_zeros():
    assert all(len(r["sec_cik"]) == 10 for r in _rows("bank_dim.csv"))


@pytest.fixture(scope="module")
def questions():
    return yaml.safe_load((ROOT / "evals" / "questions.yaml").read_text(encoding="utf-8"))


def test_question_ids_unique(questions):
    ids = [q["id"] for q in questions["questions"]]
    assert len(ids) == 10 and len(set(ids)) == 10


def test_questions_reference_known_tools_and_dimensions(questions):
    tools = set(questions["tool_registry"])
    dims = set(questions["scoring_dimensions"])
    for q in questions["questions"]:
        expected = q["expected_tools"]["required"] + q["expected_tools"]["optional"]
        assert set(expected) <= tools, q["id"]
        assert set(q["scoring"]) <= dims, q["id"]


def test_questions_reference_known_banks(questions):
    banks = {r["bank_id"] for r in _rows("bank_dim.csv")}
    assert questions["defaults"]["focal_bank"] in banks
    for q in questions["questions"]:
        assert set(q["entities"].get("banks", [])) <= banks, q["id"]
