""" Resolva a proposta híbrida: referência SLSQP (programação sequencial por mínimos quadrados),
    LPs (modelos de programação linear) PuLP (biblioteca de modelagem de programação linear em Python) 
    e validação NASEM (Academias Nacionais de Ciências, Engenharia e Medicina).

    O caso é estático, por vaca/dia, no início do período configurado. A resolução
    usa model.solve(), como no exemplo da aula, e registra o solver selecionado.
    O procedimento não garante ótimo global do problema nutricional não linear.
"""

import csv
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pulp

from trabalho_po.arquivos import CASO, ROOT, ler, salvar
from trabalho_po.aproximacao import aproximar
from trabalho_po.modelo import construir
from trabalho_po.ponte_rufas import original, preparar
from trabalho_po.validacao import por_id, validar


def refinar(rc, referencia, ajustes, destino=None):
    """Tente reduzir o custo preservando a melhor dieta nutricionalmente válida.

    referencia vem do otimizador original; ajustes vem de limites.json.
    Se destino for informado, cada LP (programação linear) e seus coeficientes serão exportados.
    """

    melhor = np.array(referencia, dtype=float)
    ok, _ = validar(por_id(melhor, rc), rc, ajustes["tolerancia_relativa"])

    if not ok:
        raise ValueError("A referência original precisa ser nutricionalmente válida.")

    precos = np.array(rc.price_list)
    custo = float(precos @ melhor)

    # regiao_inicial controla a alteração permitida em torno da dieta de referência.
    regiao = ajustes["regiao_inicial"]
    iteracoes, ultimo_coef = [], []
    solver_nome, melhorado = None, False

    # Este limite conta resoluções de LP por formulação, não dias nem iterações do solver.
    for tentativa in range(1, ajustes["max_resolucoes"] + 1):

        linhas = aproximar(rc, melhor, ajustes["passo_gradiente"])
        model, xs = construir(rc, linhas, melhor, regiao)

        # Registrar o modelo efetivamente resolvido permite conferir suas equações.
        if destino is not None:

            model.writeLP(str(Path(destino) / f"modelo_{tentativa:02d}.lp"))

            salvar(Path(destino) / f"coeficientes_{tentativa:02d}.json", {
                "ids": [f.rufas_id for f in rc.feeds_used],
                "ponto": melhor.tolist(), "regiao": regiao, "linhas": linhas,
            })

        # O PuLP (biblioteca de modelagem de programação linear em Python) encaminha a resolução ao seu solver padrão instalado.
        model.solve()
        
        solver_nome = model.solver.name
        status = pulp.LpStatus[model.status]
        ultimo_coef = linhas
        registro = {"tentativa": tentativa, "regiao": regiao, "status_LP": status,
                    "valida_NASEM": False, "aceita": False}

        # Se o problema linear não tiver resultado ótimo, 
        # o código encerra as tentativas e preserva a melhor dieta válida já conhecida.
        if model.status != pulp.LpStatusOptimal:
            iteracoes.append(registro)
            break

        # Se tiver, extrai a candidata
        candidata = np.array([v.value() for v in xs], dtype=float)

        # Verifica se essa nova dieta satisfaz as funções nutricionais originais
        valida, _ = validar(por_id(candidata, rc), rc, ajustes["tolerancia_relativa"])

        #calcula o novo custo
        novo_custo = float(precos @ candidata)
        registro.update({"valida_NASEM": valida, "custo_USD": novo_custo})

        # Acima de USD 1, essa expressão mede a redução relativa do custo.
        ganho = (custo - novo_custo) / max(1, abs(custo))

        # nova dieta valida e de menor custo
        if valida and novo_custo < custo:
            melhor, custo, melhorado = candidata, novo_custo, True
            registro["aceita"] = True

        iteracoes.append(registro)

        # Parar quando a candidata válida não oferecer uma melhoria relevante.
        if valida and ganho <= ajustes["melhoria_relativa_minima"]:
            break

        if not valida:
            # Uma aproximação que falhou é refeita mais perto do último ponto válido.
            regiao /= 2

            if regiao < ajustes["regiao_minima"]:
                break

    # Informar explicitamente quando a dieta final continua sendo a referência original.
    return melhor, {
        "origem_dieta": "aproximacao_PuLP" if melhorado else "referencia_original_preservada",
        "estado": "melhoria_valida" if melhorado else "sem_melhoria",
        "solver": solver_nome, "versao_pulp": pulp.__version__,
        "iteracoes": iteracoes, "ultimos_coeficientes": ultimo_coef,
    }


def executar(cfg, destino, fator_preco=1.0, fator_energia=1.0, id_preco=44):
    """Execute um cenário e exporte dieta, custos em USD/vaca/dia (dólares americanos por vaca por dia) e diagnóstico.

    Os fatores mudam preço e exigência energética para a sensibilidade.
    O tempo híbrido inclui a resolução original usada como inicialização.
    """

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    # ajustes: tolerâncias, região de confiança e limites de tentativas.
    ajustes = ler(ROOT / cfg["limites"])

    # animal escolhido, alimentos disponíveis, exigências nutricionais, informações sobre o cenário preparado.
    animal, feeds, req, contexto = preparar(cfg, fator_preco, fator_energia, id_preco)

    #salva entradas para comparações futuras
    salvar(destino / "entradas.json", {"caso": cfg, "contexto": contexto, "exigencias": asdict(req)})
    
    inicio = time.perf_counter()

    # Ambos os métodos recebem o mesmo animal, alimentos e exigências deste cenário
    # e geram resultado do otimizador original e a configuração da ração
    sol, rc = original(animal, feeds, req)

    tempo_original = time.perf_counter() - inicio
    
    dieta_original = por_id(sol.x, rc)
    ok, residuos = validar(dieta_original, rc, ajustes["tolerancia_relativa"])

    salvar(destino / "referencia_original.json", {
        "success": bool(sol.success), "mensagem": str(sol.message), "valida_NASEM": ok,
        "quantidades_por_id": dieta_original, "validacao": residuos,
    })

    # Uma mensagem de sucesso do SLSQP (programação sequencial por mínimos quadrados), sozinha, não comprova validade nutricional.
    if not sol.success or not ok:
        raise ValueError(f"Referência original inválida. Diagnóstico em {destino}.")

    inicio = time.perf_counter()
    x, info = refinar(rc, sol.x, ajustes, destino)
    tempo_pulp = time.perf_counter() - inicio
    dieta_final = por_id(x, rc)
    ok, residuos = validar(dieta_final, rc, ajustes["tolerancia_relativa"])

    salvar(destino / "validacao.json", {
        "quantidades_por_id": dieta_final, "valida_NASEM": ok, "restricoes": residuos,
    })

    # Quantidades e custos são gravados com a precisão disponível; arredondar só na apresentação.
    with (destino / "dieta.csv").open("w", encoding="utf-8", newline="") as f:

        w = csv.writer(f)
        w.writerow(["rufas_id", "kg_MS_original", "kg_MS_final", "preco_USD_kg_MS", "custo_USD_final"])

        for feed, antes, depois in zip(rc.feeds_used, sol.x, x):
            w.writerow([feed.rufas_id, antes, depois, feed.purchase_cost, feed.purchase_cost * depois])

    resumo = {
        "caso": cfg["nome"], "contexto": contexto, "valida_NASEM": ok,
        "quantidades_por_id": dieta_final,
        "custo_original_USD_vaca_dia": float(np.dot(rc.price_list, sol.x)),
        "custo_final_USD_vaca_dia": float(np.dot(rc.price_list, x)),
        "tempo_original_s": tempo_original,
        "tempo_adicional_PuLP_s": tempo_pulp,
        "tempo_hibrido_total_s": tempo_original + tempo_pulp, **info,
    }

    salvar(destino / "resumo.json", resumo)

    return resumo


if __name__ == "__main__":
    # A simulação do ano inteiro pertence ao lançador simular.py.
    resumo = executar(ler(CASO), ROOT / "trabalho_po/resultados/caso_base")
    print("Estado:", resumo["estado"], "Solver:", resumo["solver"])
    print("Custo final USD/vaca/dia:", resumo["custo_final_USD_vaca_dia"])  # USD/vaca/dia (dólares americanos por vaca por dia)
