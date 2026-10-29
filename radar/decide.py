"""Vale a pena se candidatar agora? (fase de teste: nov–jan, início em 01/02/2027)

Testar agora   = vaga fácil (júnior/estágio, ≤1 lacuna) em empresa onde levar um "não" não custa nada
                 (consultorias e recrutadoras republicam a mesma vaga toda semana).
Esperar preparo = vaga boa mas difícil (pleno, 2+ lacunas) ou empresa de topo: guardar para quando
                 projeto, inglês e SQL/Python estiverem prontos (jan/fev), para não "queimar" a chance.
Não vale       = nota baixa, pede início imediato, exige outro idioma.
"""
from __future__ import annotations

import re

from .classify import LANG_RX, SOFT
from .models import Job, norm

IMMEDIATE = re.compile(
    r"inicio imediato|entrada imediata|disponibilidade imediata|integracao imediata|immediate (start|availability|joiner)"
    r"|start (asap|immediately)|available (to start )?immediately|join (asap|immediately)")


def _has(company: str, names: list[str]) -> bool:
    c = norm(company)
    return any(re.search(r"\b" + re.escape(norm(n)) + r"\b", c) for n in names)


def _needs_other_language(desc: str) -> bool:
    d = norm(desc)
    for rx in LANG_RX.values():
        m = re.search(rx, d)
        if m and not re.search(SOFT, d[max(0, m.start() - 70): m.end() + 70]):
            return True
    return False


def decide(job: Job, cfg: dict) -> Job:
    rules = cfg.get("apply_now", {})
    protect = rules.get("protect_companies", [])
    safe = cfg.get("consultancies", []) + rules.get("safe_companies", [])
    d = norm(job.description)

    if IMMEDIATE.search(d):
        job.apply, job.apply_why = "Não vale", "pede início imediato (você só chega em fevereiro)"
    elif _needs_other_language(job.description):
        job.apply, job.apply_why = "Não vale", "exige outro idioma"
    elif job.score < rules.get("min_score", 55):
        job.apply, job.apply_why = "Não vale", "pouco encaixe com o perfil"
    elif _has(job.company, protect):
        job.apply, job.apply_why = "Esperar preparo", "empresa de topo: guardar para quando estiver pronto"
    elif job.seniority == "Pleno" or len(job.gaps) >= 2:
        falta = f"faltam {', '.join(job.gaps)}" if len(job.gaps) >= 2 else "pede ~3 anos"
        job.apply, job.apply_why = "Esperar preparo", f"difícil agora ({falta})"
    else:
        why = [f"{job.seniority.lower()}" if job.seniority else "senioridade não informada",
               "nenhuma lacuna" if not job.gaps else f"só falta {job.gaps[0]}"]
        if _has(job.company, safe):
            why.append("consultoria que repete vagas: um 'não' agora não fecha a porta")
        if job.track in ("Data Analyst", "BI"):
            why.append("usa o que você já domina")
        else:
            why.append("bom para desenvolver o stack de engenharia")
        job.apply, job.apply_why = "Testar agora", "; ".join(why)
    return job


def decide_from_saved(ref: dict, cfg: dict) -> tuple[str, str]:
    """Mesma regra de decide(), usando só o que está gravado no Notion (sem a descrição)."""
    rules = cfg.get("apply_now", {})
    if ref.get("seniority") == "Estágio" or re.search(r"\b(intern|internship|estagi|trainee)", norm(ref.get("title"))):
        return "Não vale", "estágio (sem vínculo universitário)"
    if re.search(r"Francês|Alemão|Neerlandês|Italiano", ref.get("languages") or "") or \
            re.search(r"french|german|dutch|italian", norm(ref.get("title"))):
        return "Não vale", "exige outro idioma"
    if (ref.get("score") or 0) < rules.get("min_score", 55):
        return "Não vale", "pouco encaixe com o perfil"
    if _has(ref.get("company", ""), rules.get("protect_companies", [])):
        return "Esperar preparo", "empresa de topo: guardar para quando estiver pronto"
    gaps = ref.get("gaps") or []
    if ref.get("seniority") == "Pleno" or len(gaps) >= 2:
        return "Esperar preparo", f"difícil agora ({'faltam ' + ', '.join(gaps) if len(gaps) >= 2 else 'pede ~3 anos'})"
    job = Job("", ref.get("title", ""), ref.get("company", ""), "", score=ref.get("score") or 0)
    job.seniority, job.gaps, job.track = ref.get("seniority"), gaps, ref.get("track")
    return decide(job, cfg).apply, job.apply_why
