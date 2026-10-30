"""Job Radar Lisboa — coleta, pontua, grava no Notion e avisa das vagas novas boas.

Uso:
  python -m radar.main                       # todas as fontes, grava no Notion
  python -m radar.main --dry-run             # não grava no Notion
  python -m radar.main --sources itjobs,linkedin --hours-old 336
  python -m radar.main --fixtures tests/fixtures/jobs.json --dry-run   # teste offline
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import yaml

from .classify import is_lisbon_area
from .models import Job
from .decide import decide
from .score import score_job

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_NOTION_DB = "96144502e4594f3ba11efd90b2f66980"  # base "Vagas" do Lucas
ALL_SOURCES = ["linkedin", "indeed", "itjobs", "builtin", "netempregos", "teamlyzer", "michaelpage", "freehire",
               "themuse", "workable", "himalayas", "jooble", "ats"]
# Bloqueiam os servidores do GitHub (403), por isso ficam fora do padrão: glassdoor, google, landingjobs

log = logging.getLogger("radar")


def collect(cfg: dict, sources: list[str], hours_old: int, stats: dict) -> list[Job]:
    from .sources import aggregators, ats, jobspy_boards, portals

    jobs: list[Job] = []
    boards = [s for s in sources if s in ("linkedin", "indeed", "glassdoor", "google")]
    if boards:
        jobs += jobspy_boards.collect(cfg, sites=boards, hours_old=hours_old, stats=stats)
    for name, fn in (("itjobs", portals.itjobs), ("landingjobs", portals.landingjobs),
                     ("builtin", portals.builtin), ("netempregos", portals.netempregos),
                     ("teamlyzer", portals.teamlyzer), ("michaelpage", portals.michaelpage),
                     ("freehire", aggregators.freehire), ("themuse", aggregators.themuse),
                     ("workable", aggregators.workable_search), ("himalayas", aggregators.himalayas),
                     ("jooble", portals.jooble), ("ats", ats.collect)):
        if name in sources:
            try:
                jobs += fn(cfg, stats)
            except Exception as e:  # noqa: BLE001 — uma fonte nunca derruba a execução
                log.exception("%s falhou", name)
                stats[name] = {"brutas": 0, "erros": [str(e)[:200]]}
    return jobs


def dedupe(jobs: list[Job]) -> list[Job]:
    """Mesma vaga em vários portais vira uma só (fica a de descrição mais completa)."""
    best: dict[str, Job] = {}
    seen_urls = set()
    for j in jobs:
        if j.url in seen_urls:
            continue
        seen_urls.add(j.url)
        cur = best.get(j.key)
        if cur is None or len(j.description) > len(cur.description):
            if cur is not None and cur.source != j.source:
                j.extra_flags["also_on"] = sorted(set(cur.extra_flags.get("also_on", [])) | {cur.source})
            best[j.key] = j
        else:
            cur.extra_flags["also_on"] = sorted(set(cur.extra_flags.get("also_on", [])) | {j.source})
    return list(best.values())


def too_old(job: Job, max_age_days: int) -> bool:
    if not job.posted:
        return False
    try:
        return datetime.strptime(job.posted[:10], "%Y-%m-%d").date() < date.today() - timedelta(days=max_age_days)
    except ValueError:
        return False


def write_outputs(ranked: list[Job], excluded: list[Job], stats: dict, new_alerts: list[Job]) -> str:
    DATA.mkdir(exist_ok=True)
    with open(DATA / "latest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["score", "trilha", "senioridade", "vaga", "empresa", "local", "fonte",
                    "publicada", "tenho", "lacunas", "idiomas", "candidatar", "por que", "link"])
        for j in ranked:
            w.writerow([j.score, j.track, j.seniority or "", j.title, j.company, j.location, j.source,
                        j.posted or "", ", ".join(j.matched), ", ".join(j.gaps), ", ".join(j.languages), j.apply or "", j.apply_why, j.url])

    lines = [f"# Job Radar Lisboa — {datetime.now():%Y-%m-%d %H:%M}", "",
             "## Coleta por fonte", "", "| Fonte | Vagas | Observação |", "|---|---:|---|"]
    for src, st in sorted(stats.items()):
        obs = "; ".join(st.get("erros") or []) or "ok"
        lines.append(f"| {src} | {st.get('brutas', 0)} | {obs[:160].replace('|', '/')} |")
    lines += ["", f"**{len(ranked)} vagas no ranking**, {len(excluded)} descartadas "
                  f"(sênior, fora da trilha, fora de Lisboa ou antigas).", ""]
    for track in ("Data Analyst", "BI", "Analytics Engineer", "Data Engineer"):
        group = [j for j in ranked if j.track == track]
        if not group:
            continue
        lines += [f"## {track} ({len(group)})", "", "| Score | Agora? | Vaga | Empresa | Senioridade | Lacunas | Fonte |",
                  "|---:|---|---|---|---|---|---|"]
        for j in group[:25]:
            lines.append(f"| {j.score} | {j.apply or ''} | [{j.title.replace('|', '/')}]({j.url}) | {j.company.replace('|', '/')} | "
                         f"{j.seniority or '—'} | {', '.join(j.gaps) or '—'} | {j.source} |")
        lines.append("")
    report = "\n".join(lines)
    (DATA / "latest.md").write_text(report, encoding="utf-8")

    alert_path = DATA / "alert.md"
    if new_alerts:
        body = ["Vagas novas com score alto encontradas pelo radar:", ""]
        for j in new_alerts:
            body.append(f"- **{j.score}** · [{j.title}]({j.url}) · {j.company} · {j.track} · "
                        f"{j.seniority or 'senioridade não informada'} · {j.source}")
            body.append(f"  - Tenho: {', '.join(j.matched) or '—'} | Lacunas: {', '.join(j.gaps) or '—'}")
            body.append(f"  - Candidatar agora? **{j.apply}** — {j.apply_why}")
        alert_path.write_text("\n".join(body), encoding="utf-8")
    elif alert_path.exists():
        alert_path.unlink()
    return report


def write_summary(new_today: list[Job], ranked: list[Job], stats: dict, flags: dict) -> str:
    """Resumo curto do dia (lido pela tarefa agendada que manda a mensagem às 00:00)."""
    DATA.mkdir(exist_ok=True)
    good = [j for j in new_today if not j.excluded and j.apply in ("Testar agora", "Avaliar")]
    later = [j for j in new_today if not j.excluded and j.apply == "Esperar preparo"]
    out = [j for j in new_today if j.excluded or j.apply == "Não vale"]

    def open_(j):  # ignora as que você já marcou como inscrito/descartar no Notion
        f = flags.get(j.url) or flags.get(j.key) or {}
        return not f.get("inscrito") and not f.get("descartar")

    best = sorted([j for j in good if open_(j)], key=lambda j: j.score, reverse=True)[:6]
    if len(best) < 6:  # completa com as melhores ainda abertas (não novas)
        extra = [j for j in ranked if j.apply == "Testar agora" and j not in best and open_(j)]
        best += extra[: 6 - len(best)]
    gaps: dict[str, int] = {}
    for j in ranked:
        if j.apply in ("Testar agora", "Esperar preparo"):
            for g in j.gaps:
                gaps[g] = gaps.get(g, 0) + 1
    top_gaps = sorted(gaps.items(), key=lambda kv: -kv[1])[:5]

    lines = [f"Fiz a atualização de {datetime.now():%d/%m}: **{len(good)} vagas novas combinando**, "
             f"{len(out)} fora do perfil e {len(later)} para depois.", ""]
    if best:
        lines.append("**Melhores agora:**")
        for i, j in enumerate(best, 1):
            tag = "" if j in good else " _(já estava aberta)_"
            lines.append(f"{i}. [{j.title}]({j.url}) · {j.company} · nota {j.score} · {j.apply}{tag}")
        lines.append("")
    if top_gaps:
        lines.append("**Lacunas que mais aparecem nas vagas boas:** " + ", ".join(f"{g} ({n})" for g, n in top_gaps))
    fontes = ", ".join(f"{k} {v.get('brutas', 0)}" for k, v in sorted(stats.items()) if k != "Notion")
    lines.append(f"_Fontes: {fontes}._")
    text = "\n".join(lines)
    (DATA / "summary.md").write_text(text, encoding="utf-8")
    (DATA / "summary.json").write_text(json.dumps({
        "date": date.today().isoformat(), "combinando": len(good), "fora": len(out), "depois": len(later),
        "melhores": [{"vaga": j.title, "empresa": j.company, "nota": j.score, "link": j.url} for j in best],
        "lacunas": dict(top_gaps)}, ensure_ascii=False, indent=1), encoding="utf-8")

    # Mapa de lacunas completo (ideia do /upskill do ai-job-search): o que estudar primeiro
    rows = ["# O que estudar primeiro", "", "Ferramentas pedidas nas vagas do ranking que ainda não estão no seu perfil.",
            "", "| Ferramenta | Vagas que pedem |", "|---|---:|"]
    rows += [f"| {g} | {n} |" for g, n in sorted(gaps.items(), key=lambda kv: -kv[1])]
    (DATA / "gaps.md").write_text("\n".join(rows), encoding="utf-8")
    return text


def notify_telegram(alerts: list[Job]) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat and alerts):
        return
    text = "🎯 Vagas novas (Lisboa)\n\n" + "\n\n".join(
        f"{j.score} · {j.title} — {j.company}\n{j.url}" for j in alerts[:10])
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text, "disable_web_page_preview": "true"}, timeout=20)
    except requests.RequestException as e:
        log.warning("Telegram falhou: %s", e)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Job Radar Lisboa")
    ap.add_argument("--sources", default=",".join(ALL_SOURCES))
    ap.add_argument("--hours-old", type=int, default=int(os.getenv("HOURS_OLD", "72")))
    ap.add_argument("--max-age-days", type=int, default=30)  # depois de ~30 dias a vaga quase sempre já está em fase final
    ap.add_argument("--dry-run", action="store_true", help="não grava no Notion")
    ap.add_argument("--fixtures", help="JSON com vagas de exemplo (teste offline)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load((ROOT / "config" / "profile.yaml").read_text(encoding="utf-8"))
    stats: dict = {}

    if args.fixtures:
        raw = [Job(**j) for j in json.loads(Path(args.fixtures).read_text(encoding="utf-8"))]
        stats["fixtures"] = {"brutas": len(raw)}
    else:
        sources = [s.strip() for s in args.sources.split(",") if s.strip()]
        raw = collect(cfg, sources, args.hours_old, stats)

    jobs = dedupe(raw)
    ranked, excluded = [], []
    for j in jobs:
        if not is_lisbon_area(j.location):
            j.excluded = f"fora de Lisboa ({j.location})"
        elif too_old(j, args.max_age_days):
            j.excluded = "antiga"
        else:
            score_job(j, cfg)
            if not j.excluded:
                decide(j, cfg)
        (excluded if j.excluded else ranked).append(j)
    ranked.sort(key=lambda j: j.score, reverse=True)
    log.info("%d brutas → %d únicas → %d no ranking", len(raw), len(jobs), len(ranked))

    # Vagas novas = nunca vistas em execuções anteriores (data/seen.json fica versionado no repo)
    seen_path = DATA / "seen.json"
    seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else {}
    first_run = not seen
    today = date.today().isoformat()
    new_alerts = [j for j in ranked if j.score >= cfg["alert_score"] and j.key not in seen]
    new_today = [j for j in jobs if j.key not in seen]
    for j in jobs:  # vistas = avaliadas (inclusive descartadas), para o resumo não recontar
        seen.setdefault(j.key, today)
    if first_run:
        new_alerts = new_alerts[:15]  # primeira execução: não inunda o alerta

    to_notion = [j for j in ranked if j.score >= cfg["min_score_notion"]]
    notion_flags: dict = {}
    if not args.dry_run and not args.fixtures:
        from .notion import from_env
        client = from_env(DEFAULT_NOTION_DB)
        if client:
            client.check()
            created, updated = client.upsert(to_notion, cfg)
            stats["Notion"] = {"brutas": len(created), "erros": [f"{updated} atualizadas"]}
            notion_flags = client.flags

    report = write_outputs(ranked, excluded, stats, new_alerts)
    write_summary(new_today, ranked, stats, notion_flags)
    if not args.fixtures:
        DATA.mkdir(exist_ok=True)
        seen_path.write_text(json.dumps(seen, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
        notify_telegram(new_alerts)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(report)
    print(report[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
