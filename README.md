# MetaOrganico

Dashboard de itens orgânicos — Meta (Facebook + Instagram) e Google Ads.

Nesta primeira etapa: conector para extrair dados orgânicos do Meta (posts de Facebook e Instagram,
com métricas de alcance, impressões e engajamento). O conector do Google Ads vem em seguida.

## Configurar credenciais

1. Copie `.env.example` para `.env`.
2. Gere um Meta Access Token de longa duração (idealmente um System User Token, que não expira)
   em Business Settings → Usuários do sistema, com as permissões: `pages_show_list`,
   `pages_read_engagement`, `pages_read_user_content` (necessária para reações/comentários/shares
   de posts do Facebook), `instagram_basic`, `instagram_manage_insights`, `read_insights`.
3. Preencha `META_ACCESS_TOKEN` no `.env`. `META_PAGE_ID` e `META_IG_ACCOUNT_ID` são opcionais —
   se ausentes, o conector auto-descobre a primeira página/conta vinculada ao token.

O `.env` nunca é commitado (está no `.gitignore`).

## Limitações conhecidas da API (não são bugs do código)

- **Facebook — alcance/impressões por post não existem mais na API.** A Graph API descontinuou
  `post_impressions`, `post_reach` e `post_engaged_users` para posts de Page globalmente (todas as
  versões, mesmo pinando uma antiga). Esses campos sempre vêm como `null` ("não disponível"), nunca
  como `0`. A única forma de obter essa métrica hoje é o export manual do Meta Business Suite.
- **Facebook — reações/comentários/shares exigem `pages_read_user_content`.** Sem essa permissão no
  token, `curtidas`/`comentarios`/`compartilhamentos` vêm como `null`.
- **Facebook — `cliques`/`video_views` podem vir `null`** para posts sem link ou sem vídeo — não é erro.
- **Instagram funciona bem via API** (alcance, salvamentos, compartilhamentos, visitas ao perfil,
  seguidores gerados, interações totais — e, para Reels, tempo médio assistido e visualizações).
  `impressions` foi descontinuada também no Instagram (erro global desde a v22.0) — não é buscada.
- **Stories não têm histórico retroativo.** A API só expõe stories ainda ativos (até 24h após a
  publicação) via `/{{ig-id}}/stories`. Não dá pra "puxar stories antigos" — só acumular ao longo do
  tempo, rodando `fetch_meta_organic.py` periodicamente (ex.: diariamente, antes de cada story expirar).
  O histórico acumulado fica em `data/meta_stories_history.json` (local, gitignored) e cresce a cada
  execução; nada se perde entre execuções, mas nada anterior ao início da coleta pode ser recuperado.
- **Thumbnail do Facebook vem do campo `full_picture`** do post (capa/imagem de destaque). Para posts
  sem imagem (ex.: texto puro), fica vazio — o dashboard mostra "—" no lugar.
- **Colaboradores de post Collab do Instagram são experimentais.** O campo `collaborators` (usernames
  co-autores de um post feito com "Adicionar colaborador") não é consistentemente documentado nas
  versões públicas da Graph API — o suporte de leitura pode variar por versão/permissão do token. O
  conector busca esse campo em lote por post e, se a API rejeitar (campo inexistente/sem permissão),
  trata como "sem colaboradores" em vez de falhar o fetch inteiro. Se posts que você sabe serem collab
  não aparecerem marcados no dashboard, valide o campo manualmente contra a Graph API antes de assumir
  que é um bug do código.

## Rodar

```bash
pip install -r requirements.txt
python scripts/fetch_meta_organic.py   # posts (90d) + stories ativos (acumula histórico)
python scripts/fetch_meta_ads_snapshot.py   # opcional: KPIs pagos (Meta Ads) via REPORTCLAUDE
python scripts/gerar_dashboard.py
```

Gera `data/meta_organic.json` com os posts orgânicos do Facebook e Instagram dos últimos
`ORGANIC_LOOKBACK_DAYS` dias (padrão 90), e acumula `data/meta_stories_history.json` com os
stories capturados a cada execução. Para o histórico de Stories crescer de verdade, agende essa
execução para rodar pelo menos 1x por dia (ex.: GitHub Actions com `schedule`, como já existe no
REPORTCLAUDE).

## Calendário dinâmico

Há um seletor de período (datas + atalhos 7d/30d/90d/Tudo) no topo do dashboard. Ele recalcula em
JS, na hora, praticamente tudo que tem data associada nas duas abas: KPIs, rankings, tabelas de
posts, gráfico por formato, Stories, Collab, tema/produto/idioma/público-alvo, creators e os
gráficos de Tendência de conta. **Só duas seções ficam de fora**, porque a própria API não dá
dado com data para elas — não é limitação do dashboard:
- **Demografia dos seguidores** (país/cidade/idade/gênero) — é uma foto dos seguidores agora, a
  Graph API não guarda "demografia de 3 meses atrás".
- **Meta Ads / Orgânico x Pago** — vem de um snapshot fixo de 30 dias raspado do REPORTCLAUDE, sem
  série diária disponível.

## Aba "KPIs de Conteúdo"

O dashboard tem duas abas: **Visão Geral** (a original, com todas as tabelas de posts) e
**KPIs de Conteúdo** — um recorte estratégico com alcance/descoberta, engajamento (com taxas
derivadas e um Índice de Intenção que pesa mais salvamentos/compartilhamentos/cliques do que
curtidas), quebra por tema/produto/idioma, e performance real de creators a partir dos posts
em Collab. As duas abas leem o **mesmo** `data/meta_organic.json` — nada é buscado ou calculado
duas vezes.

**O que é dado real da API, e o que não é:**

- Alcance, interações, salvos, compartilhamentos, visitas ao perfil, seguidores por post,
  visualizações de vídeo e tempo médio assistido (Reels) — **reais**, vêm da Graph API.
- Impressões, retenção completa (% de conclusão de vídeo), alcance não-seguidor e cliques no
  link da bio por post — **não existem** na Graph API atual (aparecem como "—" no dashboard).
- Taxa de engajamento/salvamento/compartilhamento e o Índice de Intenção
  (`salvos×3 + compart.×3 + cliques_perfil×2 + comentários×1 + curtidas×0,5`) — **calculados**
  a partir dos números reais acima; a fórmula do índice está exposta na própria tela.
- **Tema** e **produto citado** — classificados **automaticamente por palavra-chave na
  legenda** (ver `TEMA_KEYWORDS`/`PRODUTO_KEYWORDS` em `scripts/gerar_dashboard.py`). É uma
  heurística simples e pode errar (ex.: um post que menciona "Cristo" de passagem entra como
  tema "Cristo Redentor" mesmo se não for o assunto principal).
- **Idioma** — detectado por contagem de palavras comuns de PT/EN/ES na legenda; heurística,
  não é 100% confiável para legendas curtas ou mistas.
- **Público-alvo** — a classificação **mais fraca das quatro automáticas**: primeiro tenta achar
  ocasião explícita na legenda (`PUBLICO_KEYWORDS`: lua de mel, despedida de solteiro, família,
  grupo de amigos); se não achar nada, estima só pelo idioma detectado (estrangeiro → "Turista
  internacional", português → "Público local/nacional"). Isso é um chute grosseiro, não segmentação
  de audiência de verdade — trate como ponto de partida e corrija manualmente sempre que puder.
- **Gancho inicial, objetivo e CTA** — **não têm heurística automática** (são subjetivos demais
  para inferir de forma confiável). Ficam "Não classificado" até alguém preencher manualmente.
- **Creators**: alcance/interações/salvos/etc. por creator são **reais**, somados a partir dos
  posts com `collaborators` preenchido. **Custo, receita e ROI não existem em nenhuma API da
  Meta** — vêm de contrato e do Rezdy, fora do escopo deste conector.
- **Demografia dos seguidores (país, cidade, idade, gênero)** — **real**, vem do metric
  `follower_demographics` da Graph API (ver `fetch_audience_demographics` em
  `connectors/meta_organic.py`). Diferença importante em relação a tudo mais na aba: isso **não é
  por post** — é uma foto da base de seguidores no momento do fetch, então **não muda com o
  calendário** do dashboard. A própria Meta só libera esse dado com a conta tendo **pelo menos 100
  seguidores** (abaixo disso vem vazio, por privacidade — não é bug daqui) e exige a permissão
  `instagram_manage_insights` (já listada acima). Se algum dos 4 breakdowns não vier, o dashboard
  mostra "não disponível" só naquele quadro, sem esconder os outros três.
- **Tendência de conta (reach, seguidores, visualizações, visitas, cliques no link, interações)**
  — **real**, na Visão Geral, replicando os cartões de linha do Meta Business Suite. Ao contrário da
  demografia, **essa aqui segue o calendário** do dashboard normalmente — tem data por ponto, então
  o filtro de período recalcula soma e % igual às outras seções. "Seguidores" nesses gráficos é a
  **variação líquida no período** (ganhos − perdas), não o total da conta (esse fica fixo no card
  "Seguidores gerados (IG)" da Visão Geral, que soma por post, e no total atual mostrado no perfil).
  Duas origens diferentes por trás (testado contra a API real, v19.0):
  - `reach` e `follower_count` (seguidores) aceitam `metric_type=time_series` — um ponto por dia,
    barato. **`follower_count` só responde para os últimos ~30 dias**, mesmo pedindo mais (limite
    da própria Meta, não do código) — por isso o gráfico de Seguidores é mais curto que os outros,
    e datas fora dessa janela simplesmente não aparecem nele mesmo com um período maior selecionado.
  - `views`, `profile_views`, `visitas ao perfil`, `website_clicks` e `total_interactions` **só
    aceitam `metric_type=total_value`** (um número agregado, não série) — pra virar gráfico diário,
    o conector faz uma chamada por dia (em lotes de até 50 via endpoint de batch). Isso é caro, então
    fica limitado a `ACCOUNT_TIMESERIES_DAYS` (padrão 90 dias). Para uma janela maior, rode uma vez
    com `ACCOUNT_TIMESERIES_DAYS=365 python scripts/fetch_meta_organic.py` — o resultado se acumula
    em `data/meta_account_timeseries.json` (mesmo princípio do backfill de posts).

### Curadoria manual (`data/content_tags.json` e `data/creators.json`)

Esses dois arquivos são versionados (exceção no `.gitignore`) porque guardam conhecimento de
negócio que nenhuma API tem. Comece vazios (`{}`) e preencha aos poucos:

```jsonc
// data/content_tags.json — chave = id do post (campo "id" em IG_ROWS/ig-body).
// Qualquer campo aqui tem prioridade sobre a classificação automática.
{
  "17912345678901234": {
    "tema": "Cristo Redentor",
    "produto": "Doors Off",
    "idioma": "Português",
    "gancho": "Vista aérea",
    "publico": "Turista premium",
    "objetivo": "Desejo",
    "cta": "Link na bio"
  }
}
```

```jsonc
// data/creators.json — chave = username do Instagram (sem @, igual aparece no badge Collab).
{
  "parceiro_oficial": {
    "custo": 3000,
    "leads_whatsapp": 12,
    "reservas": 4,
    "receita": 14000
  }
}
```

### Backfill de histórico

Por padrão cada execução busca só os últimos `ORGANIC_LOOKBACK_DAYS` dias (90), mas
`fetch_meta_organic.py` **funde por id** com o que já existe em `data/meta_organic.json` — o
histórico só cresce, nunca é substituído. Para trazer tudo desde uma data específica pela
primeira vez (ex.: 01/01/2025), rode uma vez com uma janela maior:

```bash
ORGANIC_LOOKBACK_DAYS=600 python scripts/fetch_meta_organic.py
python scripts/gerar_dashboard.py
```

As execuções diárias seguintes podem voltar a usar o padrão de 90 dias — a fusão por id
preserva o que já foi trazido no backfill. **Stories são a exceção**: a API não expõe
histórico retroativo, então nada anterior ao início da coleta pode ser recuperado, não importa
o valor de `ORGANIC_LOOKBACK_DAYS`.

## Aba "Exportação" (dado manual de planilha)

Terceira aba do dashboard, para dado que **não vem de nenhuma API** — colado de export manual
do Meta Business Suite (posts/Reels/Stories) e, futuramente, do Ads Manager. Existe porque:

- O Business Suite dá números "oficiais" de `Visualizações` que a Graph API não expõe direito
  para todo post.
- O mesmo export de conteúdo traz, misturado, tanto os **posts publicados pela própria conta**
  quanto **posts publicados por outras contas que marcaram/mencionaram a nossa** — isso é UGC de
  creators/clientes, e a Graph API não dá nenhum acesso a dado de contas de terceiros. A aba
  separa os dois casos automaticamente comparando o campo "Nome de usuário da conta" da planilha
  com o `username` da própria conta (vindo de `meta_organic.json`).

Rodar:

```bash
python scripts/importar_planilha_manual.py caminho/export1.csv caminho/export2.csv
# ou, sem argumentos, processa tudo que estiver em data/manual_exports/
python scripts/gerar_dashboard.py
```

Funde por chave (`post_id` + coluna "Data" do export, que normalmente é `"Total"` — um
snapshot acumulado, não série diária) com o que já existe em `data/manual_content.json`:
reimportar a mesma planilha (ex.: um export mais novo do mesmo período) atualiza os posts já
conhecidos em vez de duplicar. Um export de Ads Manager (colunas como `Nome da campanha`,
`Valor usado (BRL)`) ainda não tem uma planilha real para validar o schema — os dados desse
tipo são preservados como vieram (sem normalização especulativa) e aparecem numa tabela genérica
na aba.

## Estrutura

```
connectors/
  meta_organic.py              Cliente da Graph API (Facebook + Instagram orgânico)
scripts/
  fetch_meta_organic.py        CLI que roda o conector e salva o JSON
  importar_planilha_manual.py  Importa export manual do Business Suite/Ads Manager
data/                          Saída gerada (gitignored, exceto curadoria manual)
```
