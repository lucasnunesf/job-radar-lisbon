"""Filtro 2: casos reais que a triagem manual de 09/11/2026 descartou e o radar tinha deixado como 'Testar agora'."""
from pathlib import Path
from types import SimpleNamespace

import yaml

from radar import review
from radar.classify import location_verdict, track_of
from radar.decide import decide
from radar.models import Job
from radar.score import score_job

CFG = yaml.safe_load((Path(__file__).resolve().parent.parent / "config" / "profile.yaml").read_text(encoding="utf-8"))
BASE = ("We are looking for a Data Analyst to join our team in Lisbon. You will build dashboards in Power BI, "
        "write SQL queries and Python scripts, and work with business stakeholders on KPIs. ")


def run(title, desc=BASE, company="Some Consulting", loc="Lisboa, Portugal"):
    j = Job("LinkedIn", title, company, f"https://x.pt/{abs(hash(title + desc))}", loc, desc)
    score_job(j, CFG)
    if not j.excluded:
        decide(j, CFG)
    return j


def test_cargos_que_nao_sao_dados():
    for t in ("Team Leader - CRM Operations, Governance & Reporting", "Online Data Analyst - Portuguese (PT)",
              "Junior Financial Consultant (Regulatory Reporting)", "Operations Advisor - Derivatives Trade Reporting",
              "Data Coordinator (Reporting & Governance)"):
        assert track_of(t) is None, t


def test_senioridade_escondida():
    assert run("Data Engineer III").excluded == "sênior"
    assert run("Data Analyst", BASE + "Mid level profile with 2 years of SQL and more than 6 years of experience in data.").excluded == "sênior"
    assert run("Data Engineer II").seniority == "Pleno"


def test_local_no_titulo():
    assert location_verdict("Portugal", title="Business Intelligence Support (m/f) - Hybrid (Brussels)")[0] == "fora"
    assert location_verdict("Portugal", title="Data Analyst - Remote USA")[0] == "fora"
    assert location_verdict("Lisboa", title="Data Analyst")[0] == "lisboa"


def test_ferramenta_base_que_nao_tem():
    j = run("Snowflake Data Engineer", BASE + "Strong hands-on experience with Snowflake. Snowflake data modelling. Azure Data Factory.")
    assert j.apply == "Esperar preparo" and "Snowflake" in j.apply_why
    j = run("ETL Developer", BASE + "IBM DataStage PX is mandatory. Experience with DataStage jobs.")
    assert j.apply == "Não vale" and "DataStage" in j.apply_why
    j = run("SAS / Data Engineer", BASE + "Hands-on SAS experience is essential.")
    assert j.apply == "Não vale"


def test_x_ou_y_nao_barra():
    j = run("Data Analyst", BASE + "Experience with Power BI or Tableau is required.")
    assert j.apply == "Testar agora", j.apply_why
    j = run("Data Analyst", BASE + "Tableau is a plus.")
    assert j.apply == "Testar agora", j.apply_why


def test_ingles_c1():
    j = run("Data Analyst", BASE + "English level C1 is required.")
    assert j.apply == "Esperar preparo" and "C1" in j.apply_why
    assert run("Data Analyst", BASE + "Fluent English.").apply == "Testar agora"


def _jobs_iguais():
    txt = BASE * 3 + "Our client in the banking sector needs Power BI dashboards for regulatory reports. " * 4
    a = Job("LinkedIn", "Microsoft Fabric / Power BI Developer", "Match Profiler", "https://a/1", "Lisboa", txt)
    b = Job("LinkedIn", "Microsoft Fabric / Power BI Developer", "Decskill", "https://b/2", "Lisboa", txt + " Apply now.")
    for j in (a, b):
        j.apply, j.apply_why = "Testar agora", "ok"
    return a, b


def test_mesma_vaga_em_consultorias(tmp_path):
    a, b = _jobs_iguais()
    review.mark_duplicates([a], tmp_path / "fp.json", {})
    review.mark_duplicates([b], tmp_path / "fp.json", {})
    assert "Match Profiler" in b.apply_why and not b.excluded
    # se a primeira já foi candidatada, a segunda sai
    a, b = _jobs_iguais()
    review.mark_duplicates([a], tmp_path / "fp2.json", {})
    review.mark_duplicates([b], tmp_path / "fp2.json", {"https://a/1": {"inscrito": True}})
    assert b.excluded and "Match Profiler" in b.excluded


def test_empresa_com_muitas_candidaturas():
    flags = {f"u{i}": {"id": str(i), "inscrito": True, "company": c}
             for i, c in enumerate(["Egor", "Grupo Egor", "Egor Portugal"])}
    j = Job("ITJobs", "Data Engineer", "Grupo Egor", "https://e/1")
    j.apply = "Testar agora"
    review.apply_company_load([j], flags, 3)
    assert j.apply == "Esperar preparo"


def test_link_morto(monkeypatch):
    def fake(url, **kw):
        if "whatjobs" in url:
            return SimpleNamespace(status_code=200, url="https://pt.whatjobs.com/jobs?q=data", history=[1], text="")
        if "closed" in url:
            return SimpleNamespace(status_code=200, url=url, history=[], text="This job is no longer accepting applications")
        return SimpleNamespace(status_code=200, url=url, history=[], text="Apply now")
    monkeypatch.setattr(review.requests, "get", fake)
    assert review.link_status("https://pt.whatjobs.com/job/Data-Engineer/lisboa/123456")[0] is True
    assert review.link_status("https://jobs.lever.co/x/closed")[0] is True
    assert review.link_status("https://jobs.lever.co/x/open")[0] is False
    assert review.link_status("https://www.linkedin.com/jobs/view/1")[0] is None  # LinkedIn nunca é checado


def test_whatjobs_fora():
    from radar.main import _blacklisted
    j = Job("freehire", "Data Engineer", "X", "https://pt.whatjobs.com/job/Data-Engineer/lisboa/1")
    assert _blacklisted(j, CFG)
