"""Amostra da estrutura de portais promissores (links de vaga, itens RSS)."""
import re, requests
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
H = {"User-Agent": UA, "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"}
out = []
def sample(name, url, rx):
    r = requests.get(url, headers=H, timeout=25)
    links = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r.text, re.S | re.I):
        href, txt = m.group(1), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        if re.search(rx, href, re.I):
            links.append(f"{href} | {txt[:70]}")
    out.append(f"## {name} ({r.status_code})\n" + "\n".join(dict.fromkeys(links).keys().__iter__().__class__ and list(dict.fromkeys(links))[:12]))
sample("Net-Empregos busca", "https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data+analyst&cidade=&categoria=0&zona=0&tipo=0", r"emprego|oferta|\d{5,}")
sample("Sapo Emprego", "https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa", r"offer|oferta")
sample("Teamlyzer", "https://pt.teamlyzer.com/companies/jobs?tags=data", r"job")
sample("Michael Page", "https://www.michaelpage.pt/jobs/lisboa?search=data", r"job")
sample("Expresso Emprego", "https://expressoemprego.pt/ofertas-emprego/lisboa?q=data+analyst", r"oferta|emprego")
r = requests.get("https://www.net-empregos.com/rssfeed.asp", headers=H, timeout=25)
items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
out.append(f"## Net-Empregos RSS: {len(items)} itens\n" + "\n---\n".join(i[:700] for i in items[:2]))
# página de uma vaga do Net-Empregos e do Sapo
for name, url, rx in [("NE vaga", "https://www.net-empregos.com/pesquisa-empregos.asp?chaves=data+analyst&cidade=&categoria=0&zona=0&tipo=0", r'href="(/\d{6,}/[^"]+)"'),
                      ("Sapo vaga", "https://emprego.sapo.pt/offers?pesquisa=data%20analyst&local=lisboa", r'href="(https://emprego\.sapo\.pt/offers/[^"?]+)"')]:
    m = re.search(rx, requests.get(url, headers=H, timeout=25).text)
    if m:
        u = m.group(1) if m.group(1).startswith("http") else "https://www.net-empregos.com" + m.group(1)
        t = requests.get(u, headers=H, timeout=25).text
        out.append(f"## {name} {u}\nJSON-LD JobPosting: {t.count('JobPosting')}\n" +
                   re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S))[:1500])
open("data/probe2.md", "w").write("\n\n".join(out))
