"""Portais portugueses e europeus: ITJobs, Landing.jobs, Built In, Net-Empregos.

Estratégia para portais em HTML: pegar a lista de links de vagas da página de busca,
filtrar pelo título e abrir só as vagas relevantes, lendo o bloco schema.org JobPosting
(JSON-LD) que quase todos os portais publicam para o Google. Assim o parser não depende
do layout visual de cada site.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..classify import is_lisbon_area, title_is_relevant
from ..http import get, session
from ..models import Job, norm, strip_html

log = logging.getLogger("radar")

def _is_lisbon_area(text: str) -> bool:
    return is_lisbon_area(text)


# ---------------------------------------------------------------- JSON-LD genérico
def _jobposting_from_html(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if item.get("@type") == "JobPosting":
                    return item
                stack.extend(item.get("@graph", []) if isinstance(item.get("@graph"), list) else [])
    return None


def _job_from_detail(source: str, url: str, fallback_title: str) -> Job | None:
    r = get(url)
    if r is None:
        return None
    jp = _jobposting_from_html(r.text) or {}
    soup = BeautifulSoup(r.text, "html.parser")

    org = jp.get("hiringOrganization") or {}
    company = org.get("name", "") if isinstance(org, dict) else str(org)

    locs = jp.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    places = []
    for loc in locs:
        addr = (loc or {}).get("address", {}) if isinstance(loc, dict) else {}
        if isinstance(addr, dict):
            country = addr.get("addressCountry")
            country = country.get("name") if isinstance(country, dict) else country
            places.append(", ".join(x for x in (addr.get("addressLocality"), country) if isinstance(x, str) and x))
    remote = "Remoto" if jp.get("jobLocationType") == "TELECOMMUTE" else None

    description = strip_html(jp.get("description"))
    if not description:  # sem JSON-LD: usa o texto principal da página
        main = soup.find("main") or soup.body
        description = main.get_text(" ", strip=True)[:15000] if main else ""

    title = jp.get("title") or fallback_title
    return Job(source=source, title=strip_html(title), company=strip_html(company), url=url,
               location="; ".join(p for p in places if p), description=description,
               posted=(jp.get("datePosted") or "")[:10] or None, remote=remote)


def _collect_links(search_urls: list[str], pattern: str, base: str, max_pages_per_term=2) -> dict[str, str]:
    """Devolve {url_da_vaga: título} a partir das páginas de busca."""
    rx = re.compile(pattern)
    found: dict[str, str] = {}
    for url in search_urls:
        r = get(url)
        if r is None:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].split("?")[0].split("#")[0]
            if not rx.search(href):
                continue
            full = urljoin(base, href)
            title = a.get_text(" ", strip=True) or a.get("title", "")
            if len(title) > len(found.get(full, "")):
                found[full] = title
        time.sleep(1.5)
    return found


def _html_portal(source, search_urls, pattern, base, max_details, stats) -> list[Job]:
    links = _collect_links(search_urls, pattern, base)
    # título vazio (link de imagem/logo) ainda pode ser vaga: deixa passar
    candidates = [(u, t) for u, t in links.items() if not t or title_is_relevant(t)]
    jobs = []
    for url, title in candidates[:max_details]:
        job = _job_from_detail(source, url, title)
        if job and title_is_relevant(job.title) and _is_lisbon_area(job.location + " " + job.description[:3000]):
            jobs.append(job)
        time.sleep(1.2)
    log.info("%s: %d links, %d relevantes", source, len(links), len(jobs))
    stats[source] = {"brutas": len(jobs), "links": len(links), "erros": [] if links else ["nenhum link encontrado"]}
    return jobs


# ---------------------------------------------------------------- ITJobs
ITJOBS_WORK_MODEL = {0: "Presencial", 1: "Remoto", 2: "Híbrido"}


def itjobs(cfg, stats) -> list[Job]:
    key = os.getenv("ITJOBS_API_KEY")
    if not key:
        urls = [f"https://www.itjobs.pt/emprego?q={t.replace(' ', '+')}&location=14" for t in cfg["search_terms"]]
        return _html_portal("ITJobs", urls, r"/oferta/\d+/", "https://www.itjobs.pt", 60, stats)

    jobs, errors = {}, []
    for term in cfg["search_terms"]:
        r = get("https://api.itjobs.pt/job/search.json",
                params={"api_key": key, "q": term, "limit": 100})
        if r is None:
            errors.append(f"{term}: sem resposta")
            continue
        payload = r.json()
        if "error" in payload:
            errors.append(f"{term}: {payload['error'].get('message')}")
            continue
        for it in payload.get("results", []):
            locs = it.get("locations") or []
            loc_names = ", ".join(l.get("name", "") for l in locs)
            wm = ITJOBS_WORK_MODEL.get(it.get("workModel"))
            if not (any(str(l.get("id")) == "14" for l in locs) or wm == "Remoto" or not locs):
                continue
            url = f"https://www.itjobs.pt/oferta/{it['id']}/{it.get('slug', '')}"
            jobs[url] = Job(source="ITJobs", title=it.get("title", ""),
                            company=(it.get("company") or {}).get("name", ""), url=url,
                            location=loc_names, description=strip_html(it.get("body")),
                            posted=(it.get("publishedAt") or "")[:10] or None, remote=wm)
        time.sleep(1)
    out = [j for j in jobs.values() if title_is_relevant(j.title)]
    stats["ITJobs"] = {"brutas": len(out), "erros": errors[:3]}
    return out


# ---------------------------------------------------------------- Landing.jobs
def landingjobs(cfg, stats, pages=12) -> list[Job]:
    jobs, companies, errors = [], {}, []
    for page in range(pages):
        r = get("https://landing.jobs/api/v1/jobs", params={"limit": 50, "offset": page * 50},
                headers={"Accept": "application/json"})
        if r is None:
            from ..http import last_status
            errors.append(f"página {page}: HTTP {last_status.get('code')}")
            break
        try:
            items = r.json()
        except ValueError:
            errors.append("resposta não é JSON")
            break
        items = items.get("jobs", items) if isinstance(items, dict) else items
        if not items:
            break
        for it in items:
            title = it.get("title", "")
            if not title_is_relevant(title):
                continue
            locs = it.get("locations") or []
            city = it.get("city") or ", ".join(
                filter(None, ((l.get("city") or "") for l in locs if isinstance(l, dict))))
            remote = "Remoto" if it.get("remote") else None
            if not (_is_lisbon_area(city) or remote):
                continue
            cid = it.get("company_id")
            if cid and cid not in companies:
                cr = get(f"https://landing.jobs/api/v1/companies/{cid}")
                companies[cid] = (cr.json().get("name", "") if cr is not None else "")
            desc = "\n".join(strip_html(it.get(k)) for k in
                             ("role_description", "main_requirements", "nice_to_have", "perks") if it.get(k))
            tags = it.get("tags") or []
            if tags:
                desc += "\nTags: " + ", ".join(t if isinstance(t, str) else t.get("name", "") for t in tags)
            jobs.append(Job(source="Landing.jobs", title=title, company=companies.get(cid, ""),
                            url=it.get("url") or f"https://landing.jobs/at/{cid}/{it.get('id')}",
                            location=city, description=desc,
                            posted=(it.get("published_at") or "")[:10] or None, remote=remote,
                            extra_flags={"relocation": bool(it.get("relocation_paid") or it.get("visa_support"))}))
        time.sleep(1)
    stats["Landing.jobs"] = {"brutas": len(jobs), "erros": errors[:3]}
    return jobs


# ---------------------------------------------------------------- Built In
def builtin(cfg, stats) -> list[Job]:
    urls = [f"https://builtin.com/jobs/eu/portugal/lisbon?search={t.replace(' ', '+')}" for t in cfg["search_terms"]]
    return _html_portal("Built In", urls, r"^/job/[^/]+/\d+", "https://builtin.com", 50, stats)


# ---------------------------------------------------------------- Net-Empregos
def netempregos(cfg, stats) -> list[Job]:
    urls = [f"https://www.net-empregos.com/pesquisa-empregos.asp?chaves={t.replace(' ', '+')}&cidade=&categoria=0&zona=0&tipo=0"
            for t in cfg["search_terms"]]
    return _html_portal("Net-Empregos", urls, r"^/?\d{5,}/[^/]+/?$", "https://www.net-empregos.com", 40, stats)


# ---------------------------------------------------------------- Jooble (API, precisa de JOOBLE_API_KEY)
def jooble(cfg, stats) -> list[Job]:
    key = os.getenv("JOOBLE_API_KEY")
    if not key:
        stats["Jooble"] = {"brutas": 0, "erros": ["sem JOOBLE_API_KEY (pedir em jooble.org/api/about)"]}
        return []
    jobs, errors = {}, []
    for term in cfg["search_terms"]:
        r = session.post(f"https://jooble.org/api/{key}", json={"keywords": term, "location": "Lisboa", "page": 1},
                         timeout=25)
        if r.status_code != 200:
            errors.append(f"{term}: HTTP {r.status_code}")
            continue
        for it in r.json().get("jobs", []):
            if not title_is_relevant(it.get("title", "")) or not is_lisbon_area(it.get("location", "")):
                continue
            jobs[it["link"]] = Job("Jooble", strip_html(it["title"]), it.get("company", ""), it["link"],
                                   it.get("location", ""), strip_html(it.get("snippet", "")),
                                   (it.get("updated") or "")[:10] or None)
        time.sleep(1)
    stats["Jooble"] = {"brutas": len(jobs), "erros": errors[:3]}
    return list(jobs.values())
