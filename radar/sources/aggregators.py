"""Agregadores com API JSON pública (testados a partir do GitHub Actions):
freehire.me, The Muse, Workable (busca global) e Himalayas (remoto aberto a Portugal)."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from ..classify import is_lisbon_area, title_is_relevant
from ..http import get
from ..models import Job, strip_html

log = logging.getLogger("radar")
JSON = {"Accept": "application/json"}


def _d(v) -> str | None:
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v if v < 10**11 else v / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    return str(v)[:10]


def _mode(v) -> str | None:
    v = str(v or "").lower()
    return {"remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial", "on_site": "Presencial"}.get(v)


def _keep(title: str, location: str) -> bool:
    return title_is_relevant(title) and is_lisbon_area(location)


# ---------------------------------------------------------------- freehire.me
def freehire(cfg: dict, stats: dict, days: int = 30) -> list[Job]:
    """Agregador open-source de ~50 ATS. O endpoint /agent devolve a descrição completa."""
    terms = cfg["search_terms"]
    jobs, errors = {}, []
    # a API aceita até 5 alternativas com OR por consulta
    for i in range(0, len(terms), 5):
        q = " OR ".join(terms[i:i + 5])
        for offset in (0, 50):
            r = get("https://freehire.me/api/v1/agent/jobs/search", headers=JSON, tries=2,
                    params={"q": q, "countries": "pt", "posted_within_days": days, "limit": 50, "offset": offset,
                            "description_format": "markdown"})
            if r is None:
                errors.append(f"{q[:30]}: sem resposta")
                break
            data = r.json().get("data") or []
            for j in data:
                loc = j.get("location") or ""
                if not _keep(j.get("title", ""), loc or "Portugal"):
                    continue
                url = (j.get("url") or "").split("?utm_source")[0]
                jobs[url] = Job("freehire", j["title"], j.get("company", ""), url, loc,
                                strip_html(j.get("description", "")), _d(j.get("posted_at") or j.get("created_at")),
                                remote=_mode(j.get("work_mode")))
            if len(data) < 50:
                break
            time.sleep(1)
    stats["freehire"] = {"brutas": len(jobs), "erros": errors[:3]}
    return list(jobs.values())


# ---------------------------------------------------------------- The Muse
def themuse(cfg: dict, stats: dict, pages: int = 5) -> list[Job]:
    jobs, errors = [], []
    for page in range(pages):
        r = get("https://www.themuse.com/api/public/jobs", headers=JSON, tries=2,
                params=[("location", "Lisbon, Portugal"), ("category", "Data and Analytics"),
                        ("category", "Data Science"), ("category", "Business Operations"),
                        ("level", "Entry Level"), ("level", "Mid Level"), ("page", page)])
        if r is None:
            errors.append(f"página {page}: sem resposta")
            break
        payload = r.json()
        for j in payload.get("results", []):
            loc = "; ".join(l.get("name", "") for l in j.get("locations") or [])
            if not _keep(j.get("name", ""), loc):
                continue
            jobs.append(Job("The Muse", j["name"], (j.get("company") or {}).get("name", ""),
                            (j.get("refs") or {}).get("landing_page", ""), loc, strip_html(j.get("contents", "")),
                            _d(j.get("publication_date"))))
        if page + 1 >= payload.get("page_count", 0):
            break
        time.sleep(1)
    stats["The Muse"] = {"brutas": len(jobs), "erros": errors[:3]}
    return jobs


# ---------------------------------------------------------------- Workable (busca global de vagas)
def workable_search(cfg: dict, stats: dict) -> list[Job]:
    jobs, errors = {}, []
    for term in cfg["search_terms"]:
        r = get("https://jobs.workable.com/api/v1/jobs", headers=JSON, tries=2,
                params={"query": term, "location": "Lisbon, Portugal"})
        if r is None:
            errors.append(f"{term}: sem resposta")
            continue
        for j in r.json().get("jobs", []):
            loc_obj = j.get("location") or {}
            loc = ", ".join(x for x in (loc_obj.get("city"), loc_obj.get("countryName")) if x) if isinstance(
                loc_obj, dict) else str(loc_obj)
            if not _keep(j.get("title", ""), loc):
                continue
            company = j.get("company") or {}
            company = company.get("title") or company.get("name", "") if isinstance(company, dict) else str(company)
            url = j.get("url") or f"https://jobs.workable.com/view/{j.get('id')}"
            mode = j.get("workplace") or ("remote" if j.get("remote") else None)
            jobs[url] = Job("Workable", j["title"], company, url, loc, strip_html(j.get("description", "")),
                            _d(j.get("created") or j.get("updated")), remote=_mode(mode))
        time.sleep(1)
    stats["Workable"] = {"brutas": len(jobs), "erros": errors[:3]}
    return list(jobs.values())


# ---------------------------------------------------------------- Himalayas (remoto que aceita Portugal)
def himalayas(cfg: dict, stats: dict) -> list[Job]:
    jobs, errors = {}, []
    for term in cfg["search_terms"]:
        r = get("https://himalayas.app/jobs/api/search", headers=JSON, tries=2,
                params={"q": term, "country": "Portugal"})
        if r is None:
            errors.append(f"{term}: sem resposta")
            continue
        for j in r.json().get("jobs", []):
            if not title_is_relevant(j.get("title", "")):
                continue
            url = j.get("applicationLink") or j.get("guid") or ""
            restr = ", ".join(j.get("locationRestrictions") or []) or "Remote"
            jobs[url] = Job("Himalayas", j["title"], j.get("companyName", ""), url, f"Remote ({restr})",
                            strip_html(j.get("description") or j.get("excerpt", "")), _d(j.get("pubDate")),
                            remote="Remoto")
        time.sleep(1)
    stats["Himalayas"] = {"brutas": len(jobs), "erros": errors[:3]}
    return list(jobs.values())
