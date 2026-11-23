# Otimização de Dietas para Vacas Leiteiras com PuLP e Integração ao RuFaS

*Modelagem nutricional, análise de sensibilidade e comparação da produtividade simulada.*

Trabalho da disciplina de Pesquisa Operacional desenvolvido sobre o RuFaS (Ruminant Farm Systems). O objetivo é reduzir o custo da alimentação de vacas leiteiras, atendendo às restrições nutricionais da implementação NASEM (Academias Nacionais de Ciências, Engenharia e Medicina) 2021 do simulador.

O método parte de uma dieta calculada pelo otimizador original e tenta melhorar suas quantidades usando aproximações lineares locais e PuLP (biblioteca de modelagem de programação linear em Python). Cada candidata é conferida nas funções nutricionais originais antes de ser aceita. Quando não encontra uma melhoria válida, o refinamento mantém a dieta de referência.

O projeto contempla uma formulação estática de um dia, análise de sensibilidade e comparação entre duas simulações anuais: formulação original e formulação com refinamento em PuLP. Os preços e custos são expressos em USD (dólares americanos).

## 1. Preparar o terminal e conferir o ambiente

Os comandos abaixo usam o serviço existente `geodatapy`, definido no [docker-compose.yml](../docker-compose.yml), e o Python do ambiente já instalado no contêiner. Executar os comandos no terminal, na raiz do repositório:

```bash
cd /Users/Barreto/Projects/RuFaS
docker compose ps -a
```

Se o serviço existente estiver parado, iniciá-lo:

```bash
docker compose start geodatapy
```

Conferir o Python, as bibliotecas e o solver disponível:

```bash
docker compose exec -T geodatapy /app/venv/bin/python --version
docker compose exec -T geodatapy /app/venv/bin/python -c "import RUFAS, numpy, scipy, matplotlib, pulp; print('PuLP:', pulp.__version__); print('Solvers disponíveis:', pulp.listSolvers(onlyAvailable=True))"
```

O ambiente precisa conter as dependências do RuFaS, PuLP e um solver compatível disponível. O código chama `model.solve()`, que utiliza o solver padrão disponível para o PuLP. PuLP modela o problema e encaminha sua resolução ao solver.

O repositório está montado em `/app` dentro do contêiner. Assim, os arquivos gravados pela execução aparecem nas mesmas pastas do projeto no computador. Esse procedimento utiliza o ambiente existente, sem recriá-lo ou copiar arquivos de exemplo sobre o código atual.

## 2. Revisar as configurações

As configurações são arquivos JSON. A explicação completa dos campos está no [guia de configurações](config/README.md).

### Caso base — `config/caso_base.json`

| Campo ou grupo | Configuração atual e finalidade |
|---|---|
| `animal_id` | Registro de origem `114879`, usado como referência do caso estático e fonte da vaca inicial da integração. |
| `populacao` e `metadata` | Caminhos da população e das entradas do exemplo freestall do RuFaS. |
| `alimentos` | `input/data/feed/example_Midwest_feed.json`: alimentos disponíveis por categoria e seus preços. |
| `biblioteca` | `input/data/feed/NASEM_Comp_with_TDN_urea.csv`: composição nutricional e limites dos alimentos. |
| `padrao` | `NASEM`, referência nutricional utilizada no estudo. |
| `moeda` e `unidade_quantidade` | `USD` (dólares americanos) e `kg_MS_por_vaca_por_dia` (quilogramas de matéria seca por vaca por dia). |
| `semente` | `42`, para repetir os sorteios nas mesmas condições de execução. |
| `start_date` e `end_date` | `2013:1` a `2013:365`: de 1º de janeiro a 31 de dezembro de 2013, inclusive. O formato é `ano:dia_do_ano`. |
| `hipoteses` | Distância diária, temperatura anterior e descrição do estado digestivo inicial da preparação estática. Não executam um período de aquecimento. |

A formulação estática avalia somente o primeiro dia do período. A integração percorre todas as datas configuradas. Para mudar a duração da integração, editar as datas e gerar novamente suas configurações, conforme o passo 5.

### Controles do refinamento — `config/limites.json`

| Campo | Significado e valor atual |
|---|---|
| `regiao_inicial` | Controla a alteração permitida ao redor da dieta de referência: `0.2`. |
| `regiao_minima` | Limite mínimo dessa região após reduções por candidatas inválidas: `0.001`. |
| `max_resolucoes` | Até `20` resoluções de problemas de programação linear por formulação; não representa dias simulados. |
| `tolerancia_relativa` | Tolerância numérica da validação nutricional: `0.000001`. |
| `melhoria_relativa_minima` | Critério de parada para melhoria pequena: `0.000001`. |
| `passo_gradiente` | Perturbação usada no cálculo numérico dos coeficientes da aproximação: `0.0001`. |

Os campos `perfil` e `modo` documentam a configuração. Em particular, o modo automático da simulação é ativado pela preparação das entradas, com `ration.user_input = False`.

### Cenários — `config/sensibilidade.json`

O ingrediente atual é o **110 — silagem de leguminosa em maturidade intermediária** (`Legume silage, mid-maturity`). Os preços são multiplicados por `0.8`, `1.0` e `1.2`, representando preço 20% menor, original e 20% maior. As exigências energéticas são multiplicadas por `1.0` e `1.1`.

O cruzamento produz seis cenários estáticos. O aumento da exigência energética é uma perturbação controlada; não calcula automaticamente um aumento da produção de leite.

## 3. Executar o caso estático

Executar nesta ordem:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.dados
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.ponte_rufas
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.resolver
```

1. `dados` extrai a vaca de referência, reúne os sete alimentos da configuração de lactantes e registra suas fontes em `trabalho_po/dados/`.
2. `ponte_rufas` prepara o estado inicial do animal e grava seu contexto e suas exigências nutricionais.
3. `resolver` obtém a dieta original, tenta reduzir seu custo e salva quantidades, validação, modelos de programação linear e diagnóstico em `trabalho_po/resultados/caso_base/`.

Conferir `resumo.json`, `dieta.csv` e `validacao.json` nessa pasta. Em `resumo.json`, `origem_dieta` informa se houve refinamento aceito ou preservação da referência, e `valida_NASEM` registra a conferência nutricional final.

## 4. Executar a análise de sensibilidade

Após revisar `config/sensibilidade.json`:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.experimentos
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.relatorios
```

O primeiro comando resolve cada combinação de preço e energia. O segundo lê os resultados e produz o gráfico e o relatório.

Consultar:

- `trabalho_po/resultados/sensibilidade/comparacao.csv`: comparação dos cenários, incluindo falhas.
- `trabalho_po/resultados/sensibilidade/<cenario>/`: dieta e diagnóstico de cada cenário.
- `trabalho_po/resultados/sensibilidade/custos.png`: gráfico dos custos dos cenários com dieta válida.
- `trabalho_po/docs/analise_sensibilidade.md`: tabela e orientações de interpretação.

A análise de sensibilidade é estática: seus comandos não executam um ano para cada cenário.

## 5. Preparar e executar as duas simulações anuais

Gerar as entradas do período configurado:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.preparar_simulacao
```

O comando gera entradas equivalentes em `trabalho_po/config/rufas/original/` e `trabalho_po/config/rufas/pulp/`. Configura o modo `animals_only` (somente animais e nutrição), uma vaca inicial lactante de segunda paridade e reformulação diária.

As demais categorias do exemplo são preservadas. Partos, secagem, reposição e descarte seguem o simulador: começar com uma vaca não significa manter uma única lactante durante todo o ano.

A preparação também gera `propriedades.json`, um esquema experimental que aceita uma vaca inicial. O arquivo original do esquema do RuFaS não é editado. Regenerar as entradas após alterar o caso base; as entradas geradas são substituídas diretamente, sem backups automáticos.

Executar os dois métodos com o mesmo nome de execução:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.simular --metodo original --execucao comparacao_anual_01
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.simular --metodo pulp --execucao comparacao_anual_01
```

`original` usa a formulação original. `pulp` obtém essa formulação e tenta refiná-la nas chamadas automáticas de lactantes com referência NASEM (Academias Nacionais de Ciências, Engenharia e Medicina). A dieta estática salva no passo 3 não é repetida durante o ano: o refinamento recebe a configuração nutricional preparada pelo RuFaS em cada chamada.

Os resultados ficam em `trabalho_po/resultados/integracao/comparacao_anual_01/original/` e `trabalho_po/resultados/integracao/comparacao_anual_01/pulp/`. Escolher um nome ainda não utilizado: o programa recusa uma pasta de método já existente.

| Saída de cada método | Conteúdo |
|---|---|
| `entradas_execucao.json` | Configuração, semente e assinaturas dos arquivos de entrada para conferir a equivalência das execuções. |
| `leite_diario.csv` | Leite produzido, reduções registradas, quantidade e identificadores das lactantes por dia. |
| `dietas_diarias.csv` | Quantidades formuladas por ingrediente, lote e dia, com preços e custos. |
| `custos_diarios.csv` | Totais diários de matéria seca formulada e custo dos lotes lactantes. |
| `resumo_periodo.json` | Conferência do calendário, totais, chamadas e ocorrências registradas pelo simulador. |
| `logs/` | Registros nativos da execução. |
| `chamadas_otimizador/` | Diagnósticos do refinamento, somente no método `pulp`; criada ao salvar o primeiro diagnóstico. |

As duas execuções recebem a mesma adaptação de inclusão de animais em lotes vazios, definida em `integracao.py`. Ela seleciona corretamente os alimentos da categoria e é aplicada na memória do processo, sem editar os arquivos internos do RuFaS.

### Fazer uma execução curta

Para preparar três dias, usar:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.preparar_simulacao --dias 3
```

Depois, executar os dois comandos de `simular` com outro nome, como `comparacao_curta_01`. A opção `--dias` muda o término nas entradas geradas; não altera as datas de `config/caso_base.json`.

Antes de executar o ano completo, rodar novamente `preparar_simulacao` sem `--dias` e usar um novo nome de execução. Manter as mesmas entradas entre as execuções dos dois métodos de cada comparação.

## 6. Comparar a produtividade

Depois que os dois métodos concluírem o mesmo período:

```bash
docker compose exec -T geodatapy /app/venv/bin/python -m trabalho_po.produtividade --execucao comparacao_anual_01
```

O nome precisa corresponder ao utilizado no passo 5. Este comando analisa os registros existentes; não executa novamente a simulação.

A análise confere a equivalência das entradas e a integridade dos calendários. Compara leite total, leite por vaca lactante por dia, matéria seca formulada, reduções e identificadores dos animais. Se houver diferenças na composição do rebanho, elas precisam ser consideradas na interpretação.

Resultados:

- `trabalho_po/resultados/produtividade/comparacao_anual_01/comparacao.csv`: indicadores agregados.
- `trabalho_po/resultados/produtividade/comparacao_anual_01/comparacao_diaria.csv`: comparação por data.
- `trabalho_po/resultados/produtividade/comparacao_anual_01/produtividade.png`: gráfico da comparação.
- `trabalho_po/docs/impacto_produtividade.md`: interpretação dos resultados.

## 7. Módulos e arquivos de apoio

| Arquivo | Responsabilidade |
|---|---|
| `__init__.py` | Identifica `trabalho_po` como pacote Python. |
| `arquivos.py` | Centraliza os caminhos e as funções de leitura, gravação e interpretação das datas. |
| `dados.py` | Extrai o animal, relaciona alimentos e preços com a composição nutricional e registra as fontes. |
| `ponte_rufas.py` | Prepara o caso estático e acessa os cálculos de exigências e a formulação original do RuFaS. |
| `validacao.py` | Confere as dietas nas restrições nutricionais originais, relacionando as quantidades por identificador de alimento. |
| `aproximacao.py` | Calcula aproximações lineares locais das restrições usando diferenças finitas. |
| `modelo.py` | Monta as variáveis de decisão, o objetivo de custo e as restrições do problema de programação linear em PuLP. |
| `resolver.py` | Executa o caso estático e disponibiliza `refinar()`, também utilizada pela integração anual. |
| `experimentos.py` | Executa o cruzamento dos multiplicadores de preço e energia da sensibilidade. |
| `relatorios.py` | Apresenta a sensibilidade em tabela, gráfico e relatório. |
| `integracao.py` | Adapta o refinamento ao formato do otimizador dos lotes e contém a correção de inclusão em lote vazio. |
| `preparar_simulacao.py` | Gera as entradas equivalentes dos métodos original e PuLP para o período escolhido. |
| `simular.py` | Seleciona o método, inicia o RuFaS e registra dietas, leite, custos e ocorrências. |
| `produtividade.py` | Compara os registros de duas simulações equivalentes e gera indicadores e gráfico. |
| `config/caso_base.json` | Define o animal de referência, fontes, período, moeda e hipóteses iniciais. |
| `config/limites.json` | Define tolerâncias e controles do refinamento. |
| `config/sensibilidade.json` | Define o ingrediente e os multiplicadores dos cenários. |
| `dados/animal_origem.json` | Registra os dados extraídos da vaca de referência. |
| `dados/alimentos.csv` | Reúne composição, preços e limites dos ingredientes para consulta; não é a fonte lida pela simulação anual. |
| `dados/fontes.json` | Registra as fontes e as assinaturas dos dados extraídos. |
| `dados/contexto_animal.json` e `dados/exigencias.json` | Registram o contexto inicial e as exigências nutricionais do caso estático. |

O fluxo de cálculo é:

```text
Caso estático: fontes → ponte_rufas → resolver → dieta validada
Sensibilidade: experimentos → resolver → relatorios
Integração anual: preparar_simulacao → simular → RuFaS → integracao → refinar
Comparação anual: registros de original e pulp → produtividade
```

## 8. Interpretação dos resultados

- O método é híbrido: as quantidades originais são o ponto inicial das aproximações e da busca por melhoria. A solução depende dessa referência e não possui garantia de ótimo global do problema nutricional não linear.
- Uma resolução ótima da aproximação linear só é aceita se a dieta também passar nas funções nutricionais originais e tiver custo menor que a melhor dieta válida já conhecida.
- Os preços dos alimentos vêm do exemplo RuFaS, sem cotação comercial identificada. Custos são apresentados em USD (dólares americanos), sem conversão cambial.
- Quantidades formuladas e seus custos não representam consumo medido nem despesas efetivas de compra.
- A produção de leite segue os mecanismos do simulador, incluindo curva de lactação e reduções de meta. Uma diferença simulada não demonstra, por si só, resposta biológica ou ganho consistente de produtividade.
- O modo `animals_only` executa animais e nutrição; a comparação não representa uma simulação da fazenda completa.
- O caso estático, a sensibilidade e os relatórios de produtividade podem substituir suas próprias saídas ao serem executados novamente. As pastas das simulações identificadas por `--execucao` são protegidas contra reutilização.
