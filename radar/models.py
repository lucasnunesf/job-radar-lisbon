from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def norm(text: str | None) -> str:
    """Minúsculas, sem acentos, espaços normalizados."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<(br|/p|/li|/div)[^>]*>", "\n", str(text), flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'"))
    return re.sub(r"[ \t]+", " ", text).strip()


@dataclass
class Job:
    source: str            # LinkedIn, Indeed, Glassdoor, ITJobs, Landing.jobs, Built In, Net-Empregos
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    posted: str | None = None      # YYYY-MM-DD
    remote: str | None = None      # Presencial / Híbrido / Remoto
    extra_flags: dict = field(default_factory=dict)  # ex.: {"relocation": True}

    # preenchidos pelo score
    track: str | None = None
    seniority: str | None = None
    score: int = 0
    matched: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    excluded: str | None = None
    apply: str | None = None       # Testar agora / Esperar preparo / Não vale
    apply_why: str = ""
    years_required: int | None = None  # menor nº de anos de experiência pedido (None = não informa)

    @property
    def key(self) -> str:
        title = re.sub(r"\(.*?\)|[^a-z0-9 ]", " ", norm(self.title))
        title = re.sub(r"\b(m|f|h|mf|fm|hm|mh|x)\b", " ", title)
        company = re.sub(r"[^a-z0-9 ]|\b(lda|sa|s a|unipessoal|portugal|group|grupo)\b", " ", norm(self.company))
        return f"{' '.join(company.split())}|{' '.join(title.split())}"
