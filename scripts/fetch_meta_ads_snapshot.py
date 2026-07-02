#!/usr/bin/env python3
"""
Busca um snapshot dos KPIs pagos (Meta Ads) já publicados pelo dashboard
REPORTCLAUDE e salva em data/meta_ads_snapshot.json, para comparação
orgânico x pago no dashboard do MetaOrganico.

Não chama a API do Meta Ads diretamente — reaproveita o dado já coletado
e publicado pelo REPORTCLAUDE (evita duplicar credenciais/tokens de Ads).

Run: python scripts/fetch_meta_ads_snapshot.py
"""
import json
import pathlib
import re
import sys

import requests

REPORTCLAUDE_URL = "https://performance-sketch.github.io/REPORTCLAUDE/"
ROOT       = pathlib.Path(__file__).parent.parent
OUT_FILE   = ROOT / "data" / "meta_ads_snapshot.json"


def main():
    r = requests.get(REPORTCLAUDE_URL, timeout=30)
    r.raise_for_status()

    m = re.search(r"const META_DATA\s*=\s*(\{.*?\});\s*\n", r.text)
    if not m:
        sys.exit("ERRO: META_DATA não encontrado na página do REPORTCLAUDE.")

    meta_data = json.loads(m.group(1))
    d30 = meta_data.get("d30", {})

    snapshot = {
        "fonte": REPORTCLAUDE_URL,
        "d30": d30,
    }

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: snapshot Meta Ads (30d) salvo em {OUT_FILE}")
    print(f"    Gasto R${d30.get('gasto', 0):,.2f} | Alcance {d30.get('alcance', 0):,} | Cliques {d30.get('cliques', 0):,}")


if __name__ == "__main__":
    main()
