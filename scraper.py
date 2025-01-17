import numpy as np
from selenium.common.exceptions import NoSuchElementException
import config
from utils.dados import carrega_lista_cards, carrega_lista_precos, constroi_resultados
from utils.scraper import LigaPokemonScraper, carrega_busca_avancada, retorna_preco_ebay, verifica_psa, verifica_nome
from selenium.webdriver.common.by import By

df_cards = carrega_lista_cards(config=config)
df_precos_parcial = carrega_lista_precos(config=config)

precos_website_1 = []
preco_acumulado = 0
cards_ja_buscados = set()

if not df_precos_parcial.empty:
    cards_ja_buscados = set(
        df_precos_parcial[['nome', 'num_colecao']].apply(lambda x: (x['nome'], x['num_colecao']), axis=1)
    )

if config.BUSCA_WEBSITE_1:
    scraper = LigaPokemonScraper(
        correcoes_num_colecao=config.CORRECOES_NUMERO_COLECAO,
        website=config.WEBSITE_1,
        timeout_busca_principal=config.TIMEOUT_BUSCA_PRINCIPAL,
        timeout_exibir_mais=config.TIMEOUT_EXIBIR_MAIS,
        timeout_seleciona_card=config.TIMEOUT_SELECIONA_CARD,
        timeout_botao_carrinho=config.TIMEOUT_BOTAO_CARRINHO,
        espera_botao_comprar=config.ESPERA_BOTAO_COMPRAR,
        n_max_tentativas_preco=config.N_MAX_TENTATIVAS_PRECO,
        n_max_tentativas_colecao=config.N_MAX_TENTATIVAS_COLECAO,
        debug=config.DEBUG
    )

    for idx, row in df_cards.iterrows():
        if (row['nome'], row['num_colecao']) not in cards_ja_buscados:
            cards_ja_buscados.add((row['nome'], row['num_colecao']))
            print(f"Procurando todos os {row['nome']} coleção {row['num_colecao']}")
            colecao, codigo_colecao = scraper.busca_card(row['nome'], row['num_colecao'])
            if colecao:
                scraper.seleciona_colecao(colecao)
                scraper.clica_exibir_mais()
                linhas = scraper.encontra_linhas()
                for ln in linhas:
                    qualidade_card = scraper.encontra_qualidade(ln)
                    lingua_card = scraper.encontra_lingua(ln)
                    extras = scraper.encontra_extras(ln)
                    scraper.aperta_comprar(ln)
                    preco_unitario = scraper.encontra_preco(preco_acumulado)

                    if preco_unitario == 0:
                        preco_unitario = np.nan
                    else:
                        preco_acumulado += preco_unitario

                    card_info = (row['nome'], codigo_colecao, extras, lingua_card, qualidade_card, preco_unitario)
                    print(card_info[:-1] + (round(card_info[-1], 2),))
                    precos_website_1.append(card_info)

                constroi_resultados(precos_website_1, df_precos_parcial, df_cards, config)
            else:
                print(f"Não foi encontrada esta coleção para {row['nome']}")
