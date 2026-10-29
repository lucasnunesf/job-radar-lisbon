"""LinkedIn, Indeed e Glassdoor via biblioteca python-jobspy."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime

from ..models import Job

log = logging.getLogger("radar")

SITE_LABEL = {"linkedin": "LinkedIn", "indeed": "Indeed", "glassdoor": "Glassdoor"}


def _loc(value) -> str:
    if isinstance(value, dict):
        parts = [value.get("city"), value.get("state")]
        country = value.get("country")
        country = getattr(country, "value", country)
        parts.append(str(country).title() if country else None)
        return ", ".join(p for p in parts if p)
    return str(value or "")


def _date(value) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    if value and str(value) not in ("NaT", "nan", "None"):
        return str(value)[:10]
    return None


def _remote(row) -> str | None:
    wfh = str(row.get("work_from_home_type") or "").lower()
    if "hybrid" in wfh or "híbrido" in wfh:
        return "Híbrido"
    if row.get("is_remote") is True or "remote" in wfh:
        return "Remoto"
    return None


def collect(cfg: dict, sites=("linkedin", "indeed", "glassdoor"), hours_old=72,
            per_term=25, stats: dict | None = None) -> list[Job]:
    from jobspy import scrape_jobs  # import tardio: só quando a fonte é usada

    jobs: list[Job] = []
    for site in sites:
        label = SITE_LABEL[site]
        got, errors = 0, []
        for term in cfg["search_terms"]:
            try:
                df = scrape_jobs(
                    site_name=[site],
                    search_term=term,
                    location=cfg.get("location", "Lisbon, Portugal"),
                    country_indeed="portugal",
                    results_wanted=per_term,
                    hours_old=hours_old,
                    fetch_description=True,
                    description_format="markdown",
                    verbose=0,
                )
            except Exception as e:  # uma fonte nunca derruba as outras
                errors.append(f"{term}: {e}")
                continue
            for site_err in (df.attrs.get("errors") or {}).values():
                errors.append(f"{term}: {site_err}")
            for row in df.to_dict("records"):
                if not row.get("title") or not row.get("job_url"):
                    continue
                jobs.append(Job(
                    source=label,
                    title=str(row["title"]).strip(),
                    company=str(row.get("company") or "").strip(),
                    url=str(row["job_url"]),
                    location=_loc(row.get("location")),
                    description=str(row.get("description") or ""),
                    posted=_date(row.get("date_posted")),
                    remote=_remote(row),
                ))
                got += 1
            time.sleep(3)  # pausa entre termos para reduzir bloqueio
        log.info("%s: %d vagas brutas", label, got)
        if stats is not None:
            stats[label] = {"brutas": got, "erros": errors[:3]}
    return jobs
