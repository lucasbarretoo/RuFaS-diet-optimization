"""Gere entradas equivalentes para comparar os métodos original e PuLP.

As cópias são configurações do experimento em config/rufas/, não backups.
Os arquivos de entrada originais do RuFaS não são sobrescritos.
"""

import argparse
import copy
from datetime import timedelta

from trabalho_po.arquivos import CASO, ROOT, ler, periodo, salvar
from trabalho_po.dados import extrair


def main():
    """Prepare o período do caso base, ou N dias quando --dias for informado."""
    
    parser = argparse.ArgumentParser()
    
    parser.add_argument("--dias", type=int, default=None,
                        help="Opcional: substituir o término configurado para testar N dias.")
    
    
    args = parser.parse_args()
    if args.dias is not None and args.dias < 1:
        raise ValueError("O período deve ter pelo menos um dia.")
    
    caso = ler(CASO)
    inicio, fim = periodo(caso)
    
    # Sem --dias, respeitar start_date e end_date; com a opção, alterar só as cópias geradas.
    if args.dias is not None:
        fim = inicio + timedelta(days=args.dias - 1)
    
    # O último dia faz parte do intervalo: 2013:1 a 2013:365 contém 365 dias.
    dias = (fim - inicio).days + 1

    # Carregar as configurações e o animal
    meta_origem = ler(ROOT / caso["metadata"])
    cfg = ler(ROOT / meta_origem["files"]["config"]["path"])
    animal_cfg = ler(ROOT / meta_origem["files"]["animal"]["path"])
    populacao = ler(ROOT / caso["populacao"])
    animal, _ = extrair(caso)
    
    # Preparar a população inicial
    populacao["cows"] = [animal]

    # Informacoes do rabanho
    info = animal_cfg["herd_information"]
    
    # A única vaca inicial é lactante de paridade 2; outras categorias são mantidas.
    info["cow_num"] = 1
    info["herd_num"] = 1
    
    # Manter o alvo de uma vaca coerente com os limites de reposição do estudo.
    info["herd_size_sell_threshold"] = 1
    info["herd_size_buy_threshold"] = 1
    info["milking_cow_fraction"] = 1.0 #100% das vacas iniciais devem ser lactantes.
    info["parity_fractions"] = {str(n): float(n == 2) for n in range(1, 6)} #a vaca inicial pertence à categoria de segundo parto
    animal_cfg["ration"]["user_input"] = False
    
    # Reformular diariamente nos dois métodos para manter a comparação equivalente.
    animal_cfg["ration"]["formulation_interval"] = 1
    cfg.update({"start_date": caso["start_date"],
                "nutrient_standard": "NASEM", 
                "simulation_type": "animals_only",
                "end_date": caso["end_date"] if args.dias is None else f"{fim.year}:{fim.timetuple().tm_yday}"})
    
    # O esquema nativo exige pelo menos seis vacas e substitui valores menores por 100.
    # Adaptar somente o esquema da execução para permitir a única vaca deste estudo.
    propriedades = ler(ROOT / "RUFAS/input/metadata/properties/default.json")
    
    for campo in ("cow_num", "herd_num"):
        propriedades["animal_properties"]["herd_information"][campo]["minimum"] = 1
    
    for metodo in ("original", "pulp"):

        pasta = ROOT / "trabalho_po/config/rufas" / metodo
        salvar(pasta / "config.json", cfg)
        salvar(pasta / "animal.json", animal_cfg)
        salvar(pasta / "populacao.json", populacao)
        salvar(pasta / "propriedades.json", propriedades)

        # A metadata da fazenda precisa apontar às entradas específicas do estudo.
        meta = copy.deepcopy(meta_origem)

        for chave, nome in (("config", "config.json"), ("animal", "animal.json"),
                            ("animal_population", "populacao.json")):

            meta["files"][chave]["path"] = str((pasta / nome).relative_to(ROOT))

        salvar(pasta / "metadata_fazenda.json", meta)
        tarefas = ler(ROOT / "input/data/tasks/example_freestall_task.json")

        # A troca experimental da classe em simular.py funciona no mesmo processo.
        tarefas["parallel_workers"] = 1
        tarefa = tarefas["tasks"][0]
        tarefas["tasks"] = [tarefa]
        tarefa.update({"task_type": "SIMULATION_SINGLE_RUN",
                       "metadata_file_path": str((pasta / "metadata_fazenda.json").relative_to(ROOT)),
                       "random_seeds": [caso["semente"]], "output_prefix": metodo})

        salvar(pasta / "tarefas.json", tarefas)

        # O argumento -p do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes) recebe esta metadata de tarefas, não a da fazenda.
        meta_tarefas = ler(ROOT / "input/task_manager_metadata.json")
        meta_tarefas["files"]["tasks"]["path"] = str((pasta / "tarefas.json").relative_to(ROOT))
        salvar(pasta / "metadata_tarefas.json", meta_tarefas)

    print("Configurações dos dois métodos geradas para", dias, "dias.")
    print("Início:", cfg["start_date"], "Fim:", cfg["end_date"])


if __name__ == "__main__":
    main()
