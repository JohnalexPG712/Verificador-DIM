import streamlit as st
import pandas as pd
import os
import re
import tempfile
import io
import sys
from contextlib import redirect_stdout

# Importamos las clases del script optimizado
from verificacion_dim import (
    ExtractorDIANSimplificado,
    ComparadorDatos, 
    ExtractorSubpartidas,
    ValidadorDeclaracionImportacionCompleto
)

# Configuración de la página
st.set_page_config(
    page_title="SmartDIM",
    page_icon="🚀",
    layout="wide"
)

# Estilos CSS sin bordes punteados (Visualización exacta solicitada)
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

# Inicializar estados de sesión
def inicializar_estados():
    if 'uploader_key_counter' not in st.session_state:
        st.session_state.uploader_key_counter = 0
    if 'procesamiento_completado' not in st.session_state:
        st.session_state.procesamiento_completado = False
    if 'download_counter' not in st.session_state:
        st.session_state.download_counter = 0
    # Estados para los datos binarios (Excel)
    if 'comparacion_data' not in st.session_state:
        st.session_state.comparacion_data = None
    if 'anexos_data' not in st.session_state:
        st.session_state.anexos_data = None
    # DataFrames y Objetos
    if 'reporte_comparacion' not in st.session_state:
        st.session_state.reporte_comparacion = None
    if 'reporte_anexos' not in st.session_state:
        st.session_state.reporte_anexos = None
    if 'datos_dian' not in st.session_state:
        st.session_state.datos_dian = None
    if 'datos_subpartidas' not in st.session_state:
        st.session_state.datos_subpartidas = None
    # Resúmenes de Validación
    if 'datos_proveedor' not in st.session_state:
        st.session_state.datos_proveedor = None
    if 'resumen_codigos' not in st.session_state:
        st.session_state.resumen_codigos = None
    if 'estadisticas_validacion' not in st.session_state:
        st.session_state.estadisticas_validacion = None
    if 'validacion_integridad' not in st.session_state:
        st.session_state.validacion_integridad = None

# =============================================================================
# FUNCIONES DE VISUALIZACIÓN (MANTIENEN FORMATO EXACTO)
# =============================================================================

def mostrar_resultados_validacion_formateados(datos_proveedor, resumen_codigos, estadisticas_validacion, validacion_integridad):
    """Muestra los resultados de validación en el formato específico solicitado"""
    
    # Información del Proveedor
    st.markdown("### 👤 Información del Proveedor")
    nit = datos_proveedor.get('nit', 'No disponible')
    nombre = datos_proveedor.get('nombre', 'No disponible')
    st.markdown(f"**📇 NIT:** {nit}  \n**🏢 Nombre:** {nombre}")
    
    # Resumen por código
    st.markdown("### 🗒️ Resumen por código:")
    if resumen_codigos:
        for codigo, info in resumen_codigos.items():
            cantidad = info.get('cantidad', 0)
            nombre_doc = info.get('nombre', 'DOCUMENTO')
            st.markdown(f"• **Código {codigo}:** {cantidad} - {nombre_doc}")

    # Validación de Integridad (si hay problemas críticos)
    tiene_problemas_criticos = False
    if validacion_integridad:
        st.markdown("### 🔍 VALIDACIÓN DE INTEGRIDAD:")
        
        if 'levantes_duplicados' in validacion_integridad:
            info = validacion_integridad['levantes_duplicados']
            st.markdown(f"❌ {info['cantidad']} Levantes duplicados: {info['numero']}")
            tiene_problemas_criticos = True
        
        if 'desbalance' in validacion_integridad:
            info = validacion_integridad['desbalance']
            st.markdown(f"❌ Desbalance: {info['di']} DI vs {info['levantes']} Levantes")
            tiene_problemas_criticos = True
    
    # Análisis de Integridad
    st.markdown("### 🔍 Análisis de Integridad")

    total_di_anexos = estadisticas_validacion.get('total_di', 0)
    total_di_procesadas = estadisticas_validacion.get('total_di_dian', 0)
    di_faltantes = total_di_anexos - total_di_procesadas
    
    st.markdown(
        f"""
        **📄 DI en Anexos:** {total_di_anexos}  
        **⚠️ Faltantes:** {di_faltantes}  
        **✅ DI Procesadas:** {total_di_procesadas} de {total_di_anexos} totales
        """
    )
    
    # Estado de la Validación
    st.markdown("### 📋 Estado de la Validación")
    
    if tiene_problemas_criticos:
        if 'desbalance' in validacion_integridad:
            info = validacion_integridad['desbalance']
            st.markdown(f"❌ Desbalance detectado: {info['di']} DI vs {info['levantes']} Levantes")
    else:
        # Calcular balance DI vs Levantes
        di_count = resumen_codigos.get('9', {}).get('cantidad', 0) if resumen_codigos else 0
        levantes_count = resumen_codigos.get('47', {}).get('cantidad', 0) if resumen_codigos else 0
        
        if di_count == levantes_count:
            st.markdown(f"✅ Balance correcto en anexos: {di_count} DI = {levantes_count} Levantes")
        else:
            st.markdown(f"❌ Desbalance detectado: {di_count} DI vs {levantes_count} Levantes")
            tiene_problemas_criticos = True
    
    if di_faltantes > 0:
        st.markdown(f"⚠️ Diferencia encontrada: {total_di_procesadas} DI procesadas vs {total_di_anexos} DI en anexos")
        st.markdown(f"   📝 Faltan por procesar: {di_faltantes} declaraciones de DI")
    
    # RESUMEN EJECUTIVO
    st.markdown("### 🗒️ RESUMEN EJECUTIVO")
    
    declaraciones_correctas = estadisticas_validacion.get('declaraciones_correctas', 0)
    eficiencia = (total_di_procesadas / total_di_anexos * 100) if total_di_anexos > 0 else 0
    
    st.markdown(f"[**DI Procesadas:** {total_di_procesadas}/{total_di_anexos} -{di_faltantes}] [**Validación:** {declaraciones_correctas}✅ Perfecto] [**Eficiencia:** {eficiencia:.1f}%]")
    
    # Estado Final del Proceso
    st.markdown("### 📋 Estado Final del Proceso")
    
    if tiene_problemas_criticos:
        st.markdown("🚨 **PROCESO COMPLETADO CON DIFERENCIAS**")
        st.markdown("Se detectaron inconsistencias en la validación de integridad")
    else:
        if di_faltantes > 0:
            st.markdown("⚠️ **PROCESO COMPLETADO CON INCOMPLETITUD**")
        else:
            st.markdown("✅ **PROCESO COMPLETADO EXITOSAMENTE**")
    
    st.markdown(f"📈 {total_di_procesadas} de {total_di_anexos} DI procesadas | ✅ {declaraciones_correctas} correctas | ❌ {estadisticas_validacion.get('declaraciones_con_errores', 0)} con diferencias")

# =============================================================================
# FUNCIONES DE EXTRACCIÓN DE CONSOLA (COMPATIBLES CON NUEVO SCRIPT)
# =============================================================================

def extraer_datos_de_consola_mejorado(consola_output):
    """Extrae datos del proveedor de la salida de consola"""
    datos = {'nit': 'No disponible', 'nombre': 'No disponible'}
    lineas = consola_output.split('\n')
    for i, linea in enumerate(lineas):
        # Compatibilidad con formato "   🆔 NIT: 12345"
        if 'NIT:' in linea:
            nit_match = re.search(r'NIT:\s*([0-9]+)', linea)
            if nit_match:
                datos['nit'] = nit_match.group(1)
            elif i + 1 < len(lineas):
                nit_match = re.search(r'([0-9]{6,12})', lineas[i + 1])
                if nit_match:
                    datos['nit'] = nit_match.group(1)
        
        # Compatibilidad con formato "   📛 Nombre: PROVEEDOR"
        if 'Nombre:' in linea or 'Razón Social:' in linea:
            nombre_match = re.search(r'(?:Nombre|Razón Social):\s*(.+)', linea)
            if nombre_match:
                datos['nombre'] = nombre_match.group(1).strip()
            elif i + 1 < len(lineas):
                nombre_texto = lineas[i + 1].strip()
                if nombre_texto and not nombre_texto.isdigit():
                    datos['nombre'] = nombre_texto
    return datos

def extraer_resumen_de_consola_mejorado(consola_output):
    """Extrae resumen de códigos Y validación de integridad de la salida de consola"""
    resumen = {}
    validacion_integridad = {}
    
    lineas = consola_output.split('\n')
    en_resumen = False
    en_validacion = False
    
    for linea in lineas:
        # Capturar VALIDACIÓN DE INTEGRIDAD
        if 'VALIDACIÓN DE INTEGRIDAD:' in linea or 'VALIDACION DE INTEGRIDAD:' in linea:
            en_validacion = True
            continue
        
        if en_validacion:
            if '❌' in linea:
                if 'Levantes duplicados:' in linea or 'DI duplicadas:' in linea:
                    match = re.search(r'❌\s*(\d+)\s*(?:Levantes|DI)\s*duplicados?:\s*([0-9, ]+)', linea)
                    if match:
                        validacion_integridad['levantes_duplicados'] = {
                            'cantidad': match.group(1),
                            'numero': match.group(2).strip()
                        }
                elif 'Desbalance:' in linea:
                    match = re.search(r'❌\s*Desbalance:\s*(\d+)\s*DI\s*vs\s*(\d+)\s*Levantes', linea)
                    if match:
                        validacion_integridad['desbalance'] = {
                            'di': match.group(1),
                            'levantes': match.group(2)
                        }
            # Detectar fin de sección de validación
            elif not linea.strip() or '📋 Declaraciones encontradas:' in linea:
                en_validacion = False
        
        # Capturar RESUMEN POR CÓDIGO
        if 'Resumen por código:' in linea or '🗒️ Resumen por código:' in linea:
            en_resumen = True
            continue
        
        if en_resumen and linea.strip().startswith('•'):
            # Formato: "   • Código 9: 10 - DECLARACION..."
            match = re.search(r'•\s*Código\s+(\d+):\s*(\d+)\s*-\s*(.+)', linea)
            if match:
                codigo = match.group(1)
                cantidad = int(match.group(2))
                nombre = match.group(3).strip()
                resumen[codigo] = {'cantidad': cantidad, 'nombre': nombre}
        
        if en_resumen and not linea.strip().startswith('•') and linea.strip():
            en_resumen = False
    
    return resumen, validacion_integridad

def extraer_estadisticas_de_consola_mejorado(consola_output, datos_dian):
    """Extrae estadísticas REALES de la salida de consola"""
    estadisticas = {
        'total_anexos': 0,
        'total_di': 0,
        'total_di_dian': len(datos_dian) if datos_dian is not None else 0,
        'declaraciones_con_errores': 0,
        'declaraciones_correctas': 0,
        'datos_dian': datos_dian
    }
    
    lineas = consola_output.split('\n')
    
    for linea in lineas:
        # Buscar total de anexos (Formato: "✅ 77 anexos encontrados")
        if 'anexos encontrados' in linea:
            match = re.search(r'✅\s*(\d+)\s*anexos', linea)
            if match:
                estadisticas['total_anexos'] = int(match.group(1))
        
        # Buscar total DI en anexos (usando el resumen por código)
        if 'Código 9:' in linea:
            match = re.search(r'Código\s*9:\s*(\d+)', linea)
            if match:
                estadisticas['total_di'] = int(match.group(1))
        
        # Buscar declaraciones con errores (Formato: "   • Declaraciones con errores: 3")
        if 'Declaraciones con errores:' in linea:
            match = re.search(r'Declaraciones con errores:\s*(\d+)', linea)
            if match:
                estadisticas['declaraciones_con_errores'] = int(match.group(1))
        elif 'declaraciones con errores' in linea.lower():
            match = re.search(r'(\d+)\s*declaraciones con errores', linea.lower())
            if match:
                estadisticas['declaraciones_con_errores'] = int(match.group(1))
    
    # Calcular declaraciones correctas
    estadisticas['declaraciones_correctas'] = estadisticas['total_di_dian'] - estadisticas['declaraciones_con_errores']
    
    return estadisticas

def mostrar_resumen_comparacion_simplificado(reporte_comparacion, datos_dian, datos_subpartidas):
    """Muestra solo el resumen esencial de la comparación DIM vs Subpartidas"""
    
    if reporte_comparacion is None or reporte_comparacion.empty:
        return
    
    # Filtrar solo filas individuales (excluyendo totales acumulados para conteo real)
    di_individuales = reporte_comparacion[
        (reporte_comparacion['4. Número DI'] != 'VALORES ACUMULADOS') & 
        (reporte_comparacion['4. Número DI'] != 'VALORES ACUMULADOS (MÚLTIPLES SUBPARTIDAS)')
    ]
    
    conformes = len(di_individuales[di_individuales['Resultado verificación'] == '✅ CONFORME'])
    con_diferencias = len(di_individuales[di_individuales['Resultado verificación'] == '❌ CON DIFERENCIAS'])
    
    st.markdown("### 🗒️ Resumen Comparación DIM vs Subpartidas")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total DI procesadas", len(di_individuales))
    with col2:
        st.metric("DI conformes", conformes)
    with col3:
        st.metric("DI con diferencias", con_diferencias)

# =============================================================================
# LÓGICA DE PROCESAMIENTO
# =============================================================================

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

            # 1. Comparación DIM vs Subpartidas
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
            multiples_subpartidas = comparador.detectar_multiples_subpartidas(datos_subpartidas)
            
            if multiples_subpartidas:
                st.info(f"🔍 Detectadas {len(datos_subpartidas)} subpartidas - Aplicando lógica de suma y comparación")
            else:
                st.info("🔍 Subpartida única detectada - Aplicando lógica estándar")
            
            output_comparacion = os.path.join(temp_dir, "comparacion_dim_subpartidas.xlsx")
            reporte_comparacion = comparador.generar_reporte_comparacion(
                datos_dian, datos_subpartidas, output_comparacion
            )

            # 2. Validación de anexos (Capturando salida de consola para UI)
            st.info("🔄 Validando anexos FMM...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            
            # Crear buffer para capturar los prints del script optimizado
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                # Ejecutar validación (ahora devuelve DataFrame o None)
                resultado_validacion = validador.procesar_validacion_completa(temp_dir, output_anexos)
            
            consola_output = output_buffer.getvalue()
            
            # Extraer metadatos desde la salida capturada
            datos_proveedor = extraer_datos_de_consola_mejorado(consola_output)
            resumen_codigos, validacion_integridad = extraer_resumen_de_consola_mejorado(consola_output)
            estadisticas_validacion = extraer_estadisticas_de_consola_mejorado(consola_output, datos_dian)
            
            # Determinar el reporte de anexos final
            if isinstance(resultado_validacion, dict):
                # Por si acaso devolviera un diccionario (versiones anteriores)
                reporte_anexos = resultado_validacion.get('reporte_anexos')
            else:
                # La nueva versión devuelve el DataFrame directamente
                reporte_anexos = resultado_validacion

            # Guardar resultados binarios en session_state para descarga
            with open(output_comparacion, "rb") as f:
                st.session_state.comparacion_data = f.read()
            
            with open(output_anexos, "rb") as f:
                st.session_state.anexos_data = f.read()
            
            # Actualizar estados de sesión
            st.session_state.reporte_comparacion = reporte_comparacion
            st.session_state.reporte_anexos = reporte_anexos
            st.session_state.datos_dian = datos_dian
            st.session_state.datos_subpartidas = datos_subpartidas
            st.session_state.datos_proveedor = datos_proveedor
            st.session_state.resumen_codigos = resumen_codigos
            st.session_state.estadisticas_validacion = estadisticas_validacion
            st.session_state.validacion_integridad = validacion_integridad

            return {
                'comparacion': reporte_comparacion is not None,
                'anexos': reporte_anexos is not None
            }

        except Exception as e:
            st.error(f"❌ Error en el procesamiento: {str(e)}")
            return None

def mostrar_resultados_en_pantalla():
    """Muestra los resultados detallados en pantalla"""
    
    st.markdown("---")
    st.header("📋 Resultados de la Verificación")
    
    # 1. Validación de Proveedores e Integridad
    if (st.session_state.datos_proveedor is not None and 
        st.session_state.resumen_codigos is not None and 
        st.session_state.estadisticas_validacion is not None):
        
        mostrar_resultados_validacion_formateados(
            st.session_state.datos_proveedor,
            st.session_state.resumen_codigos,
            st.session_state.estadisticas_validacion,
            st.session_state.validacion_integridad
        )
    else:
        st.error("No se pudieron cargar los datos de validación")

    # 2. Resumen Comparación DIM
    st.markdown("---")
    if st.session_state.reporte_comparacion is not None:
        mostrar_resumen_comparacion_simplificado(
            st.session_state.reporte_comparacion, 
            st.session_state.datos_dian, 
            st.session_state.datos_subpartidas
        )

    # 3. Tablas Detalladas (Expansibles)
    with st.expander("🔍 Ver Detalle de Validación de Anexos"):
        if st.session_state.reporte_anexos is not None and not st.session_state.reporte_anexos.empty:
            def resaltar_anexos(row):
                return ['background-color: #ffcccc'] * len(row) if row['Coincidencias'] == '❌ NO COINCIDE' else [''] * len(row)
            st.dataframe(st.session_state.reporte_anexos.style.apply(resaltar_anexos, axis=1), use_container_width=True)

    with st.expander("🔍 Ver Detalle de Comparación DIM vs Subpartidas"):
        if st.session_state.reporte_comparacion is not None:
            reporte = st.session_state.reporte_comparacion
            
            # Filas individuales
            di_individuales = reporte[
                ~reporte['4. Número DI'].str.contains('VALORES ACUMULADOS', na=False)
            ]
            
            def resaltar_diferencias(row):
                return ['background-color: #ffcccc'] * len(row) if '❌' in str(row['Resultado verificación']) else [''] * len(row)
            
            st.markdown("**Detalle por Declaración:**")
            st.dataframe(di_individuales.style.apply(resaltar_diferencias, axis=1), use_container_width=True)
            
            # Totales
            fila_totales = reporte[reporte['4. Número DI'].str.contains('VALORES ACUMULADOS', na=False)]
            if not fila_totales.empty:
                st.markdown("**Totales Acumulados:**")
                st.dataframe(fila_totales, use_container_width=True)
                if any('❌' in str(val) for val in fila_totales['Resultado verificación'].values):
                    st.warning("⚠️ Se detectaron diferencias en los totales")

def mostrar_botones_descarga():
    """Muestra los botones para descargar los Excel"""
    st.markdown("---")
    st.markdown("<h2 style='text-align: center;'>📥 Descargar Resultados Completos</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.session_state.comparacion_data:
            st.download_button(
                label="📥 Descargar Validación DIM vs Subpartidas (Excel)",
                data=st.session_state.comparacion_data,
                file_name="Comparacion_DIM_Subpartidas.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key=f"dl_comp_{st.session_state.download_counter}"
            )
        else:
            st.button("📊 Comparación No Disponible", disabled=True, use_container_width=True)
    
    with col2:
        if st.session_state.anexos_data:
            st.download_button(
                label="📥 Descargar Comparación Anexos FMM (Excel)",
                data=st.session_state.anexos_data,
                file_name="Validacion_Anexos_FMM.xlsx", 
                mime="application/vnd.ms-excel",
                use_container_width=True,
                key=f"dl_anex_{st.session_state.download_counter}"
            )
        else:
            st.button("📋 Validación No Disponible", disabled=True, use_container_width=True)

# =============================================================================
# MAIN
# =============================================================================

def main():
    inicializar_estados()
    st.title("Aplicación de Verificación DIM vs FMM - SmartDIM 🚀 ")
    
    with st.sidebar:
        st.header("🧭 Instrucciones")
        st.markdown("1. Cargar PDFs DIM\n2. Cargar Excel Subpartidas\n3. Cargar Excel Anexos\n4. Ejecutar Verificación")
        if st.button("🧹 Limpiar Todo", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    # Carga de Archivos
    st.header("Cargar Archivos")
    k = st.session_state.uploader_key_counter
    dian_pdfs = st.file_uploader("PDFs DIAN", type=['pdf'], accept_multiple_files=True, key=f"pdfs_{k}")
    excel_sub = st.file_uploader("Excel Subpartidas", type=['xlsx', 'xls'], key=f"sub_{k}")
    excel_anex = st.file_uploader("Excel Anexos", type=['xlsx', 'xls'], key=f"anex_{k}")
    
    if dian_pdfs and excel_sub and excel_anex:
        st.success("Archivos cargados correctamente. Listo para verificar.")
        
        # Lógica de re-renderizado si ya se procesó
        if st.session_state.procesamiento_completado and st.session_state.reporte_comparacion is not None:
            st.info("Mostrando resultados previos.")
            mostrar_resultados_en_pantalla()
            mostrar_botones_descarga()
            if st.button("🔄 Ejecutar Nueva Verificación", type="primary"):
                with st.spinner("Procesando..."):
                    if procesar_conciliacion(dian_pdfs, excel_sub, excel_anex):
                        st.session_state.procesamiento_completado = True
                        st.rerun()
        else:
            if st.button("🔄 Ejecutar Verificación", type="primary"):
                with st.spinner("Procesando..."):
                    if procesar_conciliacion(dian_pdfs, excel_sub, excel_anex):
                        st.session_state.procesamiento_completado = True
                        st.rerun()
    else:
        st.warning("⚠️ Cargue todos los archivos requeridos")

if __name__ == "__main__":
    main()
