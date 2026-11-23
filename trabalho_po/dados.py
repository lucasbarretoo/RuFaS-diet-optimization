"""Extraia o cadastro da vaca e relacione alimentos, preços e composição NASEM (Academias Nacionais de Ciências, Engenharia e Medicina).

A origem é a população e a configuração de alimentos do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes). O resultado
preserva as colunas da biblioteca e registra fontes, unidades e preços em USD (dólares americanos).
Execute pela raiz do projeto: python -m trabalho_po.dados.
"""

import csv
import hashlib
import math
from datetime import datetime, timezone

from trabalho_po.arquivos import CASO, ROOT, ler, periodo, salvar


def extrair(cfg):
    """Devolva o registro individual da vaca e a tabela dos ingredientes.

    cfg é a configuração do caso base. Esta função somente lê e confere dados;
    os arquivos de saída são gravados por main().
    """
    if (cfg["padrao"], cfg["moeda"]) != ("NASEM", "USD"):
        raise ValueError("O caso deve usar NASEM e USD.")

    #Verifica se as datas da configuração são válidas
    periodo(cfg)

    # A vaca é identificada pelo ID de origem, e não pela posição na lista.
    populacao = ler(ROOT / cfg["populacao"])
    encontrados = [a for a in populacao["cows"] if a["id"] == cfg["animal_id"]]

    if len(encontrados) != 1 or encontrados[0]["animal_type"] != "LacCow":
        raise ValueError("É necessário exatamente um registro de vaca em lactação.")

    animal = encontrados[0]
    feed = ler(ROOT / cfg["alimentos"])

    # rations informa os ingredientes por categoria de combinacao de ingredientes; feeds contém seus preços.
    rations = [r for r in feed["rations"] if r["animal_combination"] == "lac_cow"]

    if len(rations) != 1:
        raise ValueError("Ração lac_cow ausente ou duplicada.")

    feedIds = [r["feed_type"] for r in rations[0]["feeds"]]

    if len(feedIds) != len(set(feedIds)):
        raise ValueError("IDs repetidos na lista de ingredientes.")  # IDs 

    compras = {r["feed_type"]: r for r in feed["feeds"]}

    if len(compras) != len(feed["feeds"]):
        raise ValueError("Preços duplicados por ID.")  # ID 

    # Le arquivo de biblioteca de composicao nutricional NASEM
    with (ROOT / cfg["biblioteca"]).open(encoding="utf-8-sig", newline="") as f:
        biblioteca = list(csv.DictReader(f))

    comp = {int(r["rufas_id"]): r for r in biblioteca}

    if len(comp) != len(biblioteca):
        raise ValueError("IDs duplicados na biblioteca.")  # IDs

    alimentos = []
    # Ordenar pelos IDs mantém a associação entre variáveis, preços e nutrientes.
    for feedId in sorted(feedIds):

        #Obtém as composições nutricionais dos alimentos de acordo com NASEM
        row = dict(comp[feedId])

        #Obtem preco do alimento e limites maximos e minimos
        preco = float(compras[feedId]["purchased_feed_cost"])
        lo, hi = float(row["lower_limit"]), float(row["limit"])

        # Conferir os principais números; preço ausente deve gerar erro, não virar zero.
        # Colunas originais: DM (matéria seca), CP (proteína bruta), NDF (fibra em
        # detergente neutro), EE (extrato etéreo), TDN (nutrientes digestíveis totais)
        # e DE (energia digestível). As chaves abaixo conservam os nomes da biblioteca.
        valores = [float(row[k]) for k in (
            "DM", "CP", "NDF", "EE", "starch", "calcium", "phosphorus", "TDN", "DE"
        )]

        if not all(math.isfinite(v) for v in [preco, lo, hi, *valores]):
            raise ValueError(f"Valor não finito no alimento {feedId}.")

        if preco < 0 or lo < 0 or hi < lo or not 0 < float(row["DM"]) <= 100:
            raise ValueError(f"Preço, matéria seca ou limites inválidos: {feedId}.")

        row["preco_USD_por_kg_MS"] = preco
        alimentos.append(row)

    return animal, alimentos


def main():
    """Grave animal_origem.json, alimentos.csv e fontes.json para o caso escolhido."""

    cfg = ler(CASO)
    animal, alimentos = extrair(cfg)
    pasta = ROOT / "trabalho_po/dados"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "animal_origem.json"

    # A gravação substitui o registro anterior diretamente, conforme a preferência do estudo.
    salvar(destino, animal)

    with (pasta / "alimentos.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(alimentos[0]))
        writer.writeheader()
        writer.writerows(alimentos)

    fontes = {}

    # Hashes identificam o conteúdo dos insumos mesmo quando seus nomes não mudam.
    caminhos = {cfg[k] for k in ("populacao", "metadata", "alimentos", "biblioteca")}
    metadata = ler(ROOT / cfg["metadata"])
    caminhos.update(blob["path"] for blob in metadata["files"].values())

    for nome in sorted(caminhos):
        fontes[nome] = hashlib.sha256((ROOT / nome).read_bytes()).hexdigest()

    salvar(pasta / "fontes.json", {
        "extraido_em_UTC": datetime.now(timezone.utc).isoformat(),
        "sha256": fontes, "moeda": "USD", "precos": cfg["politica_precos"], 
        "unidade_preco": "USD/kg_MS", "caso": cfg, 
    })

    print("Animal:", animal["id"], "Alimentos:", len(alimentos))
    
    for row in alimentos:
        print(row["rufas_id"], row["Name"], row["preco_USD_por_kg_MS"])


if __name__ == "__main__":
    # Executar main apenas no comando python -m trabalho_po.dados, não na importação.
    main()
