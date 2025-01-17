import numpy as np

# Caminho do Tesseract (se for necessário para outra lógica, mas aqui não usamos OCR)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Endereço base do site da Liga Pokémon
WEBSITE_1 = "https://www.ligapokemon.com.br/"

# Parâmetros de Timeout e Esperas
TIMEOUT_BUSCA_PRINCIPAL = 10
TIMEOUT_EXIBIR_MAIS = 8
TIMEOUT_SELECIONA_CARD = 8
TIMEOUT_BOTAO_CARRINHO = 4
ESPERA_BOTAO_COMPRAR = 1
N_MAX_TENTATIVAS_PRECO = 16
N_MAX_TENTATIVAS_COLECAO = 3
TEMPO_ESPERA = 4  # Espera geral entre cliques e loads
DEBUG = False

# Nome do CSV final gerado
SAIDA_CSV = "resultados_final.csv"

# Dicionários se quiser usar em outra parte do código
DICT_LINGUA = {}
DICT_CONDICAO = {}
DICT_EXTRAS = {}

# Caso precise de correções no número da coleção, ajustar aqui
CORRECOES_NUMERO_COLECAO = {}

# Se for usar em outro local
DTYPES_DICT = {
    'nome': str,
    'colecao': str,
    'numero': str
}
