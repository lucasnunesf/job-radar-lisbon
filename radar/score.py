"""Score de match vaga × perfil (0 a 100).

Composição (máx. ~100):
  Trilha ............ 25  (Data Analyst / BI / Analytics Engineer = 25, Data Engineer júnior = 15)
  Ferramentas ....... 35  (peso das ferramentas que o Lucas tem ÷ peso de todas as citadas)
  Senioridade ....... 20  (Júnior 20, Estágio 18, não informado 12, Pleno 6; Sênior é excluída)
  Idioma ............. 5  (perde pontos se pede francês/alemão/etc.)
  Relocação/visto ... ±6
  Consultoria MS .... +6  (consultoria Microsoft/Azure da lista que pede stack Microsoft)
  Stack Microsoft ... +3  (Power BI, Azure ou Fabric na vaga)
"""
from __future__ import annotations

import re

from .classify import languages_of, relocation_of, seniority_of, track_of
from .models import Job, norm

# Sinônimos/regex por ferramenta (nome igual ao do profile.yaml)
SKILL_RX = {
    "SQL": r"\bsql\b|t-sql|tsql|pl/sql|plsql|sql server|mysql|postgres",
    "Python": r"\bpython\b|\bpandas\b",
    "Power BI": r"power ?bi|powerbi|\bpbi\b",
    "DAX": r"\bdax\b",
    "Power Query": r"power ?query|\bm language\b",
    "Azure": r"\bazure\b",
    "Databricks": r"databricks",
    "Delta Lake": r"delta lake|\bdelta tables?\b",
    "dbt": r"\bdbt\b",
    "Airflow": r"airflow",
    "PySpark": r"pyspark",
    "Spark": r"\bspark\b",
    "PostgreSQL": r"postgres",
    "Docker": r"docker",
    "Git": r"\bgit\b|github|gitlab|azure devops",
    "Excel": r"\bexcel\b",
    "VBA": r"\bvba\b",
    "SAP": r"\bsap\b",
    "ETL": r"\betl\b|\belt\b",
    "Data Factory": r"data factory|\badf\b",
    "Synapse": r"synapse",
    "Fabric": r"microsoft fabric|\bfabric\b",
    "Data Modeling": r"data model(l)?ing|dimensional model|star schema|kimball|modelacao de dados|modelagem de dados",
    "AWS": r"\baws\b|amazon web services|\bs3\b|\bglue\b",
    "GCP": r"\bgcp\b|google cloud",
    "BigQuery": r"bigquery",
    "Snowflake": r"snowflake",
    "Tableau": r"tableau",
    "Looker": r"looker",
    "Qlik": r"qlik",
    "SAS": r"\bsas\b",
    "Scala": r"\bscala\b",
    "Kafka": r"kafka",
    "Terraform": r"terraform",
    "Kubernetes": r"kubernetes|\bk8s\b",
    "Java": r"\bjava\b",
    "Redshift": r"redshift",
    "MicroStrategy": r"microstrategy",
    "Alteryx": r"alteryx",
    "Machine Learning": r"machine learning|\bml\b",
}
# R é caso especial: precisa de maiúscula e não pode ser "R&D"
R_RX = re.compile(r"(?<![\w&/-])R(?![\w&+#/-])(?=\s*(,|/|\bor\b|\bou\b|\band\b|\be\b|\)|\.|\s+programming|\s+language))")

TRACK_POINTS = {"Analytics Engineer": 25, "BI": 25, "Data Analyst": 25, "Data Engineer": 15}
SENIORITY_POINTS = {"Júnior": 20, "Estágio": 18, None: 12, "Pleno": 6}


def _mentions(text_norm: str, raw: str, name: str) -> bool:
    if name == "R":
        return bool(R_RX.search(raw))
    rx = SKILL_RX.get(name, r"\b" + re.escape(norm(name)) + r"\b")
    return bool(re.search(rx, text_norm))


def score_job(job: Job, cfg: dict) -> Job:
    text_raw = f"{job.title}\n{job.description}"
    text = norm(text_raw)

    job.track = track_of(job.title)
    if job.track is None:
        job.excluded = "fora das trilhas-alvo"
        return job

    job.seniority = seniority_of(job.title, job.description)
    if job.seniority == "Sênior":
        job.excluded = "sênior"
        return job

    # Ferramentas
    have = cfg["skills"]
    lack = cfg["gaps_vocab"]
    job.matched = [s for s in have if _mentions(text, text_raw, s)]
    job.gaps = [s for s in lack if _mentions(text, text_raw, s)]
    # Spark/PySpark contam uma vez só
    if "PySpark" in job.matched and "Spark" in job.matched:
        job.matched.remove("Spark")
    w_have = sum(have[s] for s in job.matched)
    w_lack = sum(lack[s] for s in job.gaps)
    ratio = w_have / (w_have + w_lack) if (w_have + w_lack) else 0.5
    # vaga que cita poucas ferramentas não deve ganhar nota cheia só por 1 acerto
    depth = min(1.0, w_have / 8)
    skill_pts = 35 * (0.7 * ratio + 0.3 * depth)

    langs, lang_penalty = languages_of(job.description)
    job.languages = langs
    reloc = relocation_of(job.description, job.extra_flags)

    company = norm(job.company)
    is_consultancy = any(re.search(r"\b" + re.escape(norm(c)) + r"\b", company) for c in cfg["consultancies"])
    ms_stack = any(s in job.matched for s in ("Power BI", "Azure", "Fabric", "Data Factory", "Synapse"))

    pts = TRACK_POINTS[job.track] + skill_pts + SENIORITY_POINTS.get(job.seniority, 12)
    pts += 5 - lang_penalty
    pts += 6 * reloc
    if is_consultancy:
        pts += 6 if ms_stack else 3
    if ms_stack:
        pts += 3

    job.score = max(0, min(100, round(pts)))
    job.reasons = [
        f"trilha {job.track}",
        f"{len(job.matched)} ferramentas que tenho / {len(job.gaps)} lacunas",
        f"senioridade {job.seniority or 'não informada'}",
    ]
    if reloc == 1:
        job.reasons.append("cita relocação/visto")
    if reloc == -1:
        job.reasons.append("exige autorização de trabalho na UE")
    if is_consultancy:
        job.reasons.append("consultoria da lista")
    if lang_penalty:
        job.reasons.append("pede outro idioma")
    job.extra_flags["relocation_signal"] = reloc
    job.extra_flags["consultancy"] = is_consultancy
    return job
