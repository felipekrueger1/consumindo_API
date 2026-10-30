import os
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh


# ------------------------------------------------------------
# 1. CONFIGURACAO DA PAGINA E CREDENCIAIS
# ------------------------------------------------------------
st.set_page_config(
    page_title="Monitoramento Industrial",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

load_dotenv(Path(__file__).resolve().parent / ".env")

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "").strip()
WRITE_KEY = os.getenv("THINGSPEAK_WRITE_KEY", "").strip()
READ_KEY = os.getenv("THINGSPEAK_READ_KEY", "").strip()

URL_ENVIO = "https://api.thingspeak.com/update.json"
URL_LEITURA = (
    f"https://api.thingspeak.com/channels/{CHANNEL_ID}/feeds.json"
    if CHANNEL_ID
    else ""
)

INTERVALO_SEGUNDOS = 16
LIMITE_TEMPERATURA_PADRAO = 70.0
LIMITE_VIBRACAO_PADRAO = 7.0


# ------------------------------------------------------------
# 2. ESTILO VISUAL
# ------------------------------------------------------------
st.markdown(
    """
    <style>
      /* Fundo e cor principal do painel */
      .stApp {
        background: #0b1220;
        color: #ffffff !important;
      }
      [data-testid="stHeader"] { background: rgba(11, 18, 32, 0.88); }
      [data-testid="stSidebar"] { background: #111c2e; }
      .block-container { padding-top: 1.7rem; padding-bottom: 2.5rem; }

      /* Textos que antes apareciam em cinza: agora ficam brancos */
      .stApp p,
      .stApp span,
      .stApp label,
      .stApp small,
      .stApp li,
      .stApp [data-testid="stCaptionContainer"],
      .stApp [data-testid="stCaptionContainer"] p,
      .stApp [data-testid="stCaptionContainer"] span,
      .stApp [data-testid="stWidgetLabel"],
      .stApp [data-testid="stWidgetLabel"] p,
      .stApp [data-testid="stMarkdownContainer"] p,
      .stApp [data-testid="stMarkdownContainer"] span,
      [data-testid="stSidebar"] p,
      [data-testid="stSidebar"] span,
      [data-testid="stSidebar"] label,
      [data-testid="stSidebar"] small {
        color: #ffffff !important;
      }

      /* Cabeçalho */
      .hero {
        padding: 1.25rem 1.5rem;
        border: 1px solid rgba(148, 163, 184, .18);
        border-radius: 16px;
        background: linear-gradient(120deg, #14243b 0%, #102d3c 100%);
        margin-bottom: 1rem;
      }
      .hero-kicker {
        color: #67e8f9 !important;
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .hero-title {
        color: #ffffff !important;
        font-size: 2rem;
        font-weight: 800;
        margin: .25rem 0;
      }
      .hero-subtitle { color: #ffffff !important; margin: 0; }

      /* Indicadores */
      div[data-testid="stMetric"] {
        background: #142136;
        border: 1px solid rgba(148, 163, 184, .16);
        padding: 14px 16px;
        border-radius: 13px;
      }
      div[data-testid="stMetricLabel"],
      div[data-testid="stMetricLabel"] p,
      div[data-testid="stMetricLabel"] label {
        color: #ffffff !important;
      }
      div[data-testid="stMetricValue"] { color: #ffffff !important; }
      .small-note { color: #ffffff !important; font-size: .82rem; }
      h1, h2, h3, h4, h5, h6 { color: #ffffff !important; }

      /* Texto dos campos e controles */
      .stTextInput input,
      .stNumberInput input,
      .stSelectbox div,
      .stMultiSelect div {
        color: #ffffff !important;
      }

      /* Legendas e rótulos dos gráficos */
      .stApp svg text { fill: #ffffff !important; }

      /* Texto das tabelas */
      [data-testid="stDataFrame"],
      [data-testid="stDataFrame"] * {
        color: #ffffff !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# 3. FUNCOES DE NEGOCIO
# ------------------------------------------------------------
def gerar_dados():
    """Gera dados ficticios para simular sensores de uma maquina."""
    estado = 1 if random.random() < 0.95 else 0

    if estado == 1:
        temperatura = random.uniform(48, 65)
        vibracao = random.uniform(1, 5.5)

        # Simula anormalidades ocasionais para testar os alertas.
        if random.random() < 0.12:
            temperatura = random.uniform(71, 78)
        if random.random() < 0.12:
            vibracao = random.uniform(7.2, 9.0)
    else:
        temperatura = random.uniform(35, 45)
        vibracao = random.uniform(0, 0.5)

    return round(temperatura, 2), round(vibracao, 2), estado


def analisar_maquina(temperatura, vibracao, estado, limite_temp, limite_vib):
    alertas = []
    if estado == 0:
        alertas.append("Máquina desligada")
    if temperatura > limite_temp:
        alertas.append("Temperatura acima do limite")
    if vibracao > limite_vib:
        alertas.append("Vibração acima do limite")

    if alertas:
        return "ALERTA", alertas
    return "NORMAL", []


def enviar_dados_get(temperatura, vibracao, estado):
    """Envia dados ao ThingSpeak usando HTTP GET, conforme a atividade."""
    if not WRITE_KEY:
        raise RuntimeError("Write API Key não configurada no arquivo .env.")

    parametros = {
        "api_key": WRITE_KEY,
        "field1": temperatura,
        "field2": vibracao,
        "field3": estado,
    }

    resposta = requests.get(URL_ENVIO, params=parametros, timeout=15)
    resposta.raise_for_status()

    try:
        resultado = resposta.json()
    except ValueError as exc:
        raise RuntimeError(f"Resposta inesperada do ThingSpeak: {resposta.text!r}") from exc

    if not isinstance(resultado, dict) or not resultado.get("entry_id"):
        raise RuntimeError(
            "O ThingSpeak não confirmou o registro. Resposta recebida: "
            f"{resposta.text!r}. Confira a Write API Key e o intervalo de 15 segundos."
        )

    return resultado


def consultar_historico_get(quantidade=100):
    """Consulta os registros do canal usando HTTP GET e retorna um DataFrame."""
    if not CHANNEL_ID or not READ_KEY:
        raise RuntimeError("Channel ID ou Read API Key não configurado no arquivo .env.")

    parametros = {"api_key": READ_KEY, "results": quantidade}
    resposta = requests.get(URL_LEITURA, params=parametros, timeout=15)
    resposta.raise_for_status()
    dados = resposta.json()

    registros = dados.get("feeds", [])
    if not registros:
        return pd.DataFrame(
            columns=["Data/hora", "Temperatura (°C)", "Vibração (mm/s)", "Estado", "Registro"]
        )

    df = pd.DataFrame(registros)
    df = df.rename(
        columns={
            "created_at": "Data/hora",
            "field1": "Temperatura (°C)",
            "field2": "Vibração (mm/s)",
            "field3": "Estado",
            "entry_id": "Registro",
        }
    )

    for coluna in ["Temperatura (°C)", "Vibração (mm/s)", "Estado", "Registro"]:
        if coluna in df.columns:
            df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    if "Data/hora" in df.columns:
        df["Data/hora"] = pd.to_datetime(df["Data/hora"], errors="coerce", utc=True)
        df["Data/hora"] = df["Data/hora"].dt.tz_convert("America/Sao_Paulo")

    colunas = ["Data/hora", "Temperatura (°C)", "Vibração (mm/s)", "Estado", "Registro"]
    return df[[c for c in colunas if c in df.columns]].sort_values("Data/hora")


def registrar_ciclo(limite_temp, limite_vib):
    """Gera uma leitura, analisa e envia ao ThingSpeak."""
    temperatura, vibracao, estado = gerar_dados()
    status, alertas = analisar_maquina(
        temperatura, vibracao, estado, limite_temp, limite_vib
    )
    resultado = enviar_dados_get(temperatura, vibracao, estado)

    leitura = {
        "momento": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "temperatura": temperatura,
        "vibracao": vibracao,
        "estado": estado,
        "status": status,
        "alertas": alertas,
        "entry_id": resultado.get("entry_id"),
    }
    return leitura


# ------------------------------------------------------------
# 4. ESTADO DA SESSAO
# ------------------------------------------------------------
valores_iniciais = {
    "monitorando": False,
    "ultima_leitura": None,
    "historico": pd.DataFrame(),
    "mensagem": None,
    "tipo_mensagem": "info",
    "logs": [],
    "ultimo_tick": 0,
    "ultima_consulta": None,
}

for chave, valor in valores_iniciais.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

# O componente agenda uma nova execucao da pagina a cada 16 segundos.
# A leitura so e enviada quando o contador muda e o modo automatico esta ativo.
tick = st_autorefresh(interval=INTERVALO_SEGUNDOS * 1000, key="atualizacao_automatica")


# ------------------------------------------------------------
# 5. CABECALHO E BARRA LATERAL
# ------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">INDÚSTRIA 4.0 · INTERNET DAS COISAS</div>
      <div class="hero-title">Painel de Monitoramento Industrial</div>
      <p class="hero-subtitle">Acompanhamento de temperatura, vibração e estado de uma máquina via API ThingSpeak.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## ⚙️ Controle do sistema")
    st.caption(f"Canal ThingSpeak: {CHANNEL_ID or 'Não configurado'}")

    credenciais_ok = bool(CHANNEL_ID and WRITE_KEY and READ_KEY)
    if credenciais_ok:
        st.success("Credenciais carregadas")
    else:
        st.error("Configure o arquivo .env")
        st.code(
            "THINGSPEAK_CHANNEL_ID=...\n"
            "THINGSPEAK_WRITE_KEY=...\n"
            "THINGSPEAK_READ_KEY=...",
            language="text",
        )

    st.markdown("---")
    st.markdown("### Limites de alerta")
    limite_temp = st.number_input(
        "Temperatura máxima (°C)", min_value=1.0, max_value=200.0,
        value=LIMITE_TEMPERATURA_PADRAO, step=1.0
    )
    limite_vib = st.number_input(
        "Vibração máxima (mm/s)", min_value=0.1, max_value=100.0,
        value=LIMITE_VIBRACAO_PADRAO, step=0.5
    )

    st.markdown("---")
    st.markdown("### Operação")
    if st.session_state.monitorando:
        st.success("Monitoramento automático ativo")
    else:
        st.info("Monitoramento automático pausado")

    iniciar = st.button(
        "▶ Iniciar automático", use_container_width=True,
        disabled=(not credenciais_ok or st.session_state.monitorando)
    )
    pausar = st.button(
        "⏸ Pausar", use_container_width=True,
        disabled=not st.session_state.monitorando
    )
    enviar_agora = st.button(
        "＋ Gerar e enviar agora", use_container_width=True,
        disabled=not credenciais_ok
    )
    atualizar = st.button(
        "↻ Atualizar histórico", use_container_width=True,
        disabled=(not CHANNEL_ID or not READ_KEY)
    )

    st.markdown("---")
    st.caption(f"Intervalo automático: {INTERVALO_SEGUNDOS} segundos")
    st.caption("Envio: GET · Consulta: GET")


# ------------------------------------------------------------
# 6. ACOES DOS BOTOES E CICLO AUTOMATICO
# ------------------------------------------------------------
if iniciar:
    st.session_state.monitorando = True
    st.session_state.ultimo_tick = tick
    st.session_state.mensagem = "Monitoramento automático iniciado. A primeira leitura será enviada no próximo ciclo."
    st.session_state.tipo_mensagem = "success"

if pausar:
    st.session_state.monitorando = False
    st.session_state.mensagem = "Monitoramento automático pausado."
    st.session_state.tipo_mensagem = "info"

ciclo_automatico = st.session_state.monitorando and tick != st.session_state.ultimo_tick
if ciclo_automatico:
    st.session_state.ultimo_tick = tick

if enviar_agora or ciclo_automatico:
    try:
        leitura = registrar_ciclo(limite_temp, limite_vib)
        st.session_state.ultima_leitura = leitura
        st.session_state.logs.insert(0, leitura)
        st.session_state.logs = st.session_state.logs[:20]
        st.session_state.mensagem = (
            f"Medição enviada ao ThingSpeak. Registro #{leitura['entry_id']}."
        )
        st.session_state.tipo_mensagem = "success"

        # Atualiza o histórico logo após uma escrita bem-sucedida.
        st.session_state.historico = consultar_historico_get(100)
        st.session_state.ultima_consulta = datetime.now().strftime("%H:%M:%S")

    except requests.exceptions.RequestException as erro:
        st.session_state.mensagem = f"Falha de comunicação com o ThingSpeak: {erro}"
        st.session_state.tipo_mensagem = "error"
    except Exception as erro:
        st.session_state.mensagem = str(erro)
        st.session_state.tipo_mensagem = "error"

if atualizar:
    try:
        st.session_state.historico = consultar_historico_get(100)
        st.session_state.ultima_consulta = datetime.now().strftime("%H:%M:%S")
        st.session_state.mensagem = "Histórico atualizado com sucesso."
        st.session_state.tipo_mensagem = "success"
    except Exception as erro:
        st.session_state.mensagem = f"Não foi possível consultar o histórico: {erro}"
        st.session_state.tipo_mensagem = "error"


# ------------------------------------------------------------
# 7. MENSAGENS DE STATUS
# ------------------------------------------------------------
if st.session_state.mensagem:
    tipo = st.session_state.tipo_mensagem
    if tipo == "success":
        st.success(st.session_state.mensagem)
    elif tipo == "error":
        st.error(st.session_state.mensagem)
    elif tipo == "warning":
        st.warning(st.session_state.mensagem)
    else:
        st.info(st.session_state.mensagem)


# ------------------------------------------------------------
# 8. INDICADORES PRINCIPAIS
# ------------------------------------------------------------
ultima = st.session_state.ultima_leitura

st.subheader("Visão geral da máquina")
col1, col2, col3, col4 = st.columns(4)

if ultima:
    col1.metric("Temperatura", f"{ultima['temperatura']:.2f} °C")
    col2.metric("Vibração", f"{ultima['vibracao']:.2f} mm/s")
    col3.metric("Estado", "Ligada" if ultima["estado"] == 1 else "Desligada")
    col4.metric("Condição", ultima["status"])
else:
    col1.metric("Temperatura", "—")
    col2.metric("Vibração", "—")
    col3.metric("Estado", "Aguardando")
    col4.metric("Condição", "Sem leitura")
    st.info("Inicie o modo automático ou clique em 'Gerar e enviar agora' para registrar a primeira medição.")

if ultima:
    if ultima["alertas"]:
        st.warning(" | ".join(ultima["alertas"]))
    else:
        st.success("Nenhuma condição de alerta identificada na última leitura.")
    st.caption(f"Última medição local: {ultima['momento']} · Registro ThingSpeak: {ultima['entry_id']}")


# ------------------------------------------------------------
# 9. GRAFICOS E HISTORICO
# ------------------------------------------------------------
st.markdown("---")
st.subheader("Histórico de medições")

historico = st.session_state.historico
if not historico.empty:
    graf1, graf2 = st.columns(2)
    with graf1:
        st.markdown("#### Temperatura")
        serie_temp = historico.dropna(subset=["Temperatura (°C)"]).set_index("Data/hora")[["Temperatura (°C)"]]
        st.line_chart(serie_temp, height=260)
    with graf2:
        st.markdown("#### Vibração")
        serie_vib = historico.dropna(subset=["Vibração (mm/s)"]).set_index("Data/hora")[["Vibração (mm/s)"]]
        st.line_chart(serie_vib, height=260)

    st.markdown("#### Registros recebidos do ThingSpeak")
    tabela = historico.copy()
    if "Estado" in tabela.columns:
        tabela["Estado"] = tabela["Estado"].map({1: "Ligada", 0: "Desligada"}).fillna("Sem informação")
    st.dataframe(tabela.sort_values("Data/hora", ascending=False), use_container_width=True, hide_index=True)
    if st.session_state.ultima_consulta:
        st.caption(f"Última consulta à API: {st.session_state.ultima_consulta}")
else:
    st.info("Ainda não há histórico carregado. Envie uma medição ou clique em 'Atualizar histórico'.")


# ------------------------------------------------------------
# 10. LOG DAS ULTIMAS EXECUCOES DA SESSAO
# ------------------------------------------------------------
st.markdown("---")
st.subheader("Eventos desta sessão")
if st.session_state.logs:
    logs_df = pd.DataFrame(st.session_state.logs)
    logs_df = logs_df.rename(
        columns={
            "momento": "Horário",
            "temperatura": "Temperatura (°C)",
            "vibracao": "Vibração (mm/s)",
            "estado": "Estado numérico",
            "status": "Condição",
            "entry_id": "Registro ThingSpeak",
        }
    )
    st.dataframe(
        logs_df[["Horário", "Temperatura (°C)", "Vibração (mm/s)", "Estado numérico", "Condição", "Registro ThingSpeak"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.caption("Os eventos gerados durante esta sessão aparecerão aqui.")

st.markdown("---")
st.markdown(
    '<p class="small-note">Projeto didático: as medições são simuladas. Os limites são exemplos e não substituem parâmetros técnicos do fabricante. '
    'Nesta atividade, o envio e a consulta à API são realizados com HTTP GET.</p>',
    unsafe_allow_html=True,
)
