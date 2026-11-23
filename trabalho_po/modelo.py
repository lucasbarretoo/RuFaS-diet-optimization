"""Monte o problema linear de menor custo com as variáveis de alimentação.

Cada x_i representa kg (quilogramas) de matéria seca do ingrediente por vaca/dia.
O preço em USD/kg MS (dólares americanos por quilograma de matéria seca) produz um objetivo em USD/vaca/dia (dólares americanos por vaca por dia).
"""

import pulp


def construir(rc, linhas, x0, regiao):
    """Devolva o modelo PuLP (biblioteca de modelagem de programação linear em Python) e suas variáveis na ordem dos alimentos de rc."""
    
    model = pulp.LpProblem("dieta_NASEM_aproximada", pulp.LpMinimize)
    variaveis = []

    for i, feed in enumerate(rc.feeds_used):

        # A região de confiança limita a mudança em torno da última dieta válida.
        # O mínimo de 1 na escala permite introduzir ingredientes inicialmente zerados.
        raio = regiao * max(1, abs(float(x0[i])))

        # Intersectar a região local com inclusão permitida e não negatividade.
        lo = max(feed.lower_limit, float(x0[i]) - raio, 0)
        hi = min(feed.limit, float(x0[i]) + raio)

        if lo > hi:
            raise ValueError(f"Limites locais incompatíveis: {feed.rufas_id}.")

        #Cria as variáveis de decisão
        variaveis.append(pulp.LpVariable(f"x_{feed.rufas_id}", cat=pulp.LpContinuous, lowBound=lo, upBound=hi))

    #Função objetivo
    # Preço vezes quantidade, somado para todos os ingredientes.
    model += pulp.lpSum(p * x for p, x in zip(rc.price_list, variaveis)), "custo_USD_vaca_dia"
    
    for linha in linhas:
        # Cada linha já foi organizada na convenção a*x+b >= 0.
        model += (
            pulp.lpSum(a * x for a, x in zip(linha["a"], variaveis)) + linha["b"] >= 0,
            linha["nome"],
        )

    return model, variaveis
