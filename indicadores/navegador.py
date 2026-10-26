"""Abertura do app no navegador (Chrome, se instalado)."""

import os
import subprocess
import webbrowser

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]


def abrir_no_chrome(url):
    for caminho in CHROME_PATHS:
        if os.path.isfile(caminho):
            subprocess.Popen([caminho, url])
            return
    print("Google Chrome não encontrado; abrindo no navegador padrão.")
    webbrowser.open(url)
