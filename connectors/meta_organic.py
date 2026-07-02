#!/usr/bin/env python3
"""
Conector Meta Orgânico — Facebook Pages + Instagram Business Account.

Credenciais lidas de variáveis de ambiente (nunca hardcoded):
  META_ACCESS_TOKEN   (obrigatório)
  META_API_VERSION    (opcional, default v19.0)
  META_PAGE_ID        (opcional — auto-descoberto via /me/accounts se ausente)
  META_IG_ACCOUNT_ID  (opcional — auto-descoberto via a página acima)
"""
import json
import os
import time
from datetime import datetime, timedelta

import requests

API_VERSION  = os.environ.get("META_API_VERSION", "v19.0")
GRAPH_BASE   = f"https://graph.facebook.com/{API_VERSION}"


class MetaOrganicError(RuntimeError):
    pass


def _require_token():
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        raise MetaOrganicError(
            "META_ACCESS_TOKEN não definido. Configure no .env (veja .env.example)."
        )
    return token


def _get(path, token, params=None, timeout=20, retries=3):
    """GET com retry exponencial (1s, 2s, 4s)."""
    p = {"access_token": token, **(params or {})}
    for attempt in range(retries):
        try:
            r = requests.get(f"{GRAPH_BASE}/{path}", params=p, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def discover_pages(token=None):
    """Lista as páginas do Facebook (com token de página e IG vinculado) acessíveis pelo token."""
    token = token or _require_token()
    try:
        resp = _get("me/accounts", token, {"fields": "id,name,access_token,instagram_business_account"})
        return resp.get("data", [])
    except requests.RequestException as e:
        raise MetaOrganicError(f"Falha ao listar páginas: {e}") from e


def resolve_targets(token=None):
    """Resolve page_id / page_token / ig_account_id a partir do .env ou auto-descoberta."""
    token = token or _require_token()
    page_id = os.environ.get("META_PAGE_ID") or ""
    ig_id   = os.environ.get("META_IG_ACCOUNT_ID") or ""
    page_token = token

    if page_id and ig_id:
        return page_id, page_token, ig_id

    paginas = discover_pages(token)
    if not paginas:
        raise MetaOrganicError("Nenhuma página encontrada para este token (verifique permissões pages_show_list).")

    page = next((p for p in paginas if p["id"] == page_id), paginas[0]) if page_id else paginas[0]
    page_id    = page["id"]
    page_token = page.get("access_token", token)
    ig_id      = ig_id or (page.get("instagram_business_account") or {}).get("id", "")
    return page_id, page_token, ig_id


def fetch_facebook_posts(page_id, page_token, days=90):
    """Posts orgânicos da Page (com insights de impressões/alcance/engajamento e reações)."""
    corte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    todos, data = [], _get(f"{page_id}/posts", page_token, {
        "fields": "id,message,story,created_time", "limit": 100,
    })
    while True:
        lote = data.get("data", [])
        todos.extend(p for p in lote if (p.get("created_time", "")[:10]) >= corte)
        if not lote or lote[-1].get("created_time", "")[:10] < corte:
            break
        next_url = (data.get("paging") or {}).get("next")
        if not next_url:
            break
        data = requests.get(next_url, timeout=20).json()

    resultado = []
    for post in todos:
        pid = post.get("id", "")
        try:
            ins = _get(f"{pid}/insights", page_token, {
                "metric": "post_impressions,post_reach,post_engaged_users,post_clicks",
            })
            insights = {}
            for item in ins.get("data", []):
                vals = item.get("values") or [{}]
                insights[item["name"]] = int(vals[-1].get("value", 0) or 0)
        except requests.RequestException:
            insights = {}
        try:
            reacts = _get(pid, page_token, {"fields": "reactions.summary(true),comments.summary(true),shares"})
            curtidas    = reacts.get("reactions", {}).get("summary", {}).get("total_count", 0)
            comentarios = reacts.get("comments", {}).get("summary", {}).get("total_count", 0)
            compart     = reacts.get("shares", {}).get("count", 0) if reacts.get("shares") else 0
        except requests.RequestException:
            curtidas = comentarios = compart = 0

        resultado.append({
            "id": pid,
            "plataforma": "facebook",
            "tipo": post.get("type", "status"),
            "mensagem": (post.get("message") or post.get("story") or "")[:180],
            "criado_em": post.get("created_time", "")[:10],
            "impressoes": insights.get("post_impressions", 0),
            "alcance": insights.get("post_reach", 0),
            "engajados": insights.get("post_engaged_users", 0),
            "cliques": insights.get("post_clicks", 0),
            "curtidas": int(curtidas or 0),
            "comentarios": int(comentarios or 0),
            "compartilhamentos": int(compart or 0),
        })
    return resultado


def _fetch_media_insights_batch(media_list, token):
    """Insights (saves, shares, reach, impressions) em lote de até 50 posts por chamada."""
    resultado = {}
    if not media_list:
        return resultado
    tipos = {m["id"]: (m.get("media_product_type") or m.get("media_type") or "").upper() for m in media_list}
    ids   = [m["id"] for m in media_list if "id" in m]

    for i in range(0, len(ids), 50):
        lote  = ids[i:i + 50]
        batch = []
        for mid in lote:
            metrics = "plays,saved,shares,reach,impressions" if tipos.get(mid) in ("REELS", "REEL", "VIDEO") \
                else "saved,shares,reach,impressions"
            batch.append({"method": "GET", "relative_url": f"{mid}/insights?metric={metrics}"})
        r = requests.post(GRAPH_BASE, data={
            "access_token": token, "batch": json.dumps(batch), "include_headers": "false",
        }, timeout=30)
        r.raise_for_status()
        for mid, res in zip(lote, r.json() or []):
            if not res or res.get("code") != 200:
                continue
            body = json.loads(res.get("body", "{}"))
            m = {}
            for item in body.get("data", []):
                val = item.get("value")
                if val is None:
                    vals = item.get("values", [])
                    val = vals[0].get("value", 0) if vals else 0
                m[item.get("name", "")] = val
            resultado[mid] = m
    return resultado


def fetch_instagram_posts(ig_id, token, days=90, with_insights=True):
    """Perfil + posts orgânicos do Instagram Business Account, com insights por post."""
    resultado = {"perfil": {}, "media": []}

    perfil = _get(ig_id, token, {
        "fields": "id,username,name,biography,followers_count,follows_count,media_count,profile_picture_url,website",
    })
    resultado["perfil"] = perfil

    corte  = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    fields = "id,media_type,media_product_type,media_url,thumbnail_url,timestamp,caption,like_count,comments_count,permalink"
    posts, data = [], _get(f"{ig_id}/media", token, {"fields": fields, "limit": 50})
    while True:
        lote = data.get("data", [])
        posts.extend(lote)
        after = (data.get("paging") or {}).get("cursors", {}).get("after")
        if not after or not lote or (lote[-1].get("timestamp") or "")[:10] < corte:
            break
        data = _get(f"{ig_id}/media", token, {"fields": fields, "limit": 50, "after": after})
    posts = [p for p in posts if (p.get("timestamp") or "")[:10] >= corte]

    if with_insights and posts:
        insights = _fetch_media_insights_batch(posts, token)
        for post in posts:
            post["insights"] = insights.get(post["id"], {})

    resultado["media"] = posts
    return resultado


def fetch_all(days=None):
    """Ponto de entrada único: resolve página/IG e busca tudo (FB + IG orgânico)."""
    token = _require_token()
    days  = days or int(os.environ.get("ORGANIC_LOOKBACK_DAYS", "90"))

    page_id, page_token, ig_id = resolve_targets(token)

    resultado = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "page_id": page_id,
        "ig_account_id": ig_id,
        "facebook_posts": [],
        "instagram": {"perfil": {}, "media": []},
    }

    try:
        resultado["facebook_posts"] = fetch_facebook_posts(page_id, page_token, days)
    except (requests.RequestException, MetaOrganicError) as e:
        resultado["facebook_error"] = str(e)

    if ig_id:
        try:
            resultado["instagram"] = fetch_instagram_posts(ig_id, token, days)
        except (requests.RequestException, MetaOrganicError) as e:
            resultado["instagram_error"] = str(e)

    return resultado
