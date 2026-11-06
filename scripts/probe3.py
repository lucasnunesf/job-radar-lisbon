"""Probe 4: estrutura de Talent.com, Careerjet, Sapo, Net-Empregos, Expresso e detalhe do LinkedIn guest."""
import json, re, time
import requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"})
def p(*a): print(" ".join(str(x) for x in a)[:1500])
def hrefs(t): return sorted(set(re.findall(r'href="([^"]+)"', t)))

r = S.get("https://pt.talent.com/jobs?k=data+analyst&l=Lisboa", timeout=25)
p("TALENT scripts:", [m[:80] for m in re.findall(r'<script[^>]*id="([^"]+)"', r.text)], "NEXT" , "__NEXT_DATA__" in r.text)
i = r.text.find("534433791798609894"); p("TALENT ctx:", re.sub(r"\s+"," ", r.text[max(0,i-1500):i+300]))
d = S.get("https://pt.talent.com/view?id=534433791798609894", timeout=25)
for k in ("datePosted", "jobLocation", "hiringOrganization", "application/ld+json", "description"):
    j = d.text.find(k); p("TALENT detail", k, j, re.sub(r"\s+"," ", d.text[max(0,j-100):j+300]) if j>=0 else "")

for u in ["https://www.careerjet.pt/empregos?s=data+analyst&l=Lisboa", "https://www.careerjet.pt/procurar/empregos?s=data+analyst&l=Lisboa",
          "https://www.careerjet.pt/search/jobs?s=data+analyst&l=Lisboa", "https://www.careerjet.pt/data-analyst-empregos/lisboa-123.html",
          "https://www.careerjet.pt/"]:
    r = S.get(u, timeout=25); p("CAREERJET", r.status_code, u, len(r.text)//1024, [h for h in hrefs(r.text) if "s=" in h or "empregos" in h or "jobad" in h][:8])
    p("   forms:", re.findall(r'<form[^>]*action="([^"]+)"', r.text)[:3], re.findall(r'<input[^>]*name="([^"]+)"', r.text)[:8])

r = S.get("https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa", timeout=25)
p("SAPO hrefs:", [h for h in hrefs(r.text) if "offer" in h or "oferta" in h][:15])
for k in ("__NEXT_DATA__", "__NUXT__", "application/ld+json", "api/", "graphql"):
    j = r.text.find(k); p("SAPO", k, j, re.sub(r"\s+"," ", r.text[max(0,j-100):j+400]) if j>=0 else "")

r = S.get("https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data+analyst&cidade=&categoria=0&zona=0&tipo=0", timeout=25)
p("NETEMP hrefs:", [h for h in hrefs(r.text) if re.search(r"/\d{5,}/", h)][:10], "zona opts:", re.findall(r'<option value="(\d+)"[^>]*>\s*(Lisboa[^<]*)<', r.text)[:3])
rs = S.get("https://www.net-empregos.com/rssfeed.asp", timeout=25)
items = re.findall(r"<item>(.*?)</item>", rs.text, re.S); p("NETEMP RSS items:", len(items), re.sub(r"\s+"," ", items[0][:600]) if items else "")

r = S.get("https://expressoemprego.pt/ofertas-emprego/lisboa?q=data+analyst", timeout=25)
p("EXPRESSO scripts:", re.findall(r'<script[^>]*src="([^"]+)"', r.text)[:12])
p("EXPRESSO api refs:", sorted(set(re.findall(r'["\'](/?api[^"\']{0,80}|https?://[^"\']*api[^"\']{0,80})["\']', r.text)))[:10])

r = S.get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=data%20analyst&geoId=90010352&f_TPR=r604800&start=0", timeout=25)
ids = re.findall(r"urn:li:jobPosting:(\d+)", r.text); locs = re.findall(r'job-search-card__location">\s*([^<]+?)\s*<', r.text)
p("LI region:", r.status_code, len(ids), sorted(set(locs)))
r2 = S.get("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=data%20analyst&geoId=90010352&f_TPR=r604800&start=25", timeout=25)
p("LI region p2:", r2.status_code, len(re.findall(r"urn:li:jobPosting:(\d+)", r2.text)))
if ids:
    d = S.get(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{ids[0]}", timeout=25)
    for k in ("show-more-less-html__markup", "description__job-criteria-text", "topcard__flavor--bullet", "posted-time-ago__text", "topcard__org-name-link"):
        j = d.text.find(k); p("LI detail", k, re.sub(r"\s+"," ", d.text[j:j+250]) if j>=0 else "-")
    p("LI card sample:", re.sub(r"\s+"," ", r.text[:2500]))
