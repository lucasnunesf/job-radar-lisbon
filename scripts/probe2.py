"""Testa APIs candidatas a novas fontes, a partir do GitHub Actions."""
import json, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "application/json, text/html;q=0.9", "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"}
out = []
def probe(name, url, method="GET", **kw):
    try:
        r = requests.request(method, url, headers={**H, **kw.pop("headers", {})}, timeout=30, **kw)
        body = r.text
        try:
            j = r.json(); body = json.dumps(j)[:900]
        except Exception:
            body = body[:400].replace("\n", " ")
        out.append(f"## {name}\nHTTP {r.status_code} · {len(r.text)//1024} KB\n{body}\n")
    except Exception as e:
        out.append(f"## {name}\nERRO {type(e).__name__}: {e}\n")
probe("freehire PT data", "https://freehire.me/api/v1/jobs/search?q=data%20analyst&countries=pt&limit=3&posted_within_days=30")
probe("freehire Lisbon", "https://freehire.me/api/v1/jobs/search?q=data&cities=Lisbon&limit=3")
probe("TheMuse Lisbon", "https://www.themuse.com/api/public/jobs?location=Lisbon%2C%20Portugal&category=Data%20and%20Analytics&page=0")
probe("Himalayas search", "https://himalayas.app/jobs/api/search?q=data%20analyst&country=Portugal&limit=3")
probe("Remotive data", "https://remotive.com/api/remote-jobs?category=data&limit=3")
probe("Arbeitnow", "https://www.arbeitnow.com/api/job-board-api?search=data%20analyst&location=Lisbon")
probe("Workable jobs search", "https://jobs.workable.com/api/v1/jobs?query=data%20analyst&location=Lisbon%2C%20Portugal")
probe("IEFP online", "https://iefponline.iefp.pt/IEFP/pesquisas/search.do?pesquisa=analista+de+dados&regiao=Lisboa")
probe("EURES search", "https://europa.eu/eures/eures-apps/searchengine/page/jv-search/search", method="POST",
      json={"resultsPerPage": 3, "page": 1, "sortSearch": "BEST_MATCH", "keywords": [{"keyword": "data analyst", "specificSearchCode": "EVERYWHERE"}],
            "publicationPeriod": "LAST_MONTH", "occupationUris": [], "skillUris": [], "requiredExperienceCodes": [],
            "positionScheduleCodes": [], "sectorCodes": [], "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [],
            "locationCodes": ["pt17"], "euresFlagCodes": [], "otherBenefitsCodes": [], "requiredLanguages": [],
            "minNumberPost": None, "sessionId": "radar"})
probe("Greenhouse sample (remotecom)", "https://boards-api.greenhouse.io/v1/boards/remotecom/jobs")
open("data/probe2.md", "w").write("\n".join(out))
