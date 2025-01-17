import PySimpleGUI as sg
import pandas as pd
import numpy as np
from pathlib import Path
import config
from utils.dados import (
    carrega_lista_cards,
    salvar_resultados_csv
)
from utils.scraper import (
    LigaPokemonScraper
)

class App:
    def __init__(self):
        self.layout_inicial()

    def layout_inicial(self):
        self.df_cards = pd.DataFrame()
        self.resultados = []
        col_input_cards = [
            [sg.Text("Arquivo de Cartas (nome;colecao;numero):")],
            [
                sg.Input(key="-FILE_CARDS-", enable_events=True, size=(40,1)),
                sg.FileBrowse("Localizar CSV", file_types=(("CSV Files", "*.csv"),))
            ],
            [sg.Listbox(values=[], size=(60,8), key="-LIST_CARDS-")]
        ]
        col_botao = [
            [sg.Button("Buscar Preços", key="-BUSCAR-", size=(12,1), disabled=True)]
        ]
        layout = [
            [
                sg.Column(col_input_cards),
                sg.Column(col_botao)
            ],
            [sg.Output(size=(100,10))],
        ]
        self.window = sg.Window("App de Raspagem - Liga Pokémon", layout, finalize=True)

    def run(self):
        while True:
            event, values = self.window.read()
            if event in (sg.WIN_CLOSED, "Exit"):
                break

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
                    else:
                        print("[ERRO] CSV inválido ou vazio.")

            if event == "-BUSCAR-":
                if self.df_cards.empty:
                    print("[AVISO] Nenhuma carta carregada. Selecione um arquivo CSV.")
                    continue

                print("[INFO] Iniciando raspagem...")
                try:
                    scraper = LigaPokemonScraper(
                        url_base=config.WEBSITE_1,
                        debug=config.DEBUG,
                        tesseract_cmd=config.TESSERACT_CMD,
                        tempo_espera=config.TEMPO_ESPERA
                    )
                    self.resultados = []
                    for idx, row in self.df_cards.iterrows():
                        nome_carta = row["nome"]
                        colecao = row["colecao"]
                        numero = row["numero"]
                        print(f"[INFO] Buscando {nome_carta} (Coleção={colecao}, N°={numero})")
                        try:
                            retorno = scraper.busca_carta_completa(
                                nome=nome_carta,
                                colecao=colecao,
                                numero=numero
                            )
                            if retorno:
                                self.resultados.extend(retorno)
                        except Exception as e:
                            print(f"[ERRO] Falha ao buscar carta: {e}")

                    scraper.fechar_driver()
                    if self.resultados:
                        salvar_resultados_csv(self.resultados, Path(config.SAIDA_CSV))
                        print("[INFO] Raspagem finalizada e resultados salvos.")
                    else:
                        print("[INFO] Nenhum resultado válido foi coletado.")
                except Exception as e:
                    print(f"[ERRO] Falha ao inicializar o scraper: {e}")

        self.window.close()

if __name__ == "__main__":
    app = App()
    app.run()
