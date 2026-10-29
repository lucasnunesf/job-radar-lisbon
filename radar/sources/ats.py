"""Páginas de carreira de empresas, via APIs públicas dos sistemas de recrutamento (ATS):
Greenhouse, Lever, Ashby, SmartRecruiters e Workable. Não precisam de chave.

Cada empresa em config/profile.yaml (ats_companies) é testada em todos os ATS; o que não
existir simplesmente não devolve nada. Só ficam vagas em Lisboa/remoto PT com título relevante.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from ..classify import is_lisbon_area, title_is_relevant
from ..http import get, session
from ..models import Job, norm, strip_html

log = logging.getLogger("radar")
SRC = "Site da empresa"


def _iso(ts) -> str | None:
    if ts is None or ts == "":
        return None
    if isinstance(ts, (int, float)):  # Lever: epoch em ms
        return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return str(ts)[:10]


def _ok(title: str, location: str) -> bool:
    return title_is_relevant(title) and is_lisbon_area(location) and location.strip() != ""


def greenhouse(slug: str) -> list[Job]:
    r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"}, tries=1)
    if r is None:
        return []
    out = []
    for j in r.json().get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        if _ok(j.get("title", ""), loc):
            out.append(Job(SRC, j["title"], slug, j.get("absolute_url", ""), loc,
                           strip_html(j.get("content", "")), _iso(j.get("first_published") or j.get("updated_at"))))
    return out


def lever(slug: str) -> list[Job]:
    r = get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, tries=1)
    if r is None:
        return []
    out = []
    data = r.json() if isinstance(r.json(), list) else []
    for j in data:
        cats = j.get("categories") or {}
        loc = cats.get("location") or ", ".join(cats.get("allLocations") or [])
        if _ok(j.get("text", ""), loc):
            desc = j.get("descriptionPlain", "") + "\n" + "\n".join(
                f"{l.get('text', '')}: {strip_html(l.get('content', ''))}" for l in j.get("lists") or [])
            out.append(Job(SRC, j["text"], slug, j.get("hostedUrl", ""), loc, desc, _iso(j.get("createdAt")),
                           remote="Remoto" if j.get("workplaceType") == "remote" else
                           "Híbrido" if j.get("workplaceType") == "hybrid" else None))
    return out


def ashby(slug: str) -> list[Job]:
    r = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", tries=1)
    if r is None:
        return []
    out = []
    for j in r.json().get("jobs", []):
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        loc = "; ".join(l for l in locs if l)
        if _ok(j.get("title", ""), loc):
            out.append(Job(SRC, j["title"], slug, j.get("jobUrl", ""), loc,
                           j.get("descriptionPlain") or strip_html(j.get("descriptionHtml", "")),
                           _iso(j.get("publishedAt")), remote="Remoto" if j.get("isRemote") else None))
    return out


def smartrecruiters(slug: str) -> list[Job]:
    r = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
            params={"country": "pt", "limit": 100}, tries=1)
    if r is None:
        return []
    out = []
    for j in r.json().get("content", []):
        l = j.get("location") or {}
        loc = ", ".join(x for x in (l.get("city"), l.get("country")) if x)
        if not _ok(j.get("name", ""), loc):
            continue
        d = get(j.get("ref", ""), tries=1)
        sections = ((d.json().get("jobAd") or {}).get("sections") or {}) if d is not None else {}
        desc = "\n".join(strip_html((s or {}).get("text", "")) for s in sections.values())
        company = (j.get("company") or {}).get("name") or slug
        out.append(Job(SRC, j["name"], company, f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                       loc, desc, _iso(j.get("releasedDate")), remote="Remoto" if l.get("remote") else None))
        time.sleep(0.3)
    return out


def workable(slug: str) -> list[Job]:
    r = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", params={"details": "true"}, tries=1)
    if r is None:
        return []
    data = r.json()
    company = data.get("name") or slug
    out = []
    for j in data.get("jobs", []):
        loc = ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        if _ok(j.get("title", ""), loc + (" remote" if j.get("telecommuting") else "")):
            out.append(Job(SRC, j["title"], company, j.get("url") or j.get("shortlink", ""), loc,
                           strip_html(j.get("description", "")), _iso(j.get("published_on") or j.get("created_at")),
                           remote="Remoto" if j.get("telecommuting") else None))
    return out


ATS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby,
       "smartrecruiters": smartrecruiters, "workable": workable}


def collect(cfg: dict, stats: dict) -> list[Job]:
    companies = cfg.get("ats_companies") or {}
    jobs, hits = [], []
    session.headers["Accept"] = "application/json"
    try:
        for name, slugs in companies.items():
            # slugs: lista de "ats:slug" (ex.: "greenhouse:talkdesk") ou só o slug (testa todos os ATS)
            for entry in (slugs if isinstance(slugs, list) else [slugs]):
                kinds = [entry.split(":", 1)[0]] if ":" in entry else list(ATS)
                slug = entry.split(":", 1)[-1]
                for kind in kinds:
                    try:
                        found = ATS[kind](slug)
                    except Exception as e:  # noqa: BLE001
                        log.debug("%s/%s: %s", kind, slug, e)
                        continue
                    for j in found:
                        if norm(j.company) == norm(slug):
                            j.company = name
                    if found:
                        hits.append(f"{name} ({kind}): {len(found)}")
                    jobs += found
                time.sleep(0.2)
    finally:
        session.headers.pop("Accept", None)
    log.info("ATS: %d vagas — %s", len(jobs), "; ".join(hits))
    stats["Sites de empresas"] = {"brutas": len(jobs), "erros": hits[:8] or ["nenhuma vaga de dados em Lisboa agora"]}
    return jobs
