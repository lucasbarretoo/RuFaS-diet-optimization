"""Compare a produtividade anual simulada usando as dietas original e híbrida.

As entradas das duas execuções precisam ser equivalentes. O leite é observado
nos registros diários do simulador, não fixado como no caso estático. A matéria
seca registrada é formulada, e não uma medição de consumo dos animais.
"""

import argparse
import csv
import math
from datetime import datetime, timedelta

from trabalho_po.arquivos import ROOT, ler, periodo


def carregar_metodo(pasta):
    
    """Confira calendário, quantidades e reduções do leite em uma execução completa."""
    
    resumo = ler(pasta / "resumo_periodo.json")
    entradas = ler(pasta / "entradas_execucao.json")
    inicio, fim = periodo(entradas["configuracao"])
    
    esperadas = [(inicio + timedelta(days=n)).date().isoformat()
                 for n in range((fim - inicio).days + 1)]
    
    dados = {}
    
    with (pasta / "leite_diario.csv").open(encoding="utf-8", newline="") as arquivo:
        
        for linha in csv.DictReader(arquivo):
            
            data = datetime.fromisoformat(linha["data"]).date().isoformat()
            
            if data in dados:
                raise ValueError("Data de produção duplicada.")
            
            registro = {"lactantes": int(linha["lactantes"]),
                        "leite_kg": float(linha["leite_kg"]),
                        "reducao_leite_kg": float(linha["reducao_leite_kg"]),
                        "leite_sem_reducao_kg": float(linha["leite_sem_reducao_kg"]),
                        "ids": set(filter(None, linha["ids_execucao"].split(",")))}
            
            valores = [registro[campo] for campo in
                       ("lactantes", "leite_kg", "reducao_leite_kg", "leite_sem_reducao_kg")]
            
            if not all(math.isfinite(valor) and valor >= 0 for valor in valores):
                raise ValueError("Produção ou contagem de animais inválida.")
            
            if len(registro["ids"]) != registro["lactantes"]:
                raise ValueError("Identificadores divergem da contagem de lactantes.")
            
            if registro["lactantes"] == 0 and registro["leite_kg"] != 0:
                raise ValueError("Produção de leite sem vacas lactantes.")
            
            if not math.isclose(registro["leite_sem_reducao_kg"],
                                registro["leite_kg"] + registro["reducao_leite_kg"], abs_tol=1e-8):
                raise ValueError("Produção e redução de leite não conferem.")
            
            dados[data] = registro
    
    if list(dados) != esperadas or resumo["dias_concluidos"] != len(esperadas):
        raise ValueError("A comparação exige todos os dias consecutivos do período.")
    
    with (pasta / "custos_diarios.csv").open(encoding="utf-8", newline="") as arquivo:
        custos = list(csv.DictReader(arquivo))
    
    if [linha["data"] for linha in custos] != esperadas:
        raise ValueError("Datas das dietas divergem dos registros de leite.")
    
    for linha in custos:
        registro = dados[linha["data"]]
        quantidade = float(linha["kg_MS_formulada_lactantes"])
    
        if not math.isfinite(quantidade) or quantidade < 0:
            raise ValueError("Matéria seca formulada inválida.")
    
        if int(linha["lactantes"]) != registro["lactantes"]:
            raise ValueError("Contagens de lactantes divergem entre os registros.")
    
        registro["materia_seca_formulada_kg"] = quantidade
    
    return dados, entradas


def comparar(pasta):
    
    """Devolva indicadores dos métodos e diferenças pareadas por data."""
    
    original, fonte_original = carregar_metodo(pasta / "original")
    nossa, fonte_nossa = carregar_metodo(pasta / "pulp")
    
    if fonte_original != fonte_nossa:
        raise ValueError("As configurações, sementes e fontes das duas execuções devem ser iguais.")
    
    if list(original) != list(nossa):
        raise ValueError("Os métodos precisam cobrir as mesmas datas.")
    
    indicadores = []
    for nome, dados in (("original_RuFaS", original), ("nossa_dieta", nossa)):
        
        leite = sum(r["leite_kg"] for r in dados.values())
        vacas_dia = sum(r["lactantes"] for r in dados.values())
        materia_seca = sum(r["materia_seca_formulada_kg"] for r in dados.values())
        
        indicadores.append({
            "metodo": nome, "dias": len(dados), "leite_total_kg": leite,
            "vacas_lactantes_dia": vacas_dia,
            "leite_kg_por_vaca_lactante_dia": leite / vacas_dia if vacas_dia else None,
            "materia_seca_formulada_kg": materia_seca,
            "leite_kg_por_kg_materia_seca_formulada": leite / materia_seca if materia_seca else None,
            "reducao_leite_acumulada_kg": sum(r["reducao_leite_kg"] for r in dados.values()),
            "dias_com_reducao_leite": sum(r["reducao_leite_kg"] > 1e-8 for r in dados.values()),
        })

    diarios = []
    for data, antes in original.items():
        
        depois = nossa[data]
        
        diarios.append({
            "data": data, "leite_RuFaS_kg": antes["leite_kg"], "leite_nossa_kg": depois["leite_kg"],
            "diferenca_leite_kg": depois["leite_kg"] - antes["leite_kg"],
            "lactantes_RuFaS": antes["lactantes"], "lactantes_nossa": depois["lactantes"],
            "mesmos_animais": antes["ids"] == depois["ids"],
            "reducao_RuFaS_kg": antes["reducao_leite_kg"], "reducao_nossa_kg": depois["reducao_leite_kg"],
            "leite_sem_reducao_RuFaS_kg": antes["leite_sem_reducao_kg"],
            "leite_sem_reducao_nossa_kg": depois["leite_sem_reducao_kg"],
            "materia_seca_formulada_RuFaS_kg": antes["materia_seca_formulada_kg"],
            "materia_seca_formulada_nossa_kg": depois["materia_seca_formulada_kg"],
        })

    return indicadores, diarios


def gravar_tabela(caminho, linhas):

    """Grave os valores sem arredondar os arquivos usados na análise."""
    
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)


def gerar_grafico(caminho, diarios):
    
    """Mostre o leite diário e a diferença, sem ocultar séries sobrepostas."""
    
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datas = [datetime.fromisoformat(r["data"]) for r in diarios]
    figura, eixos = plt.subplots(2, 1, figsize=(11, 7), sharex=True, layout="constrained")
    eixos[0].plot(datas, [r["leite_RuFaS_kg"] for r in diarios], label="RuFaS original", color="#619884")
    eixos[0].plot(datas, [r["leite_nossa_kg"] for r in diarios], label="Nossa dieta", color="#173C37", linestyle="--")
    eixos[0].set_ylabel("Leite dos lotes lactantes\n(quilogramas por dia)")
    eixos[0].set_ylim(bottom=0)
    eixos[0].legend()
    eixos[0].set_title("Produtividade simulada — mesmas entradas e mesmo período")
    eixos[1].plot(datas, [r["diferenca_leite_kg"] for r in diarios], color="#176F59")
    eixos[1].axhline(0, color="gray", linewidth=0.8)
    eixos[1].set_ylabel("Nossa dieta − original\n(quilogramas por dia)")
    eixos[1].set_xlabel("Data da simulação")
    
    for eixo in eixos:
        eixo.grid(alpha=0.2)
    
    figura.savefig(caminho, dpi=160)
    plt.close(figura)


def main():
    
    """Compare execuções anuais equivalentes; o preço do leite não é necessário."""
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--execucao", default="produtividade_2013")
    args = parser.parse_args()
    
    if not args.execucao.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Nome de execução inválido.")
    
    pasta = ROOT / "trabalho_po/resultados/integracao" / args.execucao
    indicadores, diarios = comparar(pasta)
    destino = ROOT / "trabalho_po/resultados/produtividade" / args.execucao
    destino.mkdir(parents=True, exist_ok=True)
    gravar_tabela(destino / "comparacao.csv", indicadores)
    gravar_tabela(destino / "comparacao_diaria.csv", diarios)
    gerar_grafico(destino / "produtividade.png", diarios)
    original, nossa = indicadores
    diferenca = nossa["leite_total_kg"] - original["leite_total_kg"]
    percentual = 100 * diferenca / original["leite_total_kg"] if original["leite_total_kg"] else None
    dias_diferentes = [r for r in diarios if abs(r["diferenca_leite_kg"]) > 1e-8]
    mesmos_animais = sum(r["mesmos_animais"] for r in diarios)
    mesma_producao_sem_reducao = all(math.isclose(r["leite_sem_reducao_RuFaS_kg"],
                                                    r["leite_sem_reducao_nossa_kg"], abs_tol=1e-8)
                                       for r in diarios)
    texto = "# Impacto da dieta na produtividade simulada\n\n"
    texto += (f"Execução: `{args.execucao}`. Período: {diarios[0]['data']} a {diarios[-1]['data']}. "
              "As configurações, sementes e assinaturas dos arquivos de entrada foram conferidas antes da comparação. "
              "A referência é a formulação original no cenário anual do freestall adaptado ao modo de animais e nutrição, "
              "não uma execução de fazenda completa com entradas diferentes.\n\n")
    texto += "| Indicador | RuFaS original | Nossa dieta |\n|---|---:|---:|\n"
    for rotulo, chave in [
        ("Leite total no período, quilogramas", "leite_total_kg"),
        ("Soma de vacas lactantes por dia", "vacas_lactantes_dia"),
        ("Quilogramas de leite por vaca lactante por dia", "leite_kg_por_vaca_lactante_dia"),
        ("Matéria seca formulada no período, quilogramas", "materia_seca_formulada_kg"),
        ("Leite por quilograma de matéria seca formulada", "leite_kg_por_kg_materia_seca_formulada"),
        ("Redução acumulada aplicada pelo simulador, quilogramas", "reducao_leite_acumulada_kg"),
    ]:
        valores = [f"{r[chave]:.6f}" if r[chave] is not None else "Não definido" for r in indicadores]
        texto += f"| {rotulo} | {valores[0]} | {valores[1]} |\n"
    texto += (f"\nDiferença total (nossa dieta menos original): **{diferenca:.6f} quilogramas**. "
              f"Variação relativa: **{percentual:.6f}%**.\n\n" if percentual is not None else
              f"\nDiferença total: {diferenca:.6f} quilogramas. Sem percentual porque o volume original é zero.\n\n")
    texto += (f"Os mesmos identificadores de lactantes estiveram presentes em {mesmos_animais} dos {len(diarios)} dias. "
              f"Diferenças de leite acima de 0,00000001 quilograma ocorreram em {len(dias_diferentes)} dia(s). "
              "A produtividade por vaca é o total de leite dividido pela soma de lactantes dos dias, "
              "evitando confundir variação do rebanho com produtividade individual.\n\n")
    if mesmos_animais != len(diarios):
        texto += ("As populações diárias diferiram em parte do período. Não atribuir a diferença "
                  "de volume total somente à produtividade individual das dietas.\n\n")
    if mesma_producao_sem_reducao:
        texto += ("A produção antes das reduções registradas foi igual nos dois métodos em todos os dias. "
                  "Assim, as diferenças de leite desta execução decorrem das reduções aplicadas pelo simulador, "
                  "e não de uma curva de lactação potencial maior calculada para a nova dieta.\n\n")
    for r in dias_diferentes:
        texto += (f"- {r['data']}: diferença de {r['diferenca_leite_kg']:.6f} quilogramas; "
                  f"redução original de {r['reducao_RuFaS_kg']:.6f} e nossa de {r['reducao_nossa_kg']:.6f} quilogramas; "
                  f"lactantes: {r['lactantes_RuFaS']} e {r['lactantes_nossa']}.\n")
    texto += ("\n## Limites de interpretação\n\n"
              "O leite do modelo segue uma curva de lactação, com variação aleatória e reduções de meta quando necessário. "
              "Ele não constitui um ensaio biológico de resposta a cada ingrediente. Uma execução com uma semente "
              "não demonstra ganho consistente ou significância estatística. O resultado deve ser descrito "
              "como impacto simulado nas condições avaliadas. A relação leite/matéria seca formulada não é "
              "eficiência alimentar medida por consumo real.\n\n"
              "Consultar também as ocorrências de manejo e as falhas de formulação nos resumos de cada método. "
              "Esta análise não requer preço do leite.\n\n"
              "Fontes: `leite_diario.csv`, `custos_diarios.csv`, `resumo_periodo.json` e `entradas_execucao.json` "
              "das duas execuções. Código da produção: "
              "[milk_production.py](../../RUFAS/biophysical/animal/milk/milk_production.py).\n")
    (ROOT / "trabalho_po/docs/impacto_produtividade.md").write_text(texto, encoding="utf-8")
    print("Comparação de produtividade salva em", destino)
    print("Diferença de leite no período, em quilogramas:", diferenca)


if __name__ == "__main__":
    main()
