import json
from pathlib import Path

import yaml

from radar.classify import is_lisbon_area, seniority_of, track_of
from radar.main import dedupe
from radar.models import Job
from radar.score import score_job
from radar.sources.portals import _jobposting_from_html

ROOT = Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "config" / "profile.yaml").read_text(encoding="utf-8"))
FIX = [Job(**j) for j in json.loads((ROOT / "tests/fixtures/jobs.json").read_text(encoding="utf-8"))]


def by_url(fragment):
    return next(score_job(Job(**{**j.__dict__}), CFG) for j in FIX if fragment in j.url)


def test_tracks():
    assert track_of("Junior Data Analyst (Power BI)") == "Data Analyst"
    assert track_of("BI Developer") == "BI"
    assert track_of("Analytics Engineer") == "Analytics Engineer"
    assert track_of("Junior Data Engineer") == "Data Engineer"
    assert track_of("Data Scientist") is None
    assert track_of("Analista de Dados - Estágio") == "Data Analyst"


def test_seniority():
    assert seniority_of("Senior Data Engineer", "") == "Sênior"
    assert seniority_of("Data Analyst", "Requires 5+ years of experience in SQL") == "Sênior"
    assert seniority_of("Data Analyst", "2 years of experience") == "Júnior"
    assert seniority_of("Analista de Dados - Estágio", "") == "Estágio"
    assert seniority_of("BI Developer", "3+ years of professional experience") == "Pleno"


def test_location():
    assert is_lisbon_area("Lisbon, Lisbon, Portugal")
    assert is_lisbon_area("Porto Salvo")
    assert is_lisbon_area("Portugal")
    assert not is_lisbon_area("Porto, Portugal")
    assert not is_lisbon_area("Madrid, Spain")


def test_scores_order():
    dellent = by_url("itjobs.pt/oferta/1")
    bi4all = by_url("glassdoor")
    french = by_url("jobs/view/6")
    assert dellent.score >= 75, dellent.reasons
    assert bi4all.score >= 70
    assert french.score < dellent.score - 25
    assert "Power BI" in dellent.matched and "SQL" in dellent.matched
    assert by_url("indeed.com/viewjob?jk=4").excluded == "sênior"
    assert by_url("itjobs.pt/oferta/8").excluded


def test_r_language_detection():
    job = score_job(Job("x", "Data Analyst", "", "u", description="Excel, SQL, R or Python. R&D team."), CFG)
    assert "Python" in job.matched


def test_dedupe_across_portals():
    out = dedupe(FIX)
    dellent = [j for j in out if "Dellent" in j.company]
    assert len(dellent) == 1 and dellent[0].source == "ITJobs"


def test_jsonld_parser():
    html = """<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting",
    "title":"Data Analyst","datePosted":"2026-10-20","description":"<p>SQL e Power BI</p>",
    "hiringOrganization":{"@type":"Organization","name":"ACME"},
    "jobLocation":{"@type":"Place","address":{"addressLocality":"Lisboa","addressCountry":"PT"}}}</script></html>"""
    jp = _jobposting_from_html(html)
    assert jp["hiringOrganization"]["name"] == "ACME"
