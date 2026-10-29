# Job Radar Lisboa

Busca vagas de **Data Analyst, BI Analyst e Analytics Engineer** (e Data Engineer júnior como secundário) em Lisboa,
dá uma nota de 0 a 100 pelo encaixe com o meu perfil e grava tudo na base **Vagas** do Notion, ordenada pela nota.
Roda sozinho no GitHub Actions duas vezes por dia e abre uma *issue* quando aparece vaga nova com nota alta
(o GitHub manda e-mail e notificação no app).

## Fontes

| Fonte | Como | Observação |
|---|---|---|
| LinkedIn | [python-jobspy](https://github.com/speedyapply/JobSpy) (API pública de convidado) | pode bloquear às vezes; o relatório mostra |
| Indeed (pt.indeed.com) | python-jobspy | idem |
| Glassdoor | python-jobspy | o mais instável dos três |
| ITJobs | API oficial se houver `ITJOBS_API_KEY`, senão página de busca | onde as consultorias Microsoft/Azure publicam |
| Landing.jobs | API pública | traz flag de relocação/visto |
| Built In | página de busca + JSON-LD da vaga | |
| Net-Empregos | página de busca + JSON-LD da vaga | |

Mesma vaga em vários portais vira uma só (fica a descrição mais completa).

## Score (0–100)

| Componente | Pontos |
|---|---|
| Trilha (DA / BI / AE = 25, DE júnior = 15) | 25 |
| Ferramentas que tenho ÷ ferramentas citadas (com peso) | 35 |
| Senioridade (Júnior 20, Estágio 18, não informada 12, Pleno 6) | 20 |
| Idioma (perde até 15 se exigir francês/alemão/etc.) | 5 |
| Relocação citada ou exige autorização de trabalho UE (sou cidadão UE, então é vantagem) | +3 |
| Consultoria Microsoft/Azure da lista | +6 |
| Stack Microsoft (Power BI, Azure, Fabric) | +3 |

Vagas **sênior** (título ou ≥5 anos pedidos), fora das trilhas, fora da Grande Lisboa ou com mais de 45 dias são descartadas.
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
