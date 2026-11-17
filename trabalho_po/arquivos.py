"""Funções compartilhadas para localizar arquivos, ler JSONs (arquivos em Notação de Objetos JavaScript) e validar datas.

Os demais módulos importam estas funções para usar as mesmas regras de entrada
e saída. As gravações substituem o destino diretamente, sem criar backups.
"""

import json
from datetime import datetime
from pathlib import Path

# __file__ é o caminho deste arquivo. Depois de copiá-lo para trabalho_po/,
# parents[0] corresponde a trabalho_po/ e parents[1] à raiz do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes).
ROOT = Path(__file__).resolve().parents[1]
# O operador / de Path junta as partes de um caminho; não é divisão numérica.
CASO = ROOT / "trabalho_po/config/caso_base.json"


def ler(caminho):
    """Leia um JSON (Notação de Objetos JavaScript) e devolva seus dados, como um dicionário ou uma lista Python."""
    # read_text lê o texto em UTF-8 (formato de transformação Unicode de oito bits), preservando acentos; loads interpreta o JSON (Notação de Objetos JavaScript).
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def periodo(cfg):
    """Converta start_date/end_date em datas e confira a ordem do intervalo.

    A entrada usa ano:dia_do_ano: 2013:1 até 2013:365 representa o ano completo.
    O dia final é incluído: a duração será (fim - inicio).days + 1.
    """

    datas = []
    for campo in ("start_date", "end_date"):

        texto = cfg[campo]

        try:
            # %Y representa o ano; %j representa o número do dia naquele ano.
            data = datetime.strptime(texto, "%Y:%j")

            # strptime pode levar o dia 366 de um ano comum para o ano seguinte.
            # Rejeitar essa mudança evita aceitar uma data inexistente no ano informado.
            if data.year != int(texto.split(":")[0]):
                raise ValueError("Dia inexistente nesse ano.")

        except (TypeError, ValueError) as exc:

            # Informar qual campo precisa ser corrigido e manter a causa original.
            raise ValueError(f"{campo} inválido: use ano:dia_do_ano, como 2013:1.") from exc

        datas.append(data)

    inicio, fim = datas

    if fim < inicio:
        raise ValueError("end_date deve ser igual ou posterior a start_date.")

    return inicio, fim


def salvar(caminho, valor):
    """Grave dados Python em JSON (Notação de Objetos JavaScript) legível, substituindo o conteúdo anterior.

    As pastas necessárias são criadas. Valores NaN/infinito são rejeitados,
    pois não representam números válidos no formato JSON (Notação de Objetos JavaScript) utilizado pelo estudo.
    """
    
    caminho = Path(caminho)

    # parents=True cria pastas intermediárias; exist_ok=True aceita pastas existentes.
    caminho.parent.mkdir(parents=True, exist_ok=True)
    
    # ensure_ascii=False mantém acentos; indent=2 organiza o texto com dois espaços.
    # O \n final encerra a última linha; write_text grava diretamente, sem backup.
    caminho.write_text(
        json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
