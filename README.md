![Caminhão de Gás](caminhao_gas.jpg)

# Preço médio por Estado do butijão de gás de 13kg e eventos relevantes 
  Gráfico exibe informações dos preços médios do butijão de gás de 13kg e eventos relevantes

## Passo 1: 
  Crie as pastas csv e csv_resumo

## Passo 2:
  Baixe os dataset's do glp
  1º e 2º Semestre dos anos 2004 a 2024 (total de 42 arquivos csv) e salvando todos na pasta csv.

## Passo 3:
  Execute o combustivel.ipynb.
  
  Primeiro o código simplifica as informações restringindo as colunas e cria na pasta csv_resumo planilhas com menos colunas.
  
  Em seguida criamos uma tabela glp do sqlite3.
  
  Com a base de dados sqlite podemos executar o SQL abaixo que nos traz o preço médio em VL_VENDA:
  
  **SELECT 
          ESTADO,
          PRODUTO,
          MES_ANO,
          AVG(VL_VENDA) AS VL_VENDA
      FROM 
          glp
      WHERE 
          MES_ANO IS NOT NULL 
          AND VL_VENDA IS NOT NULL
          AND VL_VENDA > 0
      GROUP BY 
          ESTADO, PRODUTO, MES_ANO
      ORDER BY 
          ESTADO, PRODUTO, MES_ANO;**
  
  Em seguida criamos resumo_glp.csv
  
  Com este resumo criamos ao final um html que exibe o gráfico do preço médio.

# Fonte:
[Dados Abertos](https://dados.gov.br/dados/conjuntos-dados/serie-historica-de-precos-de-combustiveis-e-de-glp)

# Dados acessados em: 
29/06/2025

# Visualize o resultado em: 
[Área de Trampo](https://www.areadetrampo.com.br/preco-medio-de-combustiveis-2004-a-2024-e-eventos-relevantes/)
