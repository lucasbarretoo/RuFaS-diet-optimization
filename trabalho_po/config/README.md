# Explicação dos arquivos de configuração

JSON (Notação de Objetos JavaScript) não aceita comentários `#` ou `//`. As explicações ficam neste documento
para manter os arquivos de configuração válidos. Os números e textos dos JSONs (arquivos em Notação de Objetos JavaScript)
continuam sendo lidos pelos módulos do estudo conforme o roteiro.

## `caso_base.json`: qual problema vamos estudar

| Campo | Significado e utilização |
| --- | --- |
| `nome` | Rótulo do cenário nos resultados, como `caso_base_114879`. |
| `animal_id` | ID (identificador) de origem da vaca procurada na lista `cows` da população; não é sua posição na lista. |
| `populacao` | Caminho do cadastro de animais, relativo à raiz do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes). |
| `metadata` | Arquivo que associa os insumos do cenário: configuração animal, alimentos, curva de lactação e outros. |
| `alimentos` | Configuração com ingredientes disponíveis por categoria e preços de compra; o formato local usa `feeds` e `rations`. |
| `biblioteca` | CSV (valores separados por vírgulas) de composição nutricional NASEM (Academias Nacionais de Ciências, Engenharia e Medicina), relacionado aos ingredientes pelo `rufas_id`. |
| `limites` | Caminho de `limites.json`, com controles da aproximação e da resolução. |
| `padrao` | `NASEM` (Academias Nacionais de Ciências, Engenharia e Medicina), correspondente à implementação NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) 2021 do cenário escolhido. |
| `moeda` | `USD` (dólares americanos); o extrator rejeita outra moeda. O campo não realiza conversão cambial. |
| `unidade_quantidade` | Convenção registrada: kg (quilogramas) de matéria seca por vaca/dia. Não converte quantidades automaticamente. |
| `politica_precos` | Documenta `exemplo_rufas`: preços de demonstração, sem cotação comercial identificada. |
| `semente` | Inicializa os geradores aleatórios Python e NumPy (biblioteca de computação numérica em Python). O valor 42 ajuda a repetir a preparação no mesmo código e ambiente. |
| `start_date` | Primeiro dia do período no formato `ano:dia_do_ano`. `2013:1` é 1º de janeiro de 2013. |
| `end_date` | Último dia incluído. `2013:365` é 31 de dezembro de 2013. |

Os caminhos de população, alimentos e biblioteca precisam ser coerentes com a
metadata carregada pelo RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes). `alimentos` informa quais ingredientes usar e seus
preços; `biblioteca` informa sua composição. Os teores da biblioteca não são todos
na mesma base: preservar as unidades de cada coluna.

A configuração padrão contém 365 dias. Com início em `2013:1`, usar `end_date`
igual a `2013:7` para sete dias ou `2013:30` para 30 dias. A função `periodo()`
confere datas existentes e término igual ou posterior ao início.

A preparação estática calcula a dieta do primeiro dia, mantendo o intervalo no
contexto temporal do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes). A integração executa os dias do período configurado.
Um resultado em USD/vaca/dia (dólares americanos por vaca por dia) não se transforma em custo anual apenas por mudar
`end_date`; o custo dinâmico precisa acompanhar quantidades e estados de cada dia.

### O grupo `hipoteses`

Essas condições foram propostas para preparar o primeiro cálculo. Não são
medições da vaca nem exigências do professor.

| Campo | Interpretação |
| --- | --- |
| `distancia_diaria_m` | Entrada de deslocamento em metros. Zero simplifica o caso isolado, desconsiderando o deslocamento informado para o cálculo da atividade. Um cenário mais detalhado deve justificar a distância pelo lote e pelo manejo. |
| `temperatura_anterior_C` | Valor passado à interface nutricional, inicialmente 20 °C (graus Celsius). No ramo NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) desta vaca lactante, essa entrada não participa diretamente do cálculo das exigências. Não fixa o clima da simulação anual em 20 °C (graus Celsius). |
| `estado_digestivo` | Texto que documenta a inicialização do software sem dias anteriores de preparação. Mudar o texto não executa um aquecimento. |

“Aquecimento” significa simular dias anteriores antes de começar a comparação,
formando um histórico alimentar e digestivo. No caso inicial, são usados defaults
do RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes); perdas como metano e N (nitrogênio) urinário podem começar em zero. Essa inicialização
pode afetar a energia calculada e deve ser igual na comparação dos métodos.

Na integração, o RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes) usa as condições dos lotes, o clima e a evolução diária do
animal. As hipóteses acima pertencem à preparação estática do exemplo.

## `limites.json`: como o procedimento procura uma dieta

Este arquivo guarda principalmente controles numéricos da proposta híbrida.
As necessidades nutricionais são calculadas pelo RuFaS (Ruminant Farm Systems, modelo de sistemas de produção de ruminantes); os limites de nutrientes
e inclusão vêm do código original e da biblioteca, não desses números de ajuste.
Os parâmetros foram propostos para o estudo e precisam ser avaliados nos testes.

| Campo | Efeito no código |
| --- | --- |
| `perfil` | Documenta o uso das restrições NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) originais. É descritivo no exemplo; editar o texto não seleciona outro padrão. |
| `modo` | Documenta formulação automática, com liberdade para escolher quantidades dentro dos limites. O código da ponte prepara esse modo; o texto sozinho não o altera. |
| `regiao_inicial` | Define o raio local `regiao * max(1, abs(x_i))`, em kg MS (quilogramas de matéria seca), ao redor da dieta válida. O valor 0,2 permite ±2 kg (quilogramas) para um ingrediente com 10 kg (quilogramas). |
| `regiao_minima` | Limite de parada ao reduzir a região após uma candidata inválida. Se a região ficar abaixo de 0,001, o refinamento termina. |
| `max_resolucoes` | Máximo de chamadas ao solver de LP (programação linear) por formulação, inicialmente 20. Não é a quantidade de dias nem de iterações internas do solver. |
| `tolerancia_relativa` | Margem numérica para conferir as restrições originais, escalada conforme unidade e grandeza. Não é uma redução deliberada da necessidade nutricional. |
| `melhoria_relativa_minima` | Critério de parada quando uma candidata válida oferece melhoria de custo igual ou inferior a esse valor. |
| `passo_gradiente` | Perturbação usada para estimar como cada restrição muda ao alterar um ingrediente e construir a aproximação linear. |

Exemplos dos controles:

- Com `regiao_inicial=0.2`, um ingrediente em 10 kg MS (quilogramas de matéria seca) pode variar inicialmente
  de 8 a 12 kg MS (quilogramas de matéria seca), respeitando também os limites da biblioteca. Para quantidade
  inicial zero, o raio é 0,2 kg (quilogramas), permitindo introduzir esse ingrediente.
- Se a candidata falhar na validação, a região é dividida por dois: 0,2; 0,1;
  0,05; e assim por diante, até o limite ou outro critério de parada.
- Com `tolerancia_relativa=1e-6` e MP (proteína metabolizável) exigida de 2.000 g (gramas), a tolerância de MP (proteína metabolizável)
  é 0,002 g (gramas). Outras restrições usam escalas próprias em Mcal (megacalorias), kg (quilogramas) ou porcentagens.
- O ganho de custo é `(custo_anterior-custo_novo)/max(1, abs(custo_anterior))`.
  Para custo de USD (dólares americanos) 10, o limiar `1e-6` equivale a USD (dólares americanos) 0,00001.
- O passo nominal é `max(passo, passo*max(1, abs(x_i)))`. Com 10 kg (quilogramas) e passo
  `0.0001`, a perturbação é 0,001 kg (quilogramas), observando os limites do ingrediente.

A dieta inicial vem do otimizador original. Os LPs (modelos de programação linear) tentam refiná-la e cada
candidata é conferida nas funções originais. Uma solução ótima do LP (programação linear) não prova
ótimo global do problema NASEM (Academias Nacionais de Ciências, Engenharia e Medicina). Se não houver melhoria válida, o resultado
identifica explicitamente que a referência original foi preservada.

## `sensibilidade.json`: quais cenários repetir

Este arquivo será copiado na etapa de sensibilidade.

| Campo | Significado |
| --- | --- |
| `id_alimento_preco` | ID (identificador) do ingrediente cujo preço será alterado; inicialmente 44, milho em grão. |
| `multiplicadores_preco` | Fatores 0,8; 1; 1,2: preço 20% menor, base e 20% maior, mantendo USD/kg MS (dólares americanos por quilograma de matéria seca). |
| `multiplicadores_energia` | Fatores 1 e 1,1: exigência energética base e 10% maior. |

Três níveis de preço por dois de energia geram seis cenários. O aumento de
energia é uma perturbação controlada da exigência, mantendo o mesmo leite no
caso estático. Ele não calcula automaticamente uma nova produção de leite.

## `economia.json`: preço do leite e origem

Este arquivo será copiado na etapa econômica. O valor `null` indica que o dado
ainda precisa ser informado; não equivale a preço zero.

| Campo | Significado |
| --- | --- |
| `moeda` | USD (dólares americanos), conferido pelo cálculo econômico. |
| `unidade_preco_leite` | USD/kg (dólares americanos por quilograma) de leite, compatível com a produção em kg (quilogramas). |
| `arquivo_preco_leite` | Exportação local `trabalho_po/dados/milk-price-wisconsin-2013.csv`, obtida no Quick Stats. |
| `preco_leite_USD_por_kg` | Média simples dos 12 preços mensais de 2013, convertida automaticamente para dólares americanos por quilograma. |
| `fonte_preco_leite` | URL (localizador uniforme de recursos, ou endereço na internet) e identificação da fonte consultada. |
| `periodo_preco_leite` | Período e localidade da observação, para interpretar o resultado. |
| `observacao` | Descrição da origem ou da conversão física realizada. |

`preco_leite.py` lê a exportação de Wisconsin em 2013 e calcula a média dos
12 meses, excluindo a linha de resumo `MARKETING YEAR`. A média é 20,30 dólares
americanos por 100 libras. O programa divide por 45,359237 para obter
aproximadamente 0,4475383922353015 dólar americano por quilograma, sem câmbio.
Não há digitação interativa do preço. `economia.py` calcula receita = preço × kg (quilogramas) leite e
IOFC (margem sobre o custo alimentar) = receita − custo alimentar. IOFC (margem sobre o custo alimentar) é margem sobre custo alimentar, não lucro
líquido. A comparação inicial é estática e usa a mesma produção nos dois métodos.

## Gravação dos arquivos

`arquivos.salvar()` escreve diretamente o JSON (Notação de Objetos JavaScript) de destino e substitui seu
conteúdo anterior, sem criar backup. Comentários explicativos ficam nos módulos
Python e neste README (documento de orientação, ou leia-me); os JSONs (arquivos em Notação de Objetos JavaScript) de configuração e de dados mantêm seu formato.
