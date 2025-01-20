import PySimpleGUI as sg
import pandas as pd
import numpy as np
import random
import time
import threading
from datetime import datetime
from pathlib import Path
import config
import matplotlib
matplotlib.use("Agg")  # Para evitar conflitos de backend
import matplotlib.pyplot as plt
from io import BytesIO
from utils.dados import (
    carrega_lista_cards,
    salvar_resultados_csv,
    salvar_monitoramento,
    carrega_historico_raspagem
)
from utils.scraper import (
    LigaPokemonScraper
)

class App:
    def __init__(self):
        # Define o tema inicial
        sg.theme(config.TEMA_INICIAL)
        self.layout_inicial()

    def layout_inicial(self):
        self.df_cards = pd.DataFrame()
        self.resultados = []
        self.df_monitor = pd.DataFrame()
        self.monitor_intervalo = 60

        # Seção de tema personalizável
        col_tema = [
            [sg.Text("Tema:")],
            [sg.Combo(sg.theme_list(), default_value=config.TEMA_INICIAL, key="-TEMA-", enable_events=True, size=(20,1))]
        ]

        # Seção para importar cartas
        col_input_cards = [
            [sg.Text("Arquivo de Cartas (nome;colecao;numero):")],
            [
                sg.Input(key="-FILE_CARDS-", enable_events=True, size=(40,1)),
                sg.FileBrowse("Localizar CSV", file_types=(("CSV Files", "*.csv"),))
            ],
            [sg.Listbox(values=[], size=(60,8), key="-LIST_CARDS-")],
            [sg.Button("Buscar Preços", key="-BUSCAR-", size=(12,1), disabled=True)]
        ]

        # Seção de resultados em tabela
        col_tabela = [
            [sg.Text("Resultados da Raspagem / Monitoramento:")],
            [sg.Table(values=[],
                      headings=["Nome","Colecao","Num","Cond","Qtde","Preço","Total","Língua"],
                      key="-TABLE-RESULTS-", 
                      auto_size_columns=True,
                      enable_events=True,
                      display_row_numbers=True,
                      justification="left",
                      num_rows=10,
                      size=(None,10))]
        ]

        # Barra de progresso
        col_progress = [
            [sg.Text("Progresso de Busca/Monitoramento:")],
            [sg.ProgressBar(config.PROGRESS_MAX, orientation='h', size=(40, 20), key="-PROGRESS-")]
        ]

        # Logs separados
        col_logs = [
            [sg.Text("Logs:")],
            [sg.Multiline(size=(70,15), key="-LOGS-", autoscroll=True, disabled=True)]
        ]

        # Monitor
        col_monitor = [
            [sg.Text("Arquivo Monitor (nome;colecao;numero):")],
            [
                sg.Input(key="-FILE_MONITOR-", enable_events=True, size=(40,1)),
                sg.FileBrowse("Localizar CSV", file_types=(("CSV Files", "*.csv"),))
            ],
            [sg.Listbox(values=[], size=(60,8), key="-LIST_MONITOR-")],
            [sg.Text("Intervalo de Monitor (seg):"), sg.Input(str(config.MONITOR_INTERVALO_BASE), size=(5,1), key="-INTERVALO-")],
            [sg.Button("Iniciar Monitoramento", key="-MONITORAR-", size=(20,1), disabled=True)]
        ]

        # Botão para gerar gráfico
        col_graficos = [
            [sg.Button("Gerar Gráfico Tendência", key="-GERAR-GRAFICO-", disabled=True)],
            [sg.Image(key="-GRAFICO-")]
        ]

        # Layout principal
        layout = [
            [sg.Column(col_tema), sg.VerticalSeparator(), sg.Column(col_input_cards)],
            [sg.HorizontalSeparator()],
            [sg.Column(col_tabela), sg.VerticalSeparator(), sg.Column(col_progress)],
            [sg.HorizontalSeparator()],
            [sg.Column(col_monitor), sg.VerticalSeparator(), sg.Column(col_graficos), sg.VerticalSeparator(), sg.Column(col_logs)]
        ]
        self.window = sg.Window("App de Raspagem - Liga Pokémon (Completo)", layout, finalize=True)
        self.progress_bar = self.window["-PROGRESS-"]

    def run(self):
        while True:
            event, values = self.window.read(timeout=100)
            if event in (sg.WIN_CLOSED, "Exit"):
                break

            if event == "-TEMA-":
                tema_escolhido = values["-TEMA-"]
                sg.theme(tema_escolhido)
                # Forçar recriação da janela para aplicar o tema
                self.window.close()
                self.layout_inicial()
                continue

            if event == "-FILE_CARDS-":
                csv_path = values["-FILE_CARDS-"]
                if csv_path:
                    self.df_cards = carrega_lista_cards(csv_path, config)
                    if not self.df_cards.empty:
                        linhas_exibicao = []
                        for idx, row in self.df_cards.iterrows():
                            texto = f"Nome={row['nome']}, Colecao={row['colecao']}, Numero={row['numero']}"
                            linhas_exibicao.append(texto)
                        self.window["-LIST_CARDS-"].update(linhas_exibicao)
                        self.window["-BUSCAR-"].update(disabled=False)

            if event == "-BUSCAR-":
                if self.df_cards.empty:
                    self.log("[AVISO] Nenhuma carta carregada.")
                    continue
                self.raspagem_individual()

            if event == "-FILE_MONITOR-":
                csv_path = values["-FILE_MONITOR-"]
                if csv_path:
                    self.df_monitor = carrega_lista_cards(csv_path, config)
                    if not self.df_monitor.empty:
                        linhas_exibicao = []
                        for idx, row in self.df_monitor.iterrows():
                            texto = f"Monitor => Nome={row['nome']}, Colecao={row['colecao']}, Numero={row['numero']}"
                            linhas_exibicao.append(texto)
                        self.window["-LIST_MONITOR-"].update(linhas_exibicao)
                        self.window["-MONITORAR-"].update(disabled=False)

            if event == "-MONITORAR-":
                if self.df_monitor.empty:
                    self.log("[AVISO] Nenhuma carta para monitorar.")
                    continue
                intervalo_str = values["-INTERVALO-"]
                try:
                    self.monitor_intervalo = int(intervalo_str)
                except:
                    self.monitor_intervalo = config.MONITOR_INTERVALO_BASE
                self.monitorar_precos()

            if event == "-GERAR-GRAFICO-":
                # Gera gráfico do histórico
                self.gerar_grafico()

        self.window.close()

    def raspagem_individual(self):
        """
        Raspagem única (sem monitoramento)
        Exibe progresso, resumo e notifica se subir/cair 10%.
        """
        self.log("[INFO] Iniciando raspagem individual...")
        scraper = LigaPokemonScraper(
            url_base=config.WEBSITE_1,
            debug=config.DEBUG,
            tesseract_cmd=config.TESSERACT_CMD,
            tempo_espera=config.TEMPO_ESPERA
        )
        self.resultados = []
        total = len(self.df_cards)
        contador = 0
        precos_anteriores = {}

        for idx, row in self.df_cards.iterrows():
            contador += 1
            perc = int((contador / total) * 100)
            self.progress_bar.Update(perc)

            nome_carta = row["nome"]
            colecao = row["colecao"]
            numero = row["numero"]
            self.log(f"[INFO] Buscando {nome_carta} (Coleção={colecao}, N°={numero})")

            try:
                retorno = scraper.busca_carta_completa(
                    nome=nome_carta,
                    colecao=colecao,
                    numero=numero
                )
                if retorno:
                    # Adiciona ao self.resultados
                    self.resultados.extend(retorno)
                    # Notificação de variação de preço em comparação a algo anterior (exemplo hipotético)
                    # Se a carta já estava em precos_anteriores e agora variou 10%
                    preco_atual = retorno[0].get("preco", 0.0)
                    if nome_carta in precos_anteriores:
                        preco_ant = precos_anteriores[nome_carta]
                        dif = preco_atual - preco_ant
                        if preco_ant > 0:
                            pct = (abs(dif) / preco_ant) * 100
                            if pct >= 10:
                                if dif > 0:
                                    sg.popup(f"Preço de {nome_carta} subiu {pct:.1f}% (de R${preco_ant} para R${preco_atual})!")
                                else:
                                    sg.popup(f"Preço de {nome_carta} caiu {pct:.1f}% (de R${preco_ant} para R${preco_atual})!")
                    precos_anteriores[nome_carta] = preco_atual
                else:
                    self.log("[INFO] Nenhum resultado válido para essa carta.")
            except Exception as e:
                self.log(f"[ERRO] Falha ao buscar carta: {e}")

        scraper.fechar_driver()

        if self.resultados:
            salvar_resultados_csv(self.resultados, Path(config.SAIDA_CSV))
            self.log("[INFO] Raspagem finalizada e resultados salvos.")
            # Mostra na tabela
            self.mostra_resultados_tabela(self.resultados)
            # Resumo
            self.mostra_resumo_buscas(self.resultados)
        else:
            self.log("[INFO] Nenhum resultado foi coletado.")

    def monitorar_precos(self):
        """
        Monitoramento com controle de intervalo, barra de progresso,
        logs, notificação de variação de 10%.
        """
        self.log("[INFO] Iniciando monitoramento contínuo de preços...")

        while True:
            scraper = LigaPokemonScraper(
                url_base=config.WEBSITE_1,
                debug=config.DEBUG,
                tesseract_cmd=config.TESSERACT_CMD,
                tempo_espera=config.TEMPO_ESPERA
            )
            total = len(self.df_monitor)
            contador = 0
            results_monitor = []

            # Aqui guardamos preços anteriores em dict local (poderia ser em CSV)
            precos_anteriores = {}

            for idx, row in self.df_monitor.iterrows():
                contador += 1
                perc = int((contador / total) * 100)
                self.progress_bar.Update(perc)

                nome_carta = row["nome"]
                colecao = row["colecao"]
                numero = row["numero"]
                self.log(f"[MONITOR] Conferindo {nome_carta} (Coleção={colecao}, N°={numero})...")

                try:
                    retorno = scraper.busca_carta_completa(
                        nome=nome_carta,
                        colecao=colecao,
                        numero=numero
                    )
                    if retorno:
                        item = retorno[0]
                        preco_atual = item.get("preco", 0.0)
                        dt_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # Salva no CSV de monitoramento
                        salvar_monitoramento(nome_carta, colecao, numero, preco_atual, dt_str, config.MONITOR_CSV)
                        self.log(f"[MONITOR] Preço verificado: R$ {preco_atual}")

                        # Notificar variação de preço
                        if nome_carta in precos_anteriores:
                            preco_ant = precos_anteriores[nome_carta]
                            dif = preco_atual - preco_ant
                            if preco_ant > 0:
                                pct = (abs(dif) / preco_ant) * 100
                                if pct >= 10:
                                    if dif > 0:
                                        sg.popup(f"O preço de {nome_carta} subiu {pct:.1f}% (de R${preco_ant} para R${preco_atual}).")
                                    else:
                                        sg.popup(f"O preço de {nome_carta} caiu {pct:.1f}% (de R${preco_ant} para R${preco_atual}).")
                        precos_anteriores[nome_carta] = preco_atual
                        results_monitor.append(item)
                    else:
                        self.log("[MONITOR] Não foi encontrado NM para essa carta.")
                except Exception as e:
                    self.log(f"[MONITOR ERRO] Falha ao monitorar {nome_carta}: {e}")

            scraper.fechar_driver()

            # Atualiza tabela de resultados monitorados
            if results_monitor:
                self.mostra_resultados_tabela(results_monitor)

            # Espera "parecer humano"
            tempo_base = self.monitor_intervalo
            variacao = config.MONITOR_VARIACAO
            espera = tempo_base + random.randint(0, variacao)
            self.log(f"[MONITOR] Aguardando {espera} segundos até a próxima verificação...")
            time.sleep(espera)

    def mostra_resultados_tabela(self, lista_resultados):
        """
        Preenche a sg.Table com dados de 'lista_resultados'
        """
        table_values = []
        for dic in lista_resultados:
            table_values.append([
                dic.get("nome",""),
                dic.get("colecao",""),
                dic.get("numero",""),
                dic.get("condicao",""),
                dic.get("quantidade",0),
                dic.get("preco",0.0),
                dic.get("preco_total",0.0),
                dic.get("lingua",""),
            ])
        self.window["-TABLE-RESULTS-"].update(table_values)

    def mostra_resumo_buscas(self, lista_resultados):
        """
        Exibe um resumo da busca: número de cartas, preço médio, menor preço
        """
        if not lista_resultados:
            return
        precos = [r.get("preco",0.0) for r in lista_resultados if r.get("preco",0.0) > 0]
        if not precos:
            return
        n = len(precos)
        menor = min(precos)
        maior = max(precos)
        media = sum(precos)/n
        self.log(f"[RESUMO] Total de cartas: {n}, Menor Preço: {menor}, Maior Preço: {maior}, Preço Médio: {media:.2f}")

    def gerar_grafico(self):
        """
        Lê o CSV de resultados, filtra por uma carta e plota a variação de preços ao longo do tempo.
        EXEMPLO SIMPLES: plota algo genérico.
        """
        df_hist = carrega_historico_raspagem(config.SAIDA_CSV)
        if df_hist.empty:
            sg.popup("Nenhum histórico encontrado para gerar gráfico.")
            return

        # Exemplo: gera gráfico da coluna 'preco'
        df_hist["preco"] = df_hist["preco"].astype(float)
        plt.figure(figsize=(5,3))
        plt.plot(df_hist["preco"], marker="o")
        plt.title("Histórico de Preços (Exemplo)")
        plt.xlabel("Índice (Busca)")
        plt.ylabel("Preço (R$)")

        buf = BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        self.window["-GRAFICO-"].update(data=buf.getvalue())

    def log(self, texto):
        """
        Escreve uma linha de log na Multiline.
        """
        self.window["-LOGS-"].print(texto, end="")

def main():
    sg.theme(config.TEMA_INICIAL)
    app = App()
    app.run()

if __name__ == "__main__":
    main()
