"""LinkedIn pela API pública de convidado (sem login), filtrando pela região "Lisboa e Região".

Por que não só o python-jobspy: ele busca por texto ("Lisbon, Portugal") + raio, e às vezes traz Porto
ou "Portugal" genérico. Aqui usamos o geoId da área metropolitana de Lisboa (90010352, achado com
jobs-guest/api/typeaheadHits) e só abrimos a página da vaga quando o título interessa e não é sênior,
o que economiza requisições e permite buscar mais termos sem ser bloqueado.

Ideia do ai-job-search (linkedin-search): endpoints jobs-guest + backoff em 429/5xx.
"""
from __future__ import annotations

import html
import logging
import random
import re
import time

from ..classify import SENIOR_TITLE, title_is_relevant
from ..http import session
from ..models import Job, norm, strip_html

log = logging.getLogger("radar")
SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
LISBON_REGION = "90010352"  # "Lisboa e Região"


def _get(url, params=None, tries=4):
    """GET com backoff exponencial em 429/5xx (LinkedIn limita convidados)."""
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=25)
        except Exception as e:  # noqa: BLE001
            log.warning("LinkedIn: %s", e)
            r = None
        if r is not None and r.status_code == 200:
            return r
        code = getattr(r, "status_code", "erro")
        if code in (400, 404):
            return None
        time.sleep(min(60, 4 * 2 ** attempt) + random.random() * 2)
    return None


def _txt(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).strip()


def parse_cards(page: str) -> list[dict]:
    cards = []
    for block in page.split("<li")[1:]:
        m = re.search(r"urn:li:jobPosting:(\d+)", block)
        if not m:
            continue
        title = re.search(r'base-search-card__title">(.*?)</h3>', block, re.S)
        company = re.search(r'base-search-card__subtitle">(.*?)</h4>', block, re.S)
        loc = re.search(r'job-search-card__location">(.*?)</span>', block, re.S)
        when = re.search(r'<time[^>]*datetime="([\d-]+)"', block)
        cards.append({"id": m.group(1),
                      "title": " ".join(_txt(title.group(1) if title else "").split()),
                      "company": " ".join(_txt(company.group(1) if company else "").split()),
                      "location": " ".join(_txt(loc.group(1) if loc else "").split()),
                      "posted": when.group(1) if when else None})
    return cards


def parse_detail(page: str) -> dict:
    desc = re.search(r'show-more-less-html__markup[^"]*">(.*?)</div>', page, re.S)
    crit = [(_txt(h), _txt(v)) for h, v in re.findall(
        r'description__job-criteria-subheader">(.*?)</h3>\s*<span[^>]*>(.*?)</span>', page, re.S)]
    loc = re.search(r'topcard__flavor--bullet">(.*?)</span>', page, re.S)
    return {"description": strip_html(desc.group(1)) if desc else "",
            "criteria": {" ".join(h.split()): " ".join(v.split()) for h, v in crit},
            "location": " ".join(_txt(loc.group(1)).split()) if loc else ""}


def collect(cfg: dict, stats: dict, hours_old: int = 72, pages: int = 4) -> list[Job]:
    geo = str((cfg.get("location_filter") or {}).get("linkedin_geo_id") or LISBON_REGION)
    seconds = max(86400, hours_old * 3600)
    cards: dict[str, dict] = {}
    errors, blocked = [], 0
    for term in cfg["search_terms"]:
        for page in range(pages):
            r = _get(SEARCH, {"keywords": term, "geoId": geo, "f_TPR": f"r{seconds}", "start": page * 10})
            if r is None:
                blocked += 1
                errors.append(f"{term} p{page}: bloqueado/sem resposta")
                break
            found = parse_cards(r.text)
            for c in found:
                cards.setdefault(c["id"], c)
            if len(found) < 10:
                break
            time.sleep(1.5 + random.random())
        time.sleep(2)

    wanted = [c for c in cards.values()
              if title_is_relevant(c["title"]) and not re.search(SENIOR_TITLE, norm(c["title"]))]
    jobs = []
    for c in wanted:
        d = _get(DETAIL.format(id=c["id"]), tries=3)
        info = parse_detail(d.text) if d is not None else {"description": "", "criteria": {}, "location": ""}
        level = next((v for k, v in info["criteria"].items() if re.search(r"senior|nivel|level", norm(k))), "")
        desc = info["description"]
        if level:
            desc = f"Nível de experiência (LinkedIn): {level}\n\n{desc}"
        jobs.append(Job(source="LinkedIn", title=c["title"], company=c["company"],
                        url=f"https://www.linkedin.com/jobs/view/{c['id']}",
                        location=info["location"] or c["location"], description=desc,
                        posted=c["posted"]))
        time.sleep(1 + random.random())
    log.info("LinkedIn (região Lisboa): %d cards, %d relevantes", len(cards), len(jobs))
    stats["LinkedIn"] = {"brutas": len(jobs), "cards": len(cards), "erros": errors[:3]}
    return jobs
