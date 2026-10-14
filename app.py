"""Visualizador web dos indicadores SEPLAN.

Lista os registros de Dados/dados_de_base_indicadores-v5.json e, quando o
arquivo JSON referenciado em "link_do_arquivo_json" existe na pasta Dados/tabelas_bi
(ex.: avancasc_habitacao_prata_densidade_demografica_2022_den_demografica.json),
exibe um link para visualizar esses dados.

Uso:  python app.py [--porta 8000]
"""

import argparse
import html
import json
import os
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "Dados"
ARQUIVO_INDICADORES = DADOS_DIR / "dados_de_base_indicadores-v5.json"
TABELAS_DIR = DADOS_DIR / "tabelas_bi"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

CSS = """
:root { --bg:#f5f7fa; --card:#fff; --txt:#1f2933; --muted:#616e7c; --pri:#0b5cad;
        --borda:#d9e2ec; --head:#e4ecf5; --ok:#1b7f3b; }
* { box-sizing:border-box; }
body { margin:0; font-family:Segoe UI, Roboto, Arial, sans-serif; background:var(--bg); color:var(--txt); }
header { background:var(--pri); color:#fff; padding:18px 24px; }
header h1 { margin:0; font-size:1.35rem; }
header p { margin:4px 0 0; opacity:.85; font-size:.9rem; }
main { padding:20px 24px; }
a { color:var(--pri); }
.card { background:var(--card); border:1px solid var(--borda); border-radius:8px; padding:16px; margin-bottom:16px; }
.filtros { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
input, select { padding:8px 10px; border:1px solid var(--borda); border-radius:6px; font-size:.9rem; }
input[type=search] { min-width:280px; flex:1; }
.tabela-wrap { overflow:auto; max-height:72vh; border:1px solid var(--borda); border-radius:8px; background:var(--card); }
table { border-collapse:collapse; width:100%; font-size:.85rem; }
th, td { padding:8px 10px; border-bottom:1px solid var(--borda); text-align:left; vertical-align:top; }
th { background:var(--head); position:sticky; top:0; cursor:pointer; user-select:none; white-space:nowrap; z-index:1; }
tr:hover td { background:#f0f6ff; }
td.num { text-align:right; font-variant-numeric:tabular-nums; }
.btn { display:inline-block; padding:5px 10px; background:var(--ok); color:#fff; border-radius:5px;
       text-decoration:none; white-space:nowrap; font-size:.8rem; }
.btn:hover { filter:brightness(1.1); }
.sem { color:var(--muted); font-size:.8rem; white-space:nowrap; }
.stats { display:flex; flex-wrap:wrap; gap:12px; }
.stat { background:var(--card); border:1px solid var(--borda); border-radius:8px; padding:12px 16px; min-width:150px; }
.stat b { display:block; font-size:1.3rem; }
.stat span { color:var(--muted); font-size:.8rem; }
dl { display:grid; grid-template-columns:max-content 1fr; gap:6px 14px; margin:0; font-size:.9rem; }
dt { font-weight:600; color:var(--muted); }
dd { margin:0; }
.contador { color:var(--muted); font-size:.85rem; }
"""

# Ordenação por clique no cabeçalho + filtro de texto (compartilhado pelas páginas)
JS = """
function ordenar(th) {
  const tabela = th.closest('table'), tbody = tabela.tBodies[0];
  const idx = [...th.parentNode.children].indexOf(th);
  const asc = th.dataset.ordem !== 'asc';
  tabela.querySelectorAll('th').forEach(t => { delete t.dataset.ordem; t.textContent = t.textContent.replace(/ [▲▼]$/, ''); });
  th.dataset.ordem = asc ? 'asc' : 'desc';
  th.textContent += asc ? ' ▲' : ' ▼';
  const val = tr => tr.children[idx].dataset.v ?? tr.children[idx].textContent.trim();
  [...tbody.rows].sort((a, b) => {
    const x = val(a), y = val(b), nx = parseFloat(x), ny = parseFloat(y);
    const r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y, 'pt-BR');
    return asc ? r : -r;
  }).forEach(tr => tbody.appendChild(tr));
}
function filtrar() {
  const termo = document.getElementById('busca').value.toLowerCase();
  const sel = document.getElementById('grupo');
  const grupo = sel ? sel.value : '';
  const col = sel ? +sel.dataset.col : -1;
  let n = 0;
  document.querySelectorAll('#tabela tbody tr').forEach(tr => {
    const ok = tr.textContent.toLowerCase().includes(termo) &&
               (!grupo || tr.children[col].textContent.trim() === grupo);
    tr.style.display = ok ? '' : 'none';
    if (ok) n++;
  });
  document.getElementById('contador').textContent = n + ' registro(s)';
}
document.querySelectorAll('th').forEach(th => th.addEventListener('click', () => ordenar(th)));
"""


def esc(valor):
    return "" if valor is None else html.escape(str(valor))


def carregar_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def localizar_arquivo_dados(nome):
    """Resolve link_do_arquivo_json para um arquivo existente em Dados/tabelas_bi/.

    No catálogo o link vem como tabelas_bi/catalogo.schema.tabela.json, mas os
    arquivos salvos usam underscores (catalogo_schema_tabela.json).
    """
    if not nome:
        return None
    relativo = Path(nome)
    pasta = TABELAS_DIR / relativo.parent.relative_to(TABELAS_DIR.name) \
        if relativo.parts[:1] == (TABELAS_DIR.name,) else TABELAS_DIR
    arquivo = relativo.name
    base = arquivo[:-5] if arquivo.lower().endswith(".json") else arquivo
    for candidato in (arquivo, base.replace(".", "_") + ".json"):
        caminho = (pasta / candidato).resolve()
        if caminho.is_file() and TABELAS_DIR in caminho.parents:
            return caminho
    return None


def pagina(titulo, corpo):
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title><style>{CSS}</style></head>
<body>{corpo}<script>{JS}</script></body></html>"""


def pagina_indicadores():
    indicadores = carregar_json(ARQUIVO_INDICADORES)
    eixos = sorted({i.get("bloco_eixo") or "" for i in indicadores})
    com_dados = 0
    linhas = []
    for ind in indicadores:
        arquivo = localizar_arquivo_dados(ind.get("link_do_arquivo_json"))
        if arquivo:
            com_dados += 1
            acao = f'<a class="btn" href="/dados?id={ind["id"]}">Visualizar dados</a>'
        else:
            acao = '<span class="sem">Sem arquivo</span>'
        fontes = " ".join(
            f'<a href="{esc(u)}" target="_blank" rel="noopener">fonte</a>'
            for u in (ind.get("link_da_fonte_publico"), ind.get("link_da_fonte_publico_2"))
            if u and str(u).startswith("http")
        )
        linhas.append(f"""<tr>
<td class="num">{esc(ind.get("id"))}</td><td>{acao}</td>
<td>{esc(ind.get("bloco_eixo"))}</td><td><b>{esc(ind.get("indicador"))}</b></td>
<td>{esc(ind.get("descricao"))}</td><td>{esc(ind.get("formula_de_calculo"))}</td>
<td>{esc(ind.get("unidade_de_medida"))}</td><td>{esc(ind.get("fonte_dos_dados"))} {fontes}</td>
<td>{esc(ind.get("temporalidade"))}</td><td><code>{esc(ind.get("tabela_databricks"))}</code></td>
</tr>""")

    opcoes = "".join(f'<option value="{esc(e)}">{esc(e)}</option>' for e in eixos)
    corpo = f"""
<header><h1>Indicadores SEPLAN — Dados de Base v5</h1>
<p>{ARQUIVO_INDICADORES.name}</p></header>
<main>
<div class="stats" style="margin-bottom:16px">
  <div class="stat"><b>{len(indicadores)}</b><span>indicadores</span></div>
  <div class="stat"><b>{len(eixos)}</b><span>blocos / eixos</span></div>
  <div class="stat"><b>{com_dados}</b><span>com dados disponíveis</span></div>
</div>
<div class="card filtros">
  <input type="search" id="busca" placeholder="Buscar indicador, fonte, tabela..." oninput="filtrar()">
  <select id="grupo" data-col="2" onchange="filtrar()"><option value="">Todos os eixos</option>{opcoes}</select>
  <span class="contador" id="contador">{len(indicadores)} registro(s)</span>
</div>
<div class="tabela-wrap"><table id="tabela"><thead><tr>
<th>ID</th><th>Dados</th><th>Bloco / Eixo</th><th>Indicador</th><th>Descrição</th>
<th>Fórmula de cálculo</th><th>Unidade</th><th>Fonte</th><th>Temporalidade</th><th>Tabela Databricks</th>
</tr></thead><tbody>{"".join(linhas)}</tbody></table></div>
</main>"""
    return pagina("Indicadores SEPLAN", corpo)


def formatar(valor):
    if isinstance(valor, float):
        return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return esc(valor)


def pagina_dados(id_indicador):
    indicadores = carregar_json(ARQUIVO_INDICADORES)
    ind = next((i for i in indicadores if str(i.get("id")) == str(id_indicador)), None)
    if ind is None:
        return None
    arquivo = localizar_arquivo_dados(ind.get("link_do_arquivo_json"))
    if arquivo is None:
        return None
    registros = carregar_json(arquivo)
    colunas = list(dict.fromkeys(k for r in registros for k in r))
    numericas = [c for c in colunas
                 if c not in ("id", "ano") and all(isinstance(r.get(c), (int, float))
                                                    for r in registros if r.get(c) is not None)]

    estatisticas = ""
    if numericas and registros:
        col = numericas[0]
        valores = [r[col] for r in registros if r.get(col) is not None]
        maior = max(registros, key=lambda r: r.get(col) or float("-inf"))
        menor = min(registros, key=lambda r: r.get(col) if r.get(col) is not None else float("inf"))
        rotulo = "municipio" if "municipio" in colunas else colunas[0]
        estatisticas = f"""<div class="stats" style="margin-bottom:16px">
  <div class="stat"><b>{len(registros)}</b><span>registros</span></div>
  <div class="stat"><b>{formatar(sum(valores) / len(valores))}</b><span>média ({esc(col)})</span></div>
  <div class="stat"><b>{formatar(maior[col])}</b><span>maior: {esc(maior.get(rotulo))}</span></div>
  <div class="stat"><b>{formatar(menor[col])}</b><span>menor: {esc(menor.get(rotulo))}</span></div>
</div>"""

    filtro_grupo = ""
    if "fecam" in colunas:
        grupos = sorted({str(r.get("fecam") or "") for r in registros})
        opcoes = "".join(f'<option value="{esc(g)}">{esc(g)}</option>' for g in grupos)
        filtro_grupo = (f'<select id="grupo" data-col="{colunas.index("fecam")}" onchange="filtrar()">'
                        f'<option value="">Todas as FECAM</option>{opcoes}</select>')

    cabecalho = "".join(f"<th>{esc(c)}</th>" for c in colunas)
    linhas = []
    for r in registros:
        celulas = []
        for c in colunas:
            v = r.get(c)
            if isinstance(v, (int, float)):
                celulas.append(f'<td class="num" data-v="{v}">{formatar(v)}</td>')
            else:
                celulas.append(f"<td>{esc(v)}</td>")
        linhas.append(f"<tr>{''.join(celulas)}</tr>")

    corpo = f"""
<header><h1>{esc(ind.get("indicador"))}</h1>
<p>{esc(ind.get("bloco_eixo"))} · {esc(ind.get("unidade_de_medida"))} · {esc(arquivo.name)}</p></header>
<main>
<p><a href="/">← Voltar aos indicadores</a> · <a href="/json?id={ind["id"]}" target="_blank">JSON bruto</a></p>
<div class="card"><dl>
  <dt>Descrição</dt><dd>{esc(ind.get("descricao"))}</dd>
  <dt>Fórmula</dt><dd>{esc(ind.get("formula_de_calculo"))}</dd>
  <dt>Fonte</dt><dd>{esc(ind.get("fonte_dos_dados"))}</dd>
  <dt>Temporalidade</dt><dd>{esc(ind.get("temporalidade"))}</dd>
  <dt>Tabela Databricks</dt><dd><code>{esc(ind.get("tabela_databricks"))}</code></dd>
</dl></div>
{estatisticas}
<div class="card filtros">
  <input type="search" id="busca" placeholder="Buscar município, código IBGE..." oninput="filtrar()">
  {filtro_grupo}
  <span class="contador" id="contador">{len(registros)} registro(s)</span>
</div>
<div class="tabela-wrap"><table id="tabela"><thead><tr>{cabecalho}</tr></thead>
<tbody>{"".join(linhas)}</tbody></table></div>
</main>"""
    return pagina(ind.get("indicador") or "Dados", corpo)


class Handler(BaseHTTPRequestHandler):
    def _responder(self, status, conteudo, tipo="text/html; charset=utf-8"):
        dados = conteudo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):
        url = urlparse(self.path)
        id_ind = parse_qs(url.query).get("id", [None])[0]
        try:
            if url.path == "/":
                return self._responder(200, pagina_indicadores())
            if url.path == "/dados":
                html_dados = pagina_dados(id_ind)
                if html_dados:
                    return self._responder(200, html_dados)
            if url.path == "/json":
                ind = next((i for i in carregar_json(ARQUIVO_INDICADORES)
                            if str(i.get("id")) == str(id_ind)), None)
                arquivo = ind and localizar_arquivo_dados(ind.get("link_do_arquivo_json"))
                if arquivo:
                    return self._responder(200, arquivo.read_text(encoding="utf-8"),
                                           "application/json; charset=utf-8")
            self._responder(404, pagina("Não encontrado",
                                        '<main><h2>Não encontrado</h2><a href="/">Voltar</a></main>'))
        except Exception as exc:  # mostra o erro no navegador em vez de derrubar a conexão
            self._responder(500, pagina("Erro", f"<main><h2>Erro</h2><pre>{esc(exc)}</pre></main>"))

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def abrir_no_chrome(url):
    for caminho in CHROME_PATHS:
        if os.path.isfile(caminho):
            subprocess.Popen([caminho, url])
            return
    print("Google Chrome não encontrado; abrindo no navegador padrão.")
    webbrowser.open(url)


def main():
    parser = argparse.ArgumentParser(description="Visualizador de indicadores SEPLAN")
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o Chrome")
    args = parser.parse_args()

    servidor = ThreadingHTTPServer(("127.0.0.1", args.porta), Handler)
    url = f"http://127.0.0.1:{args.porta}/"
    print(f"Servidor em {url}  (Ctrl+C para encerrar)")
    if not args.sem_navegador:
        threading.Timer(0.5, abrir_no_chrome, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
