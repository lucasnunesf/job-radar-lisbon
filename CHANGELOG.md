# Changelog

## 2026-11-06
- Foco estrito em Lisboa: outras cidades, outros países e remoto aberto a vários países saem; "Portugal" sem cidade perde 8 pontos.
- LinkedIn pela região "Lisboa e Região" (geoId) com backoff; python-jobspy vira reserva, com raio de 25 milhas.
- Nova fonte Expresso Emprego; mais termos de busca (analista de dados, BI developer, reporting analyst, data engineer).
- Lista negra de títulos/empresas no perfil.
- `run_windows_extra.bat` para Glassdoor, Landing.jobs e Google Jobs a partir de casa.

## 2026-11-02
- Teste automático para a ordem do resumo diário ("Testar agora" antes de "Avaliar", por nota).

## 2026-11-01
- Teste automático para o filtro de local genérico ("Portugal" + cidade no link).

## 2026-10-31
- Changelog criado para registrar a evolução do radar.

## 2026-10-30
- Resumo diário às 00:00 (Brasília) via tarefa agendada; GitHub Actions de reserva às 06:20.
- Novas fontes: freehire.me, The Muse, Workable, Himalayas e descoberta semanal de empresas (~3.300 boards Greenhouse/Lever).
- Score: bônus de recência e de certificação/formação; mapa de lacunas em `data/gaps.md`.
- Local genérico "Portugal": confere a cidade no link/título.

## 2026-11-07
- Verificação do radar: execuções diárias de 01/11 a 07/11 sem falhas; resumo diário das 00h funcionando.

## 2026-10-29
- Fontes Net-Empregos (RSS), Teamlyzer, Michael Page e páginas de carreira (ATS).
- Coluna "Candidatar agora?" (Testar agora / Avaliar / Esperar preparo / Não vale).
- Filtros: estágio descartado, 4+ anos de experiência descartado, janela de 30 dias.
- Colunas no Notion: Inscrito, Descartar, Experiência pedida e Janela.

## 2026-10-28
- Primeira versão: LinkedIn, Indeed, ITJobs, Built In, score de match e envio ao Notion.
