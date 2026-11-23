"""Execute a grade de sensibilidade e mantenha também os cenários que falharem.

Cada combinação de preço e energia recebe uma resolução original e uma tentativa
de refinamento com PuLP (biblioteca de modelagem de programação linear em Python), com o mesmo contexto e a mesma semente de preparação.
"""

import csv
from itertools import product

from trabalho_po.arquivos import CASO, ROOT, ler, salvar
from trabalho_po.resolver import executar


def main():
    """Cruze os multiplicadores de sensibilidade.json e grave comparacao.csv."""

    cfg = ler(CASO)
    grade = ler(ROOT / "trabalho_po/config/sensibilidade.json")
    pasta = ROOT / "trabalho_po/resultados/sensibilidade"
    pasta.mkdir(parents=True, exist_ok=True)

    linhas = []
    # O produto cartesiano de três preços por duas exigências gera seis cenários.
    for fp, fe in product(grade["multiplicadores_preco"], grade["multiplicadores_energia"]):

        nome = f"preco_{fp:g}_energia_{fe:g}"
        row = {"cenario": nome, "fator_preco": fp, "fator_energia": fe,
               "estado": "falhou", "original_USD": None, "final_USD": None,
               "origem_dieta": None, "valida_NASEM": False, "erro": ""}

        try:

            # executar prepara o animal novamente, reotimizando os dois métodos no cenário.
            r = executar(cfg, pasta / nome, fp, fe, grade["id_alimento_preco"])

            row.update({"estado": r["estado"],
                        "original_USD": r["custo_original_USD_vaca_dia"],
                        "final_USD": r["custo_final_USD_vaca_dia"],
                        "origem_dieta": r["origem_dieta"], "valida_NASEM": r["valida_NASEM"]})

        except (ValueError, RuntimeError) as exc:

            # Falhas fazem parte da análise; não excluir silenciosamente essas linhas.
            row["erro"] = str(exc)
            salvar(pasta / nome / "falha.json", row)

        linhas.append(row)

    # As dietas detalhadas permanecem nas pastas dos cenários; aqui vai a comparação agregada.
    with (pasta / "comparacao.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)

    print("Cenários registrados:", len(linhas))


if __name__ == "__main__":
    main()
