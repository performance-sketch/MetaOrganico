#!/usr/bin/env python3
"""
Busca os dados orgânicos do Meta (Facebook + Instagram) e salva em data/meta_organic.json.

Run:  python scripts/fetch_meta_organic.py
"""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

from connectors.meta_organic import MetaOrganicError, fetch_all  # noqa: E402


def _merge_stories_history(novos, out_dir):
    """Acumula stories vistos ao longo do tempo — a API só expõe os ativos
    (últimas 24h), então cada execução precisa somar ao histórico já salvo,
    sem perder o que já foi capturado em execuções anteriores."""
    hist_path = out_dir / "meta_stories_history.json"
    historico = {}
    if hist_path.exists():
        for s in json.loads(hist_path.read_text(encoding="utf-8")):
            historico[s["id"]] = s
    for s in novos:
        historico[s["id"]] = s  # atualiza insights se o story ainda está ativo
    lista = sorted(historico.values(), key=lambda s: s.get("timestamp", ""), reverse=True)
    hist_path.write_text(json.dumps(lista, ensure_ascii=False, indent=2), encoding="utf-8")
    return lista


def main():
    try:
        dados = fetch_all()
    except MetaOrganicError as e:
        sys.exit(f"ERRO: {e}")

    out_dir = ROOT / "data"
    out_dir.mkdir(exist_ok=True)

    stories_ativos = dados.get("instagram", {}).get("stories_ativos", [])
    historico = _merge_stories_history(stories_ativos, out_dir)

    out_path = out_dir / "meta_organic.json"
    out_path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    n_fb = len(dados.get("facebook_posts", []))
    n_ig = len(dados.get("instagram", {}).get("media", []))
    print(f"OK: {n_fb} posts Facebook, {n_ig} posts Instagram -> {out_path}")
    print(f"    Stories ativos agora: {len(stories_ativos)} | histórico acumulado: {len(historico)}")

    if dados.get("facebook_error"):
        print(f"AVISO Facebook: {dados['facebook_error']}")
    if dados.get("instagram_error"):
        print(f"AVISO Instagram: {dados['instagram_error']}")
    if dados.get("instagram_stories_error"):
        print(f"AVISO Stories: {dados['instagram_stories_error']}")


if __name__ == "__main__":
    main()
