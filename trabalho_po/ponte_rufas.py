"""Prepare o animal e reutilize os cálculos nutricionais do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes).

A ponte obtém leite e exigências NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) sem inventar valores para o cadastro.
As unidades são kg MS (quilogramas de matéria seca), Mcal (megacalorias) e gramas por vaca/dia, conforme cada grandeza.
Execute python -m trabalho_po.ponte_rufas para exportar contexto e exigências.
"""

import copy
import random
from dataclasses import asdict
from pathlib import Path

import numpy as np
from RUFAS.input_manager import InputManager
from RUFAS.rufas_time import RufasTime
from RUFAS.biophysical.animal.animal import Animal
from RUFAS.biophysical.animal.animal_config import AnimalConfig
from RUFAS.biophysical.animal.animal_module_constants import AnimalModuleConstants
from RUFAS.biophysical.animal.milk.lactation_curve import LactationCurve
from RUFAS.biophysical.animal.milk.milk_production import MilkProduction
from RUFAS.biophysical.animal.nutrients.nutrition_supply_calculator import NutritionSupplyCalculator
from RUFAS.biophysical.animal.ration.ration_manager import RationManager
from RUFAS.biophysical.animal.ration.ration_optimizer import RationOptimizer
from RUFAS.biophysical.animal.data_types.animal_combination import AnimalCombination
from RUFAS.data_structures.feed_storage_to_animal_connection import (
    AvailableFeedsBuilder, NutrientStandard,
)

from trabalho_po.arquivos import CASO, ROOT, ler, periodo, salvar
from trabalho_po.dados import extrair


def preparar(cfg, fator_preco=1.0, fator_energia=1.0, id_preco=44):
    """Devolva animal, alimentos, exigências e contexto do primeiro dia do período.

    A preparação usa os defaults iniciais, sem simular dias de aquecimento.
    Os fatores permitem perturbar o preço de um alimento e a exigência energética.
    """

    if fator_preco <= 0 or fator_energia <= 0:
        raise ValueError("Multiplicadores devem ser positivos.")

    # Repetir os sorteios da preparação ao comparar cenários no mesmo ambiente.
    random.seed(cfg["semente"])
    np.random.seed(cfg["semente"])

    # O InputManager é compartilhado: limpar a carga anterior antes de outro cenário.
    im = InputManager()
    im.flush_pool()

    valido = im.start_data_processing(
        metadata_path=Path(cfg["metadata"]), input_root=ROOT,
        task_id="TRABALHO_PO", cross_validation_file_paths=None,
    )

    if not valido:
        raise ValueError("Entradas RuFaS inválidas; consultar os logs do InputManager.")  # RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes)

    if im.get_data("config.nutrient_standard") != "NASEM":  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
        raise ValueError("A configuração da fazenda precisa usar NASEM.")  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)

    # Carregar os parâmetros oficiais de manejo e da qualidade do leite.
    AnimalConfig.initialize_animal_config()

    inicio, fim = periodo(cfg)

    # Preservar o intervalo anual (ou de teste), mas avaliar somente seu primeiro dia.
    tempo = RufasTime(start_date=inicio, end_date=fim)
    LactationCurve.set_lactation_parameters(tempo)

    MilkProduction.set_milk_quality(
        AnimalConfig.milk_fat_percent, AnimalConfig.true_protein_percent,
        AnimalModuleConstants.MILK_LACTOSE,
    )

    # Exigências e oferta precisam usar o mesmo padrão nutricional.
    Animal.set_nutrient_standard(NutrientStandard.NASEM)  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
    NutritionSupplyCalculator.nutrient_standard = NutrientStandard.NASEM  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
    origem, tabela = extrair(cfg)

    # A cópia em memória evita modificar o registro de origem; não cria backup em disco.
    animal = Animal(copy.deepcopy(origem), tempo)

    # O construtor começa com leite zero. Calcular o leite antes das exigências da lactante.
    animal.daily_milking_update_without_history()

    # Atualizar o submodelo de fósforo usando o estado inicial preparado.
    animal._daily_nutrients_update()
    feed_cfg = im.get_data("feed")

    # Esta chamada prepara o modo automático; o campo "modo" do JSON (Notação de Objetos JavaScript) é descritivo.
    RationManager.set_ration_feeds(feed_cfg)
    ids = {int(row["rufas_id"]) for row in tabela}

    feeds = [f for f in AvailableFeedsBuilder.setup_available_feeds(
        feed_cfg, NutrientStandard.NASEM  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
    ) if f.rufas_id in ids]

    if {f.rufas_id for f in feeds} != ids:
        raise ValueError("Alimentos carregados divergem dos alimentos extraídos.")

    for feed in feeds:

        # Exemplo: 1,2 significa preço 20% maior, permanecendo em USD/kg MS (dólares americanos por quilograma de matéria seca).
        if feed.rufas_id == id_preco:
            feed.purchase_cost *= fator_preco

    hip = cfg["hipoteses"]
    # Distância zero é uma simplificação, não uma medição. A temperatura é recebida
    # pela interface, mas não entra diretamente nas exigências NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) desta lactante.
    # O texto estado_digestivo documenta a inicialização; não executa um aquecimento.
    req = animal.calculate_nutrition_requirements(
        housing=im.get_data("animal.housing"),
        walking_distance=hip["distancia_diaria_m"],
        previous_temperature=hip["temperatura_anterior_C"], available_feeds=feeds,
    )

    # Perturbar só a energia, mantendo o mesmo animal e a mesma produção.
    for nome in ("maintenance_energy", "growth_energy", "pregnancy_energy", "lactation_energy", "activity_energy"):
        setattr(req, nome, getattr(req, nome) * fator_energia)

    # Registrar os valores utilizados, inclusive perdas iniciais que podem ser zero.
    contexto = {
        "start_date": cfg["start_date"], "end_date": cfg["end_date"],
        "data_avaliacao": cfg["start_date"], "dias_no_periodo": (fim - inicio).days + 1,
        "animal_id_origem": origem["id"], "animal_id_execucao": animal.id,
        "peso_kg": animal.body_weight, "dias_em_lactacao": animal.days_in_milk,
        "paridade": animal.calves, "leite_kg_dia": animal.milk_production.daily_milk_produced,
        "gordura_leite_percentual": MilkProduction.fat_percent,
        "proteina_verdadeira_leite_percentual": MilkProduction.true_protein_percent,
        "lactose_percentual": MilkProduction.lactose_percent,
        "escore_corporal": animal.body_condition_score_5,
        "metano_g_dia": animal.enteric_methane,
        "nitrogenio_urinario_kg_dia": animal.digestive_system.manure_excretion.urine_nitrogen,
        "fosforo_submodelo_g_dia": animal.nutrients.phosphorus_requirement,
        "alojamento": im.get_data("animal.housing"), "hipoteses": hip,
        "estado_nutricional_anterior": "defaults_RuFaS; previous_nutrition_supply=None",
        "fator_preco": fator_preco, "id_preco": id_preco, "fator_energia": fator_energia,
    }

    valores = [req.dry_matter, req.total_energy_requirement,
               req.metabolizable_protein, contexto["leite_kg_dia"]]

    if not all(np.isfinite(v) and v > 0 for v in valores):
        raise ValueError("Leite ou exigências inválidos; revisar a inicialização.")

    return animal, feeds, req, contexto


def original(animal, feeds, req):
    """Obtenha a referência SLSQP (programação sequencial por mínimos quadrados) em modo automático para esse mesmo contexto.

    O retorno é (OptimizeResult, RationConfig), contrato usado também pelo RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes).
    Metano é informado em g/dia (gramas por dia) e nitrogênio urinário em kg/dia (quilogramas por dia).
    """
    return RationOptimizer().attempt_optimization(
        nutrient_standard=NutrientStandard.NASEM,  # NASEM (Academias Nacionais de Ciências, Engenharia e Medicina)
        pen_average_body_weight=animal.body_weight,
        pen_average_enteric_methane=animal.enteric_methane,
        pen_average_urine_nitrogen=animal.digestive_system.manure_excretion.urine_nitrogen,
        requirements=req, initial_dry_matter_requirement=req.dry_matter,
        initial_protein_requirement=req.metabolizable_protein,
        pen_available_feeds=feeds, animal_combination=AnimalCombination.LAC_COW,
    )


def main():
    """Exporte contexto_animal.json e exigencias.json com as unidades dos cálculos."""

    _, _, req, contexto = preparar(ler(CASO))
    pasta = ROOT / "trabalho_po/dados"
    salvar(pasta / "contexto_animal.json", contexto)

    # asdict converte a estrutura de exigências em dicionários que podem ir para JSON (Notação de Objetos JavaScript).
    salvar(pasta / "exigencias.json", {
        "valores": asdict(req), "energia_total_Mcal_dia": req.total_energy_requirement,
        "unidades": {"energia": "Mcal/dia", "proteina_metabolizavel": "g/dia",  # Mcal/dia (megacalorias por dia); g/dia (gramas por dia)
                     "calcio_e_fosforo": "g/dia", "materia_seca": "kg_MS/dia"},  # g/dia (gramas por dia)
    })
    
    print("Leite kg/dia:", contexto["leite_kg_dia"])  # kg/dia (quilogramas por dia)
    print("MS kg/dia:", req.dry_matter, "Energia Mcal/dia:", req.total_energy_requirement)  # MS (matéria seca); kg/dia (quilogramas por dia); Mcal/dia (megacalorias por dia)


if __name__ == "__main__":
    main()
