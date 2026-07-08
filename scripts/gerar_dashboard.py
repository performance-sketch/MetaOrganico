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
TAGS_FILE     = ROOT / "data" / "content_tags.json"
CREATORS_FILE = ROOT / "data" / "creators.json"
INDEX_FILE    = ROOT / "index.html"

# Classificação automática por palavras-chave na legenda — é uma heurística
# simples, não uma leitura de intenção real do post. Serve para dar um ponto
# de partida em "por tipo de conteúdo"; pode e deve ser corrigida manualmente
# via data/content_tags.json (id do post -> {tema, produto, idioma, gancho,
# publico, objetivo, cta}), que sempre tem prioridade sobre a heurística.
TEMA_KEYWORDS = [
    ("Cristo Redentor", ["cristo", "redeemer", "corcovado"]),
    ("Pão de Açúcar", ["pão de açúcar", "pao de acucar", "sugarloaf"]),
    ("Praias", ["praia", "beach", "ipanema", "copacabana", "leblon"]),
    ("Bastidores", ["bastidor", "behind the scenes", "backstage", "making of"]),
    ("Segurança", ["segurança", "seguranca", "safety", "manutenção"]),
    ("Luxo", ["luxo", "luxury", " vip ", "exclusiv"]),
]
PRODUTO_KEYWORDS = [
    ("Doors Off", ["doors off", "doors-off", "doorsoff", "portas abertas"]),
    ("Doors On", ["doors on", "doors-on", "doorson"]),
    ("45 min", ["45 min", "45min", "45 minutos"]),
    ("30 min", ["30 min", "30min", "30 minutos"]),
    ("Gift Card", ["gift card", "giftcard"]),
]
IDIOMA_MARCADORES = [
    ("Português", ["você", "voo", "não", "reserva", "experiência"]),
    ("Español", ["vuelo", "reserva", "experiencia", " tú ", "increíble"]),
    ("English", [" the ", " you ", " book ", " flight ", " experience "]),
]


def _match_keywords(texto, tabela):
    t = f" {(texto or '').lower()} "
    for rotulo, palavras in tabela:
        if any(p in t for p in palavras):
            return rotulo
    return None


def detectar_idioma(legenda):
    t = f" {(legenda or '').lower()} "
    pontos = {rotulo: sum(1 for m in marcadores if m in t) for rotulo, marcadores in IDIOMA_MARCADORES}
    rotulo, melhor = max(pontos.items(), key=lambda kv: kv[1])
    return rotulo if melhor > 0 else "Não identificado"


def load_json_or_empty(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def classificar_post(post_id, legenda, tem_collab, tags_manuais):
    """Tags manuais (data/content_tags.json) sempre vencem a heurística automática."""
    manual = tags_manuais.get(post_id, {})
    tema = manual.get("tema") or _match_keywords(legenda, TEMA_KEYWORDS) or ("Creators" if tem_collab else "Não classificado")
    return {
        "tema": tema,
        "produto": manual.get("produto") or _match_keywords(legenda, PRODUTO_KEYWORDS) or "Não identificado",
        "idioma": manual.get("idioma") or detectar_idioma(legenda),
        "gancho": manual.get("gancho") or "Não classificado",
        "publico": manual.get("publico") or "Não classificado",
        "objetivo": manual.get("objetivo") or "Não classificado",
        "cta": manual.get("cta") or "Não classificado",
        "classificado_manualmente": bool(manual),
    }


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


def _pct(numerador, denominador):
    if numerador is None or not denominador:
        return None
    return round(numerador / denominador * 100, 2)


def build_ig_rows(media, tags_manuais):
    rows = []
    for p in media:
        ins = p.get("insights", {}) or {}
        legenda_completa = p.get("caption") or ""
        colaboradores = p.get("collaborators") or []
        alcance = ins.get("reach")
        salvos = ins.get("saved")
        compart = ins.get("shares")
        interacoes = ins.get("total_interactions")
        visitas = ins.get("profile_visits")
        curtidas = p.get("like_count", 0) or 0
        comentarios = p.get("comments_count", 0) or 0

        partes_intencao = [v for v in (salvos, compart, visitas, comentarios, curtidas) if v is not None]
        indice_intencao = round(
            (salvos or 0) * 3 + (compart or 0) * 3 + (visitas or 0) * 2 + (comentarios or 0) * 1 + (curtidas or 0) * 0.5, 1
        ) if partes_intencao else None

        row = {
            "id": p.get("id", ""),
            "data": (p.get("timestamp") or "")[:10],
            "formato": media_format(p),
            "legenda": legenda_completa[:140],
            "link": p.get("permalink", ""),
            "thumb": p.get("thumbnail_url") or p.get("media_url") or "",
            "colaboradores": colaboradores,
            "curtidas": curtidas,
            "comentarios": comentarios,
            "alcance": alcance,
            "salvos": salvos,
            "compartilhamentos": compart,
            "visitas_perfil": visitas,
            "seguidores": ins.get("follows"),
            "interacoes": interacoes,
            "visualizacoes": ins.get("views"),
            "tempo_medio_assistido": ins.get("ig_reels_avg_watch_time"),
            "taxa_engajamento": _pct(interacoes, alcance),
            "taxa_salvamento": _pct(salvos, alcance),
            "taxa_compartilhamento": _pct(compart, alcance),
            "indice_intencao": indice_intencao,
        }
        row.update(classificar_post(row["id"], legenda_completa, bool(colaboradores), tags_manuais))
        rows.append(row)
    return rows


def build_fb_rows(posts):
    rows = []
    for p in posts:
        rows.append({
            "id": p.get("id", ""),
            "data": p.get("criado_em", ""),
            "legenda": (p.get("mensagem") or "")[:140],
            "thumb": p.get("thumb") or "",
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


def agg_by_dimensao(ig_rows, campo):
    """Agrupa posts por uma dimensão de conteúdo (tema, produto ou idioma)."""
    grupos = {}
    for r in ig_rows:
        chave = r.get(campo) or "Não classificado"
        g = grupos.setdefault(chave, {"valor": chave, "n": 0, "alcance": [], "interacoes": [], "indice_intencao": []})
        g["n"] += 1
        for campo_origem, campo_grupo in (("alcance", "alcance"), ("interacoes", "interacoes"), ("indice_intencao", "indice_intencao")):
            v = r.get(campo_origem)
            if v is not None:
                g[campo_grupo].append(v)

    def media(lst):
        return round(sum(lst) / len(lst), 1) if lst else None

    resultado = []
    for g in grupos.values():
        resultado.append({
            "valor": g["valor"], "n": g["n"],
            "alcance_total": sum(g["alcance"]),
            "alcance_medio": media(g["alcance"]),
            "interacoes_media": media(g["interacoes"]),
            "indice_intencao_medio": media(g["indice_intencao"]),
        })
    resultado.sort(key=lambda x: x["alcance_total"], reverse=True)
    return resultado


def build_creator_rows(ig_rows, creators_manual):
    """Performance orgânica real por creator, a partir dos posts marcados como
    Collab. Custo/receita/ROI são manuais (data/creators.json) — a Graph API
    não tem esse dado, ele vive em contrato + Rezdy."""
    por_creator = {}
    for r in ig_rows:
        for username in r["colaboradores"]:
            c = por_creator.setdefault(username, {
                "username": username, "n_posts": 0, "alcance": 0, "interacoes": 0,
                "salvos": 0, "compartilhamentos": 0, "visitas_perfil": 0, "seguidores": 0,
            })
            c["n_posts"] += 1
            for campo in ("alcance", "interacoes", "salvos", "compartilhamentos", "visitas_perfil", "seguidores"):
                v = r.get(campo)
                if v is not None:
                    c[campo] += v

    resultado = []
    for username, c in por_creator.items():
        manual = creators_manual.get(username, {})
        custo, receita = manual.get("custo"), manual.get("receita")
        resultado.append({
            **c,
            "custo": custo,
            "leads_whatsapp": manual.get("leads_whatsapp"),
            "reservas": manual.get("reservas"),
            "receita": receita,
            "roi": round(receita / custo, 2) if custo and receita else None,
        })
    resultado.sort(key=lambda c: c["alcance"], reverse=True)
    return resultado


def main():
    dados = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    perfil    = dados.get("instagram", {}).get("perfil", {})
    ig_media  = dados.get("instagram", {}).get("media", [])
    fb_posts  = dados.get("facebook_posts", [])

    tags_manuais    = load_json_or_empty(TAGS_FILE)
    creators_manual = load_json_or_empty(CREATORS_FILE)

    ig_rows = build_ig_rows(ig_media, tags_manuais)
    fb_rows = build_fb_rows(fb_posts)

    total_alcance    = sum(r["alcance"] for r in ig_rows if r["alcance"] is not None)
    total_interacoes = sum(r["interacoes"] for r in ig_rows if r["interacoes"] is not None)
    total_visitas    = sum(r["visitas_perfil"] for r in ig_rows if r["visitas_perfil"] is not None)
    total_seguidores = sum(r["seguidores"] for r in ig_rows if r["seguidores"] is not None)
    total_video_views = sum(r["visualizacoes"] for r in ig_rows if r["visualizacoes"] is not None)
    total_curtidas    = sum(r["curtidas"] for r in ig_rows if r["curtidas"] is not None)
    total_comentarios = sum(r["comentarios"] for r in ig_rows if r["comentarios"] is not None)
    total_salvos      = sum(r["salvos"] for r in ig_rows if r["salvos"] is not None)
    total_compart_ig  = sum(r["compartilhamentos"] for r in ig_rows if r["compartilhamentos"] is not None)

    def media_campo(campo):
        vals = [r[campo] for r in ig_rows if r.get(campo) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    taxas_medias = {
        "engajamento": media_campo("taxa_engajamento"),
        "salvamento": media_campo("taxa_salvamento"),
        "compartilhamento": media_campo("taxa_compartilhamento"),
    }
    ranking_intencao = top_n(ig_rows, "indice_intencao", 10)

    por_tema    = agg_by_dimensao(ig_rows, "tema")
    por_produto = agg_by_dimensao(ig_rows, "produto")
    por_idioma  = agg_by_dimensao(ig_rows, "idioma")
    creator_rows = build_creator_rows(ig_rows, creators_manual)

    datas_cobertas = [r["data"] for r in ig_rows if r["data"]] + [r["data"] for r in fb_rows if r["data"]]
    periodo_inicio = min(datas_cobertas) if datas_cobertas else "—"
    periodo_fim    = max(datas_cobertas) if datas_cobertas else "—"

    por_formato = agg_by_format(ig_rows)
    collab_rows = [r for r in ig_rows if r["colaboradores"]]
    collab_rows.sort(key=lambda r: r["alcance"] or 0, reverse=True)

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
    ranking_intencao_json = json.dumps(ranking_intencao, ensure_ascii=False)

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
    ranking_intencao_json = safe(ranking_intencao_json)

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

    if collab_rows:
        collab_cards = "".join(f"""
      <a class="top3-card" href="{r['link'] or '#'}" target="_blank" title="{(r['legenda'] or '').replace('"', '&quot;')}">
        {f'<img src="{r["thumb"]}" loading="lazy" alt="">' if r['thumb'] else '<div style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.7rem">sem imagem</div>'}
        <div class="top3-metric">{fmt_int(r['alcance'])}<small>com @{', @'.join(r['colaboradores'])} · {r['formato']}</small></div>
      </a>""" for r in collab_rows[:6])
        collab_section_html = f"""
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">🤝 Publicações em Collab (Instagram) — {len(collab_rows)}</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Posts publicados em coautoria com outra conta — o alcance tende a somar parte da audiência do colaborador. Campo experimental: valide com a Graph API se algum post aparecer sem colaborador esperado.</div>
    <div class="top3-wrap" style="grid-template-columns:repeat(6,1fr)">{collab_cards}</div>
  </div>
"""
    else:
        collab_section_html = """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">🤝 Nenhuma publicação em Collab detectada no período (ou o campo <code>collaborators</code> não está disponível para este token/versão da API).</div>
  </div>
"""

    def linha_dimensao(r):
        return f"""<tr>
          <td>{r['valor']}</td><td style="text-align:right">{r['n']}</td>
          <td style="text-align:right">{fmt_int(r['alcance_total'])}</td>
          <td style="text-align:right">{fmt_int(r['alcance_medio'])}</td>
          <td style="text-align:right">{fmt_int(r['interacoes_media'])}</td>
          <td style="text-align:right">{fmt_int(r['indice_intencao_medio'])}</td>
        </tr>"""

    def tabela_dimensao(titulo, linhas):
        corpo = "".join(linha_dimensao(r) for r in linhas) or '<tr><td colspan="6" style="color:var(--sub)">Sem dados</td></tr>'
        return f"""
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">{titulo}</div>
        <div style="overflow-x:auto">
          <table>
            <thead><tr>
              <th>Valor</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance total</th>
              <th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th>
              <th style="text-align:right">Índice intenção médio</th>
            </tr></thead>
            <tbody>{corpo}</tbody>
          </table>
        </div>
      </div>"""

    if creator_rows:
        linhas_creator = "".join(f"""<tr>
          <td>@{c['username']}</td><td style="text-align:right">{c['n_posts']}</td>
          <td style="text-align:right">{fmt_int(c['alcance'])}</td><td style="text-align:right">{fmt_int(c['interacoes'])}</td>
          <td style="text-align:right">{fmt_int(c['salvos'])}</td><td style="text-align:right">{fmt_int(c['compartilhamentos'])}</td>
          <td style="text-align:right">{fmt_int(c['visitas_perfil'])}</td><td style="text-align:right">{fmt_int(c['seguidores'])}</td>
          <td style="text-align:right">{f"R$ {c['custo']:,.0f}" if c['custo'] else '—'}</td>
          <td style="text-align:right">{f"R$ {c['receita']:,.0f}" if c['receita'] else '—'}</td>
          <td style="text-align:right">{f"{c['roi']}x" if c['roi'] else '—'}</td>
        </tr>""" for c in creator_rows)
        creators_table_html = f"""
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Creator</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance</th>
          <th style="text-align:right">Interações</th><th style="text-align:right">Salvos</th>
          <th style="text-align:right">Compart.</th><th style="text-align:right">Visitas perfil</th>
          <th style="text-align:right">Seguidores</th><th style="text-align:right">Custo</th>
          <th style="text-align:right">Receita</th><th style="text-align:right">ROI</th>
        </tr></thead>
        <tbody>{linhas_creator}</tbody>
      </table>
    </div>
    <div class="text-xs mt-3" style="color:var(--sub)">Alcance/interações/salvos etc. são reais, somados a partir dos posts marcados como Collab. Custo, receita e ROI não existem na API da Meta — preencha manualmente em <code>data/creators.json</code> (chave = username do Instagram) para aparecerem aqui.</div>"""
    else:
        creators_table_html = """
    <div class="text-sm" style="color:var(--sub)">Nenhum creator com posts em Collab detectado ainda. Assim que houver publicações com <code>collaborators</code> preenchido, a performance orgânica real deles aparece aqui automaticamente.</div>"""

    conteudo_tab_html = f"""
  <div class="card mb-5" style="border-color:var(--cyan);background:rgba(6,182,212,.06)">
    <div class="text-sm">🧭 <strong>Período coberto: {periodo_inicio} até {periodo_fim}</strong> (posts de Facebook + Instagram — Stories não entram, a API não permite histórico retroativo). Alguns KPIs abaixo não existem na Graph API atual (impressões, retenção completa de vídeo, alcance não-seguidor, cliques no link da bio) — aparecem como "—". Tema/produto/idioma são <strong>classificados automaticamente por palavra-chave na legenda</strong> (heurística, pode errar); gancho inicial, público provável, objetivo e CTA exigem tagueamento manual em <code>data/content_tags.json</code> (ainda vazio).</div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🔭 Alcance e descoberta</div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <div><div class="kpi-label">Alcance (IG)</div><div class="kpi-val">{fmt_int(total_alcance)}</div></div>
      <div><div class="kpi-label">Impressões</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">descontinuado pela API</div></div>
      <div><div class="kpi-label">Visualizações de vídeo</div><div class="kpi-val">{fmt_int(total_video_views)}</div></div>
      <div><div class="kpi-label">Retenção média (Reels)</div><div class="kpi-val">{fmt_int(media_campo('tempo_medio_assistido'))}<span style="font-size:.9rem">s</span></div><div class="text-xs" style="color:var(--sub)">tempo médio assistido, não é % de conclusão</div></div>
      <div><div class="kpi-label">Novos seguidores (por post)</div><div class="kpi-val">{fmt_int(total_seguidores)}</div></div>
      <div><div class="kpi-label">Alcance não-seguidor</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">não exposto pela API</div></div>
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">❤️ Engajamento</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Para a Vertical Rio, salvamentos, compartilhamentos e cliques pesam mais que curtidas — indicam desejo/intenção, não só aprovação passiva.</div>
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-4">
      <div><div class="kpi-label">Curtidas</div><div class="kpi-val">{fmt_int(total_curtidas)}</div></div>
      <div><div class="kpi-label">Comentários</div><div class="kpi-val">{fmt_int(total_comentarios)}</div></div>
      <div><div class="kpi-label">Compartilhamentos</div><div class="kpi-val">{fmt_int(total_compart_ig)}</div></div>
      <div><div class="kpi-label">Salvamentos</div><div class="kpi-val">{fmt_int(total_salvos)}</div></div>
      <div><div class="kpi-label">Respostas em Stories</div><div class="kpi-val">{fmt_int(stories_totais.get('respostas'))}</div></div>
      <div><div class="kpi-label">Cliques no perfil</div><div class="kpi-val">{fmt_int(total_visitas)}</div></div>
      <div><div class="kpi-label">Cliques no link da bio</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">só agregado por conta, não por post</div></div>
      <div><div class="kpi-label">Taxa de engajamento média</div><div class="kpi-val">{taxas_medias['engajamento'] if taxas_medias['engajamento'] is not None else '—'}%</div></div>
      <div><div class="kpi-label">Taxa de salvamento média</div><div class="kpi-val">{taxas_medias['salvamento'] if taxas_medias['salvamento'] is not None else '—'}%</div></div>
      <div><div class="kpi-label">Taxa de compartilhamento média</div><div class="kpi-val">{taxas_medias['compartilhamento'] if taxas_medias['compartilhamento'] is not None else '—'}%</div></div>
    </div>
    <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">🏆 Top 10 — Índice de Intenção <span style="text-transform:none;font-weight:400">(salvos×3 + compart.×3 + cliques perfil×2 + comentários×1 + curtidas×0,5)</span></div>
    <div style="overflow-x:auto"><table><thead><tr><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Índice</th></tr></thead><tbody id="rank-intencao"></tbody></table></div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🗂️ Por tipo de conteúdo</div>
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {tabela_dimensao("Por tema", por_tema)}
      {tabela_dimensao("Por produto citado", por_produto)}
      {tabela_dimensao("Por idioma", por_idioma)}
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">🤝 Creators — performance orgânica</div>
    {creators_table_html}
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
  .thumb-cell {{ width:44px; height:44px; border-radius:6px; object-fit:cover; display:block; background:var(--surface2); }}
  .thumb-cell.empty {{ display:flex; align-items:center; justify-content:center; color:var(--sub); font-size:.6rem; }}
  .badge-collab {{ background:rgba(34,197,94,.15); color:#4ade80; }}
  .tabs {{ display:flex; gap:8px; }}
  .tab-btn {{ background:var(--surface); border:1px solid var(--border); color:var(--sub); padding:9px 18px; border-radius:9px; font-size:.82rem; font-weight:600; cursor:pointer; }}
  .tab-btn.active {{ background:var(--indigo); color:#fff; border-color:var(--indigo); }}
  .mt-3 {{ margin-top:12px; }}
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

  <div class="tabs mb-5">
    <button class="tab-btn active" data-tab="geral" onclick="mudarAba('geral')">📊 Visão Geral</button>
    <button class="tab-btn" data-tab="conteudo" onclick="mudarAba('conteudo')">🧭 KPIs de Conteúdo</button>
  </div>

  <div id="tab-geral">
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
    <div class="card"><div class="kpi-label">Posts em Collab (IG)</div><div class="kpi-val">{len(collab_rows)}</div></div>
  </div>
{ads_section_html}
{stories_section_html}
{collab_section_html}
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
          <th>Capa</th><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Alcance</th>
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
          <th>Capa</th><th>Data</th><th>Legenda</th><th style="text-align:right">Curtidas</th>
          <th style="text-align:right">Comentários</th><th style="text-align:right">Compart.</th>
          <th style="text-align:right">Cliques</th><th style="text-align:right">Video views</th>
        </tr></thead>
        <tbody id="fb-body"></tbody>
      </table>
    </div>
  </div>
  </div><!-- /tab-geral -->

  <div id="tab-conteudo" style="display:none">
{conteudo_tab_html}
  </div><!-- /tab-conteudo -->

<script>
const IG_ROWS     = {ig_rows_json};
const FB_ROWS     = {fb_rows_json};
const POR_FORMATO = {por_formato_json};
const RANKINGS    = {rankings_json};
const ADS           = {ads_json};
const ORGANICO_30D  = {organico_30d_json};
const STORY_ROWS     = {story_rows_json};
const STORIES_RANKINGS = {story_rankings_json};
const RANKING_INTENCAO = {ranking_intencao_json};

const fN = v => v === null || v === undefined ? '—' : Number(v).toLocaleString('pt-BR');
const trunc = (s, n) => (s || '').length > n ? s.slice(0, n) + '…' : (s || '—');
const thumbCell = thumb => thumb
  ? `<img class="thumb-cell" src="${{thumb}}" loading="lazy" alt="">`
  : `<div class="thumb-cell empty">—</div>`;

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
preencherTabela('rank-intencao',     RANKING_INTENCAO,      rankRow('indice_intencao'));

function mudarAba(nome) {{
  document.getElementById('tab-geral').style.display = nome === 'geral' ? '' : 'none';
  document.getElementById('tab-conteudo').style.display = nome === 'conteudo' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === nome));
}}

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
  <td>${{thumbCell(r.thumb)}}</td>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td><span class="badge badge-pink">${{r.formato}}</span>${{r.colaboradores && r.colaboradores.length ? ` <span class="badge badge-collab" title="Collab com @${{r.colaboradores.join(', @')}}">🤝 collab</span>` : ''}}</td>
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
  <td>${{thumbCell(r.thumb)}}</td>
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
