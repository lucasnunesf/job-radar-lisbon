"""Probe 5: Careerjet /emprego, Net-Empregos busca, APIs internas de Sapo e Expresso, Talent detalhe."""
import re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"})
def p(*a): print(" ".join(str(x) for x in a)[:1800])
def sq(t): return re.sub(r"\s+", " ", t)
for u in ["https://www.careerjet.pt/emprego?s=data+analyst&l=Lisboa", "https://www.careerjet.pt/emprego?s=data+analyst&l=Lisboa&p=2"]:
    r = S.get(u, timeout=25); jobs = sorted(set(re.findall(r'/jobad/pt[0-9a-f]+', r.text)))
    p("CJ", r.status_code, len(jobs), r.url)
    i = r.text.find(jobs[0]) if jobs else -1
    if i >= 0: p("   ctx:", sq(r.text[i-200:i+1500]))
if jobs:
    d = S.get("https://www.careerjet.pt" + jobs[0], timeout=25); p("CJ detail", d.status_code, d.url[:120], "JobPosting" in d.text, sq(d.text[d.text.find("<h1"):d.text.find("<h1")+800]))
r = S.get("https://www.net-empregos.com/", timeout=25)
p("NE forms:", re.findall(r'<form[^>]*>', r.text)[:4], re.findall(r'<(?:input|select)[^>]*name="([^"]+)"', r.text)[:12])
p("NE zonas:", re.findall(r'<option[^>]*value="([^"]*)"[^>]*>\s*([^<]{3,25})<', r.text)[:40])
for u in ["https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data&cidade=&categoria=0&zona=0&tipo=0",
          "https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data+analyst"]:
    r = S.get(u, timeout=25); p("NE", r.status_code, len(r.text)//1024, sorted(set(re.findall(r'href="(/\d{6,}/[^"]+)"', r.text)))[:5], sq(r.text[r.text.find("<body"):r.text.find("<body")+600]))
r = S.get("https://emprego.sapo.pt/build/assets/app-offers-results-Bk6FlLw7.js", timeout=25)
p("SAPO js", r.status_code, len(r.text)//1024, sorted(set(re.findall(r'["\'`](/?(?:api|offers|ajax)[^"\'`\s]{0,80})["\'`]', r.text)))[:25])
p("SAPO fetch ctx:", [sq(r.text[m.start()-150:m.start()+250]) for m in re.finditer(r"fetch\(|axios|\.get\(", r.text)][:3])
pg = S.get("https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa", timeout=25).text
p("SAPO data attrs:", sorted(set(re.findall(r'data-[a-z-]+="[^"]{0,60}"', pg)))[:30])
r = S.get("https://expressoemprego.pt/js/main?v=0Zw6mTQlhzWn8G99CyR5UPPFUG6Cm_3Boi1BdWRfXzs1", timeout=25)
p("EXP js urls:", sorted(set(re.findall(r'["\'](/[A-Za-z][^"\'\s]{3,80})["\']', r.text)))[:40])
pg = S.get("https://expressoemprego.pt/ofertas-emprego/lisboa?q=data+analyst", timeout=25).text
p("EXP forms:", re.findall(r'<form[^>]*>', pg)[:4], "hrefs:", sorted(set(re.findall(r'href="(/[^"]+)"', pg)))[:40])
