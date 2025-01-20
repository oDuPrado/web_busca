import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException
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

    def fecha_banner_cookies(self):
        """
        Fecha banner de cookies, se existir
        """
        try:
            banner = self.driver.find_element(By.ID, "lgpd-cookie")
            fechar_btn = banner.find_element(By.TAG_NAME, "button")
            fechar_btn.click()
            print("[INFO] Banner de cookies fechado.")
            time.sleep(1)
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"[AVISO] Erro ao fechar banner de cookies: {e}")

    def monta_url_carta(self, nome, colecao, numero):
        nome_url = nome.replace(" ", "%20")
        return f"{self.url_base}?view=cards/card&card={nome_url}%20({numero})&ed={colecao}&num={numero}"

    def busca_carta_completa(self, nome, colecao, numero):
        url = self.monta_url_carta(nome, colecao, numero)
        self.driver.get(url)
        time.sleep(self.tempo_espera)
        self.fecha_banner_cookies()

        resultados = []
        try:
            marketplace = self.driver.find_element(By.ID, "marketplace-stores")
            stores = marketplace.find_elements(By.CLASS_NAME, "store")
        except NoSuchElementException:
            print("[AVISO] Sem marketplace-stores. Nenhum vendedor encontrado.")
            return resultados

        for store in stores:
            lingua, condicao = self.extrai_lingua_e_condicao(store)
            if "NM" in condicao.upper():
                botao_comprar = self.localiza_botao_comprar_nm(store)
                if botao_comprar:
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
        return resultados

    def extrai_lingua_e_condicao(self, store):
        """
        Encontra a 'infos-quality-and-language.desktop-only'
        e tenta achar a condition com NM no 'title'.
        """
        try:
            infos = store.find_element(By.CLASS_NAME, "infos-quality-and-language.desktop-only")
            imgs = infos.find_elements(By.TAG_NAME, "img")
            lingua = ""
            for img in imgs:
                titulo = img.get_attribute("title") or ""
                if titulo:
                    lingua = titulo
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
        try:
            botao = store.find_element(By.CSS_SELECTOR, "div.btn-green.cursor-pointer")
            return botao
        except NoSuchElementException:
            return None

    def abre_modal_carrinho(self):
        try:
            cart_icon = self.driver.find_element(By.CSS_SELECTOR, "div.cart-icon-container.icon-container")
            cart_icon.click()
            time.sleep(1)
            meu_carrinho_btn = self.driver.find_element(By.CSS_SELECTOR, "a.btn-view-cart")
            meu_carrinho_btn.click()
            time.sleep(self.tempo_espera)
        except NoSuchElementException:
            pass

    def localiza_item_no_carrinho(self, nome, numero):
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
        dados = {}
        # Quantidade
        try:
            estoque_elem = row.find_element(By.CSS_SELECTOR, "div.item-estoque")
            texto_est = estoque_elem.text.strip()  # "8 unids."
            qtd = 0
            for parte in texto_est.split():
                if parte.isdigit():
                    qtd = int(parte)
                    break
            dados["quantidade"] = qtd
        except NoSuchElementException:
            dados["quantidade"] = 0

        # Preço unitário
        try:
            subpreco_elem = row.find_element(By.CSS_SELECTOR, "div.preco.item-subpreco")
            dados["preco"] = self.converte_preco_para_float(subpreco_elem.text.strip())
        except NoSuchElementException:
            dados["preco"] = 0.0

        # Preço total
        try:
            total_elem = row.find_element(By.CSS_SELECTOR, "div.preco-total.item-total")
            dados["preco_total"] = self.converte_preco_para_float(total_elem.text.strip())
        except NoSuchElementException:
            dados["preco_total"] = 0.0

        return dados

    def remove_item_carrinho(self, row):
        try:
            remove_btn = row.find_element(By.CSS_SELECTOR, "div.btn-circle.remove.delete.item-delete")
            remove_btn.click()
            time.sleep(1)
        except NoSuchElementException:
            pass

    def converte_preco_para_float(self, txt):
        val = txt.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            return float(val)
        except:
            return 0.0
