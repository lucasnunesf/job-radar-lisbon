"""Testa quais portais respondem a partir do GitHub Actions (status, tamanho, JSON-LD, links de vaga)."""
import re
import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
URLS = {
    "Net-Empregos busca": "https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data+analyst&cidade=&categoria=0&zona=0&tipo=0",
    "Net-Empregos RSS": "https://www.net-empregos.com/rssfeed.asp",
    "Sapo Emprego": "https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa",
    "Expresso Emprego": "https://expressoemprego.pt/ofertas-emprego/lisboa?q=data+analyst",
    "Jooble HTML": "https://pt.jooble.org/emprego-data-analyst/Lisboa",
    "Talent.com": "https://pt.talent.com/jobs?k=data+analyst&l=Lisboa",
    "Careerjet": "https://www.careerjet.pt/empregos?s=data+analyst&l=Lisboa",
    "Teamlyzer": "https://pt.teamlyzer.com/companies/jobs?tags=data",
    "Welcome to the Jungle": "https://www.welcometothejungle.com/en/jobs?query=data%20analyst&refinementList%5Boffices.country_code%5D%5B%5D=PT",
    "Remotive API": "https://remotive.com/api/remote-jobs?category=data&limit=5",
    "Himalayas API": "https://himalayas.app/jobs/api?limit=5",
    "Arbeitnow API": "https://www.arbeitnow.com/api/job-board-api",
    "EURES": "https://europa.eu/eures/portal/jv-se/search?keywordsEverywhere=data%20analyst&location=pt&lang=pt",
    "Landing.jobs site": "https://landing.jobs/jobs?q=data+analyst",
    "Landing.jobs API": "https://landing.jobs/api/v1/jobs?limit=5",
    "Glassdoor PT": "https://www.glassdoor.pt/Emprego/lisboa-data-analyst-empregos-SRCH_IL.0,6_IC3261253_KO7,19.htm",
    "Built In": "https://builtin.com/jobs/eu/portugal/lisbon?search=data+analyst",
    "BeBee": "https://pt.bebee.com/empregos?term=data+analyst&location=Lisboa",
    "Indeed RSS": "https://pt.indeed.com/rss?q=data+analyst&l=Lisboa",
    "LinkedIn guest": "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=data%20analyst&location=Lisbon&start=0",
    "Michael Page": "https://www.michaelpage.pt/jobs/lisboa?search=data",
    "Hays": "https://www.hays.pt/pesquisa-de-emprego/data/lisboa",
    "Randstad": "https://www.randstad.pt/emprego/pesquisa/?query=data+analyst",
    "Adecco": "https://www.adecco.pt/pesquisa-de-emprego/?k=data",
}
lines = ["| Fonte | HTTP | KB | JSON-LD | links /job |", "|---|---|---|---|---|"]
for name, url in URLS.items():
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"}, timeout=25)
        t = r.text
        jl = t.count('"JobPosting"')
        links = len(set(re.findall(r'href="([^"]*(?:job|oferta|emprego|vaga|offer)[^"]*)"', t, re.I)))
        lines.append(f"| {name} | {r.status_code} | {len(t)//1024} | {jl} | {links} |")
    except Exception as e:
        lines.append(f"| {name} | erro {type(e).__name__} | | | |")
open("data/probe.md", "w").write("\n".join(lines))
print("\n".join(lines))
