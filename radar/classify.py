"""Classificação por trilha, senioridade, idioma, relocação e local."""
from __future__ import annotations

import re

from .models import norm

TRACK_RULES = [  # ordem importa: a primeira que casar vence
    ("Analytics Engineer", r"analytics engineer|analytics engineering|engenheir[oa] de analytics"),
    ("Data Analyst", r"data analyst|analista de dados"),
    ("BI", r"\bbi\b|business intelligence|power ?bi|reporting|tableau|qlik|data visuali[sz]ation|dashboard|looker"),
    ("Data Analyst", r"analytics analyst|insights? analyst|data & analytics analyst"
                     r"|product analyst|marketing analyst|commercial analyst|analista (de )?(bi|reporting|business)"
                     r"|business (data|analytics) analyst|\bdata analytics\b|procurement analyst|supply chain analyst"),
    ("Data Engineer", r"data engineer|engenheir[oa] de dados|etl developer|databricks|data platform engineer"
                      r"|big data|data integration|azure data"),
]

NOT_DATA = r"scientist|cientista|machine learning engineer|ml engineer|software engineer|full ?stack|frontend|backend" \
           r"|sales|vendas|recruiter|recrutador|account manager|teacher|professor|nurse|enfermeir"

SENIOR_TITLE = r"\b(senior|sr\.?|sênior|lead|principal|head|manager|gestor|director|diretor|staff|architect|arquiteto|chief|expert)\b"
INTERN_TITLE = r"\b(intern|internship|estagio|estagiario|trainee|summer)\b|programa de estagio"
JUNIOR_TITLE = r"\b(junior|jr\.?|entry[- ]level|graduate|recem[- ]licenciado|associate)\b"
MID_TITLE = r"\b(mid|medior|pleno|intermediate|intermedio)\b"

YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|–|to|a|ou|or)?\s*(\d{1,2})?\s*\+?\s*(?:years?|anos?|yrs)", re.I)

LISBON_HINTS = ("lisboa", "lisbon", "oeiras", "amadora", "sintra", "cascais", "loures", "odivelas",
                "almada", "carnaxide", "alfragide", "porto salvo", "setubal", "barreiro", "seixal",
                "vila franca", "linda-a-velha", "paco de arcos", "queluz", "parque das nacoes")
OTHER_PT_CITIES = ("porto", "braga", "coimbra", "aveiro", "faro", "leiria", "guimaraes", "viseu", "evora",
                   "funchal", "madeira", "acores", "azores", "covilha", "vila real", "castelo branco",
                   "matosinhos", "maia", "gaia", "fundao", "santarem", "tomar", "viana do castelo")


def track_of(title: str) -> str | None:
    t = norm(title)
    if re.search(NOT_DATA, t) and not re.search(r"analytics engineer|data engineer|analyst|\bbi\b", t):
        return None
    for name, rx in TRACK_RULES:
        if re.search(rx, t):
            return name
    return None


def title_is_relevant(title: str) -> bool:
    return track_of(title) is not None


def min_years(text: str) -> int | None:
    """Menor 'X anos/years' de experiência pedido no texto (ignora números absurdos)."""
    found = []
    for m in YEARS.finditer(text or ""):
        ctx = norm(text[max(0, m.start() - 60): m.end() + 60])
        if not re.search(r"experien|experience|work|trabalh|background|track record", ctx):
            continue
        n = int(m.group(1))
        if 0 < n <= 15:
            found.append(n)
    return min(found) if found else None


def seniority_of(title: str, description: str) -> str | None:
    t = norm(title)
    if re.search(SENIOR_TITLE, t):
        return "Sênior"
    if re.search(INTERN_TITLE, t):
        return "Estágio"
    if re.search(JUNIOR_TITLE, t):
        return "Júnior"
    years = min_years(description)
    if re.search(MID_TITLE, t):
        return "Sênior" if years and years >= 4 else "Pleno"
    if years is not None:
        if years >= 4:  # 4+ anos pedidos = fora do perfil
            return "Sênior"
        if years >= 3:
            return "Pleno"
        return "Júnior"
    d = norm(description)
    if re.search(r"entry[- ]level|junior|recem[- ]licenciad|graduate program|first job|primeiro emprego", d):
        return "Júnior"
    return None


LANG_RX = {
    "Francês": r"\b(french|frances|francais)\b",
    "Alemão": r"\b(german|alemao|deutsch)\b",
    "Neerlandês": r"\b(dutch|holandes|neerlandes|flemish)\b",
    "Italiano": r"\b(italian|italiano)\b",
    "Espanhol": r"\b(spanish|espanhol|castellano)\b",
}
SOFT = r"plus|nice to have|advantage|valoriza|preferr|preferencial|desejavel|bonus|differential|diferencial"


def languages_of(description: str) -> tuple[list[str], int]:
    """Idiomas citados e penalidade (Lucas: português nativo, inglês B2)."""
    d = norm(description)
    langs, penalty = [], 0
    if re.search(r"\b(portuguese|portugues)\b", d):
        langs.append("Português")
    if re.search(r"\b(english|ingles)\b", d):
        langs.append("Inglês")
        if re.search(r"native english|english native|ingles nativo|\bc2\b", d):
            penalty += 3
    for lang, rx in LANG_RX.items():
        m = re.search(rx, d)
        if not m:
            continue
        langs.append(lang)
        ctx = d[max(0, m.start() - 70): m.end() + 70]
        penalty += 2 if re.search(SOFT, ctx) else (6 if lang == "Espanhol" else 15)
    return langs, penalty


def relocation_of(description: str, flags: dict) -> int:
    """+1 aceita relocação/visto, -1 exige autorização de trabalho na UE, 0 não diz."""
    d = norm(description)
    if re.search(r"no (visa )?sponsorship|not (able to )?(offer|provide) (visa )?sponsorship|eu citizens? only"
                 r"|must (already )?(have|hold) (the )?(right|permission|valid work permit)"
                 r"|valid (eu |european )?work (permit|authori[sz]ation)|right to work in (the )?(eu|portugal)|cidadania europeia|autorizacao de residencia valida", d):
        return -1
    if flags.get("relocation") or re.search(
            r"relocation|relocalizacao|visa (sponsorship|support)|apoio (ao|no) visto|sponsor(ship)? (your|a) visa"
            r"|help with (the )?visa|relocation package|mudanca para portugal", d):
        return 1
    return 0


def is_lisbon_area(location: str) -> bool:
    """Lisboa e arredores, remoto, ou 'Portugal' genérico. Porto/Braga/etc. e exterior ficam fora."""
    t = norm(location)
    if not t:
        return True
    if any(h in t for h in LISBON_HINTS):
        return True
    if re.search(r"\b(remote|remoto|remotely|teletrabalho)\b", t):
        return True
    if any(re.search(r"\b" + c + r"\b", t) for c in OTHER_PT_CITIES):
        return False
    return "portugal" in t
