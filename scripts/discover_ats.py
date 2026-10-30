"""Descobre quais empresas (entre ~3.300 boards do Greenhouse e ~40 do Lever) têm vagas em Portugal.

Lista de candidatas: config/ats_candidates.json (tokens públicos reunidos pelo projeto open-source
Cla-Code-Community/candidate). Resultado: config/ats_found.json, usado na coleta diária.
Roda 1x por semana no GitHub Actions (workflow "Descobrir empresas").
"""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PT = re.compile(r"portugal|lisbon|lisboa|oeiras|porto salvo|almada|sintra|cascais|amadora|\bpt\b", re.I)
S = requests.Session()
S.headers["User-Agent"] = "job-radar-lisbon (uso pessoal)"


def greenhouse(token):
    try:
        r = S.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs", timeout=20)
        if r.status_code != 200:
            return None
        jobs = r.json().get("jobs", [])
        n = sum(1 for j in jobs if PT.search((j.get("location") or {}).get("name", "")))
        return (token, n) if n else None
    except Exception:
        return None


def lever(site, region):
    host = "api.eu.lever.co" if region == "eu" else "api.lever.co"
    try:
        r = S.get(f"https://{host}/v0/postings/{site}?mode=json", timeout=20)
        if r.status_code != 200:
            return None
        n = sum(1 for j in r.json() if PT.search(json.dumps(j.get("categories") or {})))
        return (site, region, n) if n else None
    except Exception:
        return None


def main():
    cand = json.loads((ROOT / "config" / "ats_candidates.json").read_text())
    with ThreadPoolExecutor(16) as ex:
        gh = [x for x in ex.map(greenhouse, cand["greenhouse"]) if x]
        lv = [x for x in ex.map(lambda t: lever(*t), cand["lever"]) if x]
    out = {"greenhouse": sorted(t for t, _ in gh), "lever": sorted([s, r] for s, r, _ in lv),
           "_detalhe": {"greenhouse": dict(gh), "lever": {s: n for s, _, n in lv}}}
    (ROOT / "config" / "ats_found.json").write_text(json.dumps(out, indent=1))
    print(f"Greenhouse com vagas em PT: {len(gh)} | Lever: {len(lv)}")


if __name__ == "__main__":
    main()
