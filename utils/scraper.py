import time
import random
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)
from selenium.webdriver.common.alert import Alert

class LigaPokemonScraper:
    """
    Faz a raspagem de uma única carta por vez:
    1) Abre o navegador (WebDriver).
    2) Carrega a página da carta (com base em nome, colecao e numero).
    3) Localiza as lojas com condição NM, adiciona ao carrinho e extrai o preço/quantidade.
    4) Fecha o navegador ao final.
    * Não remove itens do carrinho, pois cada carta roda em uma sessão independente.
    """
    def __init__(self, url_base, debug, tesseract_cmd, tempo_espera):
        self.url_base = url_base
        self.debug = debug
        self.tesseract_cmd = tesseract_cmd
        self.tempo_espera = tempo_espera

        # Os atributos abaixo são inicializados a cada busca (abrindo e fechando o browser)
        self.driver = None
        self.espera_explicita = None

    def inicializar_driver(self):
        """
        Inicializa o WebDriver com as opções necessárias.
        Se debug=False, roda em modo headless.
        """
        opcoes_chrome = Options()
        opcoes_chrome.add_argument("--disable-notifications")
        opcoes_chrome.add_argument("--disable-popup-blocking")

        # Se não estiver em modo debug, executa em modo headless (sem interface)
        if not self.debug:
            opcoes_chrome.add_argument("--headless=new")
            opcoes_chrome.add_argument("--disable-gpu")

        self.driver = webdriver.Chrome(options=opcoes_chrome)
        self.espera_explicita = WebDriverWait(self.driver, timeout=15, poll_frequency=0.5)
        print("[STATUS] Navegador Chrome inicializado com sucesso")

    def fechar_driver(self):
        """
        Fecha o navegador ao final de cada busca.
        """
        try:
            if self.driver:
                self.driver.quit()
                print("[STATUS] Navegador Chrome finalizado com sucesso")
        except WebDriverException as erro:
            print(f"[ERRO CRÍTICO] Falha ao fechar navegador: {str(erro)}")

    def fechar_banner_cookies(self):
        """
        Fecha o banner de cookies, se aparecer.
        """
        try:
            banner_cookies = self.espera_explicita.until(
                EC.presence_of_element_located((By.ID, "lgpd-cookie"))
            )
            botao_fechar = banner_cookies.find_element(By.TAG_NAME, "button")
            self.driver.execute_script("arguments[0].click();", botao_fechar)
            print("[AÇÃO] Banner de cookies fechado")
            time.sleep(0.5)
        except TimeoutException:
            pass
        except Exception as erro_inesperado:
            print(f"[AVISO] Erro ao manipular banner de cookies: {str(erro_inesperado)}")

    def construir_url_carta(self, nome, colecao, numero):
        """
        Monta a URL final para acessar a página da carta.
        """
        nome_formatado = nome.replace(" ", "%20").strip()
        return f"{self.url_base}?view=cards/card&card={nome_formatado}%20({numero})&ed={colecao}&num={numero}"

    def buscar_carta_completa(self, nome, colecao, numero):
        """
        Fluxo principal:
        1) Inicializa o driver.
        2) Abre a página da carta.
        3) Localiza lojas com NM e extrai informações (preço, estoque).
        4) Fecha o driver.
        Retorna uma lista de dicionários com dados de cada loja NM encontrada.
        """
        resultados_coletados = []

        try:
            self.inicializar_driver()  # Abre o navegador

            url_carta = self.construir_url_carta(nome, colecao, numero)
            self.driver.get(url_carta)

            # Aguarda o marketplace
            self.espera_explicita.until(
                EC.presence_of_element_located((By.ID, "marketplace-stores"))
            )

            self.fechar_banner_cookies()

            # Processar as lojas encontradas na página
            resultados_coletados = self.processar_lojas(nome, colecao, numero)

        except TimeoutException:
            print("[ERRO] Tempo excedido ao tentar carregar o marketplace.")
        except Exception as erro_geral:
            print(f"[FALHA CRÍTICA] Erro geral na busca da carta: {erro_geral}")
        finally:
            self.fechar_driver()  # Fecha o navegador ao final

        return resultados_coletados

    def processar_lojas(self, nome, colecao, numero):
        """
        Percorre todas as lojas que anunciam a carta
        e, se a condição for NM, adiciona ao carrinho, extrai dados, e retorna.
        Não remove o item do carrinho para evitar alertas.
        """
        resultados_coletados = []
        try:
            container_lojas = self.driver.find_element(By.ID, "marketplace-stores")
            lista_lojas = container_lojas.find_elements(By.CLASS_NAME, "store")
        except NoSuchElementException:
            return resultados_coletados

        for indice, loja in enumerate(lista_lojas, start=1):
            try:
                # Verifica se a loja está com condição NM
                if not self.verificar_disponibilidade_loja(loja):
                    continue

                # Clica em "Comprar"
                if self.adicionar_carrinho_tratando_erros(loja):
                    # Extrai detalhes (abre o carrinho, etc.)
                    dados_item = self.extrair_detalhes_item(nome, colecao, numero)
                    if dados_item:
                        resultados_coletados.append(dados_item)

                    # Como não removemos do carrinho, se adicionarmos outra do mesmo tipo
                    # pode gerar alert. Então, se já achou 1 item NM, encerramos.
                    # (Você pode continuar se quiser comparar outras lojas, mas terá alert)
                    break

            except Exception as erro_processamento:
                print(f"[ERRO] Falha ao processar a loja {indice}: {erro_processamento}")
                break

        return resultados_coletados

    def verificar_disponibilidade_loja(self, elemento_loja):
        """
        Checa se o título do elemento .quality contém "NM".
        """
        try:
            elemento_condicao = elemento_loja.find_element(By.CLASS_NAME, "quality")
            return "NM" in elemento_condicao.get_attribute("title").upper()
        except NoSuchElementException:
            return False

    def adicionar_carrinho_tratando_erros(self, elemento_loja):
        """
        Tenta clicar no botão 'Comprar' daquela loja até 3 vezes.
        """
        for tentativa in range(3):
            try:
                botao_comprar = elemento_loja.find_element(By.CSS_SELECTOR, "div.btn-green.cursor-pointer")
                self.driver.execute_script("""
                    arguments[0].scrollIntoView({
                        behavior: 'smooth',
                        block: 'center',
                        inline: 'nearest'
                    });
                    arguments[0].click();
                """, botao_comprar)

                self.verificar_alertas_pos_clique()
                return True
            except Exception as erro_clique:
                print(f"[TENTATIVA {tentativa+1}] Falha ao clicar em 'Comprar': {erro_clique}")
                time.sleep(1)
        return False

    def verificar_alertas_pos_clique(self):
        """
        Se surgir um alert sobre "remover item do carrinho",
        aceita. (Pode ocorrer se a carta já estava no carrinho)
        """
        try:
            alerta = self.espera_explicita.until(EC.alert_is_present())
            texto_alerta = alerta.text.lower()
            if "remover" in texto_alerta:
                alerta.accept()
                time.sleep(0.3)
        except TimeoutException:
            pass

    def extrair_detalhes_item(self, nome, colecao, numero):
        """
        1) Abre o carrinho.
        2) Localiza o item recém-adicionado.
        3) Extrai preço unit e quantidade.
        (Não remove do carrinho para não gerar alertas extras.)
        """
        if not self.abrir_modal_carrinho():
            return None

        item_carrinho = self.localizar_item_carrinho(nome, numero)
        if not item_carrinho:
            return None

        detalhes = {
            "nome": nome,
            "colecao": colecao,
            "numero": numero,
            "preco_unitario": 0.0,
            "quantidade_disponivel": 0,
            "condicao": "NM",
            "lingua": "Inglês"
        }
        try:
            # Extrai preço
            elemento_preco = item_carrinho.find_element(By.CSS_SELECTOR, "div.preco-total.item-total")
            preco_unit = self.converter_texto_preco(elemento_preco.text)
            detalhes["preco_unitario"] = preco_unit

            # Extrai quantidade
            elemento_quantidade = item_carrinho.find_element(By.CSS_SELECTOR, "div.item-estoque")
            qtd_texto = ''.join(filter(str.isdigit, elemento_quantidade.text)) or "0"
            detalhes["quantidade_disponivel"] = int(qtd_texto)

            # Para compatibilidade com "salvar_resultados_csv"
            # Mapeamos "preco" e "preco_total"
            detalhes["preco"] = preco_unit
            detalhes["preco_total"] = preco_unit

        except NoSuchElementException:
            print("[AVISO] Não foi possível localizar preço ou quantidade no carrinho.")
        return detalhes

    def abrir_modal_carrinho(self):
        """
        Clica no ícone do carrinho => "Ver carrinho"
        Aguarda o modal ficar visível.
        """
        try:
            icone_carrinho = self.driver.find_element(By.CSS_SELECTOR, "div.cart-icon-container")
            icone_carrinho.click()
            time.sleep(0.5)

            botao_ver_carrinho = self.espera_explicita.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-view-cart"))
            )
            botao_ver_carrinho.click()

            # Aguarda a modal
            self.espera_explicita.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.modal-content"))
            )
            return True
        except TimeoutException:
            print("[ERRO] Falha ao abrir carrinho (timeout).")
            return False
        except NoSuchElementException:
            print("[ERRO] Elementos para abrir carrinho não encontrados.")
            return False

    def localizar_item_carrinho(self, nome, numero):
        """
        No carrinho, achar a <div row> cujo texto contenha f"{nome} ({numero})"
        """
        try:
            div_itens = self.driver.find_element(By.CSS_SELECTOR, "div.itens")
            rows = div_itens.find_elements(By.CSS_SELECTOR, "div.row")
            for row in rows:
                texto_item = row.find_element(By.CSS_SELECTOR, "p.cardtitle").text
                if f"{nome} ({numero})" in texto_item:
                    return row
        except NoSuchElementException:
            return None
        return None

    def converter_texto_preco(self, texto_bruto):
        """
        Converte 'R$ 1.234,56' => 1234.56 (float).
        """
        try:
            texto_limpo = (texto_bruto.replace("R$", "")
                                      .replace(".", "")
                                      .replace(",", ".")
                                      .strip())
            return round(float(texto_limpo), 2)
        except ValueError:
            return 0.0
