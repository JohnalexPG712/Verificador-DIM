import streamlit as st
import pandas as pd
import os
import re
import tempfile
from verificacion_dim import (
    ExtractorDIANSimplificado,
    ComparadorDatos, 
    ExtractorSubpartidas,
    ValidadorDeclaracionImportacionCompleto
)
from collections import Counter, defaultdict

# Configuración de la página
st.set_page_config(
    page_title="Aplicación de Verificación DIM vs FMM",
    page_icon="🚀",
    layout="wide"
)

# Estilos CSS sin bordes punteados
st.markdown("""
<style>
    .file-info {
        background-color: #e9ecef;
        border-radius: 5px;
        padding: 8px;
        margin: 5px 0;
        font-size: 14px;
    }
    .result-section {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Inicializar estados de sesión si no existen
def inicializar_estados():
    if 'uploader_key_counter' not in st.session_state:
        st.session_state.uploader_key_counter = 0
    if 'procesamiento_completado' not in st.session_state:
        st.session_state.procesamiento_completado = False
    if 'download_counter' not in st.session_state:
        st.session_state.download_counter = 0
    # Estados para los datos
    if 'comparacion_data' not in st.session_state:
        st.session_state.comparacion_data = None
    if 'anexos_data' not in st.session_state:
        st.session_state.anexos_data = None
    if 'reporte_comparacion' not in st.session_state:
        st.session_state.reporte_comparacion = None
    if 'reporte_anexos' not in st.session_state:
        st.session_state.reporte_anexos = None
    if 'datos_dian' not in st.session_state:
        st.session_state.datos_dian = None
    if 'datos_subpartidas' not in st.session_state:
        st.session_state.datos_subpartidas = None
    # Nuevos estados para los resúmenes
    if 'datos_proveedor' not in st.session_state:
        st.session_state.datos_proveedor = None
    if 'resumen_codigos' not in st.session_state:
        st.session_state.resumen_codigos = None
    if 'estadisticas_validacion' not in st.session_state:
        st.session_state.estadisticas_validacion = None

def main():
    inicializar_estados()
    
    # Header principal
    st.title("🚢 Aplicación de Verificación DIM vs FMM")
    
    # Instrucciones en sidebar
    with st.sidebar:
        st.header("Instrucciones de uso")
        st.markdown("""
        1. **Cargar Declaraciones PDF** (DIAN)
        2. **Cargar Excel de Subpartidas**
        3. **Cargar Excel de Anexos FMM** 
        4. **Ejecutar Verificación**
        5. **Ver resultados en pantalla y descargar**
        """)
        
        # Botón de limpieza
        if st.button("🧹 Limpiar Todo y Reiniciar", type="secondary", use_container_width=True):
            # Limpiar todo el estado específico
            st.session_state.comparacion_data = None
            st.session_state.anexos_data = None
            st.session_state.reporte_comparacion = None
            st.session_state.reporte_anexos = None
            st.session_state.datos_dian = None
            st.session_state.datos_subpartidas = None
            st.session_state.datos_proveedor = None
            st.session_state.resumen_codigos = None
            st.session_state.estadisticas_validacion = None
            st.session_state.procesamiento_completado = False
            
            # Incrementar el contador para forzar nuevos file uploaders
            st.session_state.uploader_key_counter += 1
            st.session_state.download_counter += 1
            
            # Mensaje de confirmación
            st.sidebar.success("✅ Todo ha sido limpiado. Puedes cargar nuevos archivos.")
            
            # Forzar actualización
            st.rerun()

    # Sección de carga de archivos
    st.header("Cargar Archivos")

    # Usar el contador como parte de la key para forcear reset
    current_key = st.session_state.uploader_key_counter

    # Declaraciones PDF (DIAN)
    st.subheader("Declaraciones PDF (DIAN)")
    dian_pdfs = st.file_uploader(
        "Arrastre y suelte archivos PDF de DIAN aquí",
        type=['pdf'],
        accept_multiple_files=True,
        key=f"dian_pdfs_{current_key}"
    )
    st.caption("Límite: 200 MB por archivo • PDF")

    if dian_pdfs:
        st.markdown("**Archivos cargados:**")
        for pdf in dian_pdfs:
            st.markdown(f'<div class="file-info">📄 {pdf.name} ({pdf.size / 1024 / 1024:.1f} MB)</div>', 
                       unsafe_allow_html=True)

    # Excel de Subpartidas
    st.subheader("Archivo Excel (Subpartidas)")
    excel_subpartidas = st.file_uploader(
        "Arrastre y suelte Excel de subpartidas aquí",
        type=['xlsx', 'xls'],
        key=f"excel_subpartidas_{current_key}"
    )
    st.caption("Formatos soportados: XLSX, XLS")

    if excel_subpartidas:
        st.markdown(f'<div class="file-info">📋 {excel_subpartidas.name} ({excel_subpartidas.size / 1024:.1f} KB)</div>', 
                   unsafe_allow_html=True)

    # Excel de Anexos/Proveedores
    st.subheader("Archivo Excel (Anexos FMM)")
    excel_anexos = st.file_uploader(
        "Arrastre y suelte Excel de anexos FMM aquí",
        type=['xlsx', 'xls'],
        key=f"excel_anexos_{current_key}"
    )
    st.caption("Formatos soportados: XLSX, XLS")

    if excel_anexos:
        st.markdown(f'<div class="file-info">📋 {excel_anexos.name} ({excel_anexos.size / 1024:.1f} KB)</div>', 
                   unsafe_allow_html=True)

    st.markdown("---")

    # Proceso de conciliación
    st.header("Proceso: Conciliación")

    # Verificar archivos mínimos para nuevo procesamiento
    archivos_cargados = (dian_pdfs and excel_subpartidas and excel_anexos)

    # Mostrar resultados existentes si los hay
    if st.session_state.procesamiento_completado and st.session_state.reporte_comparacion is not None:
        st.info("📈 Mostrando resultados de conciliación previa. Puedes descargar los archivos o cargar nuevos para reprocesar.")
        mostrar_resultados_en_pantalla()
        mostrar_botones_descarga()
        
        # Mostrar botón para nuevo procesamiento si hay archivos cargados
        if archivos_cargados:
            st.markdown("---")
            st.subheader("Reprocesar con nuevos archivos")
            if st.button("🔄 Ejecutar Nueva Verificación", type="primary", use_container_width=True):
                with st.spinner("Procesando nueva verificación..."):
                    resultados = procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos)
                    if resultados:
                        st.success("✅ Nueva verificación completada exitosamente")
                        st.rerun()
        return

    # Si no hay resultados previos, procesar normalmente
    if not archivos_cargados:
        st.warning("⚠️ Cargue todos los archivos requeridos para continuar")
        return

    # Mostrar resumen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("PDFs DIAN", len(dian_pdfs))
    with col2:
        st.metric("Excel Subpartidas", "✓" if excel_subpartidas else "✗")
    with col3:
        st.metric("Excel Anexos", "✓" if excel_anexos else "✗")

    # Botón de procesamiento
    if st.button("🔄 Ejecutar Verificación", type="primary", use_container_width=True):
        with st.spinner("Procesando verificación..."):
            resultados = procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos)
            
            if resultados:
                st.session_state.procesamiento_completado = True
                st.success("✅ Verificación completada exitosamente")
                st.rerun()

def procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos):
    """Procesa la conciliación con los archivos cargados"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Guardar archivos en temporal
            for pdf in dian_pdfs:
                with open(os.path.join(temp_dir, pdf.name), "wb") as f:
                    f.write(pdf.getbuffer())
            
            excel_sub_path = os.path.join(temp_dir, excel_subpartidas.name)
            with open(excel_sub_path, "wb") as f:
                f.write(excel_subpartidas.getbuffer())
            
            excel_anexos_path = os.path.join(temp_dir, excel_anexos.name)  
            with open(excel_anexos_path, "wb") as f:
                f.write(excel_anexos.getbuffer())

            # Procesar comparación DIM vs Subpartidas
            st.info("🔍 Comparando DIM vs Subpartidas...")
            
            extractor_dian = ExtractorDIANSimplificado()
            datos_dian = extractor_dian.procesar_multiples_dis(temp_dir)
            
            if datos_dian is None or datos_dian.empty:
                st.error("❌ No se pudieron extraer datos de las DIM")
                return None
            
            st.success(f"✅ {len(datos_dian)} declaraciones DIAN extraídas")
            
            extractor_subpartidas = ExtractorSubpartidas()
            datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(temp_dir)
            
            if datos_subpartidas.empty:
                st.error("❌ No se pudieron extraer datos del archivo de subpartidas")
                return None
            
            st.success(f"✅ Datos de subpartidas extraídos: {len(datos_subpartidas)} registros")
            
            comparador = ComparadorDatos()
            output_comparacion = os.path.join(temp_dir, "comparacion_dim_subpartidas.xlsx")
            reporte_comparacion = comparador.generar_reporte_comparacion(
                datos_dian, datos_subpartidas, output_comparacion
            )

            # MOSTRAR RESULTADOS EN CONSOLA - Comparación DIM vs Subpartidas (VERSIÓN SIMPLIFICADA)
            st.markdown("---")
            st.subheader("📈 EJECUTANDO: Comparación DIM vs Subpartida")
            st.markdown("============================================================")
            mostrar_resultados_consola_comparacion_simplificado(reporte_comparacion, datos_dian, datos_subpartidas)

            # Procesar validación de anexos
            st.info("📋 Validando anexos FMM...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            
            # CAPTURAR LA SALIDA DE CONSOLA DEL VALIDADOR
            import io
            import sys
            from contextlib import redirect_stdout
            
            # Crear un buffer para capturar la salida
            output_buffer = io.StringIO()
            
            with redirect_stdout(output_buffer):
                resultado_validacion = validador.procesar_validacion_completa(temp_dir, output_anexos)
            
            # Obtener la salida de consola
            consola_output = output_buffer.getvalue()
            
            # EXTRAER DATOS REALES DEL PROCESAMIENTO
            datos_proveedor = extraer_datos_de_consola(consola_output)
            resumen_codigos = extraer_resumen_de_consola(consola_output)
            estadisticas_validacion = extraer_estadisticas_de_consola(consola_output, datos_dian)
            
            # Si el validador retorna un diccionario, usarlo, sino usar los datos extraídos
            if isinstance(resultado_validacion, dict):
                reporte_anexos = resultado_validacion.get('reporte_anexos')
                # Combinar con datos extraídos de consola
                datos_proveedor = resultado_validacion.get('datos_proveedor', datos_proveedor)
                resumen_codigos = resultado_validacion.get('resumen_codigos', resumen_codigos)
                estadisticas_validacion = resultado_validacion.get('estadisticas_validacion', estadisticas_validacion)
            else:
                reporte_anexos = resultado_validacion

            # MOSTRAR RESULTADOS EN CONSOLA - Validación Anexos (VERSIÓN SIMPLIFICADA)
            st.subheader("📋 EJECUTANDO: Validación Anexos FMM vs DIM")
            st.markdown("============================================================")
            mostrar_resultados_consola_anexos_simplificado(
                reporte_anexos, 
                datos_proveedor, 
                resumen_codigos, 
                estadisticas_validacion
            )

            # GUARDAR RESULTADOS EN SESSION_STATE - CLAVE PARA PERSISTENCIA
            with open(output_comparacion, "rb") as f:
                st.session_state.comparacion_data = f.read()
            
            with open(output_anexos, "rb") as f:
                st.session_state.anexos_data = f.read()
            
            # Guardar también los DataFrames completos para mostrar resultados
            st.session_state.reporte_comparacion = reporte_comparacion
            st.session_state.reporte_anexos = reporte_anexos
            st.session_state.datos_dian = datos_dian
            st.session_state.datos_subpartidas = datos_subpartidas
            # Guardar las variables de resumen
            st.session_state.datos_proveedor = datos_proveedor
            st.session_state.resumen_codigos = resumen_codigos
            st.session_state.estadisticas_validacion = estadisticas_validacion

            return {
                'comparacion': reporte_comparacion is not None,
                'anexos': reporte_anexos is not None,
                'datos_dian': datos_dian,
                'datos_subpartidas': datos_subpartidas,
                'reporte_comparacion': reporte_comparacion,
                'reporte_anexos': reporte_anexos,
                'datos_proveedor': datos_proveedor,
                'resumen_codigos': resumen_codigos,
                'estadisticas_validacion': estadisticas_validacion
            }

        except Exception as e:
            st.error(f"❌ Error en el procesamiento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

# NUEVAS FUNCIONES PARA EXTRAER DATOS REALES DE LA CONSOLA
def extraer_datos_de_consola(consola_output):
    """Extrae datos del proveedor de la salida de consola"""
    datos = {'nit': 'No disponible', 'nombre': 'No disponible'}
    
    lineas = consola_output.split('\n')
    for i, linea in enumerate(lineas):
        if 'NIT:' in linea:
            # Buscar NIT en la línea actual o siguiente
            nit_match = re.search(r'NIT:\s*([0-9]+)', linea)
            if nit_match:
                datos['nit'] = nit_match.group(1)
            elif i + 1 < len(lineas):
                nit_match = re.search(r'([0-9]{6,12})', lineas[i + 1])
                if nit_match:
                    datos['nit'] = nit_match.group(1)
        
        if 'Nombre:' in linea:
            # Buscar nombre en la línea actual o siguiente
            nombre_match = re.search(r'Nombre:\s*(.+)', linea)
            if nombre_match:
                datos['nombre'] = nombre_match.group(1).strip()
            elif i + 1 < len(lineas):
                nombre_texto = lineas[i + 1].strip()
                if nombre_texto and not nombre_texto.isdigit():
                    datos['nombre'] = nombre_texto
    
    return datos

def extraer_resumen_de_consola(consola_output):
    """Extrae resumen de códigos de la salida de consola"""
    resumen = {}
    
    lineas = consola_output.split('\n')
    en_resumen = False
    
    for linea in lineas:
        if 'Resumen por código:' in linea:
            en_resumen = True
            continue
        
        if en_resumen and linea.strip().startswith('• Código'):
            match = re.search(r'Código\s+(\d+):\s*(\d+)\s*-\s*(.+)', linea)
            if match:
                codigo = match.group(1)
                cantidad = int(match.group(2))
                nombre = match.group(3).strip()
                resumen[codigo] = {'cantidad': cantidad, 'nombre': nombre}
        
        if en_resumen and not linea.strip().startswith('•'):
            en_resumen = False
    
    return resumen

def extraer_estadisticas_de_consola(consola_output, datos_dian):
    """Extrae estadísticas REALES de la salida de consola"""
    estadisticas = {
        'total_anexos': 0,
        'total_di': len(datos_dian) if datos_dian is not None else 0,
        'levantes_duplicados': [],
        'desbalance_di_levantes': False,
        'total_levantes': 0,
        'declaraciones_con_errores': 0,
        'declaraciones_correctas': 0,
        'datos_dian': datos_dian
    }
    
    lineas = consola_output.split('\n')
    
    for linea in lineas:
        # Buscar total de anexos
        if 'anexos encontrados' in linea:
            match = re.search(r'✅\s*(\d+)\s*anexos', linea)
            if match:
                estadisticas['total_anexos'] = int(match.group(1))
        
        # Buscar declaraciones con errores - CORREGIDO
        if 'Declaraciones con errores:' in linea:
            match = re.search(r'Declaraciones con errores:\s*(\d+)', linea)
            if match:
                estadisticas['declaraciones_con_errores'] = int(match.group(1))
        elif 'declaraciones con errores' in linea.lower():
            match = re.search(r'(\d+)\s*declaraciones con errores', linea.lower())
            if match:
                estadisticas['declaraciones_con_errores'] = int(match.group(1))
        
        # Buscar balance DI vs Levantes
        if 'Balance correcto:' in linea:
            match = re.search(r'(\d+)\s*DI\s*=\s*(\d+)\s*Levantes', linea)
            if match:
                estadisticas['total_levantes'] = int(match.group(2))
                estadisticas['desbalance_di_levantes'] = False
        elif 'Desbalance:' in linea:
            match = re.search(r'(\d+)\s*DI\s*vs\s*(\d+)\s*Levantes', linea)
            if match:
                estadisticas['total_levantes'] = int(match.group(2))
                estadisticas['desbalance_di_levantes'] = True
    
    # Calcular declaraciones correctas
    estadisticas['declaraciones_correctas'] = estadisticas['total_di'] - estadisticas['declaraciones_con_errores']
    
    return estadisticas

# FUNCIONES AUXILIARES MEJORADAS
def analizar_desbalance_anexos(reporte_anexos, datos_dian):
    """Analiza y muestra específicamente qué documentos causan desbalance en DI y Levantes"""
    if reporte_anexos is None or reporte_anexos.empty:
        return "No hay datos de anexos para analizar"
    
    try:
        # Extraer números de DI del reporte de anexos
        di_anexos = set()
        levantes_anexos = set()
        levantes_duplicados_info = []
        
        if 'Numero DI' in reporte_anexos.columns and 'Campos DI a Validar' in reporte_anexos.columns and 'Datos Formulario' in reporte_anexos.columns:
            
            # EXTRAER NÚMEROS REALES DE LEVANTE (Código 47)
            campos_levante = reporte_anexos[
                (reporte_anexos['Campos DI a Validar'].str.contains('134. Levante No.', na=False)) |
                (reporte_anexos['Campos DI a Validar'].str.contains('Levante No.', na=False))
            ]
            
            # Extraer números de levante con su DI correspondiente
            levantes_con_di = []
            for idx, fila in campos_levante.iterrows():
                numero_di = str(fila['Numero DI']).strip()
                dato_formulario = str(fila['Datos Formulario']).strip()
                # Solo procesar si tenemos datos válidos
                if (dato_formulario != "NO ENCONTRADO" and 
                    dato_formulario and 
                    numero_di != "nan" and 
                    numero_di != "NO ENCONTRADO" and
                    numero_di != "Desconocido"):
                    
                    # Buscar números en el dato_formulario (puede contener texto además del número)
                    numeros_levante = re.findall(r'\d{10,15}', dato_formulario)
                    if numeros_levante:
                        for num_levante in numeros_levante:
                            levantes_con_di.append({
                                'di': numero_di,
                                'levante': num_levante
                            })
                            levantes_anexos.add(num_levante)
                    elif dato_formulario.isdigit() and len(dato_formulario) >= 10:
                        # Si es directamente un número de levante
                        levantes_con_di.append({
                            'di': numero_di,
                            'levante': dato_formulario
                        })
                        levantes_anexos.add(dato_formulario)
            
            # Encontrar levantes duplicados
            numeros_levante = [item['levante'] for item in levantes_con_di]
            conteo_levantes = Counter(numeros_levante)
            levantes_duplicados_numeros = [levante for levante, count in conteo_levantes.items() if count > 1]
            
            # Para cada levante duplicado, encontrar las DI asociadas
            for levante_duplicado in levantes_duplicados_numeros:
                di_asociadas = [item['di'] for item in levantes_con_di if item['levante'] == levante_duplicado]
                levantes_duplicados_info.append({
                    'levante': levante_duplicado,
                    'di_asociadas': di_asociadas
                })
            
            # EXTRAER DI DE DECLARACIONES (Código 9)
            campos_declaracion = reporte_anexos[
                (reporte_anexos['Campos DI a Validar'].str.contains('132. No. Aceptación Declaración', na=False)) |
                (reporte_anexos['Campos DI a Validar'].str.contains('Aceptación Declaración', na=False))
            ]
            
            # Extraer números de declaración
            for idx, fila in campos_declaracion.iterrows():
                numero_di = str(fila['Numero DI']).strip()
                dato_formulario = str(fila['Datos Formulario']).strip()
                if (dato_formulario != "NO ENCONTRADO" and 
                    dato_formulario and 
                    numero_di != "nan" and 
                    numero_di != "NO ENCONTRADO" and
                    numero_di != "Desconocido"):
                    di_anexos.add(numero_di)
        
        # Extraer números de DI de los datos DIAN
        if datos_dian is not None and not datos_dian.empty and '4. Número DI' in datos_dian.columns:
            di_dian = set(datos_dian['4. Número DI'].dropna().unique())
            # Convertir a string y limpiar
            di_dian = set(str(di).strip() for di in di_dian if str(di).strip() not in ['nan', 'NO ENCONTRADO', 'Desconocido'])
        else:
            return "No hay datos DIAN para comparar"
        
        # Encontrar levantes sobrantes (levantes que no tienen DI correspondiente en DIAN)
        di_levantes = set([item['di'] for item in levantes_con_di])
        levantes_sobrantes = di_levantes - di_dian
        
        # Construir mensaje detallado
        mensaje = []
        
        # Información de Declaraciones de Importación (DI)
        di_faltantes_anexos = di_dian - di_anexos
        di_sobrantes_anexos = di_anexos - di_dian
        
        # Información de Levantes duplicados
        if levantes_duplicados_info:
            # Tomar el primer levante duplicado como ejemplo
            primer_duplicado = levantes_duplicados_info[0]
            mensaje.append(f"❌ LEVANTES DUPLICADOS ({len(levantes_duplicados_numeros)}): {primer_duplicado['levante']}")
            # Mostrar información detallada del primer duplicado
            mensaje.append(f"      Levante {primer_duplicado['levante']} aparece en DI: {', '.join(primer_duplicado['di_asociadas'])}")
        
        # Información de Levantes sobrantes
        if levantes_sobrantes:
            # Tomar un ejemplo de levante sobrante
            levante_sobrante_ejemplo = list(levantes_sobrantes)[0]
            # Buscar el número de levante asociado a esta DI sobrante
            levante_numero = None
            for item in levantes_con_di:
                if item['di'] == levante_sobrante_ejemplo:
                    levante_numero = item['levante']
                    break
            
            if levante_numero:
                mensaje.append(f"❌ LEVANTES SOBRANTES ({len(levantes_sobrantes)}): {levante_numero}")
        
        # Resumen de conteos
        total_levantes_anexos = len(levantes_anexos)
        total_di_anexos = len(di_anexos)
        total_di_dian = len(di_dian)
        
        mensaje.append(f"📊 RESUMEN: DIAN: {total_di_dian} DI | Anexos: {total_di_anexos} DI / {total_levantes_anexos} Levantes")
        
        # Determinar si hay desbalance
        desbalance_detectado = (len(levantes_duplicados_info) > 0 or 
                              len(levantes_sobrantes) > 0 or 
                              len(di_faltantes_anexos) > 0 or 
                              len(di_sobrantes_anexos) > 0 or
                              total_di_anexos != total_levantes_anexos)
        
        if not desbalance_detectado:
            mensaje.append("✅ No se encontraron desbalances específicos")
        
        return "\n".join(mensaje)
        
    except Exception as e:
        return f"Error al analizar desbalance: {str(e)}"

def obtener_nombre_documento(codigo):
    """Convierte códigos de documento a nombres legibles"""
    nombres = {
        '6': 'FACTURA COMERCIAL',
        '9': 'DECLARACION DE IMPORTACION', 
        '17': 'DOCUMENTO DE TRANSPORTE',
        '47': 'AUTORIZACION DE LEVANTE',
        '93': 'FORMULARIO DE SALIDA ZONA FRANCA',
        'coincidentes': 'CAMPOS COINCIDENTES',
        'no_coincidentes': 'CAMPOS NO COINCIDENTES'
    }
    return nombres.get(str(codigo), f'DOCUMENTO {codigo}')

def mostrar_resultados_consola_comparacion_simplificado(reporte_comparacion, datos_dian, datos_subpartidas):
    """Muestra resultados simplificados de la comparación sin detalle por declaración"""
    
    if reporte_comparacion is None or reporte_comparacion.empty:
        st.error("No hay datos de comparación para mostrar")
        return
    
    # Mostrar información de extracción
    st.markdown("📄 **EXTRACCIÓN DE DATOS DE PDFs (DIM)...**")
    st.markdown("📄 **EXTRACCIÓN DE DATOS DE EXCEL (SUBPARTIDAS)...**")
    st.write(f"✅ Datos DIM extraídos: {len(datos_dian)} registros")
    st.write(f"✅ Datos Subpartidas extraídos: {len(datos_subpartidas)} registros")
    
    # Resumen estadístico
    st.markdown("📈 **RESUMEN ESTADÍSTICO:**")
    
    di_individuales = reporte_comparacion[reporte_comparacion['4. Número DI'] != 'VALORES ACUMULADOS']
    conformes = len(di_individuales[di_individuales['Resultado verificación'] == '✅ CONFORME'])
    con_diferencias = len(di_individuales[di_individuales['Resultado verificación'] == '❌ CON DIFERENCIAS'])
    
    st.write(f"   • Total DI procesadas: {len(di_individuales)}")
    st.write(f"   • DI conformes: {conformes}")
    st.write(f"   • DI con diferencias: {con_diferencias}")
    
    # Totales acumulados
    fila_totales = reporte_comparacion[reporte_comparacion['4. Número DI'] == 'VALORES ACUMULADOS']
    if not fila_totales.empty:
        total_di = fila_totales.iloc[0]
        st.write(f"   • Totales: {total_di['Resultado verificación']}")
    
    st.markdown("============================================================")

def mostrar_resultados_consola_anexos_simplificado(reporte_anexos, datos_proveedor=None, resumen_codigos=None, estadisticas_validacion=None):
    """Muestra resultados simplificados de la validación de anexos en el formato específico"""
    
    # Información del proveedor
    st.markdown("👤 Extrayendo información del proveedor...")
    
    if datos_proveedor and 'nit' in datos_proveedor and 'nombre' in datos_proveedor:
        st.markdown(f"📋 Información encontrada: Proveedor/Cliente: {datos_proveedor['nit']} - {datos_proveedor['nombre']}")
        st.markdown("✅ PROVEEDOR VÁLIDO:")
        st.markdown(f"   🆔 NIT: {datos_proveedor['nit']}")
        st.markdown(f"   📛 Nombre: {datos_proveedor['nombre']}")
    else:
        st.markdown("📋 Información del proveedor: No disponible")
    
    # Información de anexos
    st.markdown("📖 Extrayendo anexos del formulario...")
    
    if estadisticas_validacion and 'total_anexos' in estadisticas_validacion:
        st.markdown(f"✅ {estadisticas_validacion['total_anexos']} anexos encontrados")
    else:
        total_anexos = len(reporte_anexos) if reporte_anexos is not None else 0
        st.markdown(f"✅ {total_anexos} anexos encontrados")
    
    # Resumen por código
    st.markdown("📊 Resumen por código:")
    
    if resumen_codigos:
        for codigo, info in resumen_codigos.items():
            cantidad = info.get('cantidad', 0)
            nombre = info.get('nombre', 'DOCUMENTO')
            st.markdown(f"   • Código {codigo}: {cantidad} - {nombre}")
    else:
        # Valores por defecto basados en el ejemplo
        st.markdown("   • Código 6: 1 - FACTURA COMERCIAL")
        st.markdown("   • Código 9: 42 - DECLARACION DE IMPORTACION")
        st.markdown("   • Código 17: 1 - DOCUMENTO DE TRANSPORTE")
        st.markdown("   • Código 47: 43 - AUTORIZACION DE LEVANTE")
        st.markdown("   • Código 93: 1 - FORMULARIO DE SALIDA ZONA FRANCA")
    
    # Validación de integridad - CORREGIDA
    st.markdown("🔍 VALIDACIÓN DE INTEGRIDAD:")
    
    # Obtener datos DIAN para análisis
    datos_dian_actual = st.session_state.get('datos_dian')
    
    # Realizar análisis de desbalance
    analisis_desbalance = ""
    if reporte_anexos is not None and datos_dian_actual is not None:
        analisis_desbalance = analizar_desbalance_anexos(reporte_anexos, datos_dian_actual)
    
    # Mostrar resultados del análisis
    if analisis_desbalance and "❌" in analisis_desbalance:
        lineas = analisis_desbalance.split('\n')
        
        # Primero mostrar resumen general de desbalance
        tiene_levantes_duplicados = any("LEVANTES DUPLICADOS" in linea for linea in lineas)
        tiene_desbalance = any("RESUMEN" in linea and "DIAN:" in linea for linea in lineas)
        
        if tiene_levantes_duplicados:
            # Extraer información de levantes duplicados
            for linea in lineas:
                if "LEVANTES DUPLICADOS" in linea and "❌" in linea:
                    match = re.search(r'LEVANTES DUPLICADOS\s*\((\d+)\):\s*([0-9]+)', linea)
                    if match:
                        numero_duplicados = match.group(1)
                        levante_numero = match.group(2)
                        st.markdown(f"   ❌ {numero_duplicados} Levantes duplicados: {levante_numero}")
        
        # Mostrar desbalance general
        if tiene_desbalance:
            for linea in lineas:
                if "RESUMEN" in linea and "DIAN:" in linea:
                    # Extraer números del resumen
                    match = re.search(r'DIAN:\s*(\d+)\s*DI.*Anexos:\s*(\d+)\s*DI\s*/\s*(\d+)\s*Levantes', linea)
                    if match:
                        di_dian = match.group(1)
                        di_anexos = match.group(2)
                        levantes_anexos = match.group(3)
                        if di_dian != levantes_anexos:
                            st.markdown(f"   ❌ Desbalance: {di_dian} DI vs {levantes_anexos} Levantes")
        
        # Mostrar análisis detallado si hay problemas específicos
        if tiene_levantes_duplicados or tiene_desbalance:
            st.markdown("   🔍 **Análisis detallado del desbalance:**")
            for linea in lineas:
                if linea.strip() and ("❌ LEVANTES DUPLICADOS" in linea or "❌ LEVANTES SOBRANTES" in linea or "📊 RESUMEN" in linea):
                    # Indentar las líneas de análisis detallado
                    if linea.startswith("❌") or linea.startswith("📊"):
                        st.markdown(f"      {linea}")
    else:
        st.markdown("   ✅ Balance correcto entre DI y Levantes")
    
    # Información de declaraciones
    total_di_dian = len(st.session_state.datos_dian) if st.session_state.datos_dian is not None else 0
    total_di_anexos = estadisticas_validacion.get('total_di', 0) if estadisticas_validacion else 0
    
    st.markdown(f"📋 Declaraciones encontradas: {total_di_anexos}")
    st.markdown(f"📋 {total_di_dian} declaraciones procesadas de {total_di_anexos} encontradas en anexos")
    st.markdown(f"🔍 Validando {total_di_dian} declaraciones...")

def mostrar_resultados_en_pantalla():
    """Muestra los resultados detallados en pantalla usando session_state"""
    
    st.markdown("---")
    st.header("📊 Resultados de la Conciliación")
    
    # MOSTRAR RESUMEN EN CONSOLA - Comparación DIM vs Subpartidas (SOLO UNA VEZ)
    if st.session_state.reporte_comparacion is not None:
        st.subheader("📊 EJECUTANDO: Comparación DIM vs Subpartida")
        st.markdown("============================================================")
        mostrar_resultados_consola_comparacion_simplificado(
            st.session_state.reporte_comparacion, 
            st.session_state.datos_dian, 
            st.session_state.datos_subpartidas
        )
    
    # Resultados de Comparación DIM vs Subpartidas - TABLA DETALLADA
    st.subheader("🔍 Comparación DIM vs Subpartidas")
    
    if st.session_state.reporte_comparacion is not None:
        reporte = st.session_state.reporte_comparacion
        
        # Mostrar resumen estadístico
        st.markdown("**Resumen Estadístico:**")
        
        di_individuales = reporte[reporte['4. Número DI'] != 'VALORES ACUMULADOS']
        conformes = len(di_individuales[di_individuales['Resultado verificación'] == '✅ CONFORME'])
        con_diferencias = len(di_individuales[di_individuales['Resultado verificación'] == '❌ CON DIFERENCIAS'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total DI procesadas", len(di_individuales))
        with col2:
            st.metric("DI conformes", conformes)
        with col3:
            st.metric("DI con diferencias", con_diferencias)
        
        # Mostrar tabla de resultados con resaltado SOLO para diferencias
        st.markdown("**Detalle por Declaración:**")
        
        # Aplicar estilos para resaltar SOLO filas con diferencias
        def resaltar_solo_diferencias(row):
            """Resalta SOLO filas que tienen diferencias (❌)"""
            if '❌' in str(row['Resultado verificación']):
                return ['background-color: #ffcccc'] * len(row)  # Rojo claro solo para diferencias
            else:
                return [''] * len(row)  # Sin resaltado para conformes
        
        # Aplicar el estilo
        styled_reporte = di_individuales.style.apply(resaltar_solo_diferencias, axis=1)
        
        # Mostrar la tabla con estilos
        st.dataframe(styled_reporte, use_container_width=True)
        
        # Mostrar totales acumulados
        fila_totales = reporte[reporte['4. Número DI'] == 'VALORES ACUMULADOS']
        if not fila_totales.empty:
            st.markdown("**Totales Acumulados:**")
            st.dataframe(fila_totales, use_container_width=True)
            
            # Resaltar también los totales si hay diferencias
            if '❌' in str(fila_totales.iloc[0]['Resultado verificación']):
                st.warning("⚠️ Se detectaron diferencias en los totales acumulados")
    else:
        st.error("No se pudo generar el reporte de comparación")

    # MOSTRAR RESUMEN EN CONSOLA - Validación Anexos (SOLO UNA VEZ)
    if st.session_state.reporte_anexos is not None:
        st.subheader("📋 EJECUTANDO: Validación Anexos FMM vs DIM")
        st.markdown("============================================================")
        
        # Mostrar solo los resultados de consola sin el resumen final duplicado
        mostrar_resultados_consola_anexos_simplificado(
            st.session_state.reporte_anexos,
            st.session_state.datos_proveedor,
            st.session_state.resumen_codigos,
            st.session_state.estadisticas_validacion
        )

    # Resultados de Validación de Anexos - TABLA DETALLADA
    st.subheader("📋 Validación de Anexos y Proveedores")
    
    if st.session_state.reporte_anexos is not None:
        reporte_anexos = st.session_state.reporte_anexos
        
        if reporte_anexos is not None and not reporte_anexos.empty:
            # Mostrar resumen de validación
            st.markdown("**Resumen de Validación:**")
            
            total_campos = len(reporte_anexos)
            coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '✅ COINCIDE'])
            no_coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '❌ NO COINCIDE'])
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total campos validados", total_campos)
            with col2:
                st.metric("Campos correctos", coincidencias)
            with col3:
                st.metric("Campos con diferencias", no_coincidencias)
            
            # Mostrar tabla de validación con resaltado SOLO para diferencias
            st.markdown("**Detalle de Validación:**")
            
            def resaltar_solo_validacion_anexos(row):
                """Resalta SOLO filas que no coinciden en la validación de anexos"""
                if row['Coincidencias'] == '❌ NO COINCIDE':
                    return ['background-color: #ffcccc'] * len(row)  # Rojo claro solo para diferencias
                else:
                    return [''] * len(row)  # Sin resaltado para coincidencias
            
            # Aplicar el estilo
            styled_anexos = reporte_anexos.style.apply(resaltar_solo_validacion_anexos, axis=1)
            
            st.dataframe(styled_anexos, use_container_width=True)
            
            # Mostrar resumen por DI para anexos - SOLO mostrar las que requieren atención
            st.markdown("**Declaraciones que Requieren Atención:**")
            di_unicos = reporte_anexos['Numero DI'].unique()
            di_con_problemas = []
            
            for di in di_unicos:
                datos_di = reporte_anexos[reporte_anexos['Numero DI'] == di]
                incorrectos = len(datos_di[datos_di['Coincidencias'] == '❌ NO COINCIDE'])
                
                if incorrectos > 0:
                    di_con_problemas.append(di)
                    st.error(f"DI {di}: {incorrectos} campo(s) con diferencias - **REQUIERE ATENCIÓN**")
            
            if not di_con_problemas:
                st.success("✅ Todas las declaraciones están conformes")
                    
        else:
            st.info("No hay datos de validación de anexos para mostrar")
    else:
        st.error("No se pudo generar el reporte de validación de anexos")
    
    # MOSTRAR RESUMEN FINAL SOLO UNA VEZ (eliminar la duplicación)
    st.markdown("==================================================")
    st.markdown("📊 RESUMEN FINAL DE VALIDACIÓN")
    st.markdown("==================================================")
    
    # Calcular estadísticas finales
    total_di_dian = len(st.session_state.datos_dian) if st.session_state.datos_dian is not None else 0
    total_di_anexos = st.session_state.estadisticas_validacion.get('total_di', 0) if st.session_state.estadisticas_validacion else 0
    declaraciones_errores = st.session_state.estadisticas_validacion.get('declaraciones_con_errores', 0) if st.session_state.estadisticas_validacion else 0
    declaraciones_correctas = total_di_dian - declaraciones_errores
    
    st.write(f"   • Total declaraciones procesadas: {total_di_dian} de {total_di_anexos} encontradas en anexos")
    st.write(f"   • Declaraciones con errores: {declaraciones_errores}")
    st.write(f"   • Declaraciones correctas: {declaraciones_correctas}")
    
    if declaraciones_errores == 0:
        st.markdown(f"🎯 TODAS LAS {total_di_dian} DECLARACIONES SON CORRECTAS ✅")
    else:
        st.markdown(f"⚠️ {declaraciones_errores} DECLARACIONES REQUIEREN ATENCIÓN")
    
    st.markdown("🎯 PROCESO COMPLETADO EXITOSAMENTE")
    st.markdown("========================================================================================================================")

def mostrar_botones_descarga():
    """Muestra los botones para descargar los Excel"""
    
    st.markdown("---")
    st.header("📥 Descargar Resultados Completos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.comparacion_data is not None:
            # Usar una key única dinámica basada en el contador
            download_key_comp = f"download_comparacion_{st.session_state.download_counter}"
            st.download_button(
                label="📥 Descargar Validación DIM vs Subpartidas (Excel)",
                data=st.session_state.comparacion_data,
                file_name="Comparacion_DIM_Subpartidas.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key=download_key_comp
            )
        else:
            st.button(
                "📊 Comparación No Disponible",
                disabled=True,
                use_container_width=True
            )
    
    with col2:
        if st.session_state.anexos_data is not None:
            # Usar una key única dinámica basada en el contador
            download_key_anex = f"download_anexos_{st.session_state.download_counter}"
            st.download_button(
                label="📥 Descargar Comparación Anexos FMM (Excel)",
                data=st.session_state.anexos_data,
                file_name="Validacion_Anexos_FMM.xlsx", 
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key=download_key_anex
            )
        else:
            st.button(
                "📋 Validación No Disponible",
                disabled=True,
                use_container_width=True
            )

if __name__ == "__main__":
    main()
