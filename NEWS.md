# condepe 0.1.4

* Sem mudança no código. A versão acrescenta o `CITATION.cff` (autores com
  ORCID) e passa a ser arquivada no Zenodo, que atribui um DOI ao pacote.

# condepe 0.1.3

* `condepe_layer(id)`: qualquer camada geográfica publicada no catálogo
  (`terras_indigenas`, `up_perh`…) como `GeoDataFrame`.
* Catálogo guardado (até 6 h) e versão nova publicada nesse intervalo: o
  arquivo em `atual/` já não batia com o SHA-256 do catálogo e a chamada
  falhava com `IntegrityError`. Agora o cliente lê a árvore imutável da
  própria versão (`<versão>/…` no canônico, tag no espelho) antes de desistir.
* Guia de mapas com a seção "Camadas geográficas" (rodovias, hidrografia e
  terras indígenas sobre a malha).

# condepe 0.1.2

* `condepe_roads()`: a malha rodoviária de Pernambuco (DER-PE, SRE 2026-2027,
  com os trechos federais do SNV/DNIT) como `GeoDataFrame` de linhas, lida do
  GeoParquet `referencia/rodovias.parquet` publicado pelo Observatório, com
  filtro por tipo (estaduais, federais, vicinais, acessos).
* `condepe_hydrography()`: hidrografia de Pernambuco recortada da ANA — rios
  (BHO nível 5), rios principais, massas d'água, reservatórios acompanhados
  (com capacidade e demandas) e Unidades de Planejamento Hídrico.

# condepe 0.1.1

* Mapas: `condepe_geometry()` (Malha Municipal de Pernambuco da Condepe/Fidem,
  conferida pelo SHA-256 do manifesto, ou a malha do IBGE), dissolvida em
  regiões com `level`; `condepe_regions()` com onze regionalizações (Regiões de
  Desenvolvimento, meso e microrregiões, regiões imediatas e intermediárias,
  regiões e macrorregiões de saúde, GRE, regiões fiscais, DRO do DER, regiões
  metropolitanas), lida da tabela publicada pelo Observatório
  (`referencia/regioes.parquet`, com cache e SHA-256) ou da cópia embutida,
  sem rede ou com `offline=True`; `condepe_add_geometry()` junta os dados à malha. `geopandas` é opcional
  (`pip install "condepe[geo]"`).
* `condepe_cite()`: a citação com a fonte original primeiro e o Observatório
  como organizador — de um resultado (também depois de filtrar ou
  concatenar, `df.pipe(condepe_cite)`), de identificadores de fonte ou do
  acervo.
* O cache não apaga mais as malhas ao trocar de versão do catálogo.
* Documentação e site em português; tabela das fontes, no estilo do Notion,
  na página inicial; páginas novas de mapas e da relação das
  fontes do Observatório.

# condepe 0.1.0

* First version: `condepe_catalog()`, `condepe_indicators()`, `condepe_data()`,
  `condepe_series()` and `condepe_localities()`, reading the Observatory open data
  (canonical endpoint, Hugging Face mirror as fallback) with a disk cache per
  catalogue version and sha256 verification.
