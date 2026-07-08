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

## Estrutura

```
connectors/
  meta_organic.py       Cliente da Graph API (Facebook + Instagram orgânico)
scripts/
  fetch_meta_organic.py CLI que roda o conector e salva o JSON
data/                   Saída gerada (gitignored)
```
