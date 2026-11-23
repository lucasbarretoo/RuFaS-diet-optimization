"""Execute uma simulação do estudo e registre leite e chamadas do otimizador.

Exemplo: python -m trabalho_po.simular --metodo pulp --execucao ano_2013.
As configurações precisam ter sido geradas por preparar_simulacao.py.
"""

import argparse
import csv
import sys
from datetime import timedelta
from hashlib import sha256

from trabalho_po.arquivos import ROOT, CASO, ler, periodo, salvar


def concluir_periodo(saida, cfg, metodo, chamadas_totais):

    """Confira todos os dias e registre custos formulados e ocorrências do simulador."""

    inicio, fim = periodo(cfg)

    with (saida / "custos_diarios.csv").open(encoding="utf-8", newline="") as f:
        dias = list(csv.DictReader(f))

    datas = [r["data"] for r in dias]
    esperado = (fim - inicio).days + 1

    if len(dias) != esperado or len(set(datas)) != esperado:
        raise RuntimeError(f"Período incompleto: {len(dias)} registros para {esperado} dias esperados.")
    
    if datas[0] != inicio.date().isoformat() or datas[-1] != fim.date().isoformat():
        raise RuntimeError("Datas registradas divergem do período configurado.")
    
    if datas != [(inicio + timedelta(days=n)).date().isoformat() for n in range(esperado)]:
        raise RuntimeError("O registro deve conter todos os dias consecutivos, em ordem.")
    
    chamadas = [ler(arquivo) for arquivo in (saida / "chamadas_otimizador").glob("chamada_*.json")]
    estados = {}
    
    for chamada in chamadas:
        estado = chamada["estado"]
        estados[estado] = estados.get(estado, 0) + 1
    
    ocorrencias = {}
    
    for arquivo in (saida / "logs").glob("*_errors_*.json"):
    
        for nome, registro in ler(arquivo).items():
    
            if isinstance(registro, dict) and registro.get("values"):
                ocorrencias[nome] = len(registro["values"])
    
    salvar(saida / "resumo_periodo.json", {
        "metodo": metodo, "start_date": cfg["start_date"], "end_date": cfg["end_date"],
        "tipo_simulacao": cfg["simulation_type"],
        "dias_concluidos": len(dias), "intervalo_reformulacao_dias": 1,
        "chamadas_otimizador_hibrido": chamadas_totais,
        "estados_das_chamadas": estados,
        "ocorrencias_registradas_pelo_RuFaS": ocorrencias,
        "minimo_lactantes_no_periodo": min(int(r["lactantes"]) for r in dias),
        "maximo_lactantes_no_periodo": max(int(r["lactantes"]) for r in dias),
        "kg_MS_formulada_lactantes_periodo": sum(float(r["kg_MS_formulada_lactantes"]) for r in dias),
        "custo_formulado_lactantes_USD_periodo": sum(float(r["custo_formulado_lactantes_USD"]) for r in dias),
        "observacao": "Custo das rações formuladas dos lotes lactantes; não é despesa de compra nem consumo efetivamente medido.",
    })


def main():
    
    """Selecione o método, prepare a instrumentação e chame a entrada oficial do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes)."""
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--metodo", choices=("original", "pulp"), default="pulp")
    parser.add_argument("--execucao", default="periodo_configurado")
    args = parser.parse_args()
    
    if not args.execucao.replace("_", "").replace("-", "").isalnum():
        raise ValueError("Use letras, números, _ e - no nome da execução.")
    
    from RUFAS.biophysical.animal.herd_manager import HerdManager
    import RUFAS.biophysical.animal.pen as pen_modulo
    from RUFAS.main import main as main_rufas
    from trabalho_po.integracao import OtimizadorPuLP, adicionar_animal_ao_lote
    from RUFAS.biophysical.animal.data_types.animal_combination import AnimalCombination
    import RUFAS.input_manager as entrada_modulo

    # Usar o esquema experimental sem alterar os arquivos originais do simulador.
    entrada_modulo.PROPERTIES_FILE_PATHS["default"] = (
        ROOT / "trabalho_po/config/rufas" / args.metodo / "propriedades.json"
    )

    #Ao adicionar um animal a um lote vazio no modo automático, 
    # o código original passa o dicionário de todas as categorias, 
    # mas a função espera apenas a lista de alimentos da categoria do lote.
    HerdManager._add_animal_to_pen_and_id_map = adicionar_animal_ao_lote

    #resultados
    saida = ROOT / "trabalho_po/resultados/integracao" / args.execucao / args.metodo
    
    # Uma pasta distinta identifica cada execução;
    if saida.exists():
        raise ValueError("A pasta desta execução já existe. Escolha outro --execucao para preservar os resultados.")
    
    saida.mkdir(parents=True)
    
    # execucao com metodo pulp
    if args.metodo == "pulp":

        # Altera otimizador de rações para o PULP
        # Substituir a classe apenas neste processo, sem editar o código-fonte de Pen.
        OtimizadorPuLP.trilha = saida / "chamadas_otimizador"
        OtimizadorPuLP.contador = 0
        pen_modulo.RationOptimizer = OtimizadorPuLP
    
    cfg = ler(ROOT / "trabalho_po/config/rufas" / args.metodo / "config.json")
    pasta_configuracao = ROOT / "trabalho_po/config/rufas" / args.metodo
    metadata_fazenda = ler(pasta_configuracao / "metadata_fazenda.json")
    tarefas = ler(pasta_configuracao / "tarefas.json")
    fontes = {nome: sha256((pasta_configuracao / nome).read_bytes()).hexdigest()
              for nome in ("config.json", "animal.json", "populacao.json", "propriedades.json")}
    
    for nome in ("feed", "weather", "lactation", "NASEM_Comp"):
        caminho = ROOT / metadata_fazenda["files"][nome]["path"]
        fontes[nome] = sha256(caminho.read_bytes()).hexdigest()
    
    salvar(saida / "entradas_execucao.json", {
        "configuracao": cfg, "random_seeds": tarefas["tasks"][0]["random_seeds"],
        "sha256_fontes": fontes,
    })
    
    inicio_periodo, _ = periodo(cfg)

    formulacao_original = HerdManager.formulate_rations

    def formulacao_com_contexto(self, available_feeds, current_temperature, ration_interval_length, simulation_day):
       
        """A formulação ocorre antes da rotina diária: datar suas chamadas desde esse ponto."""
       
        OtimizadorPuLP.dia_atual = simulation_day
        OtimizadorPuLP.data_atual = (inicio_periodo + timedelta(days=simulation_day)).date().isoformat()
       
        return formulacao_original(self, available_feeds, current_temperature, ration_interval_length, simulation_day)

    HerdManager.formulate_rations = formulacao_com_contexto

    rotina_original = HerdManager.execute_daily_routines

    def rotina_com_registro(self, available_feeds, time, weather):
        """Execute a rotina nativa e acrescente leite e IDs (identificadores) das lactantes ao CSV (valores separados por vírgulas) diário."""
        
        OtimizadorPuLP.dia_atual = time.simulation_day
        OtimizadorPuLP.data_atual = time.current_date.date().isoformat()

        resultado = rotina_original(self, available_feeds, time, weather)

        # seleciona vacas em lactação
        lactantes = [a for a in self.cows if a.is_milking]

        # Reúne os dados de produção de leite do dia
        linha = {"dia": time.simulation_day, "data": time.current_date.isoformat(),
                 "lactantes": len(lactantes),
                 "leite_kg": sum(a.milk_production.daily_milk_produced for a in lactantes),
                 "reducao_leite_kg": sum(a.milk_production.milk_production_reduction for a in lactantes),
                 "leite_sem_reducao_kg": sum(a.milk_production.daily_milk_produced + a.milk_production.milk_production_reduction for a in lactantes),
                 "ids_execucao": ",".join(str(a.id) for a in lactantes)}
                 
        arquivo = saida / "leite_diario.csv"
        novo = not arquivo.exists()
        with arquivo.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linha))
            if novo:
                w.writeheader()
            w.writerow(linha)

        # Registrar as quantidades formuladas, não multiplicar uma dieta fixa por 365.
        precos = {alimento.rufas_id: alimento.purchase_cost for alimento in available_feeds}
        ingredientes = []

        for lote in self.all_pens:

            if lote.animal_combination is not AnimalCombination.LAC_COW or not lote.is_populated:
                continue

            animais = len(lote.animals_in_pen)

            for codigo, quantidade in lote.ration.items():

                codigo = int(codigo)

                # Registrar quantidades formuladas por ingrediente e lote, preços e custos, todos do dia atual.
                ingredientes.append({
                    "dia": time.simulation_day, "data": time.current_date.date().isoformat(),
                    "lote": lote.id, "animais": animais, "rufas_id": codigo,
                    "kg_MS_formulada_animal_dia": float(quantidade),
                    "kg_MS_formulada_lote_dia": float(quantidade) * animais,
                    "preco_USD_kg_MS": precos[codigo],
                    "custo_formulado_USD_lote_dia": float(quantidade) * animais * precos[codigo], #custo alimentação formulada, não consumo efetivo
                })

        dietas = saida / "dietas_diarias.csv"

        if ingredientes:

            novo = not dietas.exists()

            with dietas.open("a", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(ingredientes[0]))
                if novo:
                    w.writeheader()
                w.writerows(ingredientes)

        registro = {
            "dia": time.simulation_day, "data": time.current_date.date().isoformat(),
            "lactantes": len(lactantes),
            "kg_MS_formulada_lactantes": sum(r["kg_MS_formulada_lote_dia"] for r in ingredientes),
            "custo_formulado_lactantes_USD": sum(r["custo_formulado_USD_lote_dia"] for r in ingredientes),
        }

        custos = saida / "custos_diarios.csv"
        novo = not custos.exists()

        with custos.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(registro))
            if novo:
                w.writeheader()
            w.writerow(registro)

        return resultado

    # conserva o retorno original, necessário ao restante da simulação.
    HerdManager.execute_daily_routines = rotina_com_registro


    #Inicia a execução oficial do RuFaS
    metadata = ROOT / "trabalho_po/config/rufas" / args.metodo / "metadata_tarefas.json"
    # -p: metadata de tarefas; -g: sem gráficos; -o: resultados; -l: logs.
    sys.argv = ["main.py", "-p", str(metadata), "-g", "-o", str(saida),
                "-l", str(saida / "logs")]
    main_rufas()
    arquivo = saida / "leite_diario.csv"

    # Terminar o processo não basta: verificar evidência de execução e uso do adaptador.
    if not arquivo.exists():
        raise RuntimeError("Não há registro diário; verificar falhas do gerenciador de tarefas.")
    
    if args.metodo == "pulp" and OtimizadorPuLP.contador == 0:
        raise RuntimeError("O adaptador não recebeu nenhuma formulação NASEM de lactantes.")  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
    
    cfg = ler(ROOT / "trabalho_po/config/rufas" / args.metodo / "config.json")
    concluir_periodo(saida, cfg, args.metodo, OtimizadorPuLP.contador)
    print("Simulação registrada em", saida)


if __name__ == "__main__":
    main()
