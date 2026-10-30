import os
import time
import random
import requests

from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID")
WRITE_KEY = os.getenv("THINGSPEAK_WRITE_KEY")
READ_KEY = os.getenv("THINGSPEAK_READ_KEY")

URL_ENVIO = "https://api.thingspeak.com/update.json"

URL_LEITURA = (
    f"https://api.thingspeak.com/channels/"
    f"{CHANNEL_ID}/feeds.json"
)

INTERVALO = 16

LIMITE_TEMPERATURA = 70.0
LIMITE_VIBRACAO = 7.0


def gerar_dados():

    # 95% de chance de a maquina estar ligada
    estado = 1 if random.random() < 0.95 else 0

    if estado == 1:

        temperatura = random.uniform(48, 65)
        vibracao = random.uniform(1, 5.5)

        # Simular ocasionalmente anormalidades
        if random.random() < 0.12:
            temperatura = random.uniform(71, 78)

        if random.random() < 0.12:
            vibracao = random.uniform(7.2, 9)

    else:

        temperatura = random.uniform(35, 45)
        vibracao = random.uniform(0, 0.5)

    return (
        round(temperatura, 2),
        round(vibracao, 2),
        estado
    )


def analisar_maquina(temperatura, vibracao, estado):

    alertas = []

    if estado == 0:
        alertas.append("MAQUINA DESLIGADA")

    if temperatura > LIMITE_TEMPERATURA:
        alertas.append("TEMPERATURA ELEVADA")

    if vibracao > LIMITE_VIBRACAO:
        alertas.append("VIBRACAO ELEVADA")

    if alertas:
        print("\n!!! ALERTA INDUSTRIAL !!!")

        for alerta in alertas:
            print("-", alerta)

    else:
        print("\nSTATUS: Funcionamento normal")


def enviar_dados(temperatura, vibracao, estado):

    parametros = {

        "api_key": WRITE_KEY,

        "field1": temperatura,

        "field2": vibracao,

        "field3": estado

    }

    resposta = requests.get(
        URL_ENVIO,
        params=parametros,
        timeout=15
    )

    if resposta.status_code != 200:

        print("Erro HTTP no envio:", resposta.status_code)
        print("Resposta:", resposta.text)

        return False

    try:
        resultado = resposta.json()

    except ValueError:
        print("Resposta inesperada:", resposta.text)
        return False

    if not isinstance(resultado, dict):

        print("ThingSpeak nao confirmou o registro.")
        return False

    entry_id = resultado.get("entry_id")

    if entry_id:

        print("\nENVIO REALIZADO COM SUCESSO!")
        print("ID do registro:", entry_id)

        return True

    print("Falha ao registrar os dados.")
    print("Resposta:", resultado)

    return False


def consultar_dados():

    parametros = {

        "api_key": READ_KEY,

        "results": 5

    }

    resposta = requests.get(
        URL_LEITURA,
        params=parametros,
        timeout=15
    )

    resposta.raise_for_status()

    dados = resposta.json()

    registros = dados.get("feeds", [])

    print("\n========== HISTORICO DA MAQUINA ==========")

    if not registros:

        print("Nenhum registro encontrado.")

        return

    for registro in registros:

        print("\nRegistro:", registro.get("entry_id"))

        print(
            "Data:",
            registro.get("created_at")
        )

        print(
            "Temperatura:",
            registro.get("field1"),
            "°C"
        )

        print(
            "Vibracao:",
            registro.get("field2"),
            "mm/s"
        )

        print(
            "Estado:",
            "Ligada" if registro.get("field3") == "1"
            else "Desligada"
        )


def iniciar_monitoramento():

    print("========================================")
    print("     MONITORAMENTO INDUSTRIAL")
    print("========================================")

    while True:

        try:

            print("\nGERANDO NOVA LEITURA...")

            # Gerar valores automaticamente
            temperatura, vibracao, estado = gerar_dados()

            print("\n========== SENSORES ==========")

            print(f"Temperatura: {temperatura} °C")

            print(f"Vibracao: {vibracao} mm/s")

            print(
                "Estado:",
                "Ligada" if estado == 1 else "Desligada"
            )

            # Analisar os valores
            analisar_maquina(
                temperatura,
                vibracao,
                estado
            )

            # Enviar os valores utilizando GET
            enviado = enviar_dados(
                temperatura,
                vibracao,
                estado
            )

            # Consultar historico utilizando GET
            if enviado:

                consultar_dados()

            else:

                print("\nConsulta do historico nao realizada.")

            print("\nProxima leitura em 16 segundos...")

            time.sleep(INTERVALO)

        except requests.exceptions.RequestException as erro:

            print("\nErro de comunicacao:", erro)

            print("Nova tentativa em 16 segundos...")

            time.sleep(INTERVALO)


if __name__ == "__main__":

    if not all([CHANNEL_ID, WRITE_KEY, READ_KEY]):

        print("ERRO: Verifique as configuracoes do arquivo .env")

    else:

        try:

            iniciar_monitoramento()

        except KeyboardInterrupt:

            print("\nMonitoramento encerrado pelo usuario.")