"""Filtro 2: o que a triagem manual de 09/11/2026 pegou e o filtro 1 deixava passar.

Roda depois do score/decide, só nas vagas que iriam como "Testar agora"/"Avaliar":
  1. link morto ou vaga fechada (agregadores redirecionam para a busca; páginas dizem "no longer accepting");
  2. mesma vaga de cliente publicada por várias consultorias (texto quase igual);
  3. empresa/grupo com muitas candidaturas abertas (espere resposta antes de mandar outra).
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests

from .http import UA
from .models import Job, norm

log = logging.getLogger("radar")

CLOSED = re.compile(
    r"no longer accepting applications|not currently accepting applications|this job (is no longer|has expired|is closed)"
    r"|job (not found|no longer available|has been filled|is no longer)|position (has been )?filled|vaga (encerrada|expirou|fechada"
    r"|ja nao (esta|se encontra) disponivel)|oferta (expirou|encerrada|ja nao (esta|se encontra) disponivel)"
    r"|anuncio (expirou|removido)|page (you are looking for )?(doesn.t|does not) exist|pagina nao encontrada")
# Bloqueiam robôs ou mandam para login: não dá para concluir nada
SKIP_HOSTS = re.compile(r"linkedin\.|indeed\.|glassdoor\.|google\.")
LOGIN_PATH = re.compile(r"login|signin|sign-in|authwall|auth|account|captcha|challenge")
LISTING_PATH = re.compile(r"/(search|jobs/?$|vagas/?$|ofertas/?$|empregos/?$|careers/?$)|[?&](q|query|keywords?)=")


def link_status(url: str, timeout: int = 10) -> tuple[bool | None, str]:
    """(morto?, motivo). None = não deu para saber (403, timeout): na dúvida, a vaga fica."""
    if not url or SKIP_HOSTS.search(urlparse(url).netloc):
        return None, ""
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "pt-PT,en;q=0.8"},
                         timeout=timeout, allow_redirects=True)
    except requests.RequestException:
        return None, ""
    if r.status_code in (404, 410):
        return True, f"link devolve {r.status_code}"
    if r.status_code != 200:
        return None, ""
    a, b = urlparse(url), urlparse(r.url)
    if LOGIN_PATH.search(b.path):
        return None, ""
    if r.history and (a.netloc != b.netloc or a.path.rstrip("/") != b.path.rstrip("/")):
        if LISTING_PATH.search(b.path + ("?" + b.query if b.query else "")) or len(b.path.strip("/")) < len(a.path.strip("/")) // 2:
            return True, "link redireciona para a lista de vagas (anúncio saiu do ar)"
    if CLOSED.search(norm(r.text[:200_000])):
        return True, "a página diz que a vaga está fechada"
    return False, ""


def check_links(jobs: list[Job], limit: int = 60) -> int:
    """Marca como excluídas as vagas com link morto. Devolve quantas caíram."""
    dead = 0
    for j in jobs[:limit]:
        is_dead, why = link_status(j.url)
        if is_dead:
            j.excluded = f"link morto: {why}"
            dead += 1
    return dead


# ---------------------------------------------------------------- vagas iguais em consultorias diferentes
def signature(text: str, k: int = 64) -> list[int]:
    """Bottom-k MinHash de 5-gramas de palavras: compara textos sem guardar o texto."""
    words = re.findall(r"[a-z0-9+#]+", norm(text))
    grams = {" ".join(words[i:i + 5]) for i in range(max(0, len(words) - 4))}
    hashes = sorted(int(hashlib.md5(g.encode()).hexdigest()[:12], 16) for g in grams)
    return hashes[:k]


def similarity(a: list[int], b: list[int]) -> float:
    if not a or not b:
        return 0.0
    k = min(len(a), len(b))
    union_k = sorted(set(a) | set(b))[:k]
    sa, sb = set(a), set(b)
    return sum(1 for h in union_k if h in sa and h in sb) / k


def company_root(company: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", norm(company))
             if w not in ("grupo", "group", "the", "portugal", "lda", "sa", "consulting", "recruitment", "it", "solutions")]
    return words[0] if words else norm(company)


def mark_duplicates(jobs: list[Job], store_path: Path, flags: dict, threshold: float = 0.5, days: int = 60,
                    persist: bool = True) -> int:
    """Mesma vaga (texto ≥ threshold) em outra empresa nos últimos `days` dias.
    Se a outra já foi candidatada (Notion: Inscrito), exclui esta; se não, avisa no 'por quê'."""
    store = json.loads(store_path.read_text(encoding="utf-8")) if store_path.exists() else {}
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    store = {k: v for k, v in store.items() if v.get("d", "") >= cutoff}
    n = 0
    for j in jobs:
        if len(j.description) < 400:
            continue
        sig = signature(j.description)
        root = company_root(j.company)
        for key, v in store.items():
            if key == j.key or company_root(v["c"]) == root:
                continue
            if similarity(sig, v["h"]) >= threshold:
                other = flags.get(v.get("u", "")) or flags.get(key) or {}
                if other.get("inscrito"):
                    j.excluded = f"mesma vaga de cliente já candidatada via {v['c']}"
                else:
                    j.apply_why += f"; mesmo anúncio também em {v['c']} ({v['t'][:50]}): candidate por uma só"
                n += 1
                break
        store[j.key] = {"c": j.company, "t": j.title, "u": j.url, "h": sig, "d": store.get(j.key, {}).get("d") or date.today().isoformat()}
    if persist:
        store_path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    return n


def company_load(flags: dict, days: int = 45) -> dict[str, int]:
    """Candidaturas (Inscrito) por empresa/grupo nos últimos `days` dias, a partir do Notion."""
    cutoff = date.today() - timedelta(days=days)
    seen, count = set(), {}
    for ref in flags.values():
        if not ref.get("inscrito") or ref.get("id") in seen:
            continue
        seen.add(ref.get("id"))
        try:
            if ref.get("applied") and datetime.strptime(ref["applied"][:10], "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            pass
        r = company_root(ref.get("company", ""))
        count[r] = count.get(r, 0) + 1
    return count


def apply_company_load(jobs: list[Job], flags: dict, max_open: int = 3) -> int:
    load, n = company_load(flags), 0
    for j in jobs:
        c = load.get(company_root(j.company), 0)
        if c >= max_open and j.apply == "Testar agora":
            j.apply, j.apply_why = "Esperar preparo", f"já tem {c} candidaturas recentes em {j.company}: espere resposta"
            n += 1
    return n


def review(ranked: list[Job], flags: dict, cfg: dict, data_dir: Path, check_net: bool = True, persist: bool = True) -> dict:
    rules = cfg.get("apply_now", {})
    open_ = [j for j in ranked if not j.excluded and j.apply in ("Testar agora", "Avaliar")]
    # não refaz o que já está decidido no Notion (inscrito/descartado/analisado)
    open_ = [j for j in open_ if not ((flags.get(j.url) or flags.get(j.key) or {}).get("locked"))]
    out = {"links_mortos": check_links(open_) if check_net else 0}
    open_ = [j for j in open_ if not j.excluded]
    out["duplicadas"] = mark_duplicates(open_, data_dir / "fingerprints.json", flags,
                                        rules.get("duplicate_similarity", 0.5), persist=persist)
    out["empresa_cheia"] = apply_company_load(open_, flags, rules.get("max_open_per_company", 3))
    return out
