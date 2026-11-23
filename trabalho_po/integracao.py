"""Adapte a proposta PuLP (biblioteca de modelagem de programação linear em Python) ao contrato do otimizador usado pelos lotes do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes).

A classe conserva os auxiliares de RationOptimizer e retorna a mesma dupla
de resultado e configuração. A seleção da classe ocorre no lançador simular.py.
"""

import inspect

import numpy as np
from RUFAS.biophysical.animal.data_types.animal_combination import AnimalCombination
from RUFAS.biophysical.animal.ration.ration_optimizer import RationOptimizer
from RUFAS.data_structures.feed_storage_to_animal_connection import NutrientStandard

from trabalho_po.arquivos import ROOT, ler, salvar
from trabalho_po.resolver import refinar
from trabalho_po.validacao import por_id, validar


def adicionar_animal_ao_lote(self, animal, available_feeds, current_day_conditions, simulation_day):

    """Conserve o fluxo nativo e selecione os alimentos da categoria ao abrir um lote.

    Ao incluir um animal em um lote vazio no modo automático, a implementação
    original passa RationManager.ration_feeds inteiro para _find_pen_available_feeds.
    Esse dicionário associa categorias de animais às suas listas de identificadores
    de alimentos, mas a função espera somente uma dessas listas.

    """

    from RUFAS.biophysical.animal.ration.ration_manager import RationManager

    animal_combination = self.ANIMAL_GROUPING_SCENARIO.find_animal_combination(animal)

    pen = min(self.pens_by_animal_combination[animal_combination],
              key=lambda lote: lote.current_stocking_density)

    if pen.is_populated:
        pen.update_animals([animal], animal_combination, available_feeds)

    else:

        pen.insert_single_animal_into_animals_in_pen_map(animal)
        pen.set_animal_nutritional_requirements(
            temperature=current_day_conditions.mean_air_temperature, available_feeds=available_feeds)

        if self.is_ration_defined_by_user:
            ids = RationManager.get_user_defined_ration_feeds(pen.animal_combination)

        else:
            # Obter os identificadores desta categoria, não o dicionário de todas
            # as categorias. É esta seleção que corrige a chamada original.
            ids = RationManager.get_ration_feeds(pen.animal_combination)

        alimentos = self._find_pen_available_feeds(available_feeds, ids)

        self._reformulate_ration_single_pen(
            pen=pen, pen_available_feeds=alimentos,
            current_temperature=current_day_conditions.mean_air_temperature,
            simulation_day=simulation_day)

    self.animal_to_pen_id_map[animal.id] = pen.id


class OtimizadorPuLP(RationOptimizer):

    """Adaptador experimental para lactantes, mantendo os auxiliares originais."""

    # O lançador informa a pasta de diagnóstico e zera o contador por execução.
    trilha = None
    contador = 0
    dia_atual = None
    data_atual = None

    def attempt_optimization(self, *args, **kwargs):

        """Refine a referência válida somente para lactantes NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) em modo automático."""

        # bind associa argumentos posicionais/nomeados à assinatura original.
        argumentos = inspect.signature(RationOptimizer.attempt_optimization).bind(self, *args, **kwargs)
        argumentos.apply_defaults()
        dados = argumentos.arguments

        # O otimizador original calcula a dieta e devolve também sua RationConfig
        sol, rc = super().attempt_optimization(*args, **kwargs)

        dentro_escopo = (
            dados["nutrient_standard"] is NutrientStandard.NASEM
            and dados["animal_combination"] is AnimalCombination.LAC_COW
            and dados["user_defined_ration_dictionary"] is None
        )

        if not dentro_escopo:
            # Preservar o fluxo nativo nas demais categorias e padrões.
            return sol, rc

        # Valida a dieta (rationConfig) de referência de acordo com NASEM
        ajustes = ler(ROOT / "trabalho_po/config/limites.json")
        ok, _ = validar(por_id(sol.x, rc), rc, ajustes["tolerancia_relativa"])

        if not ok:

            # Permitir que o chamador trate a falha, em vez de aceitar uma dieta inválida.
            sol.success = False
            sol.message = "Referência original não passou na validação NASEM."

        if sol.success:

            # Chama refinamento de dieta atraves do PULP
            x, info = refinar(rc, sol.x, ajustes)

            sol.x = x #Qtds finais de ingredientes apos refinamento
            sol.fun = float(np.dot(rc.price_list, x)) #Custo final da dieta apos refinamento
            sol.message = info["estado"]
            sol.origem_dieta = info["origem_dieta"]

        else:
            info = {"estado": "falha_referencia_original", "origem_dieta": "sem_dieta_validada"}
        
        type(self).contador += 1
        
        # Cada chamada registra se houve melhoria ou se a referência foi mantida.
        if self.trilha is not None:

            salvar(self.trilha / f"chamada_{type(self).contador:05d}.json", {
                "dia": type(self).dia_atual, "data": type(self).data_atual,
                "success": bool(sol.success), "mensagem": str(sol.message), **info,
                "quantidades_por_id": por_id(sol.x, rc),
            })
        return sol, rc
