"""Confira uma dieta nas funções nutricionais NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) originais do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes).

Um LP (programação linear) ótimo pode falhar nesta conferência porque contém aproximações locais.
As quantidades chegam relacionadas por rufas_id, sem depender da ordem das chaves.
O diagnóstico registra resíduos, unidades e tolerâncias por restrição.
"""

from collections.abc import Mapping
from math import isfinite
from numbers import Integral


def _normalizar_id(codigo):
    """Aceite um ID (identificador) inteiro ou seu texto decimal, como ocorre ao ler um JSON (Notação de Objetos JavaScript)."""
    if isinstance(codigo, str) and codigo.isdecimal():
        return int(codigo)
    if isinstance(codigo, Integral) and not isinstance(codigo, bool):
        return int(codigo)
    raise ValueError(f"ID de alimento inválido: {codigo!r}; use um inteiro ou seu texto decimal.")  # ID (identificador)


def _ids_alimentos(rc):
    """Confira se cada alimento da configuração possui um ID (identificador) único."""
    ids = [_normalizar_id(feed.rufas_id) for feed in rc.feeds_used]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("A configuração deve conter alimentos com IDs únicos, sem IDs repetidos.")  # IDs (identificadores)
    return ids


def _quantidade(valor):
    """Converta uma quantidade escalar em kg MS/vaca/dia (quilogramas de matéria seca por vaca por dia) e rejeite valores não finitos."""
    try:
        if isinstance(valor, bool):
            raise ValueError("Booleano não representa quantidade.")
        quantidade = float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Quantidade inválida: {valor!r}; informe um número em kg MS/vaca/dia.") from exc  # kg MS/vaca/dia (quilogramas de matéria seca por vaca por dia)
    if not isfinite(quantidade):
        raise ValueError("As quantidades devem ser números finitos em kg MS/vaca/dia.")  # kg MS/vaca/dia (quilogramas de matéria seca por vaca por dia)
    return quantidade


def por_id(vetor, rc):
    """Adapte o vetor devolvido pelo solver a {rufas_id: quantidade}.

    Somente este adaptador usa a ordem interna do resultado do solver, que deve
    corresponder à sua RationConfig. A validação pública recebe o dicionário.
    """
    ids = _ids_alimentos(rc)
    if isinstance(vetor, (Mapping, str, bytes)) or getattr(vetor, "ndim", 1) != 1:
        raise ValueError("O adaptador espera um vetor unidimensional do solver.")
    try:
        valores = list(vetor)
    except TypeError as exc:
        raise ValueError("O adaptador espera um vetor de quantidades do solver.") from exc
    if len(valores) != len(ids):
        raise ValueError("O resultado do solver deve conter uma quantidade para cada alimento.")
    return {codigo: _quantidade(valor) for codigo, valor in zip(ids, valores, strict=True)}


def funcoes(rc):
    """Obtenha as restrições NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) do otimizador original para a configuração rc."""
    # Carregar o simulador somente quando suas funções nutricionais forem usadas.
    from RUFAS.biophysical.animal.ration.ration_optimizer import RationOptimizer

    opt = RationOptimizer()
    opt.set_constraints(rc)
    return opt.NASEM_constraint_functions


def validar(quantidades_por_id, rc, tolerancia=1e-6):
    """Devolva (aprovada, diagnóstico) para {rufas_id: kg_MS_por_vaca_dia}.

    As chaves podem chegar em qualquer ordem. Todos os alimentos da configuração
    precisam aparecer, incluindo aqueles com quantidade zero. IDs (identificadores) desconhecidos,
    ausentes e duplicados após normalização são rejeitados.

    A convenção original é g(x) >= 0. Uma pequena margem numérica é calculada
    na escala de cada restrição; não se trata de redução da exigência biológica.
    """

    if not isinstance(quantidades_por_id, Mapping):
        raise ValueError("Informe a dieta como dicionário {rufas_id: quantidade}, não como vetor por posição.")

    ids = _ids_alimentos(rc)
    dieta = {}

    for chave, valor in quantidades_por_id.items():

        codigo = _normalizar_id(chave)

        # 44 e "44" representam o mesmo alimento, portanto não podem aparecer juntos.
        if codigo in dieta:
            raise ValueError(f"ID de alimento repetido na dieta: {codigo}.") 

        dieta[codigo] = _quantidade(valor)

    ausentes = sorted(set(ids) - set(dieta))
    desconhecidos = sorted(set(dieta) - set(ids))

    if ausentes or desconhecidos:
        raise ValueError(f"IDs ausentes: {ausentes}; IDs desconhecidos: {desconhecidos}.")

    # As funções originais operam sobre uma sequência. Montá-la por consulta ao ID
    # impede que a ordem de inserção do dicionário altere a associação dos alimentos.
    x = [dieta[codigo] for codigo in ids]

    req = rc.animal_requirements

    linhas = []

    for func in funcoes(rc):

        nome = func.__name__

        # Evitar tratar Mcal, gramas, kg e pontos percentuais como a mesma unidade.
        if "energy" in nome:
            escala, unidade = max(1, req.total_energy_requirement), "Mcal/dia"

        elif "protein" in nome:
            escala, unidade = max(1, req.metabolizable_protein), "g/dia"

        elif nome == "calcium_constraint":
            escala, unidade = max(1, req.calcium), "g/dia"

        elif nome == "phosphorus_constraint":
            escala = max(1, req.phosphorus, req.process_based_phosphorus)
            unidade = "g/dia"

        elif "DMI" in nome:  #consumo de matéria seca
            escala, unidade = max(1, req.dry_matter), "kg_MS/dia"

        else:
            escala, unidade = 100, "pontos_percentuais"

        residuo = float(func(x, rc))

        # Exemplo: para MP (proteína metabolizável) de 2.000 g e tolerância 0,000001, a margem é 0,002 g.
        tol = tolerancia * escala
        linhas.append({"restricao": nome, "residuo": residuo,
                       "unidade": unidade, "tolerancia": tol,
                       "valida": bool(isfinite(residuo) and residuo >= -tol)})

    for feed in rc.feeds_used:

        # Conferir também os limites de cada ingrediente, além dos nutrientes.
        codigo = _normalizar_id(feed.rufas_id)
        quantidade = dieta[codigo]
        tol = tolerancia * max(1, abs(quantidade), abs(feed.lower_limit), abs(feed.limit))

        for nome, residuo in (("minimo", quantidade - feed.lower_limit),
                              ("maximo", feed.limit - quantidade)):

            linhas.append({"restricao": f"{nome}_{codigo}", "rufas_id": codigo,
                           "residuo": float(residuo), "unidade": "kg_MS/dia",
                           "tolerancia": tol, "valida": bool(residuo >= -tol)})
                           
    return all(row["valida"] for row in linhas), linhas
