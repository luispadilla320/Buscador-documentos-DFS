import os, re, csv, json, requests, fitz
from pathlib import Path

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUSQUEDA_INICIAL = "CAMPOS BUCHELLY"

TERMINOS_OCR = [
    ""
]

RESULTADOS_POR_PAGINA = 100
CARPETA_SALIDA = "resultados"

# =====================================================
# FUNCIONES
# =====================================================

def descargar_pdf(id_ficha, destino):
    url = f"https://repositorio.agn.gob.mx/api/resources/ficha/{id_ficha}"
    try:
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        with open(destino, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Error descargando {id_ficha}: {e}")
        return False

def extraer_texto_pdf(pdf_path):
    texto = ""
    try:
        with fitz.open(pdf_path) as pdf:
            for pagina in pdf:
                texto += pagina.get_text()
    except Exception as e:
        print(f"Error leyendo PDF {pdf_path}: {e}")
    return texto

def buscar_terminos(texto, terminos):
    encontrados = []
    texto_lower = texto.lower()
    for termino in terminos:
        if termino.lower() in texto_lower:
            encontrados.append(termino)
    return encontrados


def extraer_contextos(texto, termino, ventana=250):
    contextos = []
    patron = re.compile(
        re.escape(termino),
        re.IGNORECASE
    )
    for match in patron.finditer(texto):
        inicio = max(0, match.start() - ventana)
        fin = min(len(texto), match.end() + ventana)
        contextos.append(
            texto[inicio:fin].replace("\n", " ")
        )
    return contextos

def obtener_resultados_busqueda(texto_busqueda):
    pagina = 1
    resultados = []
    while True:
        print(f"Consultando página {pagina}")
        url = "https://repositorio.agn.gob.mx/api/search"
        params = {
            "_clases": "FI",
            "_limit": RESULTADOS_POR_PAGINA,
            "_searchAllWords": texto_busqueda,
            "_page": pagina,
            "_fields": ""
        }

        response = requests.get(
            url,
            params=params,
            timeout=60
        )

        response.raise_for_status()
        data = response.json()
        fichas = data.get(
            "descripcionesDocumentales",
            []
        )

        if not fichas:
            break
        resultados.extend(fichas)
        print(
            f"Página {pagina}: "
            f"{len(fichas)} resultados"
        )
        pagina += 1
    return resultados



def main():
    Path(CARPETA_SALIDA).mkdir(
        exist_ok=True
    )
    csv_path = os.path.join(
        CARPETA_SALIDA,
        "matches.csv"
    )

    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "idFicha",
            "titulo",
            "termino"
        ])

        fichas = obtener_resultados_busqueda(
            BUSQUEDA_INICIAL
        )

        print(
            f"\nTotal de fichas encontradas: "
            f"{len(fichas)}"
        )

        for ficha in fichas:
            try:
                id_ficha = str(
                    ficha["idFicha"]
                )
                titulo = ficha.get(
                    "titulo",
                    ""
                )
                print(
                    f"\nProcesando ficha "
                    f"{id_ficha}"
                )
                temp_pdf = (
                    f"temp_{id_ficha}.pdf"
                )
                descargado = descargar_pdf(
                    id_ficha,
                    temp_pdf
                )
                if not descargado:
                    continue
                texto = extraer_texto_pdf(
                    temp_pdf
                )
                encontrados = buscar_terminos(
                    texto,
                    TERMINOS_OCR
                )
                if not encontrados:

                    os.remove(temp_pdf)

                    print(
                        "Sin coincidencias"
                    )

                    continue
                pdf_final = os.path.join(
                    CARPETA_SALIDA,
                    f"{id_ficha}.pdf"
                )
                os.replace(
                    temp_pdf,
                    pdf_final
                )
                contextos = {}

                for termino in encontrados:
                    contextos[
                        termino
                    ] = extraer_contextos(
                        texto,
                        termino
                    )
                    writer.writerow([
                        id_ficha,
                        titulo,
                        termino
                    ])
                metadata = ficha.copy()
                metadata[
                    "archivo_pdf"
                ] = f"{id_ficha}.pdf"
                metadata[
                    "terminos_encontrados"
                ] = encontrados
                metadata[
                    "contextos"
                ] = contextos
                json_path = os.path.join(
                    CARPETA_SALIDA,
                    f"{id_ficha}.json"
                )
                with open(
                    json_path,
                    "w",
                    encoding="utf-8"
                ) as f:
                    json.dump(
                        metadata,
                        f,
                        indent=4,
                        ensure_ascii=False
                    )
                print(
                    f"✓ MATCH: "
                    f"{', '.join(encontrados)}"
                )

            except Exception as e:
                print(
                    f"Error procesando "
                    f"{id_ficha}: {e}"
                )
                if os.path.exists(
                    temp_pdf
                ):
                    os.remove(temp_pdf)


if __name__ == "__main__":
    main()