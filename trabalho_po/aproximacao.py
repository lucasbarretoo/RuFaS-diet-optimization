"""Aproxime as restrições por Taylor de primeira ordem perto da dieta x0.

O gradiente é estimado numericamente por diferenças finitas.
As restrições reconhecidas como lineares usam sua forma exata.
"""

import numpy as np
from RUFAS.biophysical.animal.animal_module_constants import AnimalModuleConstants as C
from RUFAS.data_structures.feed_storage_to_animal_connection import FeedComponentType

from trabalho_po.validacao import funcoes


def aproximar(rc, x0, passo=1e-4):

    x0 = np.asarray(x0, dtype=float)
    n = len(x0)

    ndf, ee = np.array(rc.NDF_list), np.array(rc.EE_list)
    volumoso = np.array([f.feed_type is FeedComponentType.FORAGE for f in rc.feeds_used])
    req = rc.animal_requirements

    exatas = {
        "NDF_constraint_lower": (ndf - C.MINIMUM_RATION_NDF, 0.0),
        "NDF_constraint_upper": (C.MAXIMUM_RATION_NDF - ndf, 0.0),
        "forage_NDF_constraint": (ndf * volumoso - C.MINIMUM_RATION_FORAGE_NDF, 0.0),
        "fat_constraint": (C.MAXIMUM_RATION_FAT - ee, 0.0),
        "DMI_constraint_lower": (np.ones(n), -req.dry_matter * (1 - rc.dmi_constraint_fraction)),
        "DMI_constraint_upper": (-np.ones(n), rc.initial_dry_matter_requirement * (1 + rc.dmi_constraint_fraction)),
    }

    linhas = []
    for func in funcoes(rc):
        nome = func.__name__

        if nome in exatas:
            coeficientes, termo_constante = exatas[nome]
            tipo = "linear_exata"

        else:

            # valor = g(x0): saldo da restrição na dieta de referência.
            valor = float(func(x0, rc))
            # coeficientes estima o gradiente de g em x0, variando um ingrediente por vez.
            coeficientes = np.zeros(n)

            for i, feed in enumerate(rc.feeds_used):

                if feed.limit == feed.lower_limit:
                    continue

                h = max(passo, passo * max(1, abs(x0[i])))

                antes, depois = x0.copy(), x0.copy()
                antes[i] = max(feed.lower_limit, x0[i] - h)
                depois[i] = min(feed.limit, x0[i] + h)
                largura = depois[i] - antes[i]

                # Diferenças finitas estimam as derivadas sem fórmulas analíticas.
                if largura > 0:
                    coeficientes[i] = (func(depois, rc) - func(antes, rc)) / largura

            # Taylor de primeira ordem: g(x) ≈ g(x0) + gradiente(g)(x0)ᵀ(x - x0).
            # Com o gradiente estimado coeficientes: g(x) ≈ coeficientesᵀx + termo_constante,
            # onde termo_constante = g(x0) - coeficientesᵀx0.
            termo_constante = valor - float(coeficientes @ x0)
            tipo = "aproximacao_local_por_diferencas_finitas"

        if not np.isfinite(coeficientes).all() or not np.isfinite(termo_constante):
            raise ValueError(f"Coeficientes não finitos: {nome}.")

        # O modelo recebe a restrição coeficientesᵀx + termo_constante >= 0.
        linhas.append({"nome": nome, "a": coeficientes.tolist(), "b": float(termo_constante), "tipo": tipo})
        
    # A aproximação vale localmente, perto de x0.
    return linhas
