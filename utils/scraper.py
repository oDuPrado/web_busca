import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    ElementClickInterceptedException
)
import config

class LigaPokemonScraper:
    def __init__(self, url_base, debug, tesseract_cmd, tempo_espera):
        self.url_base = url_base
        self.debug = debug
        self.tempo_espera = tempo_espera
        self.driver = None
        self.inicializa_driver()

    def inicializa_driver(self):
        chrome_options = Options()
        if not self.debug:
            chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=chrome_options)
        print("[INFO] Driver iniciado.")

    def fechar_driver(self):
        try:
            self.driver.quit()
            print("[INFO] Driver fechado.")
        except:
            pass

    def monta_url_carta(self, nome, colecao, numero):
        """
        Gera a URL dinâmica:
        https://www.ligapokemon.com.br/?view=cards/card&card={nome}%20({numero})&ed={colecao}&num={numero}
        """
        nome_url = nome.replace(" ", "%20")
        return f"{self.url_base}?view=cards/card&card={nome_url}%20({numero})&ed={colecao}&num={numero}"
    
    def fecha_banner_cookies(self):
        """
        Fecha o banner de cookies caso esteja visível.
        """
        try:
            banner = self.driver.find_element(By.ID, "lgpd-cookie")
            botao_fechar = banner.find_element(By.TAG_NAME, "button")  # Botão "Fechar" do banner
            botao_fechar.click()
            print("[INFO] Banner de cookies fechado.")
            time.sleep(1)  # Aguarde um tempo para garantir que o banner desapareça
        except NoSuchElementException:
            print("[INFO] Nenhum banner de cookies encontrado.")
        except Exception as e:
            print(f"[AVISO] Falha ao tentar fechar o banner de cookies: {e}")


    def busca_carta_completa(self, nome, colecao, numero):
        url = self.monta_url_carta(nome, colecao, numero)
        self.driver.get(url)
        time.sleep(self.tempo_espera)

        resultados = []
        try:
            # Fechar o banner de cookies, se necessário
            self.fecha_banner_cookies()

            # Continuar com a busca nos stores
            marketplace = self.driver.find_element(By.ID, "marketplace-stores")
            stores = marketplace.find_elements(By.CLASS_NAME, "store")
        except NoSuchElementException:
            print("[AVISO] Sem marketplace-stores. Nenhum vendedor encontrado.")
            return resultados

        achou_nm = False

        for store in stores:
            lingua, condicao = self.extrai_lingua_e_condicao(store)
            if "NM" in condicao.upper():
                achou_nm = True
                botao_comprar = self.localiza_botao_comprar_nm(store)
                if botao_comprar:
                    # Fechar o banner novamente, se necessário
                    self.fecha_banner_cookies()
                    botao_comprar.click()
                    time.sleep(1)
                    self.abre_modal_carrinho()
                    item_carrinho = self.localiza_item_no_carrinho(nome, numero)
                    if item_carrinho:
                        dados_item = self.extrai_dados_item_carrinho(item_carrinho)
                        dados_item["nome"] = nome
                        dados_item["colecao"] = colecao
                        dados_item["numero"] = numero
                        dados_item["lingua"] = lingua
                        dados_item["condicao"] = condicao
                        resultados.append(dados_item)
                        self.remove_item_carrinho(item_carrinho)
                        return resultados
        if not achou_nm:
            print("[INFO] Não encontrou condição NM para esta carta.")
        return resultados


    def extrai_lingua_e_condicao(self, store):
        """
        Tenta localizar no store a 'infos-quality-and-language' para achar a língua e a condição.
        """
        try:
            infos = store.find_element(By.CLASS_NAME, "infos-quality-and-language.desktop-only")
            imgs = infos.find_elements(By.TAG_NAME, "img")
            lingua = ""
            for img in imgs:
                title = img.get_attribute("title") or ""
                if title:
                    lingua = title
            conds = infos.find_elements(By.CLASS_NAME, "quality")
            condicao = ""
            for c in conds:
                titulo = c.get_attribute("title") or ""
                if "NM" in titulo.upper():
                    condicao = titulo
                    break
            return (lingua, condicao)
        except NoSuchElementException:
            return ("","")

    def localiza_botao_comprar_nm(self, store):
        """
        Localiza o <div class="btn-green cursor-pointer" onclick="mpcart.buy(...)">
        """
        try:
            botao = store.find_element(By.CSS_SELECTOR, "div.btn-green.cursor-pointer")
            return botao
        except NoSuchElementException:
            return None

    def abre_modal_carrinho(self):
        """
        Clica no ícone do carrinho para abrir o modal
        e depois clica em 'Meu Carrinho'.
        """
        try:
            cart_icon = self.driver.find_element(By.CSS_SELECTOR, "div.cart-icon-container.icon-container")
            cart_icon.click()
            time.sleep(1)
            meu_carrinho_btn = self.driver.find_element(By.CSS_SELECTOR, "a.btn-view-cart")
            meu_carrinho_btn.click()
            time.sleep(self.tempo_espera)
        except NoSuchElementException:
            print("[AVISO] Não encontrou ícone ou botão 'Meu Carrinho'.")

    def localiza_item_no_carrinho(self, nome, numero):
        """
        Localiza o item no carrinho que corresponde ao nome e número.
        """
        try:
            itens_container = self.driver.find_element(By.CSS_SELECTOR, "div.itens")
            rows = itens_container.find_elements(By.CSS_SELECTOR, "div.row")
            for row in rows:
                try:
                    title_elem = row.find_element(By.CSS_SELECTOR, "p.cardtitle a")
                    texto = title_elem.text.strip()
                    if nome in texto and f"({numero})" in texto:
                        return row
                except NoSuchElementException:
                    pass
            return None
        except NoSuchElementException:
            return None

    def extrai_dados_item_carrinho(self, row):
        """
        Exemplo de row:
        <div class="col-lg-1 col-md-1 col-sm-1 col-xs-3 col-3 item-estoque " id="qEstoque_32649408">8 unids.</div>
        <div class="col-lg-2 col-md-1 hidden-xs preco item-subpreco">R$ 189,90</div>
        <div class="col-lg-2 col-md-2 col-sm-2 col-xs-5 col-5 item-xs-total">
            <div class="preco-total item-total" id="preco_32649673">R$ 4,50</div>
        </div>
        Retorna: quantidade=8, preco=189.90, preco_total=4.50
        """
        dados = {}
        try:
            estoque_elem = row.find_element(By.CSS_SELECTOR, "div.item-estoque")
            texto_estoque = estoque_elem.text.strip()  # "8 unids."
            qtd = 0
            for parte in texto_estoque.split():
                if parte.isdigit():
                    qtd = int(parte)
                    break
            dados["quantidade"] = qtd
        except NoSuchElementException:
            dados["quantidade"] = 0

        try:
            subpreco_elem = row.find_element(By.CSS_SELECTOR, "div.preco.item-subpreco")
            texto_subpreco = subpreco_elem.text.strip()  # "R$ 189,90"
            valor = self.converte_preco_para_float(texto_subpreco)
            dados["preco"] = valor
        except NoSuchElementException:
            dados["preco"] = 0.0

        try:
            total_elem = row.find_element(By.CSS_SELECTOR, "div.preco-total.item-total")
            texto_total = total_elem.text.strip()  # "R$ 4,50"
            valor_t = self.converte_preco_para_float(texto_total)
            dados["preco_total"] = valor_t
        except NoSuchElementException:
            dados["preco_total"] = 0.0

        return dados

    def remove_item_carrinho(self, row):
        """
        Clica no botão remover do carrinho: 
        <div class="btn-circle remove delete item-delete" onclick="mpDel(...)">
        """
        try:
            remove_btn = row.find_element(By.CSS_SELECTOR, "div.btn-circle.remove.delete.item-delete")
            remove_btn.click()
            time.sleep(1)
        except NoSuchElementException:
            pass

    def converte_preco_para_float(self, txt):
        """
        Converte string do tipo 'R$ 189,90' para float 189.90
        """
        t = txt.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(t)
        except:
            return 0.0
