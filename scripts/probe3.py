"""Probe detalhado de portais novos: status, links de vaga achados e se a página da vaga tem JSON-LD."""
import json, re, sys, time
import requests
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"}
S = requests.Session(); S.headers.update(H)

PORTALS = {
  "Sapo": ("https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa", r"/offers/[^\"'#]+"),
  "Expresso": ("https://expressoemprego.pt/ofertas-emprego/lisboa?q=data+analyst", r"/(oferta|ofertas-emprego)/[^\"'#]+\d"),
  "Expresso2": ("https://expressoemprego.pt/ofertas?q=data+analyst&localidade=lisboa", r"/(oferta|ofertas-emprego)/[^\"'#]+\d"),
  "Talent": ("https://pt.talent.com/jobs?k=data+analyst&l=Lisboa", r"/view\?id=[^\"'&]+"),
  "Careerjet": ("https://www.careerjet.pt/pesquisar/empregos?s=data+analyst&l=Lisboa", r"/jobad/[^\"'#]+"),
  "Jobrapido": ("https://pt.jobrapido.com/?w=data+analyst&l=lisboa", r"jobrapido\.com/jobpreview/\d+"),
  "RobertWalters": ("https://www.robertwalters.pt/jobs.html?keywords=data", r"/jobs/[^\"'#]+\.html"),
  "Hays": ("https://www.hays.pt/en/job-search/data-jobs-in-lisboa", r"/(en/)?job-detail/[^\"'#]+"),
  "HaysPT": ("https://www.hays.pt/pesquisa-de-emprego?q=data&location=Lisboa", r"/(en/)?(job-detail|oferta)/[^\"'#]+"),
  "Randstad": ("https://www.randstad.pt/candidatos/ofertas-emprego/?q=data", r"/ofertas-emprego/[^\"'#]*/\d+"),
  "Adecco": ("https://www.adecco.pt/pesquisa-de-emprego/?k=data&l=Lisboa", r"/(oferta|job)[^\"'#]+"),
  "BEP": ("https://www.bep.gov.pt/pages/oferta/Oferta_Pesquisa.aspx", r"Oferta_Detalhe[^\"'#]+"),
  "Glassdoor": ("https://www.glassdoor.com/Job/lisbon-portugal-data-analyst-jobs-SRCH_IL.0,15_IC3261253_KO16,28.htm", r"/job-listing/[^\"'#]+"),
  "Jobs.pt": ("https://www.jobs.pt/pesquisa?q=data+analyst&l=lisboa", r"/(oferta|vaga|job)[^\"'#]+"),
  "Indeed jobs": ("https://pt.indeed.com/jobs?q=data+analyst&l=Lisboa", r"jk=[0-9a-f]+"),
  "NetEmpregos busca": ("https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data&cidade=&categoria=0&zona=11&tipo=0", r"/\d+/[^\"'#]+"),
}
out = []
def p(*a):
    s = " ".join(str(x) for x in a); out.append(s); print(s)

for name, (url, pat) in PORTALS.items():
    try:
        r = S.get(url, timeout=25)
        hrefs = sorted(set(m.group(0) for m in re.finditer(pat, r.text)))
        p(f"## {name}: HTTP {r.status_code} {len(r.text)//1024}KB, final={r.url[:100]}, links={len(hrefs)}, JobPosting={r.text.count('JobPosting')}")
        for h in hrefs[:4]: p("   ", h[:160])
        if r.status_code == 200 and hrefs and not hrefs[0].startswith("jk="):
            d = S.get(urljoin(r.url, hrefs[0].replace("&amp;", "&")), timeout=25)
            p(f"   detalhe HTTP {d.status_code} {len(d.text)//1024}KB JobPosting={d.text.count('JobPosting')} title={re.search(r'<title>(.*?)</title>', d.text, re.S).group(1).strip()[:90] if '<title>' in d.text else ''}")
        if r.status_code == 200 and not hrefs:
            p("   amostra:", re.sub(r"\s+", " ", r.text[:600]))
    except Exception as e:
        p(f"## {name}: erro {type(e).__name__} {e}"[:200])
    time.sleep(1)

# LinkedIn guest com distância e geoId
for label, q in [("geo distance25", "keywords=data%20analyst&location=Lisbon%2C%20Lisbon%2C%20Portugal&distance=25&f_TPR=r604800&start=0"),
                 ("geoId 105277534", "keywords=data%20analyst&geoId=105277534&distance=25&f_TPR=r604800&start=0"),
                 ("geoId 100364837", "keywords=data%20analyst&geoId=100364837&f_TPR=r604800&start=0")]:
    try:
        r = S.get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?" + q, timeout=25)
        locs = re.findall(r'job-search-card__location">\s*([^<]+?)\s*<', r.text)
        p(f"## LinkedIn {label}: HTTP {r.status_code} cards={r.text.count('base-card')} locs={sorted(set(locs))[:8]}")
    except Exception as e:
        p("## LinkedIn erro", e)
    time.sleep(2)
# LinkedIn: resolver geoId pela API de typeahead pública
try:
    r = S.get("https://www.linkedin.com/jobs-guest/api/typeaheadHits?origin=jserp&typeaheadType=GEO&geoTypes=POPULATED_PLACE,ADMIN_DIVISION_2,MARKET_AREA,COUNTRY_REGION&query=Lisbon", timeout=25)
    p("## LinkedIn typeahead:", r.status_code, r.text[:500])
except Exception as e:
    p("## typeahead erro", e)

# EURES API pública
try:
    body = {"resultsPerPage": 10, "page": 1, "sortSearch": "MOST_RECENT", "keywords": [{"keyword": "data analyst", "specificSearchCode": "EVERYWHERE"}],
            "publicationPeriod": None, "occupationUris": [], "skillUris": [], "requiredExperienceCodes": [], "positionScheduleCodes": [],
            "sectorCodes": [], "educationAndQualificationLevelCodes": [], "positionOfferingCodes": [], "locationCodes": ["pt17"], "euresFlagCodes": [],
            "otherBenefitsCodes": [], "requiredLanguages": [], "minNumberPost": None, "sessionId": "probe"}
    r = S.post("https://europa.eu/eures/eures-apps/searchengine/page/jv-search/search", json=body, timeout=30,
               headers={"Content-Type": "application/json", "Accept": "application/json"})
    p("## EURES:", r.status_code, r.text[:700])
except Exception as e:
    p("## EURES erro", e)

open("data/probe3.md", "w").write("\n".join(out))
