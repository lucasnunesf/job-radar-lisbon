"""Probe 6: Expresso Emprego (RSS e pesquisa) e endpoint AJAX do Sapo Emprego."""
import re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
S = requests.Session(); S.headers.update({"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"})
def p(*a): print(" ".join(str(x) for x in a)[:2500])
def sq(t): return re.sub(r"\s+", " ", t)
for u in ["https://expressoemprego.pt/rss", "https://expressoemprego.pt/emprego/pesquisa/data%20analyst/lisboa",
          "https://expressoemprego.pt/emprego/pesquisa/data%20analyst", "https://expressoemprego.pt/ofertas-emprego/informatica"]:
    try:
        r = S.get(u, timeout=15)
        links = sorted(set(re.findall(r'(?:href="|<link>)(https?://expressoemprego\.pt/[^"<]*\d{5,}[^"<]*|/[^"<]*\d{5,}[^"<]*)', r.text)))
        p("EXP", r.status_code, u, len(r.text)//1024, "links", len(links), links[:5], "items", r.text.count("<item>"))
        if r.text.count("<item>"): p("   item:", sq(r.text[r.text.find("<item>"):r.text.find("<item>")+900]))
        if links:
            d = S.get(links[0] if links[0].startswith("http") else "https://expressoemprego.pt" + links[0], timeout=15)
            p("   detalhe", d.status_code, "JobPosting" in d.text, sq(re.search(r"<title>(.*?)</title>", d.text, re.S).group(1))[:120] if "<title>" in d.text else "")
    except Exception as e:
        p("EXP erro", u, type(e).__name__)
try:
    js = S.get("https://emprego.sapo.pt/build/assets/app-offers-results-Bk6FlLw7.js", timeout=15).text
    for m in re.finditer(r"(url|endpoint|route|href)\s*[:=]\s*[\"'`]([^\"'`]{3,120})", js):
        p("SAPO js", m.group(1), m.group(2))
    for m in list(re.finditer(r"ajax|XMLHttpRequest|\$http|axios|fetch", js))[:6]:
        p("SAPO ctx", sq(js[max(0, m.start()-200):m.start()+300]))
except Exception as e:
    p("SAPO erro", e)
for u in ["https://emprego.sapo.pt/offers/ajax?pesquisa=data%20analyst&local=lisboa", "https://emprego.sapo.pt/api/offers?pesquisa=data%20analyst&local=lisboa",
          "https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa&ajax=1"]:
    try:
        r = S.get(u, timeout=15, headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"})
        p("SAPO try", r.status_code, u, r.headers.get("content-type"), sq(r.text[:300]))
    except Exception as e:
        p("SAPO try erro", u, type(e).__name__)
