TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
WEBSITE_1 = "https://www.ligapokemon.com.br/"
TIMEOUT_BUSCA_PRINCIPAL = 10
TIMEOUT_EXIBIR_MAIS = 8
TIMEOUT_SELECIONA_CARD = 8
TIMEOUT_BOTAO_CARRINHO = 4
ESPERA_BOTAO_COMPRAR = 1
N_MAX_TENTATIVAS_PRECO = 16
N_MAX_TENTATIVAS_COLECAO = 3
TEMPO_ESPERA = 4
DEBUG = False

SAIDA_CSV = "resultados_final.csv"
MONITOR_CSV = "monitor_registros.csv"

# Intervalo de monitoramento (padrão 60s)
MONITOR_INTERVALO_BASE = 60
MONITOR_VARIACAO = 30

# Intervalo padrão para raspagem e monitoramento
PROGRESS_MAX = 100

# Tema inicial (não se aplica diretamente no PyQt, mas deixo como referência)
TEMA_INICIAL = "DarkBlue"

# Dicionários (caso precise no futuro)
DICT_LINGUA = {}
DICT_CONDICAO = {}
DICT_EXTRAS = {}

CORRECOES_NUMERO_COLECAO = {}

DTYPES_DICT = {
    'nome': str,
    'colecao': str,
    'numero': str
}
