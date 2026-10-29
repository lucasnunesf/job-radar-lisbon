import re, sys
sys.path.insert(0, ".")
from bs4 import BeautifulSoup
from radar.http import get
from radar.sources.portals import _main_text
out = []
for u in ["https://pt.teamlyzer.com/companies/dellent/job/data-analyst-21204",
          "https://pt.teamlyzer.com/companies/grupo-data-portugal/job/data-analyst-junior-21445"]:
    t = get(u).text
    m = _main_text(BeautifulSoup(t, "html.parser"))
    hits = [m[max(0, x.start()-120): x.end()+120].replace("\n", " ") for x in re.finditer(r"(?i)machine learning|\bml\b", m)]
    out.append(f"## {u}\nLEN {len(m)}\nHITS:\n" + "\n...\n".join(hits[:5]) + "\n\nINÍCIO:\n" + m[:1200])
open("data/probe2.md", "w").write("\n\n".join(out))
