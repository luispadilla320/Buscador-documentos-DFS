import os, re, csv, json, requests, fitz
from pathlib import Path

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUSQUEDA_INICIAL = "Huautla de Jimenez"

TERMINOS_OCR = [
    "Fernando Macias",
    "hippie",
    "hippies"
]

# Opciones:
# "agn"
# "paddle"

OCR_MODE = "paddle"

RESULTADOS_POR_PAGINA = 100

CARPETA_SALIDA = "resultados_agn"

# =====================================================
# INICIALIZAR OCR
# =====================================================

ocr_engine = None

if OCR_MODE == "paddle":

    print("Inicializando PaddleOCR...")
    from pdf2image import convert_from_path
    from paddleocr import PaddleOCR
    ocr_engine = PaddleOCR(
        lang="es"
    )

# =====================================================
# UTILIDADES
# =====================================================

def descargar_pdf(id_ficha, destino):
    url = (
        f"https://repositorio.agn.gob.mx/"
        f"api/resources/ficha/{id_ficha}"
    )
    try:
        response = requests.get(
            url,
            timeout=120
        )
        response.raise_for_status()
        with open(destino, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(
            f"Error descargando "
            f"{id_ficha}: {e}"
        )
        return False


# =====================================================
# OCR AGN
# =====================================================

def extraer_texto_agn(pdf_path):
    texto = ""
    try:
        with fitz.open(pdf_path) as pdf:
            for pagina in pdf:
                texto += pagina.get_text()
    except Exception as e:
        print(
            f"Error OCR AGN: {e}"
        )
    return texto


# =====================================================
# OCR PADDLE
# =====================================================

def extraer_texto_paddle(pdf_path):
    texto = ""
    try:
        paginas = convert_from_path(
            pdf_path,
            dpi=300
        )
        for pagina in paginas:
            resultado = ocr_engine.predict(
                pagina
            )
            if not resultado:
                continue
            for bloque in resultado:
                if (
                    isinstance(bloque, dict)
                    and "rec_texts" in bloque
                ):
                    texto += "\n".join(
                        bloque["rec_texts"]
                    )
                    texto += "\n"

    except Exception as e:
        print(
            f"Error OCR Paddle: {e}"
        )
    return texto


# =====================================================
# OCR UNIFICADO
# =====================================================

def extraer_texto(pdf_path):
    if OCR_MODE == "agn":
        return extraer_texto_agn(
            pdf_path
        )
    if OCR_MODE == "paddle":
        return extraer_texto_paddle(
            pdf_path
        )
    raise ValueError(
        "OCR_MODE inválido"
    )


# =====================================================
# BÚSQUEDA LOCAL
# =====================================================

def buscar_terminos(
    texto,
    terminos
):
    encontrados = []
    texto_lower = texto.lower()
    for termino in terminos:
        if termino.lower() in texto_lower:
            encontrados.append(
                termino
            )
    return encontrados


# =====================================================
# CONTEXTOS
# =====================================================

def extraer_contextos(
    texto,
    termino,
    ventana=300
):

    contextos = []
    patron = re.compile(
        re.escape(termino),
        re.IGNORECASE
    )
    for match in patron.finditer(
        texto
    ):
        inicio = max(
            0,
            match.start() - ventana
        )
        fin = min(
            len(texto),
            match.end() + ventana
        )
        fragmento = texto[
            inicio:fin
        ]
        fragmento = fragmento.replace(
            "\n",
            " "
        )
        contextos.append(
            fragmento
        )
    return contextos


# =====================================================
# CONSULTAR API
# =====================================================

def obtener_resultados_busqueda():
    pagina = 1
    resultados = []
    while True:
        print(
            f"Consultando página "
            f"{pagina}"
        )
        url = (
            "https://repositorio.agn.gob.mx/"
            "api/search"
        )
        params = {
            "_clases": "FI",
            "_limit": RESULTADOS_POR_PAGINA,
            "_searchAllWords": BUSQUEDA_INICIAL,
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
        resultados.extend(
            fichas
        )
        print(
            f"Página {pagina}: "
            f"{len(fichas)} fichas"
        )
        pagina += 1
    return resultados


# =====================================================
# MAIN
# =====================================================

def main():

    Path(
        CARPETA_SALIDA
    ).mkdir(
        exist_ok=True
    )

    matches_csv = os.path.join(
        CARPETA_SALIDA,
        "matches.csv"
    )

    with open(
        matches_csv,
        "w",
        newline="",
        encoding="utf-8"
    ) as csvfile:

        writer = csv.writer(
            csvfile
        )

        writer.writerow(
            [
                "idFicha",
                "titulo",
                "termino"
            ]
        )

        fichas = (
            obtener_resultados_busqueda()
        )

        print(
            f"\nTotal fichas: "
            f"{len(fichas)}"
        )

        for ficha in fichas:

            id_ficha = str(
                ficha["idFicha"]
            )

            titulo = ficha.get(
                "titulo",
                ""
            )

            temp_pdf = (
                f"temp_{id_ficha}.pdf"
            )

            try:

                print(
                    f"\nProcesando "
                    f"{id_ficha}"
                )

                ok = descargar_pdf(
                    id_ficha,
                    temp_pdf
                )

                if not ok:
                    continue

                texto = extraer_texto(
                    temp_pdf
                )

                encontrados = (
                    buscar_terminos(
                        texto,
                        TERMINOS_OCR
                    )
                )

                if not encontrados:

                    os.remove(
                        temp_pdf
                    )

                    print(
                        "Sin coincidencias"
                    )

                    continue

                pdf_final = (
                    os.path.join(
                        CARPETA_SALIDA,
                        f"{id_ficha}.pdf"
                    )
                )

                os.replace(
                    temp_pdf,
                    pdf_final
                )

                metadata = (
                    ficha.copy()
                )

                metadata[
                    "ocr_mode"
                ] = OCR_MODE

                metadata[
                    "archivo_pdf"
                ] = (
                    f"{id_ficha}.pdf"
                )

                metadata[
                    "terminos_encontrados"
                ] = encontrados

                contextos = {}

                for termino in encontrados:

                    contextos[
                        termino
                    ] = (
                        extraer_contextos(
                            texto,
                            termino
                        )
                    )

                    writer.writerow(
                        [
                            id_ficha,
                            titulo,
                            termino
                        ]
                    )

                metadata[
                    "contextos"
                ] = contextos

                metadata_path = (
                    os.path.join(
                        CARPETA_SALIDA,
                        f"{id_ficha}.json"
                    )
                )

                with open(
                    metadata_path,
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
                    "MATCH -> "
                    + ", ".join(
                        encontrados
                    )
                )

            except Exception as e:

                print(
                    f"Error en "
                    f"{id_ficha}: {e}"
                )

            finally:

                if os.path.exists(
                    temp_pdf
                ):
                    try:
                        os.remove(
                            temp_pdf
                        )
                    except:
                        pass

    print(
        "\nProceso finalizado."
    )


if __name__ == "__main__":
    main()