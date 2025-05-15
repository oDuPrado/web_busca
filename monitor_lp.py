"""
LigaPokémon • Monitor de produtos (caixas, ETB etc.)

⚙️  COMO USAR
------------
1. Instale dependências
      pip install selenium requests pysqlite3
2. Coloque chromedriver na mesma pasta OU
   defina CHROMEDRIVER_PATH.
3. Preencha TELEGRAM_TOKEN e CHAT_ID(S).
4. Rode uma vez com --add <url> ... para cadastrar produtos:
      python monitor_lp.py --add https://www.ligapokemon.com.br/?view=prod/view&pcode=133442
5. Depois simplesmente:
      python monitor_lp.py
   O script abre 1 thread por url, checa a cada ~1 min
   e avisa se o menor preço “lacrado” cair.
"""

import os, sys, time, random, sqlite3, argparse, traceback, textwrap, threading
from datetime import datetime
from typing import List, Optional

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, UnexpectedAlertPresentException,
    WebDriverException)
import sqlite3
from typing import List
from datetime import datetime

# ─────────────────────────────────────────────────────────
#                       CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "8193369149:AAHIcRbe8wp0kdXqINx-ui8D8-oPww33N-k"   # Token válido do HoHubBOT
CHAT_ID        =  [766390459,1626388239]                                        # Seu ID pessoal

DB_FILE        = "lp_monitor.db"
CHECK_MIN_S    = 55                 # intervalo mínimo entre checks
CHECK_MAX_S    = 87                 # intervalo máximo
HEADLESS       = True               # mude p/ False se quiser ver o Chrome
CHROMEDRIVER_PATH = None            # coloque aqui se não estiver no PATH

# Selectors / XPaths centralizados para alterar fácil
SEL_STORE_BLK       = 'div.store'                     # bloco de vendedor
SEL_COND            = ".//div[contains(@class,'condition') and contains(text(),'Lacrado')]"
SEL_CART_BTN        = ".//div[contains(@class,'btn-green')]"  # “Comprar”
SEL_CART_ICON       = "img.cart-icon"
SEL_VIEWCART_BTN    = "a.btn-view-cart"
SEL_ROW_CART        = "div.itens > div.row"  # Pega as linhas de itens no carrinho
SEL_TOTAL_PRICE     = "div.item-subpreco"    
SEL_QTD_CART        = "div.item-estoque"     
SEL_TOTAL_PRICE     = "div.preco-total.item-total"
SEL_REMOVE_BTN      = "div.btn-circle.remove"

# ─────────────────────────────────────────────────────────
#                 utilidades Telegram (reuso)
# ─────────────────────────────────────────────────────────
_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

def _post(method: str, data: dict) -> bool:
    try:
        r = requests.post(f"{_API}/{method}", data=data, timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:
        print(f"[ERRO Telegram] {exc}")
        return False

def send_message(msg: str, *, parse_html=True):
    chat_ids = CHAT_ID if isinstance(CHAT_ID, list) else [CHAT_ID]
    for cid in chat_ids:
        payload = {"chat_id": cid, "text": msg, "disable_web_page_preview": True}
        if parse_html:
            payload["parse_mode"] = "HTML"
        _post("sendMessage", payload)
        
def format_price_alert(product_name: str, url: str, new_price: float, last_price: float, qty: int) -> str:
    return (
        f"📉 <b>Alerta de Queda de Preço – Liga Pokémon</b>\n"
        f"🏷️ <b>{product_name}</b>\n\n"
        f"💰 <u>Preço caiu!</u>\n"
        f"• De: <s>R$ {last_price:,.2f}</s>\n"
        f"• Para: <b>R$ {new_price:,.2f}</b>\n\n"
        f"📦 <b>Disponível:</b> {qty} unidade(s)\n"
        f"🔗 <a href=\"{url}\">Acesse o produto</a>"
    )

def notify_error(ctx: str, err: Exception):
    tb = traceback.format_exception_only(type(err), err)
    msg = textwrap.dedent(f"""
        ⚠️ <b>LP Monitor – ERRO</b>
        <b>Contexto:</b> {ctx}
        <b>Hora:</b> {datetime.now():%d/%m %H:%M:%S}
        <b>Detalhe:</b> <code>{''.join(tb).strip()}</code>
    """)
    send_message(msg)

# ─────────────────────────────────────────────────────────
#                 banco SQLite (urls / preços)
# ─────────────────────────────────────────────────────────
def init_db() -> None:
    """Cria a tabela products se não existir."""
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS products (
                url TEXT PRIMARY KEY,
                last_price REAL DEFAULT 0,
                last_check TEXT
            )
        """)
        con.commit()

def add_urls(urls: List[str]) -> None:
    """Insere as URLs (ignorando duplicatas)."""
    with sqlite3.connect(DB_FILE) as con:
        for u in urls:
            con.execute(
                "INSERT OR IGNORE INTO products (url) VALUES (?)",
                (u,)
            )
        con.commit()

def get_all_urls() -> List[str]:
    """Retorna a lista de todas as URLs cadastradas."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.execute("SELECT url FROM products")
        return [row[0] for row in cur.fetchall()]

def update_price(url: str, price: float) -> None:
    """Atualiza last_price e last_check para uma URL já existente."""
    with sqlite3.connect(DB_FILE) as con:
        con.execute(
            "UPDATE products SET last_price=?, last_check=? WHERE url=?",
            (price, datetime.now().isoformat(timespec="seconds"), url)
        )
        con.commit()

def get_last_price(url: str) -> float:
    """Retorna o último preço conhecido para a URL (0 se não existir)."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.execute(
            "SELECT last_price FROM products WHERE url=?",
            (url,)
        )
        row = cur.fetchone()
        return row[0] if row else 0.0

def delete_url(url: str) -> None:
    """Remove uma URL do monitoramento."""
    with sqlite3.connect(DB_FILE) as con:
        con.execute(
            "DELETE FROM products WHERE url=?",
            (url,)
        )
        con.commit()

def edit_url(old_url: str, new_url: str) -> None:
    """Altera uma URL já cadastrada para um novo valor."""
    with sqlite3.connect(DB_FILE) as con:
        con.execute(
            "UPDATE products SET url=? WHERE url=?",
            (new_url, old_url)
        )
        con.commit()

# ─────────────────────────────────────────────────────────
#                    Selenium helpers
# ─────────────────────────────────────────────────────────
def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--disable-notifications")
    opts.add_argument("--disable-popup-blocking")
    if HEADLESS:
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1920,1080")
    if CHROMEDRIVER_PATH:
        drv = webdriver.Chrome(CHROMEDRIVER_PATH, options=opts)
    else:
        drv = webdriver.Chrome(options=opts)
    drv.set_page_load_timeout(30)
    return drv

def safe_click(el):
    drv = el._parent
    drv.execute_script("arguments[0].click();", el)

def close_alerts(driver):
    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass

def close_cookies_banner(driver):
    try:
        banner = driver.find_element(By.ID, "lgpd-cookie")
        btn = banner.find_element(By.TAG_NAME, "button")
        safe_click(btn)
    except NoSuchElementException:
        pass

# ─────────────────────────────────────────────────────────
#            lógica de captura (um produto por vez)
# ─────────────────────────────────────────────────────────
def capture_price(driver, url: str) -> Optional[float]:
    print(f"\n[LOG] === Iniciando captura: {url}")
    try:
        driver.get(url)
        print("[LOG] Página carregada.")
    except Exception as e:
        print(f"[ERRO] Falha ao carregar página: {e}")
        return None

    try:
        close_cookies_banner(driver)
        print("[LOG] Banner de cookies fechado (ou inexistente).")
    except Exception as e:
        print(f"[AVISO] Falha ao fechar cookies: {e}")

    time.sleep(2)

    # Primeiro vendedor Lacrado
    try:
        stores = driver.find_elements(By.CSS_SELECTOR, SEL_STORE_BLK)
        print(f"[LOG] Vendedores encontrados: {len(stores)}")

        encontrou_vendedor = False

        # 1º passo: procurar Lacrado
        for idx, st in enumerate(stores):
            texto_loja = st.text.lower()
            if "lacrado" in texto_loja:
                print(f"[LOG] Loja #{idx+1} é 'Lacrado'. Tentando clicar.")
                btn = st.find_element(By.XPATH, SEL_CART_BTN)
                safe_click(btn)
                encontrou_vendedor = True
                break
            
        # 2º passo: fallback – qualquer um
        if not encontrou_vendedor and stores:
            print("[LOG] Nenhum vendedor 'Lacrado'. Usando o primeiro disponível.")
            btn = stores[0].find_element(By.CSS_SELECTOR, SEL_CART_BTN)
            safe_click(btn)
            encontrou_vendedor = True

        if not encontrou_vendedor:
            print("[LOG] Nenhum vendedor clicável encontrado.")
            return None

    except Exception as e:
        print(f"[ERRO] Falha ao processar vendedores: {e}")
        return None

    # Abre carrinho
    time.sleep(2)
    try:
        cart_icon = driver.find_element(By.CSS_SELECTOR, SEL_CART_ICON)
        safe_click(cart_icon)
        print("[LOG] Ícone do carrinho clicado.")
        time.sleep(1)

        view_btn = driver.find_element(By.CSS_SELECTOR, SEL_VIEWCART_BTN)
        safe_click(view_btn)
        print("[LOG] Botão 'Ver carrinho' clicado.")
    except Exception as e:
        print(f"[ERRO] Falha ao abrir carrinho: {e}")
        return None

    # ─── Lê preço, quantidade **e nome do produto** ───
    time.sleep(3)
    try:
        # 1) captura o nome do produto
        nome_elem = driver.find_element(By.CSS_SELECTOR, "a.pretoG.b")
        product_name = nome_elem.text.strip()
        print(f"[LOG] Nome do produto: {product_name}")

        # 2) lê preço e quantidade
        rows = driver.find_elements(By.CSS_SELECTOR, SEL_ROW_CART)
        if not rows:
            print("[INFO] Nenhum item no carrinho.")
            return None
        row = rows[0]
        print("[LOG] Item no carrinho localizado.")

        price_txt = row.find_element(By.CSS_SELECTOR, SEL_TOTAL_PRICE).text
        print(f"[LOG] Preço encontrado: {price_txt}")
        price = float(price_txt.replace("R$", "").replace(".", "").replace(",", ".").strip())

        qty_txt = row.find_element(By.CSS_SELECTOR, SEL_QTD_CART).text
        print(f"[LOG] Texto de quantidade: {qty_txt}")
        qty = int("".join(filter(str.isdigit, qty_txt))) or 1

        unit_price = price  # já é unitário
        print(f"[LOG] Preço unitário final: R$ {unit_price:.2f}")

    except Exception as e:
        print(f"[ERRO] Falha ao ler dados do carrinho: {e}")
        return None

    finally:
        # limpa o carrinho
        try:
            rm_btn = driver.find_element(By.CSS_SELECTOR, SEL_REMOVE_BTN)
            safe_click(rm_btn)
            close_alerts(driver)
            print("[LOG] Item removido do carrinho.")
            time.sleep(1)
        except Exception as e:
            print(f"[AVISO] Falha ao limpar carrinho: {e}")

    # retorna preço, quantidade e nome
    return unit_price, qty, product_name


# ─────────────────────────────────────────────────────────
#                      worker por produto
# ─────────────────────────────────────────────────────────
def worker(url: str):
    driver = make_driver()
    try:
        while True:
            try:
                result = capture_price(driver, url)
                if result is None:
                    raise ValueError("Preço não capturado")

                new_price, available_qty, product_name = result
                last_price = get_last_price(url)
                print(f"[{product_name}] atual R$ {new_price:.2f} | último R$ {last_price:.2f} | estoque {available_qty}")

                if last_price == 0 or new_price < last_price:
                    msg =format_price_alert(product_name, url, new_price, last_price, available_qty)
                    send_message(msg)
                    update_price(url, new_price)
                else:
                    # só atualiza o timestamp
                    update_price(url, last_price)

            except Exception as e:
                notify_error(url, e)

            time.sleep(random.randint(CHECK_MIN_S, CHECK_MAX_S))
    finally:
        driver.quit()


# ─────────────────────────────────────────────────────────
#                           main
# ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Monitor de produtos LigaPokemon")
    parser.add_argument("--add", nargs="+", help="adiciona novas URLs ao monitor")
    args = parser.parse_args()

    init_db()
    if args.add:
        add_urls(args.add)
        print(f"[OK] {len(args.add)} url(s) adicionada(s).")
        sys.exit(0)

    urls = get_all_urls()
    if not urls:
        print("Nenhum produto cadastrado. Use --add <url>")
        sys.exit(1)

    print(f"Monitorando {len(urls)} produtos... Ctrl+C p/ sair.")
    for u in urls:
        th = threading.Thread(target=worker, args=(u,), daemon=True)
        th.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Encerrando...")

# if __name__ == "__main__":
#     main()

