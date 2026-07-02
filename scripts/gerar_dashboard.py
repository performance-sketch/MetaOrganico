#!/usr/bin/env python3
"""
Gera index.html (dashboard) a partir de data/meta_organic.json.
Run: python scripts/gerar_dashboard.py
"""
import json
import pathlib
from datetime import datetime, timedelta

ROOT          = pathlib.Path(__file__).parent.parent
DATA_FILE     = ROOT / "data" / "meta_organic.json"
ADS_FILE      = ROOT / "data" / "meta_ads_snapshot.json"
STORIES_FILE  = ROOT / "data" / "meta_stories_history.json"
INDEX_FILE    = ROOT / "index.html"


def fmt_int(n):
    return f"{n:,}".replace(",", ".") if n is not None else "—"


def media_format(post):
    t = (post.get("media_product_type") or post.get("media_type") or "").upper()
    if t in ("REELS", "REEL"):
        return "Reel"
    if t == "CAROUSEL_ALBUM":
        return "Carrossel"
    if t == "VIDEO":
        return "Vídeo"
    if t in ("IMAGE", "FEED"):
        return "Feed"
    return t.title() or "?"


def build_ig_rows(media):
    rows = []
    for p in media:
        ins = p.get("insights", {}) or {}
        rows.append({
            "id": p.get("id", ""),
            "data": (p.get("timestamp") or "")[:10],
            "formato": media_format(p),
            "legenda": (p.get("caption") or "")[:140],
            "link": p.get("permalink", ""),
            "thumb": p.get("thumbnail_url") or p.get("media_url") or "",
            "curtidas": p.get("like_count", 0) or 0,
            "comentarios": p.get("comments_count", 0) or 0,
            "alcance": ins.get("reach"),
            "salvos": ins.get("saved"),
            "compartilhamentos": ins.get("shares"),
            "visitas_perfil": ins.get("profile_visits"),
            "seguidores": ins.get("follows"),
            "interacoes": ins.get("total_interactions"),
            "visualizacoes": ins.get("views"),
            "tempo_medio_assistido": ins.get("ig_reels_avg_watch_time"),
        })
    return rows


def build_fb_rows(posts):
    rows = []
    for p in posts:
        rows.append({
            "id": p.get("id", ""),
            "data": p.get("criado_em", ""),
            "legenda": (p.get("mensagem") or "")[:140],
            "curtidas": p.get("curtidas"),
            "comentarios": p.get("comentarios"),
            "compartilhamentos": p.get("compartilhamentos"),
            "cliques": p.get("cliques"),
            "video_views": p.get("video_views"),
        })
    return rows


def build_story_rows(stories):
    rows = []
    for s in stories:
        ins = s.get("insights", {}) or {}
        rows.append({
            "id": s.get("id", ""),
            "data": (s.get("timestamp") or "")[:10],
            "link": s.get("permalink", ""),
            "thumb": s.get("thumbnail_url") or s.get("media_url") or "",
            "alcance": ins.get("reach"),
            "respostas": ins.get("replies"),
            "navegacao": ins.get("navigation"),
            "visitas_perfil": ins.get("profile_visits"),
            "seguidores": ins.get("follows"),
            "interacoes": ins.get("total_interactions"),
            "cliques_link": ins.get("link_clicks"),
            "compartilhamentos": ins.get("shares"),
            "atividade_perfil": ins.get("profile_activity"),
        })
    rows.sort(key=lambda r: r["data"], reverse=True)
    return rows


def agg_by_format(ig_rows):
    grupos = {}
    for r in ig_rows:
        g = grupos.setdefault(r["formato"], {
            "formato": r["formato"], "n": 0,
            "alcance": [], "interacoes": [], "salvos": [], "compartilhamentos": [], "visitas_perfil": [],
        })
        g["n"] += 1
        for campo in ("alcance", "interacoes", "salvos", "compartilhamentos", "visitas_perfil"):
            v = r.get(campo)
            if v is not None:
                g[campo].append(v)

    def media(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    resultado = []
    for g in grupos.values():
        resultado.append({
            "formato": g["formato"], "n": g["n"],
            "alcance_medio": media(g["alcance"]),
            "interacoes_media": media(g["interacoes"]),
            "salvos_medio": media(g["salvos"]),
            "compartilhamentos_medio": media(g["compartilhamentos"]),
            "visitas_perfil_media": media(g["visitas_perfil"]),
        })
    resultado.sort(key=lambda x: x["alcance_medio"] or 0, reverse=True)
    return resultado


def top_n(rows, campo, n=10):
    validos = [r for r in rows if r.get(campo) is not None]
    return sorted(validos, key=lambda r: r[campo], reverse=True)[:n]


def main():
    dados = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    perfil    = dados.get("instagram", {}).get("perfil", {})
    ig_media  = dados.get("instagram", {}).get("media", [])
    fb_posts  = dados.get("facebook_posts", [])

    ig_rows = build_ig_rows(ig_media)
    fb_rows = build_fb_rows(fb_posts)

    total_alcance    = sum(r["alcance"] for r in ig_rows if r["alcance"] is not None)
    total_interacoes = sum(r["interacoes"] for r in ig_rows if r["interacoes"] is not None)
    total_visitas    = sum(r["visitas_perfil"] for r in ig_rows if r["visitas_perfil"] is not None)
    total_seguidores = sum(r["seguidores"] for r in ig_rows if r["seguidores"] is not None)

    por_formato = agg_by_format(ig_rows)

    corte_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    ig_30d = [r for r in ig_rows if r["data"] >= corte_30d]
    organico_30d = {
        "alcance":    sum(r["alcance"] for r in ig_30d if r["alcance"] is not None),
        "interacoes": sum(r["interacoes"] for r in ig_30d if r["interacoes"] is not None),
        "visitas_perfil": sum(r["visitas_perfil"] for r in ig_30d if r["visitas_perfil"] is not None),
        "posts": len(ig_30d),
    }

    ads = None
    if ADS_FILE.exists():
        ads = json.loads(ADS_FILE.read_text(encoding="utf-8")).get("d30")

    stories = []
    if STORIES_FILE.exists():
        stories = json.loads(STORIES_FILE.read_text(encoding="utf-8"))
    story_rows = build_story_rows(stories)

    def soma_stories(campo):
        return sum(r[campo] for r in story_rows if r.get(campo) is not None)

    def media_stories(campo):
        vals = [r[campo] for r in story_rows if r.get(campo) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    stories_totais = {
        "n": len(story_rows),
        "alcance": soma_stories("alcance"),
        "respostas": soma_stories("respostas"),
        "navegacao": soma_stories("navegacao"),
        "visitas_perfil": soma_stories("visitas_perfil"),
        "cliques_link": soma_stories("cliques_link"),
        "alcance_medio": media_stories("alcance"),
        "interacoes_media": media_stories("interacoes"),
    }
    story_rankings = {
        "alcance":    top_n(story_rows, "alcance", 5),
        "interacoes": top_n(story_rows, "interacoes", 5),
    }

    rankings = {
        "alcance":      top_n(ig_rows, "alcance"),
        "interacoes":   top_n(ig_rows, "interacoes"),
        "salvos":       top_n(ig_rows, "salvos"),
        "compartilhamentos": top_n(ig_rows, "compartilhamentos"),
        "visitas_perfil": top_n(ig_rows, "visitas_perfil"),
    }

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    ig_rows_json      = json.dumps(ig_rows, ensure_ascii=False)
    fb_rows_json      = json.dumps(fb_rows, ensure_ascii=False)
    por_formato_json  = json.dumps(por_formato, ensure_ascii=False)
    rankings_json     = json.dumps(rankings, ensure_ascii=False)
    perfil_json       = json.dumps(perfil, ensure_ascii=False)
    ads_json           = json.dumps(ads, ensure_ascii=False)
    organico_30d_json  = json.dumps(organico_30d, ensure_ascii=False)
    story_rows_json    = json.dumps(story_rows, ensure_ascii=False)
    stories_totais_json = json.dumps(stories_totais, ensure_ascii=False)
    story_rankings_json = json.dumps(story_rankings, ensure_ascii=False)

    def safe(s):
        """Evita que uma legenda contendo '</script' feche a tag prematuramente."""
        return s.replace("</script", "<\\/script")

    ig_rows_json         = safe(ig_rows_json)
    fb_rows_json         = safe(fb_rows_json)
    por_formato_json     = safe(por_formato_json)
    rankings_json        = safe(rankings_json)
    perfil_json          = safe(perfil_json)
    ads_json             = safe(ads_json)
    organico_30d_json    = safe(organico_30d_json)
    story_rows_json      = safe(story_rows_json)
    stories_totais_json  = safe(stories_totais_json)
    story_rankings_json  = safe(story_rankings_json)

    if ads:
        ads_section_html = f"""
  <!-- KPIs Pagos -->
  <div class="card mb-5">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
      <div style="font-weight:600;font-size:.9rem">💰 Meta Ads — Pago (últimos 30 dias)</div>
      <span class="badge badge-gray">fonte: REPORTCLAUDE</span>
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
      <div><div class="kpi-label">Gasto</div><div class="kpi-val">R$ {ads.get('gasto', 0):,.0f}</div></div>
      <div><div class="kpi-label">Impressões</div><div class="kpi-val">{fmt_int(ads.get('impressoes'))}</div></div>
      <div><div class="kpi-label">Alcance</div><div class="kpi-val">{fmt_int(ads.get('alcance'))}</div></div>
      <div><div class="kpi-label">Cliques</div><div class="kpi-val">{fmt_int(ads.get('cliques'))}</div></div>
      <div><div class="kpi-label">CTR</div><div class="kpi-val">{ads.get('ctr', 0)}%</div></div>
      <div><div class="kpi-label">CPC</div><div class="kpi-val">R$ {ads.get('cpc', 0)}</div></div>
      <div><div class="kpi-label">CPM</div><div class="kpi-val">R$ {ads.get('cpm', 0)}</div></div>
      <div><div class="kpi-label">Conversas</div><div class="kpi-val">{fmt_int(ads.get('conversas'))}</div></div>
      <div><div class="kpi-label">Compras (Meta)</div><div class="kpi-val">{fmt_int(ads.get('compras_meta'))}</div></div>
      <div><div class="kpi-label">ROAS</div><div class="kpi-val">{ads.get('roas', 0)}x</div></div>
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">⚖️ Orgânico (IG) x Pago (Meta Ads) — últimos 30 dias</div>
    <canvas id="chartOrganicoVsPago" height="90"></canvas>
  </div>
"""
    else:
        ads_section_html = """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">💰 KPIs pagos (Meta Ads) não disponível — rode <code>python scripts/fetch_meta_ads_snapshot.py</code> para trazer o snapshot do REPORTCLAUDE.</div>
  </div>
"""

    if story_rows:
        stories_section_html = f"""
  <div class="card mb-5" style="border-color:var(--cyan);background:rgba(6,182,212,.06)">
    <div class="text-sm">ℹ️ <strong>Stories</strong>: a API do Instagram só expõe stories ativos (até 24h após publicar) — não existe histórico retroativo. Os {stories_totais['n']} stories abaixo são os acumulados desde que este dashboard passou a rodar periodicamente; o total cresce a cada execução do <code>fetch_meta_organic.py</code>.</div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📸 Instagram Stories — acumulado ({stories_totais['n']} stories)</div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
      <div><div class="kpi-label">Stories capturados</div><div class="kpi-val">{stories_totais['n']}</div></div>
      <div><div class="kpi-label">Alcance total</div><div class="kpi-val">{fmt_int(stories_totais['alcance'])}</div></div>
      <div><div class="kpi-label">Alcance médio</div><div class="kpi-val">{fmt_int(stories_totais['alcance_medio'])}</div></div>
      <div><div class="kpi-label">Interações médias</div><div class="kpi-val">{fmt_int(stories_totais['interacoes_media'])}</div></div>
      <div><div class="kpi-label">Visitas ao perfil</div><div class="kpi-val">{fmt_int(stories_totais['visitas_perfil'])}</div></div>
      <div><div class="kpi-label">Cliques no link</div><div class="kpi-val">{fmt_int(stories_totais['cliques_link'])}</div></div>
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Top 5 — Alcance</div>
        <div id="top3-stories-alcance" class="top3-wrap" style="grid-template-columns:repeat(5,1fr)"></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Top 5 — Interações (indício de intenção de compra)</div>
        <div id="top3-stories-interacoes" class="top3-wrap" style="grid-template-columns:repeat(5,1fr)"></div>
      </div>
    </div>
    <div style="overflow-x:auto;max-height:400px">
      <table>
        <thead><tr>
          <th>Data</th><th style="text-align:right">Alcance</th><th style="text-align:right">Interações</th>
          <th style="text-align:right">Respostas</th><th style="text-align:right">Navegação</th>
          <th style="text-align:right">Visitas perfil</th><th style="text-align:right">Cliques link</th>
          <th style="text-align:right">Compart.</th><th>Link</th>
        </tr></thead>
        <tbody id="stories-body"></tbody>
      </table>
    </div>
  </div>
"""
    else:
        stories_section_html = """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">📸 Nenhum Story capturado ainda — rode <code>python scripts/fetch_meta_organic.py</code> enquanto houver stories ativos (até 24h após publicar) para começar a acumular histórico.</div>
  </div>
"""

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MetaOrganico — Vertical Rio</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0f172a; --surface:#1e293b; --surface2:#263248;
    --border:#334155; --text:#f1f5f9; --sub:#94a3b8;
    --indigo:#6366f1; --green:#22c55e; --amber:#f59e0b;
    --red:#ef4444; --cyan:#06b6d4; --pink:#ec4899;
  }}
  body {{ background:var(--bg); color:var(--text); font-family:'Inter',system-ui,sans-serif; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; }}
  .kpi-val {{ font-size:1.75rem; font-weight:700; line-height:1.1; }}
  .kpi-label {{ font-size:0.72rem; color:var(--sub); text-transform:uppercase; letter-spacing:.05em; margin-bottom:4px; }}
  .badge {{ display:inline-block; padding:2px 8px; border-radius:99px; font-size:.7rem; font-weight:600; }}
  .badge-pink {{ background:rgba(236,72,153,.15); color:#f472b6; }}
  .badge-blue {{ background:rgba(99,102,241,.15); color:#818cf8; }}
  .badge-gray {{ background:rgba(148,163,184,.1); color:#94a3b8; }}
  table {{ width:100%; border-collapse:collapse; font-size:.82rem; }}
  th {{ color:var(--sub); font-weight:500; text-align:left; padding:8px 12px; border-bottom:1px solid var(--border); font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; white-space:nowrap; }}
  td {{ padding:9px 12px; border-bottom:1px solid rgba(51,65,85,.5); }}
  tr:last-child td {{ border-bottom:none; }}
  tr:hover td {{ background:rgba(99,102,241,.04); }}
  a.perm {{ color:var(--indigo); text-decoration:none; }}
  a.perm:hover {{ text-decoration:underline; }}
  ::-webkit-scrollbar {{ width:6px; height:6px; }}
  ::-webkit-scrollbar-track {{ background:var(--bg); }}
  ::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:3px; }}
  .top3-wrap {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-bottom:16px; }}
  .top3-card {{ position:relative; display:block; border-radius:10px; overflow:hidden; background:var(--surface2); border:1px solid var(--border); text-decoration:none; color:inherit; }}
  .top3-card img {{ width:100%; aspect-ratio:1/1; object-fit:cover; display:block; background:var(--bg); }}
  .top3-rank {{ position:absolute; top:6px; left:6px; width:22px; height:22px; border-radius:99px; background:rgba(15,23,42,.85); color:#fff; font-size:.72rem; font-weight:700; display:flex; align-items:center; justify-content:center; }}
  .top3-metric {{ position:absolute; bottom:0; left:0; right:0; padding:6px 8px; background:linear-gradient(0deg,rgba(15,23,42,.92),transparent); font-size:.78rem; font-weight:700; }}
  .top3-metric small {{ display:block; font-size:.62rem; font-weight:500; color:var(--sub); text-transform:uppercase; letter-spacing:.03em; }}
</style>
</head>
<body class="p-4 md:p-8 max-w-[1400px] mx-auto">

  <div class="flex items-center justify-between mb-6 flex-wrap gap-2">
    <div>
      <h1 class="text-xl font-bold">📱 MetaOrganico — Vertical Rio</h1>
      <div class="text-sm" style="color:var(--sub)">Instagram @{perfil.get('username','?')} · {fmt_int(perfil.get('followers_count'))} seguidores</div>
    </div>
    <div class="text-sm" style="color:var(--sub)">
      <span style="color:var(--green)">●</span> Gerado em <strong style="color:var(--text)">{gerado_em}</strong>
    </div>
  </div>

  <div class="card mb-5" style="border-color:var(--amber);background:rgba(245,158,11,.06)">
    <div class="text-sm">⚠️ <strong>Facebook</strong>: a Graph API descontinuou alcance/impressões por post globalmente — esses campos não existem mais via API (só no export manual do Meta Business Suite). Curtidas/comentários/compartilhamentos do Facebook dependem da permissão <code>pages_read_user_content</code> no token. <strong>Instagram</strong> tem dados completos abaixo.</div>
  </div>

  <!-- KPIs -->
  <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-5">
    <div class="card"><div class="kpi-label">Posts Instagram</div><div class="kpi-val">{len(ig_rows)}</div></div>
    <div class="card"><div class="kpi-label">Posts Facebook</div><div class="kpi-val">{len(fb_rows)}</div></div>
    <div class="card"><div class="kpi-label">Alcance total (IG)</div><div class="kpi-val">{fmt_int(total_alcance)}</div></div>
    <div class="card"><div class="kpi-label">Interações (IG)</div><div class="kpi-val">{fmt_int(total_interacoes)}</div></div>
    <div class="card"><div class="kpi-label">Visitas ao perfil (IG)</div><div class="kpi-val">{fmt_int(total_visitas)}</div></div>
    <div class="card"><div class="kpi-label">Seguidores gerados (IG)</div><div class="kpi-val">{fmt_int(total_seguidores)}</div></div>
  </div>
{ads_section_html}
{stories_section_html}
  <!-- Por formato -->
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📊 Instagram — Desempenho médio por formato</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Formato</th><th style="text-align:right">Posts</th>
          <th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th>
          <th style="text-align:right">Salvos médios</th><th style="text-align:right">Compart. médios</th>
          <th style="text-align:right">Visitas perfil médias</th>
        </tr></thead>
        <tbody id="formato-body"></tbody>
      </table>
    </div>
  </div>

  <canvas id="chartFormato" height="90" class="mb-5"></canvas>

  <!-- Rankings -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-5">
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🏆 Top 10 — Alcance (Instagram)</div>
      <div id="top3-alcance" class="top3-wrap"></div>
      <div style="overflow-x:auto"><table><thead><tr><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Alcance</th></tr></thead><tbody id="rank-alcance"></tbody></table></div>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🏆 Top 10 — Interações (Instagram)</div>
      <div id="top3-interacoes" class="top3-wrap"></div>
      <div style="overflow-x:auto"><table><thead><tr><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Interações</th></tr></thead><tbody id="rank-interacoes"></tbody></table></div>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🏆 Top 10 — Visitas ao perfil geradas (Instagram)</div>
      <div id="top3-visitas" class="top3-wrap"></div>
      <div style="overflow-x:auto"><table><thead><tr><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Visitas</th></tr></thead><tbody id="rank-visitas"></tbody></table></div>
    </div>
    <div class="card">
      <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🏆 Top 10 — Salvamentos (Instagram)</div>
      <div id="top3-salvos" class="top3-wrap"></div>
      <div style="overflow-x:auto"><table><thead><tr><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Salvos</th></tr></thead><tbody id="rank-salvos"></tbody></table></div>
    </div>
  </div>

  <!-- Tabela completa -->
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📋 Todos os posts — Instagram ({len(ig_rows)})</div>
    <div style="overflow-x:auto;max-height:500px">
      <table>
        <thead><tr>
          <th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Alcance</th>
          <th style="text-align:right">Interações</th><th style="text-align:right">Salvos</th>
          <th style="text-align:right">Compart.</th><th style="text-align:right">Visitas perfil</th>
          <th style="text-align:right">Seguidores</th><th>Link</th>
        </tr></thead>
        <tbody id="ig-body"></tbody>
      </table>
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📋 Todos os posts — Facebook ({len(fb_rows)})</div>
    <div class="text-xs mb-3" style="color:var(--sub)">Alcance/impressões não disponíveis via API (ver aviso acima).</div>
    <div style="overflow-x:auto;max-height:500px">
      <table>
        <thead><tr>
          <th>Data</th><th>Legenda</th><th style="text-align:right">Curtidas</th>
          <th style="text-align:right">Comentários</th><th style="text-align:right">Compart.</th>
          <th style="text-align:right">Cliques</th><th style="text-align:right">Video views</th>
        </tr></thead>
        <tbody id="fb-body"></tbody>
      </table>
    </div>
  </div>

<script>
const IG_ROWS     = {ig_rows_json};
const FB_ROWS     = {fb_rows_json};
const POR_FORMATO = {por_formato_json};
const RANKINGS    = {rankings_json};
const ADS           = {ads_json};
const ORGANICO_30D  = {organico_30d_json};
const STORY_ROWS     = {story_rows_json};
const STORIES_RANKINGS = {story_rankings_json};

const fN = v => v === null || v === undefined ? '—' : Number(v).toLocaleString('pt-BR');
const trunc = (s, n) => (s || '').length > n ? s.slice(0, n) + '…' : (s || '—');

function preencherTabela(id, rows, renderRow) {{
  const el = document.getElementById(id);
  el.innerHTML = rows.map(renderRow).join('');
}}

preencherTabela('formato-body', POR_FORMATO, f => `<tr>
  <td>${{f.formato}}</td><td style="text-align:right">${{f.n}}</td>
  <td style="text-align:right">${{fN(f.alcance_medio)}}</td><td style="text-align:right">${{fN(f.interacoes_media)}}</td>
  <td style="text-align:right">${{fN(f.salvos_medio)}}</td><td style="text-align:right">${{fN(f.compartilhamentos_medio)}}</td>
  <td style="text-align:right">${{fN(f.visitas_perfil_media)}}</td>
</tr>`);

const rankRow = (campo) => r => `<tr>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td><span class="badge badge-pink">${{r.formato}}</span></td>
  <td title="${{(r.legenda||'').replace(/"/g,'&quot;')}}">${{trunc(r.legenda, 40)}}</td>
  <td style="text-align:right;font-weight:600">${{fN(r[campo])}}</td>
</tr>`;

preencherTabela('rank-alcance',      RANKINGS.alcance,      rankRow('alcance'));
preencherTabela('rank-interacoes',   RANKINGS.interacoes,   rankRow('interacoes'));
preencherTabela('rank-visitas',      RANKINGS.visitas_perfil, rankRow('visitas_perfil'));
preencherTabela('rank-salvos',       RANKINGS.salvos,       rankRow('salvos'));

const rotuloMetrica = {{ alcance:'Alcance', interacoes:'Interações', visitas_perfil:'Visitas ao perfil', salvos:'Salvos' }};
function renderTop3(id, rows, campo, n) {{
  n = n || 3;
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = rows.slice(0, n).map((r, i) => `
    <a class="top3-card" href="${{r.link || '#'}}" target="_blank" title="${{(r.legenda||'').replace(/"/g,'&quot;')}}">
      <span class="top3-rank">#${{i+1}}</span>
      ${{r.thumb ? `<img src="${{r.thumb}}" loading="lazy" alt="">` : `<div style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.7rem">sem imagem</div>`}}
      <div class="top3-metric">${{fN(r[campo])}}<small>${{rotuloMetrica[campo]}} · ${{r.formato || 'Story'}}</small></div>
    </a>`).join('');
}}
renderTop3('top3-alcance',    RANKINGS.alcance,        'alcance');
renderTop3('top3-interacoes', RANKINGS.interacoes,     'interacoes');
renderTop3('top3-visitas',    RANKINGS.visitas_perfil, 'visitas_perfil');
renderTop3('top3-salvos',     RANKINGS.salvos,         'salvos');
renderTop3('top3-stories-alcance',    STORIES_RANKINGS.alcance,    'alcance', 5);
renderTop3('top3-stories-interacoes', STORIES_RANKINGS.interacoes, 'interacoes', 5);

preencherTabela('ig-body', IG_ROWS, r => `<tr>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td><span class="badge badge-pink">${{r.formato}}</span></td>
  <td title="${{(r.legenda||'').replace(/"/g,'&quot;')}}">${{trunc(r.legenda, 50)}}</td>
  <td style="text-align:right">${{fN(r.alcance)}}</td>
  <td style="text-align:right">${{fN(r.interacoes)}}</td>
  <td style="text-align:right">${{fN(r.salvos)}}</td>
  <td style="text-align:right">${{fN(r.compartilhamentos)}}</td>
  <td style="text-align:right">${{fN(r.visitas_perfil)}}</td>
  <td style="text-align:right">${{fN(r.seguidores)}}</td>
  <td>${{r.link ? `<a class="perm" href="${{r.link}}" target="_blank">abrir</a>` : '—'}}</td>
</tr>`);

preencherTabela('fb-body', FB_ROWS, r => `<tr>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td title="${{(r.legenda||'').replace(/"/g,'&quot;')}}">${{trunc(r.legenda, 60)}}</td>
  <td style="text-align:right">${{fN(r.curtidas)}}</td>
  <td style="text-align:right">${{fN(r.comentarios)}}</td>
  <td style="text-align:right">${{fN(r.compartilhamentos)}}</td>
  <td style="text-align:right">${{fN(r.cliques)}}</td>
  <td style="text-align:right">${{fN(r.video_views)}}</td>
</tr>`);

preencherTabela('stories-body', STORY_ROWS, r => `<tr>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td style="text-align:right">${{fN(r.alcance)}}</td>
  <td style="text-align:right">${{fN(r.interacoes)}}</td>
  <td style="text-align:right">${{fN(r.respostas)}}</td>
  <td style="text-align:right">${{fN(r.navegacao)}}</td>
  <td style="text-align:right">${{fN(r.visitas_perfil)}}</td>
  <td style="text-align:right">${{fN(r.cliques_link)}}</td>
  <td style="text-align:right">${{fN(r.compartilhamentos)}}</td>
  <td>${{r.link ? `<a class="perm" href="${{r.link}}" target="_blank">abrir</a>` : '—'}}</td>
</tr>`);

new Chart(document.getElementById('chartFormato'), {{
  type: 'bar',
  data: {{
    labels: POR_FORMATO.map(f => f.formato),
    datasets: [
      {{ label: 'Alcance médio', data: POR_FORMATO.map(f => f.alcance_medio), backgroundColor: '#6366f1' }},
      {{ label: 'Interações médias', data: POR_FORMATO.map(f => f.interacoes_media), backgroundColor: '#ec4899' }},
    ]
  }},
  options: {{ responsive:true, plugins:{{legend:{{labels:{{color:'#f1f5f9'}}}}}},
    scales:{{ x:{{ticks:{{color:'#94a3b8'}},grid:{{display:false}}}}, y:{{ticks:{{color:'#94a3b8'}},grid:{{color:'rgba(51,65,85,.4)'}}}} }} }}
}});

if (ADS) {{
  new Chart(document.getElementById('chartOrganicoVsPago'), {{
    type: 'bar',
    data: {{
      labels: ['Alcance', 'Cliques (pago) / Interações (orgânico)'],
      datasets: [
        {{ label: `Orgânico (IG, ${{ORGANICO_30D.posts}} posts)`, data: [ORGANICO_30D.alcance, ORGANICO_30D.interacoes], backgroundColor: '#ec4899' }},
        {{ label: 'Pago (Meta Ads)', data: [ADS.alcance, ADS.cliques], backgroundColor: '#22c55e' }},
      ]
    }},
    options: {{ responsive:true, plugins:{{legend:{{labels:{{color:'#f1f5f9'}}}}}},
      scales:{{ x:{{ticks:{{color:'#94a3b8'}},grid:{{display:false}}}}, y:{{ticks:{{color:'#94a3b8'}},grid:{{color:'rgba(51,65,85,.4)'}}}} }} }}
  }});
}}
</script>
</body>
</html>
"""

    INDEX_FILE.write_text(html, encoding="utf-8")
    print(f"OK: index.html gerado ({len(html):,} chars) — {len(ig_rows)} posts IG, {len(fb_rows)} posts FB")


if __name__ == "__main__":
    main()
