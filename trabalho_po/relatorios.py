"""Apresente a sensibilidade em tabela e figura a partir dos resultados já calculados.

O relatório mantém as falhas. A figura compara apenas linhas com dieta válida,
sem tratar uma referência original preservada como melhoria do método híbrido.
"""

import csv

import matplotlib
# Agg permite salvar a figura sem abrir uma janela gráfica.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from trabalho_po.arquivos import ROOT, ler


def main():
    """Leia comparacao.csv e gere custos.png e analise_sensibilidade.md."""

    pasta = ROOT / "trabalho_po/resultados/sensibilidade"

    with (pasta / "comparacao.csv").open(encoding="utf-8", newline="") as f:
        todas = list(csv.DictReader(f))

    # O CSV lê booleanos como texto; a filtragem da figura não remove falhas da tabela.
    boas = [r for r in todas if r["valida_NASEM"] == "True"]

    if boas:

        pos = list(range(len(boas)))
        plt.figure(figsize=(10, 5))
        plt.plot(pos, [float(r["original_USD"]) for r in boas], "o-", label="Original")
        plt.plot(pos, [float(r["final_USD"]) for r in boas], "s--", label="Método híbrido")
        plt.xticks(pos, [r["cenario"] for r in boas], rotation=30, ha="right")

        # O custo pertence à formulação de um dia, mesmo com um período anual configurado.
        plt.ylabel("USD/vaca/dia")  # USD/vaca/dia
        plt.legend()
        plt.tight_layout()
        plt.savefig(pasta / "custos.png", dpi=160)
        plt.close()

    texto = "# Análise de sensibilidade\n\n"
    grade = ler(ROOT / "trabalho_po/config/sensibilidade.json")
    precos = ", ".join(f"{100 * fator:g}%" for fator in grade["multiplicadores_preco"])
    energias = ", ".join(f"{100 * fator:g}%" for fator in grade["multiplicadores_energia"])

    texto += (
        f"Preço do alimento ID (identificador) {grade['id_alimento_preco']}: {precos}; "
        f"energia: {energias}.\n\n"
    )

    texto += "| Cenário | Estado | Original USD (dólares americanos) | Final USD (dólares americanos) | Origem da dieta |\n|---|---|---:|---:|---|\n"

    # Incluir também inviabilidades e cenários sem melhoria no relatório escrito.
    for r in todas:
        texto += f"| {r['cenario']} | {r['estado']} | {r['original_USD']} | {r['final_USD']} | {r['origem_dieta']} |\n"

    texto += "\nRevisar as dietas de cada pasta para explicar substituições e restrições ativas. "
    texto += "Falhas continuam na tabela. Dietas iguais podem refletir ausência de melhoria. "
    texto += "A sensibilidade é da formulação estática com aproximação local, não do sistema global.\n"
    docs = ROOT / "trabalho_po/docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "analise_sensibilidade.md").write_text(texto, encoding="utf-8")
    print("Tabela e figura, quando houver soluções válidas, geradas.")


if __name__ == "__main__":
    main()
