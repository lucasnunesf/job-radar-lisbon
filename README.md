# Job Radar Lisboa

Busca vagas de **Data Analyst, BI Analyst e Analytics Engineer** (e Data Engineer júnior como secundário) em Lisboa,
dá uma nota de 0 a 100 pelo encaixe com o meu perfil e grava tudo na base **Vagas** do Notion, ordenada pela nota.
Roda todo dia à meia-noite de Brasília (disparado por uma tarefa agendada do Claude, que depois manda um resumo no chat; o GitHub roda de reserva às 06:20) e abre uma *issue* quando aparece vaga nova com nota alta
(o GitHub manda e-mail e notificação no app).

## Fontes

| Fonte | Como | Observação |
|---|---|---|
| LinkedIn | [python-jobspy](https://github.com/speedyapply/JobSpy) (API pública de convidado) | pode bloquear às vezes; o relatório mostra |
| Indeed (pt.indeed.com) | python-jobspy | idem |
| Net-Empregos | RSS (~250 últimas vagas/dia) | filtra título e zona Lisboa |
| Teamlyzer | página de busca por tag + página da vaga | vagas tech em PT |
| Michael Page | página de busca + JSON-LD da vaga | |
| Sites de empresas | APIs públicas de Greenhouse, Lever, Ashby, SmartRecruiters e Workable | lista em `ats_companies` no `profile.yaml` |
| freehire.me | API pública (agrega ~50 ATS), filtro Portugal | descrição completa |
| The Muse | API pública, Lisboa + Data/Analytics, Entry/Mid | |
| Workable | API da busca global jobs.workable.com | |
| Himalayas | API pública, remoto que aceita Portugal | |
| Descoberta de empresas | `scripts/discover_ats.py` varre ~3.300 boards Greenhouse e ~40 Lever 1x/semana | resultado em `config/ats_found.json` |
| Jooble | API oficial (`JOOBLE_API_KEY`, pedir em jooble.org/api/about) | opcional |
| ITJobs | API oficial se houver `ITJOBS_API_KEY`, senão página de busca | onde as consultorias Microsoft/Azure publicam |
| Landing.jobs | API pública | traz flag de relocação/visto |
| Built In | página de busca + JSON-LD da vaga | |

Mesma vaga em vários portais vira uma só (fica a descrição mais completa).

## Score (0–100)

| Componente | Pontos |
|---|---|
| Trilha (DA / BI / AE = 25, DE júnior = 15) | 25 |
| Ferramentas que tenho ÷ ferramentas citadas (com peso) | 35 |
| Senioridade (Júnior 20, não informada 12, Pleno 6; estágio é descartado) | 20 |
| Idioma (perde até 15 se exigir francês/alemão/etc.) | 5 |
| Relocação citada ou exige autorização de trabalho UE (sou cidadão UE, então é vantagem) | +3 |
| Consultoria Microsoft/Azure da lista | +6 |
| Stack Microsoft (Power BI, Azure, Fabric) | +3 |
| Recência (até 3 dias +4, até 7 dias +2) | +4 |
| Vaga valoriza PL-300, DP-900 ou formação em Engenharia | +3 |

Coluna **Candidatar agora?** (fase de teste nov–jan): *Testar agora* = vaga fácil em empresa onde um "não" não custa nada; *Esperar preparo* = vaga difícil ou empresa de topo (lista `protect_companies`); *Não vale* = início imediato, outro idioma ou pouco encaixe. Regras em `radar/decide.py`.

Vagas **sênior** (título ou 4+ anos pedidos), fora das trilhas, fora da Grande Lisboa ou com mais de 30 dias são descartadas.
Pesos, ferramentas, termos de busca, consultorias e notas de corte ficam em [`config/profile.yaml`](config/profile.yaml).

## Configuração (uma vez)

1. **Settings → Secrets and variables → Actions → New repository secret**
   - `NOTION_TOKEN` — token da integração do Notion (obrigatório)
   - `ITJOBS_API_KEY` — opcional, pedir em <https://www.itjobs.pt/api>
   - `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` — opcional, alerta no Telegram
   - `NOTION_DATABASE_ID` — opcional; o padrão já é a base **Vagas**
2. No Notion, abrir a página **Vagas Lisboa — Radar diário** → `•••` → **Conexões** → adicionar a integração dona do `NOTION_TOKEN`.
3. **Actions → Job Radar Lisboa → Run workflow** com `hours_old = 336` (duas semanas) na primeira vez.

## Saídas

- Notion: base **Vagas** (coluna `Compatibilidade` = nota). O radar nunca altera `Status` nem `Encontrada em` de vagas já existentes.
- `data/latest.md` — ranking por trilha + quantas vagas cada fonte trouxe (aparece também no resumo da execução no Actions).
- `data/latest.csv` — mesma lista em CSV.
- `data/seen.json` — histórico para saber o que é novo.

## Rodar no computador

```bash
pip install -r requirements.txt
python -m radar.main --dry-run                 # sem Notion
python -m radar.main --sources itjobs,landingjobs
python -m pytest -q                            # testes offline
```

No Windows, dar dois cliques em `run_windows.bat` (pede o `NOTION_TOKEN` na primeira vez).

Fontes testadas que **bloqueiam o GitHub Actions** (403): Glassdoor, Google Jobs, Landing.jobs, Indeed RSS, Jooble (HTML).
Para testar portais de novo: Actions → **Testar portais** → Run workflow (resultado em `data/probe.md`).

## Saídas extras

- `data/summary.md` / `summary.json` — resumo do dia (novas combinando, fora, para depois, 6 melhores, lacunas).
- `data/gaps.md` — "o que estudar primeiro": ferramentas mais pedidas nas vagas do ranking que faltam no perfil.

## Ideias aproveitadas de outros projetos

- [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search): fonte freehire.me, chave estável de deduplicação e o mapa de lacunas do `/upskill`.
- [job-match-finder-skill](https://github.com/mn-youssef/job-match-finder-skill): recência entra na nota; lacunas honestas por vaga.
- [busca-trampo](https://github.com/leonardobissoli/busca-trampo): certificações/formação como critério; "não informado" em vez de chute.
- [candidate](https://github.com/Cla-Code-Community/candidate): lista pública de boards Greenhouse/Lever para descobrir empresas com vagas em Portugal.
