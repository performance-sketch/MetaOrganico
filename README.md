# MetaOrganico

Dashboard de itens orgânicos — Meta (Facebook + Instagram) e Google Ads.

Nesta primeira etapa: conector para extrair dados orgânicos do Meta (posts de Facebook e Instagram,
com métricas de alcance, impressões e engajamento). O conector do Google Ads vem em seguida.

## Configurar credenciais

1. Copie `.env.example` para `.env`.
2. Gere um Meta Access Token de longa duração em https://developers.facebook.com/tools/explorer/
   com as permissões: `pages_show_list`, `pages_read_engagement`, `instagram_basic`,
   `instagram_manage_insights`, `read_insights`.
3. Preencha `META_ACCESS_TOKEN` no `.env`. `META_PAGE_ID` e `META_IG_ACCOUNT_ID` são opcionais —
   se ausentes, o conector auto-descobre a primeira página/conta vinculada ao token.

O `.env` nunca é commitado (está no `.gitignore`).

## Rodar

```bash
pip install -r requirements.txt
python scripts/fetch_meta_organic.py
```

Gera `data/meta_organic.json` com os posts orgânicos do Facebook e Instagram dos últimos
`ORGANIC_LOOKBACK_DAYS` dias (padrão 90).

## Estrutura

```
connectors/
  meta_organic.py       Cliente da Graph API (Facebook + Instagram orgânico)
scripts/
  fetch_meta_organic.py CLI que roda o conector e salva o JSON
data/                   Saída gerada (gitignored)
```
