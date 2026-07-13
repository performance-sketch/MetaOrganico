#!/usr/bin/env python3
"""
Importa planilhas exportadas manualmente do Meta Business Suite (posts, Reels,
Stories) e do Ads Manager para data/manual_content.json — dado curado que não
vem de nenhuma API, complementar ao fetch automático (meta_organic.json).
Alimenta a aba "Exportação" do dashboard.

Run:
  python scripts/importar_planilha_manual.py                      # importa tudo de data/manual_exports/
  python scripts/importar_planilha_manual.py caminho/arquivo.csv  # importa arquivo(s) específico(s)

Cada execução funde por chave com o que já existe em data/manual_content.json
— reimportar a mesma planilha (ex.: um export mais recente do mesmo período)
atualiza os posts já conhecidos em vez de duplicar.
"""
import csv
import json
import pathlib
import sys
from datetime import datetime

ROOT       = pathlib.Path(__file__).parent.parent
IMPORT_DIR = ROOT / "data" / "manual_exports"
OUT_FILE   = ROOT / "data" / "manual_content.json"

# Colunas que identificam um export de conteúdo (posts/Reels/Stories) do Meta
# Business Suite — presentes independente da ordem/colunas extras entre exports.
COLS_CONTEUDO = {"Tipo de post", "Horário de publicação", "Identificação do post"}
# Colunas típicas de um export do Ads Manager — ainda não validado contra um
# arquivo real; se aparecer um export assim, os dados crus são preservados
# (sem normalização especulativa de campos que eu não vi de verdade).
COLS_ADS = {"Nome da campanha", "Valor usado (BRL)", "Impressões"}


def _to_int(v):
    v = (v or "").strip().replace(".", "").replace(",", "")
    if not v or v.lower() in ("total", "-", "—"):
        return None
    return int(v) if v.lstrip("-").isdigit() else None


def _to_iso(v):
    """'MM/DD/YYYY HH:MM' (formato do export do Business Suite) -> ISO."""
    v = (v or "").strip()
    if not v:
        return None
    for fmt, out in (("%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:00"), ("%m/%d/%Y", "%Y-%m-%d")):
        try:
            return datetime.strptime(v, fmt).strftime(out)
        except ValueError:
            continue
    return None


def _ler_csv(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _detectar_tipo(header):
    header = set(header)
    if COLS_ADS & header:
        return "ads"
    if COLS_CONTEUDO & header:
        return "conteudo"
    return "desconhecido"


def _e_story(row):
    return "stor" in (row.get("Tipo de post") or "").lower()


def _normalizar_conteudo(row, origem):
    post_id  = (row.get("Identificação do post") or "").strip()
    data_ref = (row.get("Data") or "Total").strip() or "Total"
    return {
        "chave": f"{post_id}__{data_ref}",
        "post_id": post_id,
        "conta": (row.get("Nome de usuário da conta") or "").strip(),
        "tipo": (row.get("Tipo de post") or "").strip(),
        "descricao": (row.get("Descrição") or "").strip(),
        "duracao_s": _to_int(row.get("Duração (s)")),
        "publicado_em": _to_iso(row.get("Horário de publicação")),
        "link": (row.get("Link permanente") or "").strip(),
        "data_ref": data_ref,
        "visualizacoes": _to_int(row.get("Visualizações")),
        "alcance": _to_int(row.get("Alcance")),
        "curtidas": _to_int(row.get("Curtidas")),
        "compartilhamentos": _to_int(row.get("Compartilhamentos")),
        "comentarios": _to_int(row.get("Comentários")),
        "salvamentos": _to_int(row.get("Salvamentos")),
        "seguimentos": _to_int(row.get("Seguimentos")),
        "origem": origem,
    }


def _chave_ads(row):
    return "||".join(str(v) for v in row.values())


def main():
    args = [pathlib.Path(a) for a in sys.argv[1:]]
    if not args:
        if not IMPORT_DIR.exists():
            sys.exit(f"ERRO: nenhum arquivo passado e {IMPORT_DIR} não existe.")
        args = sorted(IMPORT_DIR.glob("*.csv"))
    if not args:
        sys.exit("ERRO: nenhum CSV para importar (passe caminhos ou coloque em data/manual_exports/).")

    dados = {"posts": [], "stories": [], "ads": []}
    if OUT_FILE.exists():
        try:
            dados = json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    dados.setdefault("posts", [])
    dados.setdefault("stories", [])
    dados.setdefault("ads", [])

    posts_por_chave   = {p["chave"]: p for p in dados["posts"]}
    stories_por_chave = {p["chave"]: p for p in dados["stories"]}
    ads_por_chave      = {_chave_ads(a): a for a in dados["ads"]}

    resumo = []
    for path in args:
        if not path.exists():
            print(f"AVISO: {path} não encontrado, pulando.")
            continue
        linhas = _ler_csv(path)
        if not linhas:
            print(f"AVISO: {path} sem linhas, pulando.")
            continue
        tipo = _detectar_tipo(linhas[0].keys())
        n_posts = n_stories = n_ads = 0
        if tipo == "conteudo":
            for row in linhas:
                norm = _normalizar_conteudo(row, path.name)
                if _e_story(row):
                    stories_por_chave[norm["chave"]] = norm
                    n_stories += 1
                else:
                    posts_por_chave[norm["chave"]] = norm
                    n_posts += 1
        elif tipo == "ads":
            for row in linhas:
                ads_por_chave[_chave_ads(row)] = dict(row, origem=path.name)
                n_ads += 1
        else:
            print(f"AVISO: {path.name} — não reconheci as colunas (nem conteúdo, nem Ads), pulando.")
            continue
        resumo.append((path.name, tipo, n_posts, n_stories, n_ads))

    dados["posts"]   = sorted(posts_por_chave.values(), key=lambda p: p.get("publicado_em") or "")
    dados["stories"] = sorted(stories_por_chave.values(), key=lambda p: p.get("publicado_em") or "")
    dados["ads"]     = list(ads_por_chave.values())
    dados["atualizado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    OUT_FILE.parent.mkdir(exist_ok=True)
    OUT_FILE.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    for nome, tipo, n_posts, n_stories, n_ads in resumo:
        print(f"OK: {nome} ({tipo}) -> {n_posts} posts, {n_stories} stories, {n_ads} linhas de ads")
    print(f"Total acumulado: {len(dados['posts'])} posts, {len(dados['stories'])} stories, {len(dados['ads'])} linhas de ads -> {OUT_FILE}")


if __name__ == "__main__":
    main()
