#!/usr/bin/env python3
"""
Gera index.html (dashboard) a partir de data/meta_organic.json.
Run: python scripts/gerar_dashboard.py

A partir da versão com calendário dinâmico, quase toda agregação (KPIs,
rankings, por formato/tema/produto/idioma, creators) roda no navegador em
JS a partir dos posts crus (IG_ROWS_ALL/FB_ROWS_ALL/STORY_ROWS_ALL) — este
script só prepara e embute esses dados. Isso é o que permite o filtro de
período recalcular tudo instantaneamente sem gerar o HTML de novo.
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
# É calculada aqui (uma vez, na geração) porque é um atributo fixo do post —
# não muda quando o calendário do dashboard é filtrado.
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
# Público provável: primeiro tenta ocasião/perfil explícito na legenda; se não
# achar nada, cai para uma estimativa grosseira pelo idioma (idioma
# estrangeiro -> turista internacional, português -> público local/nacional).
# É a heurística mais fraca das quatro — trate como ponto de partida, não
# como segmentação confiável; corrija via data/content_tags.json quando puder.
PUBLICO_KEYWORDS = [
    ("Lua de mel / Casais", ["lua de mel", "honeymoon", "casal", "romantic", "romântic", "aniversário de casamento"]),
    ("Despedida de solteiro(a)", ["despedida de solteir", "bachelor", "bachelorette", "stag do", "hen party"]),
    ("Família", ["família", "familia", "kids", "crianças", "criancas", "family"]),
    ("Grupo de amigos", ["galera", "amigos", "friends", "amigas"]),
]


def _publico_por_idioma(idioma):
    if idioma in ("English", "Español"):
        return "Turista internacional"
    if idioma == "Português":
        return "Público local/nacional"
    return "Não classificado"


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
    idioma = manual.get("idioma") or detectar_idioma(legenda)
    publico = manual.get("publico") or _match_keywords(legenda, PUBLICO_KEYWORDS) or _publico_por_idioma(idioma)
    return {
        "tema": tema,
        "produto": manual.get("produto") or _match_keywords(legenda, PRODUTO_KEYWORDS) or "Não identificado",
        "idioma": idioma,
        "gancho": manual.get("gancho") or "Não classificado",
        "publico": publico,
        "objetivo": manual.get("objetivo") or "Não classificado",
        "cta": manual.get("cta") or "Não classificado",
        "classificado_manualmente": bool(manual),
    }


def fmt_int(n):
    return f"{n:,}".replace(",", ".") if n is not None else "—"


# Só para exibição — a API devolve código ISO-3166 alpha-2. Código que não
# estiver aqui aparece como o próprio código (não inventa nome de país).
COUNTRY_NAMES = {
    "BR": "Brasil", "US": "Estados Unidos", "PT": "Portugal", "AR": "Argentina",
    "CL": "Chile", "PE": "Peru", "MX": "México", "CO": "Colômbia", "EC": "Equador",
    "PY": "Paraguai", "ES": "Espanha", "GB": "Reino Unido", "FR": "França",
    "IT": "Itália", "UY": "Uruguai", "PR": "Porto Rico", "DE": "Alemanha",
    "AE": "Emirados Árabes Unidos", "CA": "Canadá", "IN": "Índia", "RU": "Rússia",
    "AU": "Austrália", "IE": "Irlanda", "CH": "Suíça", "NL": "Holanda",
    "CR": "Costa Rica", "VE": "Venezuela", "BE": "Bélgica", "IR": "Irã",
    "PL": "Polônia", "TR": "Turquia", "BO": "Bolívia", "GT": "Guatemala",
    "MA": "Marrocos", "ID": "Indonésia", "DO": "Rep. Dominicana", "DZ": "Argélia",
    "UA": "Ucrânia", "JP": "Japão", "CU": "Cuba", "PA": "Panamá", "RO": "Romênia",
    "ZA": "África do Sul", "AT": "Áustria", "TH": "Tailândia",
}
GENDER_LABELS = {"M": "Masculino", "F": "Feminino", "U": "Não informado"}


def render_demografia_section(demografia):
    """Demografia REAL dos seguidores atuais (follower_demographics da Graph
    API) — não é por post, não segue o calendário do dashboard. É a base de
    seguidores agora, sempre que este script for gerado de novo."""

    def tabela(chave, titulo, rotulo_valor, mapa_nomes=None, limite=None):
        pares = demografia.get(chave)
        if not pares:
            return f"""<div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">{titulo}</div>
        <div class="text-sm" style="color:var(--sub)">Não disponível (campo rejeitado pela API para este token/versão, ou a conta tem menos de 100 seguidores — abaixo disso a Meta não libera demografia, por privacidade).</div>
      </div>"""
        total = sum(v for _, v in pares)
        linhas = pares[:limite] if limite else pares
        corpo = "".join(f"""<tr>
          <td>{(mapa_nomes or {}).get(v, v)}</td>
          <td style="text-align:right">{fmt_int(n)}</td>
          <td style="text-align:right">{round(n / total * 100, 1)}%</td>
        </tr>""" for v, n in linhas)
        return f"""<div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">{titulo}</div>
        <div style="overflow-x:auto"><table><thead><tr><th>{rotulo_valor}</th><th style="text-align:right">Seguidores</th><th style="text-align:right">%</th></tr></thead><tbody>{corpo}</tbody></table></div>
      </div>"""

    if not demografia:
        return """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">👥 Demografia de seguidores não disponível — nenhum breakdown (país/cidade/idade/gênero) veio da API neste fetch. Confira <code>instagram_demografia_error</code> em <code>data/meta_organic.json</code> ou se a conta tem pelo menos 100 seguidores.</div>
  </div>
"""

    return f"""
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">👥 Demografia dos seguidores (atual)</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Retrato dos seguidores <strong>agora</strong> — dado real da API (<code>follower_demographics</code>), mas é uma foto do momento: não é por post e não muda com o calendário acima.</div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
      {tabela("gender", "Gênero", "Gênero", GENDER_LABELS)}
      {tabela("age", "Faixa etária", "Faixa")}
    </div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {tabela("country", "Top países", "País", COUNTRY_NAMES, limite=15)}
      {tabela("city", "Top cidades", "Cidade", limite=15)}
    </div>
  </div>"""


TREND_LABELS = {
    "visualizacoes": "Visualizações",
    "reach": "Alcance",
    "interacoes": "Interações com o conteúdo",
    "cliques_link": "Cliques no link",
    "visitas_perfil": "Visitas ao perfil",
    "seguidores": "Seguidores",
}
TREND_ORDER = ["visualizacoes", "reach", "interacoes", "cliques_link", "visitas_perfil", "seguidores"]


def _soma_janela(serie, dias_inicio, dias_fim):
    hoje = datetime.now().date()
    ini = (hoje - timedelta(days=dias_fim)).isoformat()
    fim = (hoje - timedelta(days=dias_inicio)).isoformat()
    return sum(v for d, v in serie if ini <= d <= fim)


def render_conta_series_section(series_conta, total_seguidores_atual):
    """Tendência de conta (Instagram) — reach e seguidores vêm de time_series
    real (um ponto por dia); visualizações/visitas/cliques/interações vêm de
    total_value chamado dia a dia (ver conector) — mesma origem, granularidade
    diária de qualquer forma. É conta inteira, não segue o calendário do
    dashboard (a API não permite recortar isso por post)."""
    disponiveis = [chave for chave in TREND_ORDER if series_conta.get(chave)]
    if not disponiveis:
        return """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">📈 Tendência de conta não disponível — nenhuma série diária veio da API neste fetch (confira <code>instagram_series_conta_error</code> em <code>data/meta_organic.json</code>).</div>
  </div>
"""

    cards = []
    for chave in disponiveis:
        serie = series_conta[chave]
        if chave == "seguidores":
            valor_grande = fmt_int(total_seguidores_atual)
            delta_html = ""
        else:
            atual    = _soma_janela(serie, 0, 29)
            anterior = _soma_janela(serie, 30, 59)
            valor_grande = fmt_int(sum(v for _, v in serie))
            if anterior:
                pct = round((atual - anterior) / anterior * 100, 1)
                cor = "good" if pct >= 0 else "critical"
                seta = "▲" if pct >= 0 else "▼"
                delta_html = f'<span class="delta {cor}">{seta} {pct}%</span>'
            else:
                delta_html = ""
        cards.append(f"""
      <div class="card">
        <div style="font-weight:600;font-size:.85rem;margin-bottom:6px">{TREND_LABELS[chave]}</div>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px">
          <div class="kpi-val">{valor_grande}</div>{delta_html}
        </div>
        <div style="position:relative;height:90px">
          <canvas id="trend-{chave}"></canvas>
        </div>
      </div>""")

    faltando = [TREND_LABELS[c] for c in TREND_ORDER if c not in disponiveis]
    aviso_faltando = f'<div class="text-xs mt-3" style="color:var(--sub)">Sem dado para: {", ".join(faltando)} (métrica rejeitada pela API para este token/versão).</div>' if faltando else ""

    return f"""
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">📈 Tendência de conta (Instagram)</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Série diária real por métrica de conta — não segue o calendário acima (a API não permite recorte por post nessas métricas). % compara os últimos 30 dias com os 30 dias anteriores.</div>
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {"".join(cards)}
    </div>
    {aviso_faltando}
  </div>
"""


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


def main():
    dados = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    perfil     = dados.get("instagram", {}).get("perfil", {})
    demografia = dados.get("instagram", {}).get("demografia_seguidores", {})
    demografia_html = render_demografia_section(demografia)

    series_file = ROOT / "data" / "meta_account_timeseries.json"
    series_conta = load_json_or_empty(series_file)
    conta_series_html = render_conta_series_section(series_conta, perfil.get("followers_count"))
    ig_media  = dados.get("instagram", {}).get("media", [])
    fb_posts  = dados.get("facebook_posts", [])

    tags_manuais    = load_json_or_empty(TAGS_FILE)
    creators_manual = load_json_or_empty(CREATORS_FILE)

    ig_rows = build_ig_rows(ig_media, tags_manuais)
    fb_rows = build_fb_rows(fb_posts)

    ads = None
    if ADS_FILE.exists():
        ads = json.loads(ADS_FILE.read_text(encoding="utf-8")).get("d30")

    stories = []
    if STORIES_FILE.exists():
        stories = json.loads(STORIES_FILE.read_text(encoding="utf-8"))
    story_rows = build_story_rows(stories)

    # Janela fixa dos últimos 30 dias — só para comparar com o snapshot de Meta
    # Ads (que também é sempre 30d). Independente do calendário do dashboard.
    corte_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    ig_30d = [r for r in ig_rows if r["data"] >= corte_30d]
    organico_30d = {
        "alcance":    sum(r["alcance"] for r in ig_30d if r["alcance"] is not None),
        "interacoes": sum(r["interacoes"] for r in ig_30d if r["interacoes"] is not None),
        "visitas_perfil": sum(r["visitas_perfil"] for r in ig_30d if r["visitas_perfil"] is not None),
        "posts": len(ig_30d),
    }

    datas_cobertas = [r["data"] for r in ig_rows if r["data"]] + [r["data"] for r in fb_rows if r["data"]]
    hoje = datetime.now().strftime("%Y-%m-%d")
    periodo_min = min(datas_cobertas) if datas_cobertas else hoje
    periodo_max = max(datas_cobertas) if datas_cobertas else hoje

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")

    def safe(s):
        """Evita que uma legenda contendo '</script' feche a tag prematuramente."""
        return s.replace("</script", "<\\/script")

    ig_rows_json         = safe(json.dumps(ig_rows, ensure_ascii=False))
    fb_rows_json         = safe(json.dumps(fb_rows, ensure_ascii=False))
    story_rows_json      = safe(json.dumps(story_rows, ensure_ascii=False))
    perfil_json          = safe(json.dumps(perfil, ensure_ascii=False))
    ads_json             = safe(json.dumps(ads, ensure_ascii=False))
    organico_30d_json    = safe(json.dumps(organico_30d, ensure_ascii=False))
    creators_manual_json = safe(json.dumps(creators_manual, ensure_ascii=False))
    conta_series_json    = safe(json.dumps({k: dict(v) for k, v in series_conta.items()}, ensure_ascii=False))
    trend_labels_json    = safe(json.dumps(TREND_LABELS, ensure_ascii=False))

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
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">⚖️ Orgânico (IG) x Pago (Meta Ads) — últimos 30 dias <span style="font-weight:400;color:var(--sub);font-size:.75rem">(fixo, não segue o calendário)</span></div>
    <canvas id="chartOrganicoVsPago" height="90"></canvas>
  </div>
"""
    else:
        ads_section_html = """
  <div class="card mb-5" style="border-color:var(--border)">
    <div class="text-sm" style="color:var(--sub)">💰 KPIs pagos (Meta Ads) não disponível — rode <code>python scripts/fetch_meta_ads_snapshot.py</code> para trazer o snapshot do REPORTCLAUDE.</div>
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
  .date-input {{ background:var(--surface2); border:1px solid var(--border); color:var(--text); padding:7px 10px; border-radius:8px; font-size:.82rem; color-scheme:dark; }}
  .preset-btn {{ background:var(--surface2); border:1px solid var(--border); color:var(--sub); padding:7px 12px; border-radius:8px; font-size:.78rem; font-weight:600; cursor:pointer; }}
  .preset-btn.active {{ background:var(--indigo); color:#fff; border-color:var(--indigo); }}
  .delta {{ font-size:.78rem; font-weight:700; }}
  .delta.good {{ color:var(--green); }}
  .delta.critical {{ color:var(--red); }}
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

  <!-- Calendário dinâmico: filtra IG_ROWS_ALL/FB_ROWS_ALL/STORY_ROWS_ALL e recalcula tudo em JS -->
  <div class="card mb-5">
    <div class="flex items-center gap-3 flex-wrap">
      <div style="font-weight:600;font-size:.82rem;color:var(--sub);white-space:nowrap">📅 Período:</div>
      <input type="date" id="filtro-de" class="date-input">
      <span style="color:var(--sub)">até</span>
      <input type="date" id="filtro-ate" class="date-input">
      <div class="flex gap-2 flex-wrap">
        <button class="preset-btn" data-dias="7">7d</button>
        <button class="preset-btn" data-dias="30">30d</button>
        <button class="preset-btn" data-dias="90">90d</button>
        <button class="preset-btn active" data-dias="0">Tudo</button>
      </div>
      <div id="filtro-resumo" class="text-xs" style="color:var(--sub);margin-left:auto">—</div>
    </div>
    <div class="text-xs mt-3" style="color:var(--sub)">Dados disponíveis de {periodo_min} até {periodo_max}. Mudar o período recalcula os KPIs, rankings e tabelas das duas abas na hora (sem recarregar a página).</div>
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
    <div class="card"><div class="kpi-label">Posts Instagram</div><div class="kpi-val" id="kpi-posts-ig">…</div></div>
    <div class="card"><div class="kpi-label">Posts Facebook</div><div class="kpi-val" id="kpi-posts-fb">…</div></div>
    <div class="card"><div class="kpi-label">Alcance total (IG)</div><div class="kpi-val" id="kpi-alcance-ig">…</div></div>
    <div class="card"><div class="kpi-label">Interações (IG)</div><div class="kpi-val" id="kpi-interacoes-ig">…</div></div>
    <div class="card"><div class="kpi-label">Visitas ao perfil (IG)</div><div class="kpi-val" id="kpi-visitas-ig">…</div></div>
    <div class="card"><div class="kpi-label">Seguidores gerados (IG)</div><div class="kpi-val" id="kpi-seguidores-ig">…</div></div>
    <div class="card"><div class="kpi-label">Posts em Collab (IG)</div><div class="kpi-val" id="kpi-collab-ig">…</div></div>
  </div>
{conta_series_html}
{ads_section_html}
  <div class="card mb-5" style="border-color:var(--cyan);background:rgba(6,182,212,.06)">
    <div class="text-sm">ℹ️ <strong>Stories</strong>: a API do Instagram só expõe stories ativos (até 24h após publicar) — não existe histórico retroativo. Os <span id="stories-count-msg">0</span> stories abaixo são os acumulados dentro do período selecionado; o total geral cresce a cada execução do <code>fetch_meta_organic.py</code>.</div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📸 Instagram Stories — acumulado (<span id="stories-count-title">0</span> stories)</div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
      <div><div class="kpi-label">Stories capturados</div><div class="kpi-val" id="kpi-stories-n">0</div></div>
      <div><div class="kpi-label">Alcance total</div><div class="kpi-val" id="kpi-stories-alcance">—</div></div>
      <div><div class="kpi-label">Alcance médio</div><div class="kpi-val" id="kpi-stories-alcance-medio">—</div></div>
      <div><div class="kpi-label">Interações médias</div><div class="kpi-val" id="kpi-stories-interacoes-media">—</div></div>
      <div><div class="kpi-label">Visitas ao perfil</div><div class="kpi-val" id="kpi-stories-visitas">—</div></div>
      <div><div class="kpi-label">Cliques no link</div><div class="kpi-val" id="kpi-stories-cliques">—</div></div>
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

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">🤝 Publicações em Collab (Instagram) — <span id="collab-count">0</span></div>
    <div class="text-xs mb-4" style="color:var(--sub)">Posts publicados em coautoria com outra conta — o alcance tende a somar parte da audiência do colaborador. Campo experimental: valide com a Graph API se algum post aparecer sem colaborador esperado.</div>
    <div id="collab-cards" class="top3-wrap" style="grid-template-columns:repeat(6,1fr)"></div>
    <div id="collab-empty" style="display:none;color:var(--sub);font-size:.85rem">Nenhuma publicação em Collab no período selecionado.</div>
  </div>

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
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📋 Todos os posts — Instagram (<span id="ig-count">0</span>)</div>
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
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">📋 Todos os posts — Facebook (<span id="fb-count">0</span>)</div>
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
  <div class="card mb-5" style="border-color:var(--cyan);background:rgba(6,182,212,.06)">
    <div class="text-sm">🧭 <strong>Período selecionado: <span id="periodo-texto">—</span></strong> (posts de Facebook + Instagram — Stories não entram, a API não permite histórico retroativo). Alguns KPIs abaixo não existem na Graph API atual (impressões, retenção completa de vídeo, alcance não-seguidor, cliques no link da bio) — aparecem como "—". Tema/produto/idioma são <strong>classificados automaticamente por palavra-chave na legenda</strong> (heurística, pode errar); gancho inicial, público provável, objetivo e CTA exigem tagueamento manual em <code>data/content_tags.json</code> (ainda vazio).</div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:16px">🔭 Alcance e descoberta</div>
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <div><div class="kpi-label">Alcance (IG)</div><div class="kpi-val" id="kpi2-alcance">…</div></div>
      <div><div class="kpi-label">Impressões</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">descontinuado pela API</div></div>
      <div><div class="kpi-label">Visualizações de vídeo</div><div class="kpi-val" id="kpi2-videoviews">…</div></div>
      <div><div class="kpi-label">Retenção média (Reels)</div><div class="kpi-val"><span id="kpi2-retencao">…</span><span style="font-size:.9rem">s</span></div><div class="text-xs" style="color:var(--sub)">tempo médio assistido, não é % de conclusão</div></div>
      <div><div class="kpi-label">Novos seguidores (por post)</div><div class="kpi-val" id="kpi2-seguidores">…</div></div>
      <div><div class="kpi-label">Alcance não-seguidor</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">não exposto pela API</div></div>
    </div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">❤️ Engajamento</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Para a Vertical Rio, salvamentos, compartilhamentos e cliques pesam mais que curtidas — indicam desejo/intenção, não só aprovação passiva.</div>
    <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-4">
      <div><div class="kpi-label">Curtidas</div><div class="kpi-val" id="kpi2-curtidas">…</div></div>
      <div><div class="kpi-label">Comentários</div><div class="kpi-val" id="kpi2-comentarios">…</div></div>
      <div><div class="kpi-label">Compartilhamentos</div><div class="kpi-val" id="kpi2-compart">…</div></div>
      <div><div class="kpi-label">Salvamentos</div><div class="kpi-val" id="kpi2-salvos">…</div></div>
      <div><div class="kpi-label">Respostas em Stories</div><div class="kpi-val" id="kpi2-respostas-stories">…</div></div>
      <div><div class="kpi-label">Cliques no perfil</div><div class="kpi-val" id="kpi2-cliques-perfil">…</div></div>
      <div><div class="kpi-label">Cliques no link da bio</div><div class="kpi-val" style="color:var(--sub)">—</div><div class="text-xs" style="color:var(--sub)">só agregado por conta, não por post</div></div>
      <div><div class="kpi-label">Taxa de engajamento média</div><div class="kpi-val" id="kpi2-taxa-engajamento">…</div></div>
      <div><div class="kpi-label">Taxa de salvamento média</div><div class="kpi-val" id="kpi2-taxa-salvamento">…</div></div>
      <div><div class="kpi-label">Taxa de compartilhamento média</div><div class="kpi-val" id="kpi2-taxa-compartilhamento">…</div></div>
    </div>
    <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">🏆 Top 10 — Índice de Intenção <span style="text-transform:none;font-weight:400">(salvos×3 + compart.×3 + cliques perfil×2 + comentários×1 + curtidas×0,5)</span></div>
    <div id="top3-intencao" class="top3-wrap" style="grid-template-columns:repeat(6,1fr)"></div>
    <div style="overflow-x:auto"><table><thead><tr><th>Capa</th><th>Data</th><th>Formato</th><th>Legenda</th><th style="text-align:right">Índice</th><th>Link</th></tr></thead><tbody id="rank-intencao"></tbody></table></div>
  </div>

  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">🗂️ Por tipo de conteúdo</div>
    <div class="text-xs mb-4" style="color:var(--sub)">Tema, produto e idioma vêm de palavra-chave na legenda. Público-alvo tenta ocasião explícita na legenda (lua de mel, despedida de solteiro, família, grupo de amigos) e, sem isso, estima pelo idioma (estrangeiro → turista internacional, português → público local) — é a classificação mais fraca das quatro, trate como ponto de partida.</div>
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Por tema</div>
        <div style="overflow-x:auto"><table><thead><tr><th>Valor</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance total</th><th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th><th style="text-align:right">Índice intenção médio</th></tr></thead><tbody id="tbody-tema"></tbody></table></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Por produto citado</div>
        <div style="overflow-x:auto"><table><thead><tr><th>Valor</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance total</th><th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th><th style="text-align:right">Índice intenção médio</th></tr></thead><tbody id="tbody-produto"></tbody></table></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Por idioma</div>
        <div style="overflow-x:auto"><table><thead><tr><th>Valor</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance total</th><th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th><th style="text-align:right">Índice intenção médio</th></tr></thead><tbody id="tbody-idioma"></tbody></table></div>
      </div>
      <div>
        <div style="font-weight:600;font-size:.82rem;margin-bottom:10px;color:var(--sub)">Por público-alvo</div>
        <div style="overflow-x:auto"><table><thead><tr><th>Valor</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance total</th><th style="text-align:right">Alcance médio</th><th style="text-align:right">Interações médias</th><th style="text-align:right">Índice intenção médio</th></tr></thead><tbody id="tbody-publico"></tbody></table></div>
      </div>
    </div>
  </div>
{demografia_html}
  <div class="card mb-5">
    <div style="font-weight:600;font-size:.9rem;margin-bottom:4px">🤝 Creators — performance orgânica</div>
    <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Creator</th><th style="text-align:right">Posts</th><th style="text-align:right">Alcance</th>
          <th style="text-align:right">Interações</th><th style="text-align:right">Salvos</th>
          <th style="text-align:right">Compart.</th><th style="text-align:right">Visitas perfil</th>
          <th style="text-align:right">Seguidores</th><th style="text-align:right">Custo</th>
          <th style="text-align:right">Receita</th><th style="text-align:right">ROI</th>
        </tr></thead>
        <tbody id="creators-body"></tbody>
      </table>
    </div>
    <div class="text-xs mt-3" style="color:var(--sub)">Alcance/interações/salvos etc. são reais, somados a partir dos posts marcados como Collab. Custo, receita e ROI não existem na API da Meta — preencha manualmente em <code>data/creators.json</code> (chave = username do Instagram) para aparecerem aqui.</div>
    <div id="creators-galerias"></div>
    <div id="creators-empty" style="display:none;color:var(--sub);font-size:.85rem;margin-top:12px">Nenhum creator com posts em Collab no período selecionado.</div>
  </div>
  </div><!-- /tab-conteudo -->

<script>
const IG_ROWS_ALL     = {ig_rows_json};
const FB_ROWS_ALL     = {fb_rows_json};
const STORY_ROWS_ALL  = {story_rows_json};
const ADS             = {ads_json};
const ORGANICO_30D    = {organico_30d_json};
const CREATORS_MANUAL = {creators_manual_json};
const CONTA_SERIES    = {conta_series_json};

const fN = v => v === null || v === undefined ? '—' : Number(v).toLocaleString('pt-BR');
const trunc = (s, n) => (s || '').length > n ? s.slice(0, n) + '…' : (s || '—');
const thumbCell = thumb => thumb
  ? `<img class="thumb-cell" src="${{thumb}}" loading="lazy" alt="">`
  : `<div class="thumb-cell empty">—</div>`;
const setText = (id, val) => {{ const el = document.getElementById(id); if (el) el.textContent = val; }};

function preencherTabela(id, rows, renderRow) {{
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = rows.map(renderRow).join('') || '<tr><td colspan="12" style="color:var(--sub)">Sem dados no período selecionado.</td></tr>';
}}

function filtrarPeriodo(rows, de, ate) {{
  return rows.filter(r => r.data && r.data >= de && r.data <= ate);
}}

function somaCampo(rows, campo) {{
  return rows.reduce((acc, r) => acc + (r[campo] || 0), 0);
}}
function mediaCampo(rows, campo) {{
  const vals = rows.map(r => r[campo]).filter(v => v !== null && v !== undefined);
  return vals.length ? Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100 : null;
}}
function topN(rows, campo, n) {{
  n = n || 10;
  return rows.filter(r => r[campo] !== null && r[campo] !== undefined).sort((a, b) => b[campo] - a[campo]).slice(0, n);
}}
function aggByFormato(igRows) {{
  const grupos = {{}};
  igRows.forEach(r => {{
    const g = grupos[r.formato] || (grupos[r.formato] = {{ formato: r.formato, n: 0, alcance: [], interacoes: [], salvos: [], compartilhamentos: [], visitas_perfil: [] }});
    g.n++;
    ['alcance', 'interacoes', 'salvos', 'compartilhamentos', 'visitas_perfil'].forEach(c => {{
      if (r[c] !== null && r[c] !== undefined) g[c].push(r[c]);
    }});
  }});
  const media = lst => lst.length ? Math.round((lst.reduce((a, b) => a + b, 0) / lst.length) * 10) / 10 : null;
  return Object.values(grupos).map(g => ({{
    formato: g.formato, n: g.n,
    alcance_medio: media(g.alcance), interacoes_media: media(g.interacoes),
    salvos_medio: media(g.salvos), compartilhamentos_medio: media(g.compartilhamentos),
    visitas_perfil_media: media(g.visitas_perfil),
  }})).sort((a, b) => (b.alcance_medio || 0) - (a.alcance_medio || 0));
}}
function aggByDimensao(igRows, campo) {{
  const grupos = {{}};
  igRows.forEach(r => {{
    const chave = r[campo] || 'Não classificado';
    const g = grupos[chave] || (grupos[chave] = {{ valor: chave, n: 0, alcance: [], interacoes: [], indice_intencao: [] }});
    g.n++;
    ['alcance', 'interacoes', 'indice_intencao'].forEach(c => {{
      if (r[c] !== null && r[c] !== undefined) g[c].push(r[c]);
    }});
  }});
  const media = lst => lst.length ? Math.round((lst.reduce((a, b) => a + b, 0) / lst.length) * 10) / 10 : null;
  return Object.values(grupos).map(g => ({{
    valor: g.valor, n: g.n,
    alcance_total: g.alcance.reduce((a, b) => a + b, 0),
    alcance_medio: media(g.alcance), interacoes_media: media(g.interacoes),
    indice_intencao_medio: media(g.indice_intencao),
  }})).sort((a, b) => b.alcance_total - a.alcance_total);
}}
function buildCreatorPostsMap(igRows) {{
  const mapa = {{}};
  igRows.forEach(r => (r.colaboradores || []).forEach(u => (mapa[u] = mapa[u] || []).push(r)));
  Object.values(mapa).forEach(lst => lst.sort((a, b) => (b.alcance || 0) - (a.alcance || 0)));
  return mapa;
}}
function buildCreatorRows(igRows) {{
  const por = {{}};
  igRows.forEach(r => (r.colaboradores || []).forEach(u => {{
    const c = por[u] || (por[u] = {{ username: u, n_posts: 0, alcance: 0, interacoes: 0, salvos: 0, compartilhamentos: 0, visitas_perfil: 0, seguidores: 0 }});
    c.n_posts++;
    ['alcance', 'interacoes', 'salvos', 'compartilhamentos', 'visitas_perfil', 'seguidores'].forEach(campo => {{
      if (r[campo] !== null && r[campo] !== undefined) c[campo] += r[campo];
    }});
  }}));
  return Object.values(por).map(c => {{
    const manual = CREATORS_MANUAL[c.username] || {{}};
    const custo = manual.custo, receita = manual.receita;
    return {{ ...c, custo, leads_whatsapp: manual.leads_whatsapp, reservas: manual.reservas, receita,
              roi: (custo && receita) ? Math.round((receita / custo) * 100) / 100 : null }};
  }}).sort((a, b) => b.alcance - a.alcance);
}}

const rotuloMetrica = {{ alcance: 'Alcance', interacoes: 'Interações', visitas_perfil: 'Visitas ao perfil', salvos: 'Salvos', indice_intencao: 'Índice de Intenção' }};
function renderTop3(id, rows, campo, n) {{
  n = n || 3;
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = rows.slice(0, n).map((r, i) => `
    <a class="top3-card" href="${{r.link || '#'}}" target="_blank" title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">
      <span class="top3-rank">#${{i + 1}}</span>
      ${{r.thumb ? `<img src="${{r.thumb}}" loading="lazy" alt="">` : `<div style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.7rem">sem imagem</div>`}}
      <div class="top3-metric">${{fN(r[campo])}}<small>${{rotuloMetrica[campo]}} · ${{r.formato || 'Story'}}</small></div>
    </a>`).join('') || '<div style="color:var(--sub);font-size:.8rem">Sem dados no período.</div>';
}}

const rankRow = (campo) => r => `<tr>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td><span class="badge badge-pink">${{r.formato}}</span></td>
  <td title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">${{trunc(r.legenda, 40)}}</td>
  <td style="text-align:right;font-weight:600">${{fN(r[campo])}}</td>
</tr>`;
const rankRowThumb = (campo) => r => `<tr>
  <td>${{thumbCell(r.thumb)}}</td>
  <td style="white-space:nowrap">${{r.data}}</td>
  <td><span class="badge badge-pink">${{r.formato}}</span></td>
  <td title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">${{trunc(r.legenda, 40)}}</td>
  <td style="text-align:right;font-weight:600">${{fN(r[campo])}}</td>
  <td>${{r.link ? `<a class="perm" href="${{r.link}}" target="_blank">abrir</a>` : '—'}}</td>
</tr>`;

function renderDimensao(id, linhas) {{
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = linhas.map(r => `<tr>
    <td>${{r.valor}}</td><td style="text-align:right">${{r.n}}</td>
    <td style="text-align:right">${{fN(r.alcance_total)}}</td><td style="text-align:right">${{fN(r.alcance_medio)}}</td>
    <td style="text-align:right">${{fN(r.interacoes_media)}}</td><td style="text-align:right">${{fN(r.indice_intencao_medio)}}</td>
  </tr>`).join('') || '<tr><td colspan="6" style="color:var(--sub)">Sem dados</td></tr>';
}}

function renderCreators(creatorRows, creatorPostsMap) {{
  const body = document.getElementById('creators-body');
  const galerias = document.getElementById('creators-galerias');
  const empty = document.getElementById('creators-empty');
  if (!creatorRows.length) {{
    body.innerHTML = '';
    galerias.innerHTML = '';
    empty.style.display = '';
    return;
  }}
  empty.style.display = 'none';
  body.innerHTML = creatorRows.map(c => `<tr>
    <td>@${{c.username}}</td><td style="text-align:right">${{c.n_posts}}</td>
    <td style="text-align:right">${{fN(c.alcance)}}</td><td style="text-align:right">${{fN(c.interacoes)}}</td>
    <td style="text-align:right">${{fN(c.salvos)}}</td><td style="text-align:right">${{fN(c.compartilhamentos)}}</td>
    <td style="text-align:right">${{fN(c.visitas_perfil)}}</td><td style="text-align:right">${{fN(c.seguidores)}}</td>
    <td style="text-align:right">${{c.custo ? 'R$ ' + fN(c.custo) : '—'}}</td>
    <td style="text-align:right">${{c.receita ? 'R$ ' + fN(c.receita) : '—'}}</td>
    <td style="text-align:right">${{c.roi ? c.roi + 'x' : '—'}}</td>
  </tr>`).join('');
  galerias.innerHTML = creatorRows.map(c => {{
    const posts = creatorPostsMap[c.username] || [];
    const cards = posts.map(r => `
      <a class="top3-card" href="${{r.link || '#'}}" target="_blank" title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">
        ${{r.thumb ? `<img src="${{r.thumb}}" loading="lazy" alt="">` : `<div style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.7rem">sem imagem</div>`}}
        <div class="top3-metric">${{fN(r.alcance)}}<small>Alcance · ${{r.formato}}</small></div>
      </a>`).join('');
    return `<div class="mt-3">
      <div style="font-size:.78rem;color:var(--sub);margin-bottom:8px">@${{c.username}} — criativos (${{posts.length}})</div>
      <div class="top3-wrap" style="grid-template-columns:repeat(6,1fr)">${{cards}}</div>
    </div>`;
  }}).join('');
}}

let chartFormatoInstance = null;

function mudarAba(nome) {{
  document.getElementById('tab-geral').style.display = nome === 'geral' ? '' : 'none';
  document.getElementById('tab-conteudo').style.display = nome === 'conteudo' ? '' : 'none';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === nome));
}}

function aplicarFiltro() {{
  const de = document.getElementById('filtro-de').value;
  const ate = document.getElementById('filtro-ate').value;
  if (!de || !ate) return;

  const igRows = filtrarPeriodo(IG_ROWS_ALL, de, ate);
  const fbRows = filtrarPeriodo(FB_ROWS_ALL, de, ate);
  const storyRows = filtrarPeriodo(STORY_ROWS_ALL, de, ate);
  const collabRows = igRows.filter(r => r.colaboradores && r.colaboradores.length).sort((a, b) => (b.alcance || 0) - (a.alcance || 0));

  setText('filtro-resumo', `${{igRows.length + fbRows.length}} posts no período (${{igRows.length}} IG · ${{fbRows.length}} FB)`);
  setText('periodo-texto', `${{de}} até ${{ate}}`);

  // KPIs — Visão Geral
  setText('kpi-posts-ig', igRows.length);
  setText('kpi-posts-fb', fbRows.length);
  setText('kpi-alcance-ig', fN(somaCampo(igRows, 'alcance')));
  setText('kpi-interacoes-ig', fN(somaCampo(igRows, 'interacoes')));
  setText('kpi-visitas-ig', fN(somaCampo(igRows, 'visitas_perfil')));
  setText('kpi-seguidores-ig', fN(somaCampo(igRows, 'seguidores')));
  setText('kpi-collab-ig', collabRows.length);
  setText('ig-count', igRows.length);
  setText('fb-count', fbRows.length);

  // Stories
  const storiesTotais = {{
    n: storyRows.length,
    alcance: somaCampo(storyRows, 'alcance'),
    alcance_medio: mediaCampo(storyRows, 'alcance'),
    interacoes_media: mediaCampo(storyRows, 'interacoes'),
    visitas_perfil: somaCampo(storyRows, 'visitas_perfil'),
    cliques_link: somaCampo(storyRows, 'cliques_link'),
  }};
  setText('stories-count-msg', storiesTotais.n);
  setText('stories-count-title', storiesTotais.n);
  setText('kpi-stories-n', storiesTotais.n);
  setText('kpi-stories-alcance', fN(storiesTotais.alcance));
  setText('kpi-stories-alcance-medio', fN(storiesTotais.alcance_medio));
  setText('kpi-stories-interacoes-media', fN(storiesTotais.interacoes_media));
  setText('kpi-stories-visitas', fN(storiesTotais.visitas_perfil));
  setText('kpi-stories-cliques', fN(storiesTotais.cliques_link));
  preencherTabela('stories-body', storyRows, r => `<tr>
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
  renderTop3('top3-stories-alcance', topN(storyRows, 'alcance', 5), 'alcance', 5);
  renderTop3('top3-stories-interacoes', topN(storyRows, 'interacoes', 5), 'interacoes', 5);

  // Collab (Visão Geral)
  setText('collab-count', collabRows.length);
  const collabCards = document.getElementById('collab-cards');
  const collabEmpty = document.getElementById('collab-empty');
  if (collabRows.length) {{
    collabEmpty.style.display = 'none';
    collabCards.innerHTML = collabRows.slice(0, 6).map(r => `
      <a class="top3-card" href="${{r.link || '#'}}" target="_blank" title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">
        ${{r.thumb ? `<img src="${{r.thumb}}" loading="lazy" alt="">` : `<div style="aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;color:var(--sub);font-size:.7rem">sem imagem</div>`}}
        <div class="top3-metric">${{fN(r.alcance)}}<small>com @${{r.colaboradores.join(', @')}} · ${{r.formato}}</small></div>
      </a>`).join('');
  }} else {{
    collabCards.innerHTML = '';
    collabEmpty.style.display = '';
  }}

  // Por formato + gráfico
  const porFormato = aggByFormato(igRows);
  preencherTabela('formato-body', porFormato, f => `<tr>
    <td>${{f.formato}}</td><td style="text-align:right">${{f.n}}</td>
    <td style="text-align:right">${{fN(f.alcance_medio)}}</td><td style="text-align:right">${{fN(f.interacoes_media)}}</td>
    <td style="text-align:right">${{fN(f.salvos_medio)}}</td><td style="text-align:right">${{fN(f.compartilhamentos_medio)}}</td>
    <td style="text-align:right">${{fN(f.visitas_perfil_media)}}</td>
  </tr>`);
  if (chartFormatoInstance) chartFormatoInstance.destroy();
  chartFormatoInstance = new Chart(document.getElementById('chartFormato'), {{
    type: 'bar',
    data: {{
      labels: porFormato.map(f => f.formato),
      datasets: [
        {{ label: 'Alcance médio', data: porFormato.map(f => f.alcance_medio), backgroundColor: '#6366f1' }},
        {{ label: 'Interações médias', data: porFormato.map(f => f.interacoes_media), backgroundColor: '#ec4899' }},
      ]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#f1f5f9' }} }} }},
      scales: {{ x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(51,65,85,.4)' }} }} }} }}
  }});

  // Rankings — Visão Geral
  const rankAlcance = topN(igRows, 'alcance');
  const rankInteracoes = topN(igRows, 'interacoes');
  const rankVisitas = topN(igRows, 'visitas_perfil');
  const rankSalvos = topN(igRows, 'salvos');
  preencherTabela('rank-alcance', rankAlcance, rankRow('alcance'));
  preencherTabela('rank-interacoes', rankInteracoes, rankRow('interacoes'));
  preencherTabela('rank-visitas', rankVisitas, rankRow('visitas_perfil'));
  preencherTabela('rank-salvos', rankSalvos, rankRow('salvos'));
  renderTop3('top3-alcance', rankAlcance, 'alcance');
  renderTop3('top3-interacoes', rankInteracoes, 'interacoes');
  renderTop3('top3-visitas', rankVisitas, 'visitas_perfil');
  renderTop3('top3-salvos', rankSalvos, 'salvos');

  // Tabelas completas
  preencherTabela('ig-body', igRows, r => `<tr>
    <td>${{thumbCell(r.thumb)}}</td>
    <td style="white-space:nowrap">${{r.data}}</td>
    <td><span class="badge badge-pink">${{r.formato}}</span>${{r.colaboradores && r.colaboradores.length ? ` <span class="badge badge-collab" title="Collab com @${{r.colaboradores.join(', @')}}">🤝 collab</span>` : ''}}</td>
    <td title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">${{trunc(r.legenda, 50)}}</td>
    <td style="text-align:right">${{fN(r.alcance)}}</td>
    <td style="text-align:right">${{fN(r.interacoes)}}</td>
    <td style="text-align:right">${{fN(r.salvos)}}</td>
    <td style="text-align:right">${{fN(r.compartilhamentos)}}</td>
    <td style="text-align:right">${{fN(r.visitas_perfil)}}</td>
    <td style="text-align:right">${{fN(r.seguidores)}}</td>
    <td>${{r.link ? `<a class="perm" href="${{r.link}}" target="_blank">abrir</a>` : '—'}}</td>
  </tr>`);
  preencherTabela('fb-body', fbRows, r => `<tr>
    <td>${{thumbCell(r.thumb)}}</td>
    <td style="white-space:nowrap">${{r.data}}</td>
    <td title="${{(r.legenda || '').replace(/"/g, '&quot;')}}">${{trunc(r.legenda, 60)}}</td>
    <td style="text-align:right">${{fN(r.curtidas)}}</td>
    <td style="text-align:right">${{fN(r.comentarios)}}</td>
    <td style="text-align:right">${{fN(r.compartilhamentos)}}</td>
    <td style="text-align:right">${{fN(r.cliques)}}</td>
    <td style="text-align:right">${{fN(r.video_views)}}</td>
  </tr>`);

  // Aba Conteúdo — Alcance e descoberta
  setText('kpi2-alcance', fN(somaCampo(igRows, 'alcance')));
  setText('kpi2-videoviews', fN(somaCampo(igRows, 'visualizacoes')));
  setText('kpi2-retencao', fN(mediaCampo(igRows, 'tempo_medio_assistido')));
  setText('kpi2-seguidores', fN(somaCampo(igRows, 'seguidores')));

  // Aba Conteúdo — Engajamento
  setText('kpi2-curtidas', fN(somaCampo(igRows, 'curtidas')));
  setText('kpi2-comentarios', fN(somaCampo(igRows, 'comentarios')));
  setText('kpi2-compart', fN(somaCampo(igRows, 'compartilhamentos')));
  setText('kpi2-salvos', fN(somaCampo(igRows, 'salvos')));
  setText('kpi2-respostas-stories', fN(somaCampo(storyRows, 'respostas')));
  setText('kpi2-cliques-perfil', fN(somaCampo(igRows, 'visitas_perfil')));
  const taxaEng = mediaCampo(igRows, 'taxa_engajamento');
  const taxaSalv = mediaCampo(igRows, 'taxa_salvamento');
  const taxaComp = mediaCampo(igRows, 'taxa_compartilhamento');
  setText('kpi2-taxa-engajamento', taxaEng !== null ? taxaEng + '%' : '—');
  setText('kpi2-taxa-salvamento', taxaSalv !== null ? taxaSalv + '%' : '—');
  setText('kpi2-taxa-compartilhamento', taxaComp !== null ? taxaComp + '%' : '—');

  const rankingIntencao = topN(igRows, 'indice_intencao', 10);
  preencherTabela('rank-intencao', rankingIntencao, rankRowThumb('indice_intencao'));
  renderTop3('top3-intencao', rankingIntencao, 'indice_intencao', 6);

  // Aba Conteúdo — por tipo de conteúdo
  renderDimensao('tbody-tema', aggByDimensao(igRows, 'tema'));
  renderDimensao('tbody-produto', aggByDimensao(igRows, 'produto'));
  renderDimensao('tbody-idioma', aggByDimensao(igRows, 'idioma'));
  renderDimensao('tbody-publico', aggByDimensao(igRows, 'publico'));

  // Aba Conteúdo — Creators
  renderCreators(buildCreatorRows(igRows), buildCreatorPostsMap(igRows));
}}

const TODAS_DATAS = IG_ROWS_ALL.concat(FB_ROWS_ALL).map(r => r.data).filter(Boolean);
const MIN_DATA = TODAS_DATAS.length ? TODAS_DATAS.reduce((min, d) => d < min ? d : min) : new Date().toISOString().slice(0, 10);
const MAX_DATA = TODAS_DATAS.length ? TODAS_DATAS.reduce((max, d) => d > max ? d : max) : new Date().toISOString().slice(0, 10);
['filtro-de', 'filtro-ate'].forEach(id => {{
  const el = document.getElementById(id);
  el.min = MIN_DATA;
  el.max = MAX_DATA;
}});

function aplicarPreset(dias) {{
  const fim = MAX_DATA;
  let inicio;
  if (dias === 0) {{
    inicio = MIN_DATA;
  }} else {{
    const d = new Date(fim + 'T00:00:00');
    d.setDate(d.getDate() - dias);
    inicio = d.toISOString().slice(0, 10);
    if (inicio < MIN_DATA) inicio = MIN_DATA;
  }}
  document.getElementById('filtro-de').value = inicio;
  document.getElementById('filtro-ate').value = fim;
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.toggle('active', Number(b.dataset.dias) === dias));
  aplicarFiltro();
}}

document.getElementById('filtro-de').addEventListener('change', () => {{
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  aplicarFiltro();
}});
document.getElementById('filtro-ate').addEventListener('change', () => {{
  document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
  aplicarFiltro();
}});
document.querySelectorAll('.preset-btn').forEach(b => b.addEventListener('click', () => aplicarPreset(Number(b.dataset.dias))));

aplicarPreset(0); // estado inicial: período completo

if (ADS) {{
  new Chart(document.getElementById('chartOrganicoVsPago'), {{
    type: 'bar',
    data: {{
      labels: ['Alcance', 'Cliques (pago) / Interações (orgânico)'],
      datasets: [
        {{ label: `Orgânico (IG, ${{ORGANICO_30D.posts}} posts, últimos 30d)`, data: [ORGANICO_30D.alcance, ORGANICO_30D.interacoes], backgroundColor: '#ec4899' }},
        {{ label: 'Pago (Meta Ads)', data: [ADS.alcance, ADS.cliques], backgroundColor: '#22c55e' }},
      ]
    }},
    options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: '#f1f5f9' }} }} }},
      scales: {{ x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}, y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: 'rgba(51,65,85,.4)' }} }} }} }}
  }});
}}

const rotuloTendencia = {trend_labels_json};
const fmtDataBR = iso => {{
  const [a, m, d] = iso.split('-');
  return `${{d}}/${{m}}/${{a}}`;
}};

Object.keys(CONTA_SERIES).forEach(chave => {{
  const el = document.getElementById('trend-' + chave);
  if (!el) return;
  const pontos = Object.entries(CONTA_SERIES[chave]).sort((a, b) => a[0] < b[0] ? -1 : 1);
  new Chart(el, {{
    type: 'bar',
    data: {{
      labels: pontos.map(p => p[0]),
      datasets: [{{
        label: rotuloTendencia[chave] || chave,
        data: pontos.map(p => p[1]),
        backgroundColor: 'rgba(99,102,241,.55)', hoverBackgroundColor: '#6366f1',
        borderRadius: 2, borderSkipped: false,
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: true, position: 'top', align: 'end', labels: {{ color: '#94a3b8', boxWidth: 12, font: {{ size: 11 }} }} }},
        tooltip: {{
          backgroundColor: '#1e293b', borderColor: '#334155', borderWidth: 1,
          titleColor: '#f1f5f9', bodyColor: '#f1f5f9', padding: 10, displayColors: false,
          callbacks: {{
            title: items => fmtDataBR(items[0].label),
            label: item => `${{rotuloTendencia[chave] || chave}}: ${{fN(item.parsed.y)}}`,
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ display: false }}, grid: {{ display: false }} }},
        y: {{ ticks: {{ color: '#94a3b8', maxTicksLimit: 4 }}, grid: {{ color: 'rgba(51,65,85,.4)' }} }},
      }},
    }}
  }});
}});
</script>
</body>
</html>
"""

    INDEX_FILE.write_text(html, encoding="utf-8")
    print(f"OK: index.html gerado ({len(html):,} chars) — {len(ig_rows)} posts IG, {len(fb_rows)} posts FB")


if __name__ == "__main__":
    main()
