"""Envio para a base "Vagas" do Notion (cria vaga nova ou atualiza a existente).

Nunca altera "Status" nem "Encontrada em" de vagas que já estão na base,
para não apagar o acompanhamento feito à mão.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import date

import requests

from .models import Job

log = logging.getLogger("radar")

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"


def _rt(text: str) -> list:
    text = (text or "")[:1990]
    return [{"type": "text", "text": {"content": text}}] if text else []


class Notion:
    def __init__(self, token: str, database_id: str):
        self.db = database_id.replace("-", "")
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Notion-Version": VERSION,
                               "Content-Type": "application/json"})

    def _call(self, method, path, **kw):
        for attempt in range(5):
            r = self.s.request(method, f"{API}{path}", timeout=30, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(float(r.headers.get("Retry-After", 2 + attempt)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError("Notion: muitas tentativas")

    def check(self) -> None:
        """Falha cedo, com mensagem clara, se o token não tiver acesso à base."""
        try:
            self._call("GET", f"/databases/{self.db}")
        except RuntimeError as e:
            raise RuntimeError(
                "Sem acesso à base Vagas no Notion. Abra a página 'Vagas Lisboa — Radar diário' "
                "→ ••• → Conexões → adicione a integração dona do NOTION_TOKEN. Detalhe: " + str(e))

    def existing(self) -> dict[str, dict]:
        """{chave: {'id', 'link'}} para tudo que já está na base. Chave = link e título|empresa."""
        out, cursor = {}, None
        while True:
            body = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
            data = self._call("POST", f"/databases/{self.db}/query", json=body)
            for page in data["results"]:
                p = page["properties"]
                link = (p.get("Link") or {}).get("url") or ""
                title = "".join(t["plain_text"] for t in (p.get("Vaga") or {}).get("title", []))
                company = "".join(t["plain_text"] for t in (p.get("Empresa") or {}).get("rich_text", []))
                txt = lambda k: "".join(t["plain_text"] for t in (p.get(k) or {}).get("rich_text", []))
                sel = lambda k: ((p.get(k) or {}).get("select") or {}).get("name")
                ref = {"id": page["id"], "link": link, "title": title, "company": company,
                       "score": (p.get("Compatibilidade") or {}).get("number") or 0,
                       "seniority": sel("Senioridade"), "track": sel("Trilha"),
                       "gaps": [g.strip() for g in txt("Lacunas").split(",") if g.strip()],
                       "languages": txt("Idioma"),
                       "status": ((p.get("Status") or {}).get("status") or {}).get("name")}
                if link:
                    out[link] = ref
                out[Job("", title, company, "").key] = ref
            if not data.get("has_more"):
                return out
            cursor = data["next_cursor"]

    @staticmethod
    def _props(job: Job, new: bool) -> dict:
        props = {
            "Vaga": {"title": _rt(job.title)},
            "Empresa": {"rich_text": _rt(job.company)},
            "Compatibilidade": {"number": job.score},
            "Trilha": {"select": {"name": job.track}},
            "Fonte": {"select": {"name": job.source}},
            "Link": {"url": job.url},
            "Local": {"rich_text": _rt(job.location)},
            "Requisitos que cumpro": {"rich_text": _rt(", ".join(job.matched))},
            "Lacunas": {"rich_text": _rt(", ".join(job.gaps))},
            "Idioma": {"rich_text": _rt(", ".join(job.languages))},
            "Por quê": {"rich_text": _rt(job.apply_why)},
        }
        if job.apply:
            props["Candidatar agora?"] = {"select": {"name": job.apply}}
        if job.seniority in ("Estágio", "Júnior", "Pleno"):
            props["Senioridade"] = {"select": {"name": job.seniority}}
        if job.remote:
            props["Modelo"] = {"select": {"name": job.remote}}
        if job.posted:
            props["Publicada em"] = {"date": {"start": job.posted}}
        if new:
            props["Encontrada em"] = {"date": {"start": date.today().isoformat()}}
            props["Status"] = {"status": {"name": "Nova"}}
        return props

    def upsert(self, jobs: list[Job], cfg: dict | None = None) -> tuple[list[Job], int]:
        """Devolve (vagas novas, quantidade atualizada). Com cfg, também recalcula
        'Candidatar agora?' das vagas antigas que não apareceram nesta coleta."""
        known = self.existing()
        created, updated = [], 0
        touched = set()
        for job in jobs:
            ref = known.get(job.url) or known.get(job.key)
            if ref:
                touched.add(ref["id"])
            try:
                if ref:
                    self._call("PATCH", f"/pages/{ref['id']}", json={"properties": self._props(job, new=False)})
                    updated += 1
                else:
                    children = [{"object": "block", "type": "paragraph",
                                 "paragraph": {"rich_text": _rt("Por que encaixa: " + "; ".join(job.reasons)
                                                                  + (f"\nCandidatar agora? {job.apply} — {job.apply_why}" if job.apply else ""))}}]
                    page = self._call("POST", "/pages", json={
                        "parent": {"database_id": self.db},
                        "properties": self._props(job, new=True), "children": children})
                    known[job.url] = known[job.key] = {"id": page["id"], "link": job.url}
                    created.append(job)
            except RuntimeError as e:
                log.error("Falha ao gravar '%s' (%s): %s", job.title, job.company, e)
            time.sleep(0.35)  # limite da API: ~3 req/s
        if cfg is not None:
            updated += self.backfill(known, touched, cfg)
        return created, updated

    def backfill(self, known: dict, touched: set, cfg: dict) -> int:
        """Vagas da base que não vieram nesta coleta: decide pelo que já está gravado."""
        from .decide import decide_from_saved
        done, n = set(touched), 0
        for ref in known.values():
            if ref["id"] in done:
                continue
            done.add(ref["id"])
            apply, why = decide_from_saved(ref, cfg)
            props = {"Candidatar agora?": {"select": {"name": apply}}, "Por quê": {"rich_text": _rt(why)}}
            try:
                self._call("PATCH", f"/pages/{ref['id']}", json={"properties": props})
                n += 1
            except RuntimeError as e:
                log.error("Falha no backfill de '%s': %s", ref.get("title"), e)
            time.sleep(0.35)
        return n


def from_env(default_db: str) -> Notion | None:
    token = os.getenv("NOTION_TOKEN")
    if not token:
        log.warning("NOTION_TOKEN ausente: pulando o Notion")
        return None
    return Notion(token, os.getenv("NOTION_DATABASE_ID") or default_db)
