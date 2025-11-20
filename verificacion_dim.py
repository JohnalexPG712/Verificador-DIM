import pandas as pd
import pdfplumber
import re
import os
import glob
from datetime import datetime
import numpy as np
from collections import OrderedDict
from openpyxl import load_workbook
import warnings
import unicodedata

# =============================================================================
# CLASE PARA CORRECCIÓN DE NOMBRES (PRIMER SCRIPT)
# =============================================================================

class CorrectorNombres:
    """Clase simplificada para corregir nombres basada en número de letras"""
    
    def normalizar_texto(self, texto):
        """Normaliza texto removiendo todo excepto letras"""
        if not texto or texto == "NO ENCONTRADO":
            return ""
        
        # Convertir a mayúsculas y remover tildes
        texto = str(texto).upper()
        texto = ''.join(c for c in unicodedata.normalize('NFD', texto) 
                       if unicodedata.category(c) != 'Mn')
        
        # Remover TODO excepto letras (espacios, puntos, números, caracteres especiales)
        texto = re.sub(r'[^A-Z]', '', texto)
        
        return texto
    
    def comparar_por_letras(self, nombre_pdf, nombre_excel):
        """Compara dos nombres por número de letras (sin importar espacios, puntos, etc.)"""
        if not nombre_pdf or not nombre_excel:
            return False
        
        # Normalizar ambos textos (solo letras)
        pdf_normalizado = self.normalizar_texto(nombre_pdf)
        excel_normalizado = self.normalizar_texto(nombre_excel)
        
        # Comparar si tienen el mismo número de letras
        return len(pdf_normalizado) == len(excel_normalizado)
    
    def corregir_nombre(self, nombre_pdf, nombre_excel):
        """Corrige el nombre del PDF usando el Excel como referencia si coinciden en número de letras"""
        if not nombre_excel or nombre_excel == "NO ENCONTRADO":
            return nombre_pdf
        
        # Comparar por número de letras
        if self.comparar_por_letras(nombre_pdf, nombre_excel):
            return nombre_excel
        else:
            return nombre_pdf

# =============================================================================
# CLASE 1: EXTRACCIÓN DE PDFs (DIAN) - CORREGIDA (SEGUNDO SCRIPT)
# =============================================================================

class ExtractorDIANSimplificado:
    def __init__(self):
        self.CAMPOS_DI = {
            "4.": "4. Número DI",
            "55.": "55. Cod. de Bandera", 
            "58.": "58. Tasa de Cambio",
            "59.": "59. Subpartida Arancelaria",
            "62.": "62. Cod. Modalidad",
            "66.": "66. Cod. Pais de Origen",
            "70.": "70. Cod. Pais Compra",
            "71.": "71. Peso Bruto kgs.",
            "72.": "72. Peso Neto kgs.",
            "74.": "74. Número de Bultos",
            "77.": "77. Cantidad dcms.",
            "78.": "78. Valor FOB USD",
            "79.": "79. Valor Fletes USD",
            "80.": "80. Valor Seguros USD",
            "81.": "81. Valor Otros Gastos USD"
        }

        self.patrones = {
            "4. Número DI": [
                r"(?:^|\n)\s*4\s*\.?\s*N[úu]mero\s*de\s*formulario[\s\S]*?(\d{15,16})",
                r"(?:^|\n)\s*4\s*\.?\s*N[úu]mero\s*de\s*formulario[\s\S]*?([\d\-]{15})",
                r"4\s*\.?\s*N[úu]mero\s*de\s*formulario\s*[:\-]?\s*(\d{17}(?:-\d)?)"
            ],
            "55. Cod. de Bandera": [
                r"55\s*\.\s*?C[oó]digo\s*de.*?\n(?:\s*\d+\s+){2}(\d+)"
            ],
            "58. Tasa de Cambio": [
                r"58\s*\.?\s*Tasa\s*de\s*cambio\b(?:\s*\$?\s*cvs\.?)?[\s\S]{0,200}?([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2}))"
            ],
            "59. Subpartida Arancelaria": [
                r"59\s*\.?\s*Subpartida\s*arancelaria\s*\d+\s*\.\s*Cod\s*\.\s*\d+\s*\.\s*Cod\s*\.\s*\d+\s*\.\s*Cod\s*\.\s*Modalidad\s*\d+\s*\.\s*No\s*\.\s*cuotas\s*\d+\s*\.\s*Valor\s*cuota\s*USD\s*\d+\s*\.\s*Periodicidad\s*del\s*\d+\s*\.\s*Cod\s*\.\s*país\s*\d+\s*\.\s*Cod\s*\.\s*Acuerdo\s*([\d]{10})"
            ],
            "62. Cod. Modalidad": [
                r"62\s*\.?\s*Cod\s*\.\s*Modalidad\s*(?:(?:.*?\n)|(?:(?:[:;.\-]|\s)+))[^\n]*?\b([A-Z]\d{3})\b" 
            ],
            "66. Cod. Pais de Origen": [
                r"66\s*\.?\s*Cod\s*\.\s*país[\s\S]*?\n.*?\n.*?\b(\d{3})\b" 
            ],
            "70. Cod. Pais Compra": [
                r"70\s*\.?\s*Cod\s*\.\s*país[\s\S]*?\n.*?\n.*?\b(\d{3})\b" 
            ],
            "71. Peso Bruto kgs.": [
                r"71\s*\.?\s*Peso\s*bruto\s*kgs\s*\.?\s*dcms\s*\.?[\s\S]{0,500}?(\d{1,3}(?:\.\d{3})*\.\d{2})"
            ],
            "72. Peso Neto kgs.": [
                r"72\s*\.?\s*Peso\s*neto\s*kgs\s*\.?\s*dcms\s*\.?[\s\S]{0,500}?\d{1,3}(?:\.\d{3})*\.\d{2}[\s\S]{0,100}?(\d{1,3}(?:\.\d{3})*\.\d{2})"
            ],
            "74. Número de Bultos": [
                r"74\s*\.\s*?\s*No\s*\.\s*bultos[\s\S]*?embalaje\s+(\d+[\.,]?\d*)",
                r"(?is)(?:embalaje[\s\S]{0,200}?\b[A-Z]{2,3}\b[\s\S]{0,50}?(\d{1,3}(?:\.\d{3})*)|embalaje[\s\S]{0,80}?(\d{1,3}(?:\.\d{3})*))"
            ],
            "77. Cantidad dcms.": [
                r"77\s*\.?\s*Cantidad\s*dcms\.[\s\S]*?comercial\s+(\d{1,4}(?:\.\d{3})*\.\d{2})"
            ],
            "78. Valor FOB USD": [
                r"78\s*\.?\s*Valor\s*FOB\s*USD[\s\S]*?\n\s*([\d.,]+)"
            ],
            "79. Valor Fletes USD": [
                r"79\s*\.?\s*Valor\s*fletes\s*USD[\s\S]*?\n\s*[\d.,]+\s+([\d.,]+)"
            ],
            "80. Valor Seguros USD": [
                r"80\s*\.?\s*Valor\s*Seguros\s*USD[\s\S]*?\n\s*([\d.,]+)"
            ],
            "81. Valor Otros Gastos USD": [
                r"81\s*\.?\s*Valor\s*Otros\s*Gastos\s*USD[\s\S]*?\n\s*[\d.,]+\s+([\d.,]+)"
            ]
        }

    def normalizar_numero_entero(self, numero_str, campo_nombre=""):
        """
        Normaliza números con tratamiento específico por tipo de campo
        """
        if not isinstance(numero_str, str) or numero_str == "NO ENCONTRADO":
            return np.nan

        # PARA MODALIDAD - TEXTO ALFANUMÉRICO (C200) - NO CONVERTIR
        if '62. Cod. Modalidad' in campo_nombre:
            return numero_str.strip()  # Devolver tal cual

        # PARA BULTOS - PERMITIR DECIMALES
        if '74. Número de Bultos' in campo_nombre:
            # Limpiar el string pero preservar decimales
            cleaned_str = numero_str.replace(',', '.')  # Convertir coma decimal a punto
            # Remover cualquier caracter no numérico excepto punto decimal
            cleaned_str = re.sub(r'[^\d.]', '', cleaned_str)
            
            try:
                valor = float(cleaned_str)
                return valor
            except ValueError:
                return np.nan

        # PRESERVAR CEROS A LA IZQUIERDA PARA CÓDIGOS DE PAÍS Y BANDERA
        if any(codigo in campo_nombre for codigo in ['55. Cod. de Bandera', '66. Cod. Pais de Origen', '70. Cod. Pais Compra']):
            # Para códigos, preservar ceros a la izquierda
            if numero_str.isdigit():
                return numero_str  # Devolver tal cual para preservar ceros
            # Si tiene formato "023 - ALEMANIA", extraer solo el código
            if ' - ' in numero_str:
                codigo = numero_str.split(' - ')[0].strip()
                if codigo.isdigit():
                    return codigo
            return numero_str

        # Para otros campos numéricos
        cleaned_str = re.sub(r'(?<=\d)\.(?=\d{3})', '', numero_str)
        cleaned_str = re.sub(r'(?<=\d),(?=\d{3})', '', cleaned_str)

        if ',' in cleaned_str and '.' not in cleaned_str:
            cleaned_str = cleaned_str.replace(',', '.')

        try:
            valor = float(cleaned_str)
            if valor.is_integer():
                return int(valor)
            return valor
        except ValueError:
            return np.nan

    def extraer_texto_pdf(self, pdf_path):
        texto_completo = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for pagina in pdf.pages:
                    texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
                    if texto:
                        texto_completo += texto + "\n\n"
            return texto_completo
        except Exception as e:
            return ""

    def extraer_campo(self, texto, patrones, campo_nombre=""):
        for patron in patrones:
            try:
                match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    if match.groups():
                        for group_val in match.groups():
                            if group_val and group_val.strip():
                                return group_val.strip()
                    else:
                        return match.group(0).strip()
            except re.error as e:
                pass
            except Exception as e:
                pass
        return "NO ENCONTRADO"

    def extraer_multiples_di_de_texto(self, texto_completo, pdf_filename):
        di_bloques = []
        
        form_number_matches = []
        for patron in self.patrones["4. Número DI"]:
            matches = list(re.finditer(patron, texto_completo, re.IGNORECASE | re.MULTILINE | re.DOTALL))
            form_number_matches.extend(matches)
        
        form_number_matches.sort(key=lambda m: m.start())
        
        if not form_number_matches:
            form_num = self.extraer_campo(texto_completo, self.patrones["4. Número DI"], "4. Número DI")
            if form_num != "NO ENCONTRADO":
                di_bloques.append({'form_number': form_num, 'text': texto_completo})
            else:
                di_bloques.append({'form_number': "Desconocido_" + pdf_filename, 'text': texto_completo})
            return di_bloques

        unique_matches = []
        last_end = -1
        for match in form_number_matches:
            if match.start() >= last_end:
                unique_matches.append(match)
                last_end = match.end()
        
        for i, match in enumerate(unique_matches):
            form_number = match.group(1).strip()
            start_index = match.start()
            
            if i + 1 < len(unique_matches):
                end_index = unique_matches[i+1].start()
            else:
                end_index = len(texto_completo)
            
            di_text_block = texto_completo[start_index:end_index]
            di_bloques.append({'form_number': form_number, 'text': di_text_block})

        return di_bloques

    def procesar_di_individual(self, di_text_block, form_number, pdf_filename):
        resultados = OrderedDict()
        resultados['Nombre Archivo PDF'] = pdf_filename
        resultados["4. Número DI"] = form_number

        for campo_dian_id, nombre_campo in self.CAMPOS_DI.items():
            if nombre_campo == "4. Número DI":
                continue 
            
            if nombre_campo in self.patrones:
                valor = self.extraer_campo(di_text_block, self.patrones[nombre_campo], nombre_campo)
                # Pasar el nombre del campo para la normalización especializada
                resultados[nombre_campo] = self.normalizar_numero_entero(valor, nombre_campo)
            else:
                resultados[nombre_campo] = "PATRON NO CONFIGURADO"
        
        return resultados

    def procesar_multiples_dis(self, folder_path):
        if not os.path.isdir(folder_path):
            return None

        all_results = []
        pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))

        if not pdf_files:
            return None

        for pdf_file_path in pdf_files:
            pdf_filename = os.path.basename(pdf_file_path)
            texto_completo_pdf = self.extraer_texto_pdf(pdf_file_path)
            if not texto_completo_pdf:
                continue

            di_bloques = self.extraer_multiples_di_de_texto(texto_completo_pdf, pdf_filename)
            
            if not di_bloques:
                continue

            for bloque in di_bloques:
                resultados_di = self.procesar_di_individual(bloque['text'], bloque['form_number'], pdf_filename)
                if resultados_di:
                    all_results.append(resultados_di)

        if all_results:
            return pd.DataFrame(all_results)
        else:
            return None

# =============================================================================
# CLASE 2: COMPARACIÓN DE DATOS - LÓGICA CORREGIDA (SEGUNDO SCRIPT)
# =============================================================================

class ComparadorDatos:
    def __init__(self):
        self.campos_comparacion_individual = {
            'pais_origen': ('66. Cod. Pais de Origen', 'PAIS ORIGEN'),
            'pais_compra': ('70. Cod. Pais Compra', 'PAIS COMPRA'), 
            'bandera': ('55. Cod. de Bandera', 'BANDERA')
        }
        
        self.campos_consistencia = {
            '58. Tasa de Cambio': '58. Tasa de Cambio',
            '62. Cod. Modalidad': '62. Cod. Modalidad',
            '74. Número de Bultos': '74. Número de Bultos'
        }
        
        self.campos_acumulables = {
            'peso_bruto': ('71. Peso Bruto kgs.', 'PESO BRUTO'),
            'peso_neto': ('72. Peso Neto kgs.', 'PESO NETO'),
            'cantidad': ('77. Cantidad dcms.', 'CANTIDAD'),
            'valor_fob': ('78. Valor FOB USD', 'VALOR FOB'),
            'valor_fletes': ('79. Valor Fletes USD', 'VALOR FLETES'),
            'valor_seguro': ('80. Valor Seguros USD', 'VALOR SEGURO'),
            'otros_gastos': ('81. Valor Otros Gastos USD', 'OTROS GASTOS')
        }
    
    def es_valor_valido(self, valor):
        """
        Determina si un valor es válido (no N/A, NO ENCONTRADO, NaN, etc.)
        """
        if pd.isna(valor) or valor in ["N/A", "NO ENCONTRADO", "", None]:
            return False
        return True
    
    def obtener_filas_validas_para_totales(self, datos_dian):
        """
        Filtra las filas que tienen valores válidos en campos críticos
        """
        if datos_dian is None or datos_dian.empty:
            return pd.DataFrame()
        
        campos_criticos = ['55. Cod. de Bandera', '66. Cod. Pais de Origen', '70. Cod. Pais Compra']
        
        # Crear máscara de filas válidas (todas las críticas deben ser válidas)
        mascara_valida = pd.Series([True] * len(datos_dian), index=datos_dian.index)
        
        for campo in campos_criticos:
            if campo in datos_dian.columns:
                mascara_campo = datos_dian[campo].apply(self.es_valor_valido)
                mascara_valida = mascara_valida & mascara_campo
        
        return datos_dian[mascara_valida]
    
    def formatear_numero_entero(self, valor, campo_nombre=""):
        """
        Formatea números con tratamiento específico por tipo de campo
        """
        if not self.es_valor_valido(valor):
            return "N/A"
        
        try:
            # PARA MODALIDAD - TEXTO ALFANUMÉRICO (C200)
            if '62. Cod. Modalidad' in campo_nombre:
                return str(valor)  # Devolver tal cual: "C200"
            
            # PARA BULTOS - PERMITIR DECIMALES SOLO CUANDO EXISTAN
            if '74. Número de Bultos' in campo_nombre:
                if isinstance(valor, (int, float)):
                    if valor.is_integer():
                        return str(int(valor))  # Entero: "5"
                    else:
                        # Mostrar decimales solo cuando sean necesarios
                        formatted = f"{valor:.6f}".rstrip('0').rstrip('.')
                        return formatted  # Decimal: "1.719" o "1.7"
                return str(valor)
            
            # Para códigos de país y bandera, preservar ceros a la izquierda
            if any(codigo in campo_nombre for codigo in ['55. Cod. de Bandera', '66. Cod. Pais de Origen', '70. Cod. Pais Compra']):
                if isinstance(valor, (int, float)):
                    # Formatear con ceros a la izquierda para códigos de 3 dígitos
                    return f"{int(valor):03d}"
                elif isinstance(valor, str) and valor.isdigit():
                    return f"{int(valor):03d}"
                else:
                    return str(valor)
            
            # Para otros campos numéricos
            if isinstance(valor, (int, float)):
                if valor.is_integer():
                    return str(int(valor))
                return f"{valor:.2f}"
            return str(valor)
        except:
            return str(valor)
    
    def extraer_numero_pais(self, valor):
        """
        Extrae solo el número del código de país PRESERVANDO CEROS A LA IZQUIERDA
        """
        if not self.es_valor_valido(valor):
            return None
        
        valor_str = str(valor).strip()
        
        # Si ya es un número con ceros a la izquierda, preservarlo
        if valor_str.isdigit():
            return valor_str  # Preservar "023", "001", etc.
        
        # Para formato "023 - ALEMANIA", extraer solo "023" preservando ceros
        if ' - ' in valor_str:
            partes = valor_str.split(' - ')
            if partes and partes[0].strip().isdigit():
                return partes[0].strip()  # Preservar ceros a la izquierda
        
        # Buscar cualquier número en el string preservando ceros
        numeros = re.findall(r'\d+', valor_str)
        if numeros:
            return numeros[0]  # Preservar ceros a la izquierda
        
        return valor_str
        
    def comparar_valor_individual_critico(self, valor_dian, valor_subpartida, campo_nombre):
        """
        Compara valores individuales CRÍTICOS con lógica estricta
        """
        # Formatear valor DIAN pasando el nombre del campo
        valor_dian_formateado = self.formatear_numero_entero(valor_dian, campo_nombre)
        
        if not self.es_valor_valido(valor_dian):
            return f"❌ {valor_dian_formateado}", False
        
        # Si no hay valor de subpartida para comparar, considerar OK
        if not self.es_valor_valido(valor_subpartida):
            return f"✅ {valor_dian_formateado}", True
        
        # Extraer solo números para comparación
        numero_dian = self.extraer_numero_pais(valor_dian)
        numero_subpartida = self.extraer_numero_pais(valor_subpartida)
        
        # Comparar los números extraídos
        if numero_dian and numero_subpartida and numero_dian == numero_subpartida:
            return f"✅ {valor_dian_formateado}", True
        else:
            return f"❌ {valor_dian_formateado}", False
    
    def verificar_consistencia_campo(self, datos_dian, campo_dian, numero_di):
        """
        Verifica consistencia de un campo en todas las DI
        """
        if campo_dian not in datos_dian.columns:
            return f"❌ NO ENCONTRADO"
        
        # Obtener valor de esta DI específica
        valor_actual = datos_dian[datos_dian["4. Número DI"] == numero_di][campo_dian].iloc[0] if not datos_dian[datos_dian["4. Número DI"] == numero_di].empty else "NO ENCONTRADO"
        
        if not self.es_valor_valido(valor_actual):
            return f"❌ N/A"
        
        # Formatear valor según el tipo de campo
        valor_actual_formateado = self.formatear_numero_entero(valor_actual, campo_dian)
        
        # Para Modalidad, verificar que sea C200
        if campo_dian == "62. Cod. Modalidad":
            if str(valor_actual).strip().upper() == "C200":
                return f"✅ {valor_actual_formateado}"
            else:
                return f"❌ {valor_actual_formateado}"
        
        # Verificar si este valor es consistente con los demás (para otros campos)
        valores_unicos = datos_dian[campo_dian].apply(self.es_valor_valido)
        valores_validos = datos_dian[valores_unicos][campo_dian].unique()
        
        if len(valores_validos) == 1:
            return f"✅ {valor_actual_formateado}"
        else:
            # Para campos como tasa de cambio, permitir variaciones menores
            if campo_dian == "58. Tasa de Cambio":
                valores_numericos = [v for v in valores_validos if isinstance(v, (int, float)) and not pd.isna(v)]
                if len(valores_numericos) > 1:
                    min_val = min(valores_numericos)
                    max_val = max(valores_numericos)
                    if (max_val - min_val) / min_val < 0.05:
                        return f"✅ {valor_actual_formateado}"
            
            # Verificar si este valor específico es el que causa inconsistencia
            valor_mas_comun = datos_dian[campo_dian].mode().iloc[0] if not datos_dian[campo_dian].mode().empty else None
            if valor_actual != valor_mas_comun:
                return f"❌ {valor_actual_formateado}"
            else:
                return f"✅ {valor_actual_formateado}"

    def determinar_resultado_final(self, fila_dian, fila_subpartida):
        """
        Determina el resultado final basado en comparaciones reales - LÓGICA CORREGIDA
        """
        errores_criticos = False
        
        numero_di = fila_dian.get("4. Número DI", "Desconocido")
        
        # Verificar campos críticos que deben coincidir INDIVIDUALMENTE
        for campo, (campo_dian, campo_subpartida) in self.campos_comparacion_individual.items():
            valor_dian = fila_dian.get(campo_dian, "NO ENCONTRADO")
            valor_subpartida = fila_subpartida.get(campo, "NO ENCONTRADO")
            
            # Solo comparar si tenemos ambos valores válidos
            if self.es_valor_valido(valor_subpartida) and self.es_valor_valido(valor_dian):
                numero_dian = self.extraer_numero_pais(valor_dian)
                numero_subpartida = self.extraer_numero_pais(valor_subpartida)
                
                if numero_dian and numero_subpartida:
                    if numero_dian != numero_subpartida:
                        errores_criticos = True
                        break  # Salir al primer error crítico
                else:
                    # Si no se pudieron extraer números, comparar los valores originales
                    if str(valor_dian).strip() != str(valor_subpartida).strip():
                        errores_criticos = True
                        break
            
            elif self.es_valor_valido(valor_dian) and not self.es_valor_valido(valor_subpartida):
                # Si la DI tiene valor pero la subpartida no, considerar error
                errores_criticos = True
                break
            
            elif not self.es_valor_valido(valor_dian) and self.es_valor_valido(valor_subpartida):
                # Si la subpartida tiene valor pero la DI no, considerar error
                errores_criticos = True
                break
            
            else:
                # Si ambos son inválidos, considerar error
                errores_criticos = True
                break
        
        return errores_criticos

    def generar_reporte_tabular(self, datos_dian, datos_subpartidas):
        """
        Genera reporte con nombres actualizados para Excel (DI en lugar de DIM)
        """
        if datos_dian is None or datos_dian.empty:
            return pd.DataFrame()
            
        if datos_subpartidas is None or datos_subpartidas.empty:
            return pd.DataFrame()
        
        fila_subpartida = datos_subpartidas.iloc[0]
        reporte_filas = []
        
        for _, fila_dian in datos_dian.iterrows():
            numero_di = fila_dian.get("4. Número DI", "Desconocido")
            fila_reporte = {"4. Número DI": numero_di}
            
            # 1. Campos de consistencia - CON EMOJIS (se mantienen igual)
            for campo_consistencia, campo_dian in self.campos_consistencia.items():
                valor_formateado = self.verificar_consistencia_campo(datos_dian, campo_dian, numero_di)
                fila_reporte[campo_dian] = valor_formateado
            
            # 2. Campos de comparación individual - CON NOMBRES ACTUALIZADOS A "DI"
            for campo, (campo_dian, _) in self.campos_comparacion_individual.items():
                valor_dian = fila_dian.get(campo_dian, "NO ENCONTRADO")
                valor_subpartida = fila_subpartida.get(campo, "NO ENCONTRADO")
                
                # Comparar con lógica corregida
                valor_formateado, es_correcto = self.comparar_valor_individual_critico(valor_dian, valor_subpartida, campo_dian)
                
                # NOMBRES ACTUALIZADOS PARA EXCEL - "DI" en lugar de "DIM"
                nombre_campo_di = f"{campo_dian} DI"
                nombre_campo_subpartida = f"{campo_dian} Subpartida"
                
                fila_reporte[nombre_campo_di] = valor_formateado
                fila_reporte[nombre_campo_subpartida] = self.formatear_numero_entero(valor_subpartida, f"{campo_dian} Subpartida")
            
            # 3. Campos acumulables - CON NOMBRES ACTUALIZADOS A "DI"
            for campo, (campo_dian, _) in self.campos_acumulables.items():
                valor_dian = fila_dian.get(campo_dian, "NO ENCONTRADO")
                valor_subpartida = fila_subpartida.get(campo, "NO ENCONTRADO")
                
                # NOMBRES ACTUALIZADOS PARA EXCEL - "DI" en lugar de "DIM"
                nombre_campo_di = f"{campo_dian} DI"
                nombre_campo_subpartida = f"{campo_dian} Subpartida"
                
                # Guardar valores numéricos puros
                if self.es_valor_valido(valor_dian):
                    fila_reporte[nombre_campo_di] = valor_dian
                else:
                    fila_reporte[nombre_campo_di] = None
                    
                if self.es_valor_valido(valor_subpartida):
                    fila_reporte[nombre_campo_subpartida] = valor_subpartida
                else:
                    fila_reporte[nombre_campo_subpartida] = None
            
            # Determinar resultado FINAL
            tiene_errores = self.determinar_resultado_final(fila_dian, fila_subpartida)
            fila_reporte["Resultado verificación"] = "❌ CON DIFERENCIAS" if tiene_errores else "✅ CONFORME"
            
            reporte_filas.append(fila_reporte)
            
            # SOLO MOSTRAR SI HAY DIFERENCIAS
            if tiene_errores:
                print(f"🔍 DI: {numero_di} - ❌ CON DIFERENCIAS")
        
        # Agregar totales con nombres actualizados a "DI"
        self._agregar_totales_acumulados_con_nombres_di(reporte_filas, datos_dian, fila_subpartida)
        
        # Crear DataFrame
        df_reporte = pd.DataFrame(reporte_filas)
        
        # Ordenar columnas con nombres actualizados a "DI"
        columnas_ordenadas = self._ordenar_columnas_reporte_con_di(df_reporte)
        df_reporte = df_reporte[columnas_ordenadas]
        
        return df_reporte

    def _agregar_totales_acumulados_con_nombres_di(self, reporte_filas, datos_dian, fila_subpartida):
        """Agrega fila de totales con nombres actualizados a "DI" """
        # Filtrar filas válidas para totales
        datos_dian_validos = self.obtener_filas_validas_para_totales(datos_dian)
        
        fila_totales = {"4. Número DI": "VALORES ACUMULADOS"}
        tiene_errores_totales = False
        
        # Campos de consistencia - N/A en totales
        for campo in self.campos_consistencia.keys():
            fila_totales[campo] = "N/A"
        
        # Campos individuales - N/A en totales
        for campo, (campo_dian, _) in self.campos_comparacion_individual.items():
            nombre_campo_di = f"{campo_dian} DI"
            nombre_campo_subpartida = f"{campo_dian} Subpartida"
            
            fila_totales[nombre_campo_di] = "N/A"
            fila_totales[nombre_campo_subpartida] = "N/A"
        
        # Campos acumulables - CALCULAR TOTALES CON NOMBRES ACTUALIZADOS A "DI"
        for campo, (campo_dian, _) in self.campos_acumulables.items():
            nombre_campo_di = f"{campo_dian} DI"
            nombre_campo_subpartida = f"{campo_dian} Subpartida"
            
            if campo_dian in datos_dian_validos.columns and len(datos_dian_validos) > 0:
                total_dian = datos_dian_validos[campo_dian].sum()
                valor_subpartida = fila_subpartida.get(campo, 0)
                
                # Para cantidad, solo mostrar valores sin validación
                if campo == 'cantidad':
                    fila_totales[nombre_campo_di] = total_dian
                    fila_totales[nombre_campo_subpartida] = valor_subpartida
                else:
                    # Para otros campos acumulables, agregar emojis de validación
                    try:
                        if self.es_valor_valido(valor_subpartida) and total_dian != 0:
                            diferencia_absoluta = abs(float(total_dian) - float(valor_subpartida))
                            diferencia_porcentual = (diferencia_absoluta / float(valor_subpartida)) * 100
                            
                            # Aplicar tolerancias y agregar emojis
                            if campo_dian == "78. Valor FOB USD":
                                if diferencia_absoluta < 1.0 or diferencia_porcentual < 0.5:
                                    fila_totales[nombre_campo_di] = f"✅ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"✅ {valor_subpartida:.2f}"
                                else:
                                    fila_totales[nombre_campo_di] = f"❌ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"❌ {valor_subpartida:.2f}"
                                    tiene_errores_totales = True
                            elif campo_dian in ["79. Valor Fletes USD", "80. Valor Seguros USD", "81. Valor Otros Gastos USD"]:
                                if diferencia_absoluta < 0.10 or diferencia_porcentual < 1.0:
                                    fila_totales[nombre_campo_di] = f"✅ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"✅ {valor_subpartida:.2f}"
                                else:
                                    fila_totales[nombre_campo_di] = f"❌ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"❌ {valor_subpartida:.2f}"
                                    tiene_errores_totales = True
                            else:
                                if diferencia_absoluta < 0.1 or diferencia_porcentual < 0.1:
                                    fila_totales[nombre_campo_di] = f"✅ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"✅ {valor_subpartida:.2f}"
                                else:
                                    fila_totales[nombre_campo_di] = f"❌ {total_dian:.2f}"
                                    fila_totales[nombre_campo_subpartida] = f"❌ {valor_subpartida:.2f}"
                                    tiene_errores_totales = True
                        else:
                            # Si no hay valor de subpartida, mostrar sin emojis
                            fila_totales[nombre_campo_di] = f"{total_dian:.2f}"
                            fila_totales[nombre_campo_subpartida] = f"{valor_subpartida:.2f}"
                    except:
                        # En caso de error, mostrar sin emojis
                        fila_totales[nombre_campo_di] = f"{total_dian:.2f}"
                        fila_totales[nombre_campo_subpartida] = f"{valor_subpartida:.2f}"
            else:
                fila_totales[nombre_campo_di] = "N/A"
                fila_totales[nombre_campo_subpartida] = "N/A"
        
        fila_totales["Resultado verificación"] = "❌ TOTALES NO COINCIDEN" if tiene_errores_totales else "✅ TOTALES CONFORME"
        reporte_filas.append(fila_totales)

    def _ordenar_columnas_reporte_con_di(self, df_reporte):
        """
        Ordena las columnas del reporte con nombres actualizados a "DI"
        """
        columnas_base = ['4. Número DI']
        
        # Campos de consistencia (se mantienen igual)
        columnas_consistencia = []
        for campo in self.campos_consistencia.keys():
            if campo in df_reporte.columns:
                columnas_consistencia.append(campo)
        
        # Campos de comparación individual - CON NOMBRES ACTUALIZADOS A "DI"
        columnas_individuales = []
        for campo, (campo_dian, _) in self.campos_comparacion_individual.items():
            nombre_campo_di = f"{campo_dian} DI"
            nombre_campo_subpartida = f"{campo_dian} Subpartida"
            
            if nombre_campo_di in df_reporte.columns:
                columnas_individuales.extend([
                    nombre_campo_di, 
                    nombre_campo_subpartida
                ])
        
        # Campos acumulables - CON NOMBRES ACTUALIZADOS A "DI"
        columnas_acumulables = []
        for campo, (campo_dian, _) in self.campos_acumulables.items():
            nombre_campo_di = f"{campo_dian} DI"
            nombre_campo_subpartida = f"{campo_dian} Subpartida"
            
            if nombre_campo_di in df_reporte.columns:
                columnas_acumulables.extend([
                    nombre_campo_di,
                    nombre_campo_subpartida
                ])
        
        # Resultado final
        columnas_finales = ['Resultado verificación']
        
        # Combinar todas las columnas
        todas_columnas = columnas_base + columnas_consistencia + columnas_individuales + columnas_acumulables + columnas_finales
        
        # Filtrar solo las columnas que existen en el DataFrame
        return [col for col in todas_columnas if col in df_reporte.columns]

    def generar_reporte_comparacion(self, datos_dian, datos_subpartidas, output_path):
        """
        Genera el reporte de comparación en Excel con la nueva estructura
        """
        df_reporte = self.generar_reporte_tabular(datos_dian, datos_subpartidas)
        
        if not df_reporte.empty:
            try:
                df_reporte.to_excel(output_path, index=False)
                print(f"💾 Reporte de comparación guardado en: {output_path}")
                
                # Mostrar resumen estadístico
                self._mostrar_resumen_estadistico(df_reporte)
                
            except Exception as e:
                print(f"❌ Error al guardar el reporte de comparación: {e}")
        
        return df_reporte
    
    def _mostrar_resumen_estadistico(self, df_reporte):
        """
        Muestra un resumen estadístico del reporte
        """
        di_individuales = df_reporte[df_reporte['4. Número DI'] != 'VALORES ACUMULADOS']
        
        print(f"\n📈 RESUMEN ESTADÍSTICO:")
        print(f"   • Total DI procesadas: {len(di_individuales)}")
        
        conformes = len(di_individuales[di_individuales['Resultado verificación'] == '✅ CONFORME'])
        con_diferencias = len(di_individuales[di_individuales['Resultado verificación'] == '❌ CON DIFERENCIAS'])
        
        print(f"   • DI conformes: {conformes}")
        print(f"   • DI con diferencias: {con_diferencias}")
        
        # Verificar totales
        fila_totales = df_reporte[df_reporte['4. Número DI'] == 'VALORES ACUMULADOS']
        if not fila_totales.empty:
            resultado_totales = fila_totales.iloc[0]['Resultado verificación']
            print(f"   • Totales: {resultado_totales}")

# =============================================================================
# CLASE 3: EXTRACCIÓN DE EXCEL (SUBPARTIDAS) - SEGUNDO SCRIPT
# =============================================================================

class ExtractorSubpartidas:
    def __init__(self):
        self.datos_estandarizados = pd.DataFrame()
    
    def buscar_archivo_subpartidas(self, carpeta_base):
        """
        Busca automáticamente el archivo de subpartidas en la carpeta base
        """
        patrones = [
            "*subpartida*.xlsx",
            "*subpartida*.xls", 
            "*resumen*.xlsx",
            "*resumen*.xls",
            "*.xlsx",
        ]
        
        for patron in patrones:
            archivos = glob.glob(os.path.join(carpeta_base, patron))
            for archivo in archivos:
                # Excluir archivos de resultados
                nombre_archivo = os.path.basename(archivo).lower()
                if not any(palabra in nombre_archivo for palabra in ['resultado', 'validacion', 'comparacion', 'reporte']):
                    return archivo
        
        return None
    
    def detectar_hoja_correcta(self, archivo_excel):
        """
        Detecta automáticamente la hoja correcta que contiene datos de subpartidas
        """
        try:
            # Obtener todas las hojas del archivo
            hojas_disponibles = pd.ExcelFile(archivo_excel).sheet_names
            
            # Buscar hojas que puedan contener datos de subpartidas
            palabras_clave = ['subpartida', 'resumen', 'datos', '847156', 'hoja1', 'sheet1']
            
            for hoja in hojas_disponibles:
                hoja_lower = hoja.lower()
                
                # Si el nombre de la hoja contiene palabras clave, intentar leerla
                if any(palabra in hoja_lower for palabra in palabras_clave):
                    try:
                        df_prueba = pd.read_excel(archivo_excel, sheet_name=hoja, nrows=5)
                        
                        # Verificar si tiene columnas que parezcan ser de subpartidas
                        columnas_encontradas = [col for col in df_prueba.columns if any(palabra in str(col).lower() for palabra in ['subpartida', 'descripcion', 'peso', 'pais', 'valor'])]
                        
                        if len(columnas_encontradas) >= 3:  # Si tiene al menos 3 columnas relevantes
                            return hoja
                    except Exception as e:
                        continue
            
            # Si no se encontró por palabras clave, probar todas las hojas
            for hoja in hojas_disponibles:
                try:
                    df_prueba = pd.read_excel(archivo_excel, sheet_name=hoja, nrows=5)
                    # Verificar si tiene estructura de datos
                    if len(df_prueba.columns) >= 5 and not df_prueba.empty:
                        return hoja
                except:
                    continue
            
            # Si no se encuentra ninguna hoja adecuada, usar la primera
            if hojas_disponibles:
                return hojas_disponibles[0]
            else:
                return None
                
        except Exception as e:
            return None
    
    def extraer_y_estandarizar(self, carpeta_base) -> pd.DataFrame:
        try:
            # Buscar automáticamente el archivo de subpartidas
            archivo_excel = self.buscar_archivo_subpartidas(carpeta_base)
            if not archivo_excel:
                return pd.DataFrame()
                
            # Detectar automáticamente la hoja correcta
            hoja_correcta = self.detectar_hoja_correcta(archivo_excel)
            if not hoja_correcta:
                return pd.DataFrame()
            
            # Leer los datos de la hoja detectada
            df = pd.read_excel(archivo_excel, sheet_name=hoja_correcta, header=0)
            df_estandarizado = self._estandarizar_y_filtrar_columnas(df)
            self.datos_estandarizados = df_estandarizado
            
            return df_estandarizado
            
        except Exception as e:
            return pd.DataFrame()
    
    def _estandarizar_y_filtrar_columnas(self, df: pd.DataFrame) -> pd.DataFrame:
        mapeo_columnas = {
            'SUBPARTIDA': 'subpartida',
            'DESCRIPCION': 'descripcion',
            'PESO BRUTO': 'peso_bruto',
            'PESO NETO': 'peso_neto', 
            'NUMERO BULTOS': 'numero_bultos',
            'PAIS ORIGEN': 'pais_origen',
            'PAIS COMPRA': 'pais_compra',
            'PAIS PROCEDENCIA': 'pais_procedencia',
            'PAIS DESTINO': 'pais_destino',
            'VALOR_FLETES': 'valor_fletes',
            'VALOR_SEGURO': 'valor_seguro',
            'OTROS_GASTOS': 'otros_gastos',
            'BANDERA': 'bandera',
            'UNIDAD': 'unidad',
            'VALOR FOB': 'valor_fob',
            'CANTIDAD': 'cantidad'
        }
        
        columnas_a_mantener = [col for col in mapeo_columnas.keys() if col in df.columns]
        df_filtrado = df[columnas_a_mantener].copy()
        df_renombrado = df_filtrado.rename(columns=mapeo_columnas)
        
        df_renombrado['subpartida'] = df_renombrado['subpartida'].astype(str)
        df_renombrado['descripcion'] = df_renombrado['descripcion'].astype(str)
        
        campos_numericos = ['peso_bruto', 'peso_neto', 'numero_bultos', 'valor_fletes', 
                           'valor_seguro', 'otros_gastos', 'valor_fob', 'cantidad']
        
        for campo in campos_numericos:
            if campo in df_renombrado.columns:
                df_renombrado[campo] = pd.to_numeric(df_renombrado[campo], errors='coerce')
        
        return df_renombrado

# =============================================================================
# CLASE 4: VALIDACIÓN DECLARACIÓN IMPORTACIÓN (PRIMER SCRIPT)
# =============================================================================

class ValidadorDeclaracionImportacionCompleto:
    def __init__(self):
        warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
        
        # Inicializar el corrector de nombres simplificado
        self.corrector_nombres = CorrectorNombres()
        
        self.CAMPOS_DI = {
            "5.": "5. Número de Identificación Tributaria (NIT)",
            "11.": "11. Apellidos y Nombres / Razón Social Importador",
            "42.": "42. No. Manifiesto de Carga",
            "43.": "43. Fecha Manifiesto de Carga",
            "44.": "44. No. Documento de Transporte",
            "45.": "45. Fecha Documento de Transporte",
            "51.": "51. No. Factura Comercial",
            "52.": "52. Fecha Factura Comercial",
            "132.": "132. No. Aceptación Declaración",
            "133.": "133. Fecha Aceptación",
            "134.": "134. Levante No.",
            "135.": "135. Fecha Levante"
        }

        self.MAPEOS_VALIDACION = {
            "5. Número de Identificación Tributaria (NIT)": {
                "codigo_formulario": "PROVEEDOR",
                "descripcion_esperada": "INFORMACION_PROVEEDOR",
                "tipo": "documento",
                "cambia_por_declaracion": False
            },
            "11. Apellidos y Nombres / Razón Social Importador": {
                "codigo_formulario": "PROVEEDOR", 
                "descripcion_esperada": "INFORMACION_PROVEEDOR",
                "tipo": "documento",
                "cambia_por_declaracion": False
            },
            "42. No. Manifiesto de Carga": {
                "codigo_formulario": 93,
                "descripcion_esperada": "FORMULARIO DE SALIDA ZONA FRANCA",
                "tipo": "documento",
                "cambia_por_declaracion": False
            },
            "43. Fecha Manifiesto de Carga": {
                "codigo_formulario": 93,
                "descripcion_esperada": "FORMULARIO DE SALIDA ZONA FRANCA",
                "tipo": "fecha",
                "cambia_por_declaracion": False
            },
            "44. No. Documento de Transporte": {
                "codigo_formulario": [17, 91],
                "descripcion_esperada": "DOCUMENTO OF TRANSPORTE",
                "tipo": "documento",
                "cambia_por_declaracion": False
            },
            "45. Fecha Documento de Transporte": {
                "codigo_formulario": [17, 91],
                "descripcion_esperada": "DOCUMENTO OF TRANSPORTE",
                "tipo": "fecha",
                "cambia_por_declaracion": False
            },
            "51. No. Factura Comercial": {
                "codigo_formulario": 6,
                "descripcion_esperada": "FACTURA COMERCIAL",
                "tipo": "documento",
                "cambia_por_declaracion": True
            },
            "52. Fecha Factura Comercial": {
                "codigo_formulario": 6,
                "descripcion_esperada": "FACTURA COMERCIAL",
                "tipo": "fecha",
                "cambia_por_declaracion": True
            },
            "132. No. Aceptación Declaración": {
                "codigo_formulario": 9,
                "descripcion_esperada": "DECLARACION DE IMPORTACION",
                "tipo": "documento",
                "cambia_por_declaracion": True
            },
            "133. Fecha Aceptación": {
                "codigo_formulario": 9,
                "descripcion_esperada": "DECLARACION DE IMPORTACION",
                "tipo": "fecha",
                "cambia_por_declaracion": True
            },
            "134. Levante No.": {
                "codigo_formulario": 47,
                "descripcion_esperada": "AUTORIZACION DE LEVANTE",
                "tipo": "documento",
                "cambia_por_declaracion": True
            },
            "135. Fecha Levante": {
                "codigo_formulario": 47,
                "descripcion_esperada": "AUTORIZACION DE LEVANTE",
                "tipo": "fecha",
                "cambia_por_declaracion": True
            }
        }

        self.patrones = {
            "5. Número de Identificación Tributaria (NIT)": [
                r"5\s*\.?\s*N[uú]mero\s*de\s*Identificaci[oó]n\s*Tributaria\s*\(NIT\).*?([0-9]{6,12})",
                r"5\.\s*Número de Identificación Tributaria \(NIT\)[\s\S]*?(\d{6,12})"
            ],
            "11. Apellidos y Nombres / Razón Social Importador": [
                r"11\s*\.?\s*Apellidos\s*y\s*nombres\s*o\s*Raz[oó]n\s*Social\s*\n?\s*\d{6,12}\s*\d?\s*([A-ZÁÉÍÓÚÑ0-9\s\.\-&/]+?)(?=\s*13\s*\.)",
                r"11\.\s*Apellidos y nombres o Razón Social[\s\S]*?\n\s*(\d{6,12}\s*\d?\s*[A-ZÁÉÍÓÚÑ0-9\s\.\-&/]+)"
            ],
            "42. No. Manifiesto de Carga": [
                r"42\s*\.?\s*Manifiesto\s*de\s*carga[\s\S]*?No\.?\s*([A-Z0-9]+)"
            ],
            "43. Fecha Manifiesto de Carga": [
                r"43\s*\.?\s*Año\s*[-\s]*Mes\s*[-\s]*Día.*?(\d{4}\s*[-]\s*\d{2}\s*[-]\s*\d{2})"
            ],
            "44. No. Documento de Transporte": [
                r"44\s*\.?\s*Documento\s*de\s*transporte[\s\S]*?(?:No\.?\s*)?((?:[A-Z]*[0-9]+(?:\-[A-Z0-9]+)?)|(?:[0-9]{6,11}))(?=\s|[0-9]{4}|$)"
            ],
            "45. Fecha Documento de Transporte": [
                r"45\s*\.?\s*Año.*?Día[\s\S]*?[0-9]{4}\s*-\s*[0-9]{2}\s*-\s*[0-9]{2}[\s\S]*?([0-9]{4}\s*-\s*[0-9]{2}\s*-\s*[0-9]{2})"
            ],
            "51. No. Factura Comercial": [
                r"51\s*\.?\s*No\.?\s*de\s*factura[\s\S]*?\n\s*([A-Z0-9\-]+(?:\s+[A-Z0-9\-]+)*(?:\s*/\s*[A-Z0-9]+)?)"
            ],
            "52. Fecha Factura Comercial": [
                r"52\s*\.\s*?Año\s*-\s*Mes\s*-\s*Día.*?\n(?:.*?[^\d\w-])?(\d{4}\s*-\s*\d{2}\s*-\s*\d{2})"
            ],
            "132. No. Aceptación Declaración": [
                r"132\s*\.?\s*No\.?\s*Aceptaci[oó]n\s*declaraci[oó]n[\s\S]*?(\d{12,18})"
            ],
            "133. Fecha Aceptación": [
                r"133\s*\.?\s*Fec*h?a:?\s*(\d{4}\s*[\-\s]*\d{2}\s*[\-\s]*\d{2}|\d{8})\b"
            ],
            "134. Levante No.": [
                r"134\s*\.?\s*Levante\s*No\.?\s*(\d+)"
            ],
            "135. Fecha Levante": [
                r"135\s*\.?\s*Fec*h?a[\s\S]*?([\d]{4}\s*-\s*[\d]{2}\s*-\s*[\d]{2})"
            ]
        }

        self.nit_proveedor = None
        self.nombre_proveedor = None
        self.facturas_emparejadas = {}
        self._cache_nombres = {}  # Cache para optimizar comparaciones de nombres

    def buscar_archivo_formulario(self, carpeta):
        """Busca específicamente el archivo del formulario FMM"""
        print(f"🔍 Buscando formulario FMM...")
        
        patrones_formulario = [
            "*Rpt_Impresion_Formulario*",
            "*FORMULARIO*", 
            "*FMM*",
            "*.xlsx"
        ]
        
        for patron in patrones_formulario:
            archivos = glob.glob(os.path.join(carpeta, patron))
            for archivo in archivos:
                nombre_archivo = os.path.basename(archivo)
                if "Cruce" not in nombre_archivo and "validacion" not in nombre_archivo.lower():
                    print(f"📁 Formulario encontrado: {nombre_archivo}")
                    return archivo
        
        print("❌ No se encontró archivo del formulario FMM")
        return None

    def extraer_proveedor_formulario(self, archivo_excel):
        """Extrae NIT y nombre del proveedor del formulario FMM"""
        try:
            print(f"👤 Extrayendo información del proveedor...")
            
            wb = load_workbook(archivo_excel, data_only=True)
            sheet = wb.active
            
            proveedor_encontrado = False
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value and 'Proveedor/Cliente:' in str(cell.value):
                        texto = str(cell.value)
                        print(f"📋 Información encontrada: {texto}")
                        
                        texto_limpio = texto.replace('Proveedor/Cliente:', '').strip()
                        
                        for i, char in enumerate(texto_limpio):
                            if char == ' ' and texto_limpio[:i].replace(' ', '').isdigit():
                                self.nit_proveedor = texto_limpio[:i].replace(' ', '').replace('-', '').replace('.', '')
                                self.nombre_proveedor = texto_limpio[i:].strip(' -')
                                break
                        
                        if not self.nit_proveedor and ' - ' in texto_limpio:
                            partes = texto_limpio.split(' - ', 1)
                            self.nit_proveedor = partes[0].replace(' ', '').replace('-', '').replace('.', '')
                            self.nombre_proveedor = partes[1]
                        
                        if self.nit_proveedor and self.nombre_proveedor:
                            proveedor_encontrado = True
                            print(f"✅ PROVEEDOR VÁLIDO:")
                            print(f"   🆔 NIT: {self.nit_proveedor}")
                            print(f"   📛 Nombre: {self.nombre_proveedor}")
                        else:
                            print(f"❌ ERROR: Formato de proveedor incorrecto")
                        
                        wb.close()
                        return proveedor_encontrado
            
            if not proveedor_encontrado:
                print("❌ ERROR: No se pudo extraer información del proveedor")
            
            wb.close()
            return proveedor_encontrado
            
        except Exception as e:
            print(f"❌ ERROR al extraer proveedor: {e}")
            return False

    def extraer_anexos_formulario_robusto(self, archivo_excel):
        """Extrae anexos del formulario de manera robusta con validación de duplicados"""
        try:
            print(f"📖 Extrayendo anexos del formulario...")
            
            wb = load_workbook(archivo_excel, data_only=True)
            sheet = wb.active
            
            inicio_anexos = None
            for row in range(1, sheet.max_row + 1):
                for col in range(1, sheet.max_column + 1):
                    cell_value = sheet.cell(row=row, column=col).value
                    if cell_value and 'DETALLE DE LOS ANEXOS' in str(cell_value):
                        inicio_anexos = row
                        break
                if inicio_anexos:
                    break
            
            if inicio_anexos is None:
                print("❌ ERROR: No se encontró la sección 'DETALLE DE LOS ANEXOS'")
                wb.close()
                return pd.DataFrame()
            
            encabezados = {}
            fila_encabezados = inicio_anexos + 1
            
            for col in range(1, sheet.max_column + 1):
                valor = sheet.cell(row=fila_encabezados, column=col).value
                if valor:
                    valor_str = str(valor).strip().upper()
                    if 'CÓDIGO' in valor_str or 'CODIGO' in valor_str:
                        encabezados['codigo'] = col
                    elif 'DESCRIPCIÓN' in valor_str or 'DESCRIPCION' in valor_str:
                        encabezados['descripcion'] = col
                    elif 'DOCUMENTO' in valor_str:
                        encabezados['documento'] = col
                    elif 'FECHA' in valor_str:
                        encabezados['fecha'] = col
            
            if not encabezados:
                encabezados = {
                    'codigo': 1,
                    'descripcion': 5,
                    'documento': 19,
                    'fecha': 34
                }
            
            datos_anexos = []
            fila_actual = fila_encabezados + 1
            
            for i in range(200):
                try:
                    if 'codigo' in encabezados:
                        codigo = sheet.cell(row=fila_actual, column=encabezados['codigo']).value
                    else:
                        codigo = sheet.cell(row=fila_actual, column=1).value
                    
                    if codigo is None or codigo == '':
                        filas_vacias = 0
                        for j in range(5):
                            codigo_check = sheet.cell(row=fila_actual + j, column=encabezados.get('codigo', 1)).value
                            if codigo_check is None or codigo_check == '':
                                filas_vacias += 1
                        if filas_vacias >= 3:
                            break
                        fila_actual += 1
                        continue
                    
                    try:
                        codigo_str = str(codigo).strip().split('.')[0]
                        if codigo_str not in ['6', '9', '17', '47', '93', '91']:
                            fila_actual += 1
                            continue
                    except:
                        fila_actual += 1
                        continue
                    
                    if 'descripcion' in encabezados:
                        descripcion = sheet.cell(row=fila_actual, column=encabezados['descripcion']).value
                    else:
                        descripcion = sheet.cell(row=fila_actual, column=5).value
                    
                    if 'documento' in encabezados:
                        documento = sheet.cell(row=fila_actual, column=encabezados['documento']).value
                    else:
                        documento = sheet.cell(row=fila_actual, column=19).value
                    
                    if 'fecha' in encabezados:
                        fecha = sheet.cell(row=fila_actual, column=encabezados['fecha']).value
                    else:
                        fecha = sheet.cell(row=fila_actual, column=34).value
                    
                    fecha_normalizada = self.normalizar_fecha_dd_mm_aaaa(fecha, es_fecha=True)
                    
                    datos_anexos.append({
                        'Codigo': int(float(codigo_str)),
                        'Descripcion': descripcion,
                        'Documento': documento,
                        'Fecha': fecha_normalizada,
                        'Fila_Excel': fila_actual,
                        'Usado': False
                    })
                    
                    fila_actual += 1
                    
                except Exception:
                    fila_actual += 1
                    continue
            
            wb.close()
            
            df_resultado = pd.DataFrame(datos_anexos)
            
            if not df_resultado.empty:
                print(f"✅ {len(df_resultado)} anexos encontrados")
                
                # SIEMPRE mostrar resumen por código
                resumen = df_resultado.groupby('Codigo').agg({
                    'Descripcion': 'first',
                    'Documento': 'count'
                }).reset_index()
                
                print("📊 Resumen por código:")
                for _, row in resumen.iterrows():
                    print(f"   • Código {row['Codigo']}: {row['Documento']} - {row['Descripcion']}")
                
                # ✅ VALIDACIÓN: Solo mostrar errores si existen
                count_di = len(df_resultado[df_resultado['Codigo'] == 9])
                count_levante = len(df_resultado[df_resultado['Codigo'] == 47])
                
                # Verificar duplicados
                di_duplicados = df_resultado[
                    (df_resultado['Codigo'] == 9) & 
                    (df_resultado.duplicated('Documento', keep=False))
                ]
                levante_duplicados = df_resultado[
                    (df_resultado['Codigo'] == 47) & 
                    (df_resultado.duplicated('Documento', keep=False))
                ]
                
                has_errors = False
                mensajes_error = []
                
                if not di_duplicados.empty:
                    has_errors = True
                    documentos_duplicados = di_duplicados['Documento'].unique()
                    mensajes_error.append(f"❌ {len(documentos_duplicados)} DI duplicadas: {', '.join(documentos_duplicados)}")
                
                if not levante_duplicados.empty:
                    has_errors = True
                    documentos_duplicados = levante_duplicados['Documento'].unique()
                    mensajes_error.append(f"❌ {len(documentos_duplicados)} Levantes duplicados: {', '.join(documentos_duplicados)}")
                
                if count_di != count_levante:
                    has_errors = True
                    mensajes_error.append(f"❌ Desbalance: {count_di} DI vs {count_levante} Levantes")
                
                # Mostrar errores si existen
                if has_errors:
                    print("\n🔍 VALIDACIÓN DE INTEGRIDAD:")
                    for mensaje in mensajes_error:
                        print(f"   {mensaje}")
                else:
                    print(f"✅ Balance correcto: {count_di} DI = {count_levante} Levantes")
                    
            else:
                print("❌ No se encontraron anexos")
            
            return df_resultado
            
        except Exception as e:
            print(f"❌ Error al extraer anexos: {e}")
            return pd.DataFrame()

    def extraer_todas_declaraciones_pdf(self, pdf_path):
        """Extrae TODAS las declaraciones del PDF"""
        print(f"\n📄 Procesando PDF: {os.path.basename(pdf_path)}")
        
        texto_completo = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for pagina in pdf.pages:
                    texto = pagina.extract_text(x_tolerance=3, y_tolerance=3)
                    if texto:
                        texto_completo += texto + "\n\n"
        except Exception as e:
            print(f"❌ Error al abrir el PDF: {e}")
            return []
        
        patron_declaraciones = r"4\s*\.?\s*N[uú]mero\s*de\s*formulario[\s\S]*?(\d{12,18})"
        matches = list(re.finditer(patron_declaraciones, texto_completo, re.IGNORECASE))
        
        print(f"📋 Declaraciones encontradas: {len(matches)}")
        
        declaraciones = []
        
        for i, match in enumerate(matches):
            numero_formulario = match.group(1)
            
            start_pos = match.start()
            if i < len(matches) - 1:
                end_pos = matches[i+1].start()
            else:
                end_pos = len(texto_completo)
            
            texto_declaracion = texto_completo[start_pos:end_pos]
            
            datos = self.extraer_datos_declaracion_individual(texto_declaracion, numero_formulario)
            if datos:
                declaraciones.append(datos)
        
        return declaraciones

    def extraer_datos_declaracion_individual(self, texto, numero_formulario):
        """Extrae datos de una declaración individual"""
        datos = {
            'Numero_Formulario_Declaracion': numero_formulario,
            'Archivo_PDF': os.path.basename(texto.split('\n')[0]) if texto else 'Desconocido'
        }
        
        for campo in self.CAMPOS_DI.values():
            if campo in self.patrones:
                valor = self.extraer_campo_individual(texto, self.patrones[campo], campo)
                if any(palabra in campo for palabra in ['Fecha', 'Aceptación', 'Levante']):
                    valor = self.normalizar_fecha_dd_mm_aaaa(valor, es_fecha=True)
                datos[campo] = valor
        
        return datos

    def extraer_campo_individual(self, texto, patrones, campo_nombre=""):
        """Extrae un campo específico de una declaración individual"""
        for patron in patrones:
            try:
                match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                if match:
                    if match.groups():
                        for group_val in match.groups():
                            if group_val and group_val.strip():
                                return group_val.strip()
                    else:
                        return match.group(0).strip()
            except Exception:
                continue
        return "NO ENCONTRADO"

    def normalizar_fecha_dd_mm_aaaa(self, fecha_str, es_fecha=True):
        """Normaliza formato de fecha a dd-mm-aaaa"""
        if not fecha_str or fecha_str == "NO ENCONTRADO" or str(fecha_str).strip() == "":
            return "NO ENCONTRADO"
        
        if not es_fecha:
            return str(fecha_str).strip()
        
        try:
            if isinstance(fecha_str, datetime):
                return fecha_str.strftime('%d-%m-%Y')
            
            fecha_limpia = str(fecha_str).strip()
            fecha_limpia = re.sub(r'\s+', '', fecha_limpia)
            
            if len(fecha_limpia) > 10 and fecha_limpia.isdigit():
                return fecha_limpia
            
            patrones_fecha = [
                (r'^(\d{4})(\d{2})(\d{2})$', '%Y%m%d'),
                (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),
                (r'(\d{4})/(\d{1,2})/(\d{1,2})', '%Y/%m/%d'),
                (r'(\d{1,2})-(\d{1,2})-(\d{4})', '%d-%m-%Y'),
                (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%d/%m/%Y'),
            ]
            
            for patron, formato in patrones_fecha:
                match = re.match(patron, fecha_limpia)
                if match:
                    try:
                        fecha_obj = datetime.strptime(fecha_limpia, formato)
                        return fecha_obj.strftime('%d-%m-%Y')
                    except ValueError:
                        continue
            
            return fecha_limpia
            
        except Exception as e:
            return str(fecha_str)

    def _normalizar_factura(self, factura_str):
        """Normaliza número de factura para comparación"""
        if not factura_str or factura_str == "NO ENCONTRADO":
            return ""
        
        factura_limpia = str(factura_str).strip().upper()
        factura_limpia = re.sub(r'\s*/\s*', '/', factura_limpia)
        factura_limpia = factura_limpia.replace(' ', '')
        factura_limpia = re.sub(r'[^\w\/\-]', '', factura_limpia)
        
        return factura_limpia

    def _emparejar_facturas_completo(self, facturas_declaraciones, facturas_formulario):
        """Empareja facturas manejando todos los casos posibles - SIN LOGS REPETITIVOS"""
        emparejamientos = {}
        
        # Crear conjuntos normalizados para comparación
        facturas_decl_norm = {self._normalizar_factura(f): f for f in facturas_declaraciones.values()}
        facturas_form_norm = {self._normalizar_factura(f): f for f in facturas_formulario}
        
        # CASO 1: Solo hay UNA factura en el formulario
        if len(facturas_formulario) == 1:
            factura_unica = facturas_formulario[0]
            
            # Esta misma factura se usa para TODAS las declaraciones
            for di_num, factura_decl in facturas_declaraciones.items():
                emparejamientos[di_num] = factura_unica
        
        # CASO 2: Hay múltiples facturas en el formulario
        else:
            facturas_disponibles = facturas_formulario.copy()
            
            # PRIMERO: Emparejamiento exacto
            for di_num, factura_decl in facturas_declaraciones.items():
                if di_num in emparejamientos:
                    continue
                    
                factura_decl_norm = self._normalizar_factura(factura_decl)
                
                for factura_form in facturas_disponibles[:]:
                    factura_form_norm = self._normalizar_factura(factura_form)
                    
                    if factura_decl_norm == factura_form_norm:
                        emparejamientos[di_num] = factura_form
                        facturas_disponibles.remove(factura_form)
                        break
            
            # SEGUNDO: Emparejamiento por parte numérica para los restantes
            for di_num, factura_decl in facturas_declaraciones.items():
                if di_num in emparejamientos:
                    continue
                    
                factura_decl_norm = self._normalizar_factura(factura_decl)
                
                if '/' in factura_decl_norm:
                    parte_principal_decl = factura_decl_norm.split('/')[0]
                else:
                    parte_principal_decl = factura_decl_norm
                
                for factura_form in facturas_disponibles[:]:
                    factura_form_norm = self._normalizar_factura(factura_form)
                    
                    if '/' in factura_form_norm:
                        parte_principal_form = factura_form_norm.split('/')[0]
                    else:
                        parte_principal_form = factura_form_norm
                    
                    if parte_principal_decl == parte_principal_form:
                        emparejamientos[di_num] = factura_form
                        facturas_disponibles.remove(factura_form)
                        break
            
            # TERCERO: Si aún quedan DI sin emparejar, usar las facturas restantes en orden
            di_sin_emparejar = [di for di in facturas_declaraciones.keys() if di not in emparejamientos]
            if di_sin_emparejar and facturas_disponibles:
                for i, di_num in enumerate(di_sin_emparejar):
                    if i < len(facturas_disponibles):
                        emparejamientos[di_num] = facturas_disponibles[i]
        
        # Verificar que todas las DI tengan una factura asignada
        for di_num in facturas_declaraciones.keys():
            if di_num not in emparejamientos:
                # Si no se pudo emparejar, usar la primera factura disponible
                if facturas_formulario:
                    emparejamientos[di_num] = facturas_formulario[0]
                else:
                    emparejamientos[di_num] = "NO ENCONTRADO"
        
        return emparejamientos

    def _comparar_nombres_optimizado(self, nombre_pdf, nombre_excel):
        """Función optimizada para comparación de nombres con cache"""
        cache_key = f"{nombre_pdf}_{nombre_excel}"
        if cache_key in self._cache_nombres:
            return self._cache_nombres[cache_key]
        
        resultado = self.corrector_nombres.comparar_por_letras(nombre_pdf, nombre_excel)
        self._cache_nombres[cache_key] = resultado
        return resultado

    def validar_campos_por_declaracion(self, datos_declaracion, anexos_formulario):
        """Valida los campos para una declaración específica con corrección automática de nombres - OPTIMIZADA"""
        resultados_validacion = []
        
        if anexos_formulario.empty and not (self.nit_proveedor and self.nombre_proveedor):
            return pd.DataFrame()
        
        numero_di = datos_declaracion.get('Numero_Formulario_Declaracion', 'NO ENCONTRADO')
        
        # Pre-calcular valores para evitar llamadas repetidas
        valor_nombre_pdf = datos_declaracion.get("11. Apellidos y Nombres / Razón Social Importador", "NO ENCONTRADO")
        nombre_corregido = None
        
        for campo_declaracion, config in self.MAPEOS_VALIDACION.items():
            resultado = {
                'Campos DI a Validar': campo_declaracion,
                'Datos Declaración': 'NO ENCONTRADO',
                'Datos Formulario': 'NO ENCONTRADO',
                'Numero DI': numero_di,
                'Coincidencias': '❌ NO COINCIDE'
            }
            
            try:
                codigo_esperado = config["codigo_formulario"]
                tipo = config["tipo"]
                cambia_por_declaracion = config["cambia_por_declaracion"]
                
                valor_declaracion = datos_declaracion.get(campo_declaracion, "NO ENCONTRADO")
                
                if tipo == "fecha" and valor_declaracion != "NO ENCONTRADO":
                    valor_declaracion = self.normalizar_fecha_dd_mm_aaaa(valor_declaracion, es_fecha=True)
                
                # ✅ APLICAR CORRECCIÓN DE NOMBRES PARA EL CAMPO 11 - OPTIMIZADO
                if campo_declaracion == "11. Apellidos y Nombres / Razón Social Importador":
                    if nombre_corregido is None:
                        nombre_corregido = self.corrector_nombres.corregir_nombre(
                            valor_nombre_pdf, 
                            self.nombre_proveedor if self.nombre_proveedor else ""
                        )
                    resultado['Datos Declaración'] = nombre_corregido
                else:
                    resultado['Datos Declaración'] = valor_declaracion
                
                if codigo_esperado == "PROVEEDOR":
                    if campo_declaracion == "5. Número de Identificación Tributaria (NIT)":
                        resultado['Datos Formulario'] = self.nit_proveedor if self.nit_proveedor else 'NO ENCONTRADO'
                        coincide = str(valor_declaracion).strip() == str(self.nit_proveedor).strip()
                        resultado['Coincidencias'] = '✅ COINCIDE' if coincide else '❌ NO COINCIDE'
                    
                    elif campo_declaracion == "11. Apellidos y Nombres / Razón Social Importador":
                        resultado['Datos Formulario'] = self.nombre_proveedor if self.nombre_proveedor else 'NO ENCONTRADO'
                        
                        # ✅ USAR LA LÓGICA SIMPLIFICADA DE COMPARACIÓN POR LETRAS - OPTIMIZADO
                        if self.nombre_proveedor and valor_nombre_pdf != "NO ENCONTRADO":
                            coincide = self._comparar_nombres_optimizado(
                                valor_nombre_pdf, 
                                self.nombre_proveedor
                            )
                            resultado['Coincidencias'] = '✅ COINCIDE' if coincide else '❌ NO COINCIDE'
                        else:
                            resultado['Coincidencias'] = '❌ NO COINCIDE'
                
                else:
                    anexos_correspondientes = anexos_formulario[
                        anexos_formulario['Codigo'].isin(
                            [codigo_esperado] if not isinstance(codigo_esperado, list) else codigo_esperado)
                    ]
                    
                    if anexos_correspondientes.empty:
                        resultado['Datos Formulario'] = 'NO ENCONTRADO'
                        resultado['Coincidencias'] = '❌ NO COINCIDE'
                    else:
                        if not cambia_por_declaracion:
                            anexo = anexos_correspondientes.iloc[0]
                            if tipo == "documento":
                                valor_formulario = anexo['Documento']
                            else:
                                valor_formulario = anexo.get('Fecha', 'NO ENCONTRADO')
                            
                            resultado['Datos Formulario'] = valor_formulario
                            coincide = str(valor_declaracion).strip() == str(valor_formulario).strip()
                            resultado['Coincidencias'] = '✅ COINCIDE' if coincide else '❌ NO COINCIDE'
                        
                        else:
                            if campo_declaracion == "51. No. Factura Comercial":
                                if numero_di in self.facturas_emparejadas:
                                    valor_formulario = self.facturas_emparejadas[numero_di]
                                    resultado['Datos Formulario'] = valor_formulario
                                    
                                    factura_decl_norm = self._normalizar_factura(valor_declaracion)
                                    factura_form_norm = self._normalizar_factura(valor_formulario)
                                    coincide = factura_decl_norm == factura_form_norm
                                    
                                    resultado['Coincidencias'] = '✅ COINCIDE' if coincide else '❌ NO COINCIDE'
                                else:
                                    resultado['Datos Formulario'] = 'NO ENCONTRADO'
                                    resultado['Coincidencias'] = '❌ NO COINCIDE'
                            else:
                                encontrado = False
                                for _, anexo in anexos_correspondientes.iterrows():
                                    if tipo == "documento":
                                        valor_temp = anexo['Documento']
                                    else:
                                        valor_temp = anexo.get('Fecha', 'NO ENCONTRADO')
                                    
                                    if str(valor_declaracion).strip() == str(valor_temp).strip():
                                        resultado['Datos Formulario'] = valor_temp
                                        resultado['Coincidencias'] = '✅ COINCIDE'
                                        encontrado = True
                                        break
                                
                                if not encontrado:
                                    resultado['Datos Formulario'] = anexos_correspondientes.iloc[0]['Documento'] if tipo == "documento" else anexos_correspondientes.iloc[0].get('Fecha', 'NO ENCONTRADO')
                                    resultado['Coincidencias'] = '❌ NO COINCIDE'
            
            except Exception as e:
                resultado['Datos Formulario'] = f'ERROR: {str(e)}'
                resultado['Coincidencias'] = '❌ ERROR'
            
            resultados_validacion.append(resultado)
        
        return pd.DataFrame(resultados_validacion)

    def procesar_validacion_completa(self, carpeta_pdf, archivo_salida=None):
        """Procesa la validación completa para todas las declaraciones - VERSIÓN OPTIMIZADA"""
        
        print(f"🔍 Buscando formulario FMM...")
        archivo_formulario = self.buscar_archivo_formulario(carpeta_pdf)
        if not archivo_formulario:
            print("❌ No se puede continuar sin formulario FMM")
            return None
        
        # Extraer información del proveedor (siempre mostrar resultado)
        proveedor_ok = self.extraer_proveedor_formulario(archivo_formulario)
        if not proveedor_ok:
            print("⚠️  Continuando sin información completa del proveedor")
        
        # Extraer anexos (siempre mostrar resumen)
        anexos_formulario = self.extraer_anexos_formulario_robusto(archivo_formulario)
        
        if anexos_formulario.empty and not (self.nit_proveedor and self.nombre_proveedor):
            print("❌ No se puede continuar - Sin datos del formulario")
            return None
        
        # Procesar PDFs
        pdf_files = glob.glob(os.path.join(carpeta_pdf, "*.pdf"))
        todas_declaraciones = []
        
        for pdf_file in pdf_files:
            nombre_pdf = os.path.basename(pdf_file)
            print(f"\n📄 Procesando PDF: {nombre_pdf}")
            declaraciones_pdf = self.extraer_todas_declaraciones_pdf(pdf_file)
            print(f"📋 {len(declaraciones_pdf)} declaraciones encontradas")
            todas_declaraciones.extend(declaraciones_pdf)
        
        # Emparejar facturas
        facturas_formulario = anexos_formulario[
            anexos_formulario['Codigo'] == 6
        ]['Documento'].tolist()
        
        facturas_declaraciones = {}
        for declaracion in todas_declaraciones:
            di_num = declaracion.get('Numero_Formulario_Declaracion')
            factura = declaracion.get('51. No. Factura Comercial', 'NO ENCONTRADO')
            if di_num and factura != 'NO ENCONTRADO':
                facturas_declaraciones[di_num] = factura
        
        self.facturas_emparejadas = self._emparejar_facturas_completo(facturas_declaraciones, facturas_formulario)
        
        if not archivo_salida:
            archivo_salida = os.path.join(carpeta_pdf, "Resultado Validacion Anexos FMM vs DIM.xlsx")
        
        # Procesar validación - OPTIMIZADO
        print(f"🔍 Validando {len(todas_declaraciones)} declaraciones...")
        todos_resultados = []
        declaraciones_con_errores = 0
        
        # Limpiar cache antes de procesar
        self._cache_nombres = {}
        
        for i, declaracion in enumerate(todas_declaraciones):
            resultados_validacion = self.validar_campos_por_declaracion(declaracion, anexos_formulario)
            
            if not resultados_validacion.empty:
                # Contar declaraciones con errores
                if len(resultados_validacion[resultados_validacion['Coincidencias'] == '❌ NO COINCIDE']) > 0:
                    declaraciones_con_errores += 1
                todos_resultados.append(resultados_validacion)
            
        if todos_resultados:
            df_final = pd.concat(todos_resultados, ignore_index=True)
            
            try:
                with pd.ExcelWriter(archivo_salida, engine='openpyxl') as writer:
                    df_final.to_excel(writer, sheet_name='Validacion_Detallada', index=False)
                
                total_declaraciones = len(todas_declaraciones)
                print(f"\n" + "="*50)
                print(f"📊 RESUMEN FINAL DE VALIDACIÓN")
                print(f"="*50)
                print(f"   • Total declaraciones procesadas: {total_declaraciones}")
                print(f"   • Declaraciones con errores: {declaraciones_con_errores}")
                print(f"   • Declaraciones correctas: {total_declaraciones - declaraciones_con_errores}")
                
                if declaraciones_con_errores == 0:
                    print(f"🎯 TODAS LAS {total_declaraciones} DECLARACIONES SON CORRECTAS ✅")
                else:
                    print(f"⚠️  {declaraciones_con_errores} declaraciones requieren revisión")
                
                print(f"💾 Resultados guardados en: {archivo_salida}")
                print(f"="*50)
                
                return df_final
            except Exception as e:
                print(f"❌ Error al guardar Excel: {e}")
                return None
        
        return None

# =============================================================================
# FUNCIÓN PRINCIPAL INTEGRADA
# =============================================================================

def main():
    """Función principal que ejecuta ambos scripts integrados"""
    
    # Configuración de rutas
    CARPETA_BASE = r"E:\Users\Lenovo\Desktop\PYTHON\DI\Junior Deposito 401\SLIND 401\SLIND 401\SLI 850232"
    
    # Archivos de salida
    EXCEL_OUTPUT_COMPARACION = os.path.join(CARPETA_BASE, "Resultado Validación Subpartida vs DIM.xlsx")
    EXCEL_OUTPUT_ANEXOS = os.path.join(CARPETA_BASE, "Resultado Validacion Anexos FMM vs DIM.xlsx")
    
    try:
        print("🚀 INICIANDO PROCESO COMPLETO DE EXTRACCIÓN Y COMPARACIÓN INTEGRADO")
        print("=" * 120)
        print(f"📁 Carpeta base: {CARPETA_BASE}")
        
        # Verificar que la carpeta base existe
        if not os.path.exists(CARPETA_BASE):
            print(f"❌ La carpeta base no existe: {CARPETA_BASE}")
            return
        
        # =============================================================================
        # EJECUTAR PRIMER SCRIPT: Comparación DIM vs Subpartida
        # =============================================================================
        
        print("\n" + "="*60)
        print("📊 EJECUTANDO: Comparación DIM vs Subpartida")
        print("="*60)
        
        # Paso 1: Extraer datos de PDFs (DIAN)
        print("\n📄 EXTRACCIÓN DE DATOS DE PDFs (DIAN)...")
        extractor_dian = ExtractorDIANSimplificado()
        datos_dian = extractor_dian.procesar_multiples_dis(CARPETA_BASE)
        
        # Paso 2: Extraer datos de Excel (Subpartidas)
        print("\n📊 EXTRACCIÓN DE DATOS DE EXCEL (SUBPARTIDAS)...")
        extractor_subpartidas = ExtractorSubpartidas()
        datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(CARPETA_BASE)
        
        # Mostrar información de los datos extraídos
        if datos_dian is not None and not datos_dian.empty:
            print(f"✅ Datos DIAN extraídos: {len(datos_dian)} registros")
        else:
            print("❌ No se pudieron extraer datos DIAN")
            
        if not datos_subpartidas.empty:
            print(f"✅ Datos Subpartidas extraídos: {len(datos_subpartidas)} registros")
        else:
            print("❌ No se pudieron extraer datos de subpartidas")
        
        # Paso 3: Comparar datos
        print("\n🔍 COMPARANDO DATOS EXTRAÍDOS...")
        comparador = ComparadorDatos()
        reporte_comparacion = comparador.generar_reporte_comparacion(
            datos_dian, datos_subpartidas, EXCEL_OUTPUT_COMPARACION
        )
        
        # =============================================================================
        # EJECUTAR SEGUNDO SCRIPT: Validación Anexos FMM
        # =============================================================================
        
        print("\n" + "="*60)
        print("📋 EJECUTANDO: Validación Anexos FMM vs DIM")
        print("="*60)
        
        validador = ValidadorDeclaracionImportacionCompleto()
        resultados_anexos = validador.procesar_validacion_completa(CARPETA_BASE, EXCEL_OUTPUT_ANEXOS)
        
        # =============================================================================
        # RESUMEN FINAL
        # =============================================================================
        
        print("\n" + "="*120)
        print("🎯 PROCESO COMPLETADO EXITOSAMENTE")
        print("="*120)
        
        print(f"\n📁 ARCHIVOS GENERADOS:")
        
        if os.path.exists(EXCEL_OUTPUT_COMPARACION):
            print(f"   ✅ {EXCEL_OUTPUT_COMPARACION}")
            if datos_dian is not None:
                print(f"      • {len(datos_dian)} DI procesadas")
        
        if os.path.exists(EXCEL_OUTPUT_ANEXOS):
            print(f"   ✅ {EXCEL_OUTPUT_ANEXOS}")
            if resultados_anexos is not None:
                print(f"      • Validación de anexos completada")
        
        print(f"\n📊 RESUMEN EJECUCIÓN:")
        print(f"   • Comparación DIM vs Subpartida: {'✅ COMPLETADO' if reporte_comparacion is not None else '❌ ERROR'}")
        print(f"   • Validación Anexos FMM: {'✅ COMPLETADO' if resultados_anexos is not None else '❌ ERROR'}")
            
    except Exception as e:
        print(f"❌ Error general en la ejecución: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

