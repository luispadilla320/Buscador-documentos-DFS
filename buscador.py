import os, re, csv, json, fitz, requests
import numpy as np

from pathlib import Path
from pdf2image import convert_from_path
from paddleocr import PaddleOCR

# =====================================================
# CONFIGURACIÓN
# =====================================================

BUSQUEDA_INICIAL = "hippie"

TERMINOS_OCR = [
    "Huautla"
]

# pot:
# "agn"    
# "paddle"
OCR_MODE = "agn"

RESULTADOS_POR_PAGINA = 100

CARPETA_SALIDA = "resultados_agn"

# =====================================================
# OCR
# =====================================================

ocr_engine = None

if OCR_MODE == "paddle":

    print("Inicializando PaddleOCR...")

    ocr_engine = PaddleOCR(
        lang="es",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False
    )

# =====================================================
# DESCARGA PDF
# =====================================================

def descargar_pdf(id_ficha, destino):

    url = (
        f"https://repositorio.agn.gob.mx/"
        f"api/resources/ficha/{id_ficha}"
    )

    response = requests.get(
        url,
        timeout=120
    )

    response.raise_for_status()

    with open(destino, "wb") as f:
        f.write(response.content)

# =====================================================
# OCR AGN
# =====================================================

def extraer_texto_agn(pdf_path):

    texto = ""

    with fitz.open(pdf_path) as pdf:

        for pagina in pdf:

            texto += pagina.get_text()
            texto += "\n"

    return texto

# =====================================================
# OCR PADDLE
# =====================================================

def extraer_texto_paddle(pdf_path):

    texto = ""

    paginas = convert_from_path(
        pdf_path,
        dpi=300
    )

    total = len(paginas)

    for indice, pagina in enumerate(paginas):

        print(
            f"   OCR página "
            f"{indice + 1}/{total}"
        )

        imagen = np.array(pagina)

        try:

            resultado = ocr_engine.predict(
                imagen
            )

            if not resultado:
                continue

            for item in resultado:

                if isinstance(item, dict):

                    textos = item.get(
                        "rec_texts",
                        []
                    )

                    if textos:

                        texto += "\n".join(
                            textos
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

    return extraer_texto_paddle(
        pdf_path
    )

# =====================================================
# BÚSQUEDA DE TÉRMINOS
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
# BÚSQUEDA EN API AGN
# =====================================================

def obtener_fichas():

    resultados = []

    pagina = 1

    while True:

        print(
            f"Consultando página "
            f"{pagina}"
        )

        response = requests.get(
            "https://repositorio.agn.gob.mx/api/search",
            params={
                "_clases": "FI",
                "_limit": RESULTADOS_POR_PAGINA,
                "_searchAllWords": BUSQUEDA_INICIAL,
                "_page": pagina,
                "_fields": ""
            },
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

        fichas = obtener_fichas()

        print(
            f"\nTotal fichas: "
            f"{len(fichas)}"
        )

        for ficha in fichas:

            id_ficha = str(
                ficha[
                    "idFicha"
                ]
            )

            titulo = ficha.get(
                "titulo",
                ""
            )

            temp_pdf = (
                f"tmp_{id_ficha}.pdf"
            )

            try:

                print(
                    f"\nProcesando "
                    f"{id_ficha}"
                )

                descargar_pdf(
                    id_ficha,
                    temp_pdf
                )

                texto = extraer_texto(
                    temp_pdf
                )

                print(
                    f"OCR obtenido: "
                    f"{len(texto)} "
                    f"caracteres"
                )

                # guardar OCR para revisión
                with open(
                    os.path.join(
                        CARPETA_SALIDA,
                        f"{id_ficha}_ocr.txt"
                    ),
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(texto)

                encontrados = (
                    buscar_terminos(
                        texto,
                        TERMINOS_OCR
                    )
                )

                if not encontrados:

                    print(
                        "Sin coincidencias"
                    )

                    os.remove(
                        temp_pdf
                    )

                    continue

                pdf_destino = (
                    os.path.join(
                        CARPETA_SALIDA,
                        f"{id_ficha}.pdf"
                    )
                )

                os.replace(
                    temp_pdf,
                    pdf_destino
                )

                metadata = (
                    ficha.copy()
                )

                metadata[
                    "archivo_pdf"
                ] = (
                    f"{id_ficha}.pdf"
                )

                metadata[
                    "ocr_mode"
                ] = OCR_MODE

                metadata[
                    "terminos_encontrados"
                ] = encontrados

                contextos = {}

                for termino in encontrados:

                    writer.writerow(
                        [
                            id_ficha,
                            titulo,
                            termino
                        ]
                    )

                    contextos[
                        termino
                    ] = (
                        extraer_contextos(
                            texto,
                            termino
                        )
                    )

                metadata[
                    "contextos"
                ] = contextos

                with open(
                    os.path.join(
                        CARPETA_SALIDA,
                        f"{id_ficha}.json"
                    ),
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
                    "MATCH:",
                    ", ".join(
                        encontrados
                    )
                )

            except Exception as e:

                print(
                    f"ERROR "
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
        "\nProceso terminado."
    )

if __name__ == "__main__":
    main()