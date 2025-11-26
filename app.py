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

# Estilos CSS
st.markdown("""
<style>
    .file-info {
        background-color: #e9ecef;
        border-radius: 5px;
        padding: 8px;
        margin: 5px 0;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# GESTIÓN DE ESTADO (SESSION STATE)
# =============================================================================

def inicializar_estados():
    if 'uploader_key_counter' not in st.session_state:
        st.session_state.uploader_key_counter = 0
    if 'procesamiento_completado' not in st.session_state:
        st.session_state.procesamiento_completado = False
    if 'download_counter' not in st.session_state:
        st.session_state.download_counter = 0
    
    # Datos
    if 'comparacion_data' not in st.session_state: st.session_state.comparacion_data = None
    if 'anexos_data' not in st.session_state: st.session_state.anexos_data = None
    if 'reporte_comparacion' not in st.session_state: st.session_state.reporte_comparacion = None
    if 'reporte_anexos' not in st.session_state: st.session_state.reporte_anexos = None
    if 'datos_dian' not in st.session_state: st.session_state.datos_dian = None
    if 'datos_subpartidas' not in st.session_state: st.session_state.datos_subpartidas = None
    
    # Resúmenes
    if 'datos_proveedor' not in st.session_state: st.session_state.datos_proveedor = None
    if 'resumen_codigos' not in st.session_state: st.session_state.resumen_codigos = None
    if 'estadisticas_validacion' not in st.session_state: st.session_state.estadisticas_validacion = None
    if 'validacion_integridad' not in st.session_state: st.session_state.validacion_integridad = None

# =============================================================================
# LÓGICA DE EXTRACCIÓN Y PROCESAMIENTO
# =============================================================================

def procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos):
    """Procesa la conciliación con los archivos cargados"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # 1. Guardar archivos en temporal
            for pdf in dian_pdfs:
                with open(os.path.join(temp_dir, pdf.name), "wb") as f:
                    f.write(pdf.getbuffer())
            
            with open(os.path.join(temp_dir, excel_subpartidas.name), "wb") as f:
                f.write(excel_subpartidas.getbuffer())
            
            with open(os.path.join(temp_dir, excel_anexos.name), "wb") as f:
                f.write(excel_anexos.getbuffer())

            # ---------------------------------------------------------
            # ETAPA 1: Comparación DIM vs Subpartidas
            # ---------------------------------------------------------
            st.info("🔍 Comparando DIM vs Subpartidas...")
            
            extractor_dian = ExtractorDIANSimplificado()
            datos_dian = extractor_dian.procesar_multiples_dis(temp_dir)
            
            if datos_dian is None or datos_dian.empty:
                st.error("❌ No se pudieron extraer datos de las DIM")
                return None
            
            st.success(f"✅ {len(datos_dian)} declaraciones DIAN extraídas")
            
            extractor_subpartidas = ExtractorSubpartidas()
            datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(temp_dir)
            
            comparador = ComparadorDatos()
            output_comparacion = os.path.join(temp_dir, "comparacion_dim_subpartidas.xlsx")
            reporte_comparacion = comparador.generar_reporte_comparacion(
                datos_dian, datos_subpartidas, output_comparacion
            )

            # ---------------------------------------------------------
            # ETAPA 2: Validación de Anexos FMM
            # ---------------------------------------------------------
            st.info("🔄 Validando anexos FMM...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            
            # Capturar stdout para análisis de integridad (Códigos, duplicados)
            output_buffer = io.StringIO()
            with redirect_stdout(output_buffer):
                reporte_anexos = validador.procesar_validacion_completa(temp_dir, output_anexos)
            
            consola_output = output_buffer.getvalue()

            # --- EXTRACCIÓN ROBUSTA DE METADATOS ---
            
            # A. Datos del Proveedor: Acceso directo al objeto (Infalible)
            datos_proveedor = {
                'nit': validador.nit_proveedor if validador.nit_proveedor else "No encontrado",
                'nombre': validador.nombre_proveedor if validador.nombre_proveedor else "No encontrado"
            }
            
            # B. Resumen de Códigos y Integridad: Desde consola (con Regex flexible)
            resumen_codigos, validacion_integridad = extraer_resumen_de_consola_flexible(consola_output)
            
            # C. Estadísticas: Cálculo directo sobre DataFrames (Más preciso)
            estadisticas_validacion = calcular_estadisticas_reales(
                reporte_anexos, 
                datos_dian, 
                resumen_codigos
            )

            # 3. Guardar en Session State
            if os.path.exists(output_comparacion):
                with open(output_comparacion, "rb") as f:
                    st.session_state.comparacion_data = f.read()
            
            if os.path.exists(output_anexos):
                with open(output_anexos, "rb") as f:
                    st.session_state.anexos_data = f.read()
            
            st.session_state.reporte_comparacion = reporte_comparacion
            st.session_state.reporte_anexos = reporte_anexos
            st.session_state.datos_dian = datos_dian
            st.session_state.datos_subpartidas = datos_subpartidas
            st.session_state.datos_proveedor = datos_proveedor
            st.session_state.resumen_codigos = resumen_codigos
            st.session_state.estadisticas_validacion = estadisticas_validacion
            st.session_state.validacion_integridad = validacion_integridad

            return True

        except Exception as e:
            st.error(f"❌ Error en el procesamiento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

def extraer_resumen_de_consola_flexible(consola_output):
    """Extrae el resumen de códigos con regex que ignora viñetas y espacios extra"""
    resumen = {}
    validacion_integridad = {}
    
    lineas = consola_output.split('\n')
    
    for linea in lineas:
        # Integridad
        if '❌' in linea and ('Levantes' in linea or 'Desbalance' in linea):
            if 'Levantes duplicados' in linea:
                match = re.search(r'❌\s*(\d+)', linea)
                if match: validacion_integridad['levantes_duplicados'] = {'cantidad': match.group(1), 'numero': 'Ver detalle'}
            if 'Desbalance' in linea:
                match = re.search(r'(\d+)\s*DI\s*vs\s*(\d+)', linea)
                if match: validacion_integridad['desbalance'] = {'di': match.group(1), 'levantes': match.group(2)}
        
        # Resumen de Códigos: Busca "Código X: Y" ignorando lo que haya antes (puntos, espacios)
        # Ejemplo script: "   • Código 9: 22 - DECLARACION..."
        if 'Código' in linea and ':' in linea:
            match = re.search(r'Código\s+(\d+):\s*(\d+)\s*-\s*(.+)', linea)
            if match:
                codigo = match.group(1)
                cantidad = int(match.group(2))
                nombre = match.group(3).strip()
                resumen[codigo] = {'cantidad': cantidad, 'nombre': nombre}
                
    return resumen, validacion_integridad

def calcular_estadisticas_reales(reporte_anexos, datos_dian, resumen_codigos):
    """Calcula estadísticas basadas en DataFrames y conteos, no en texto"""
    
    # 1. Total DI en FMM (Código 9 del resumen extraído)
    total_di_anexos = 0
    if resumen_codigos and '9' in resumen_codigos:
        total_di_anexos = resumen_codigos['9']['cantidad']
    
    # 2. Total DI Procesadas (Extraídas del PDF)
    total_di_procesadas = len(datos_dian) if datos_dian is not None else 0
    
    # 3. Errores y Aciertos (Basado en el reporte de validación)
    errores = 0
    correctas = 0
    
    if reporte_anexos is not None and not reporte_anexos.empty:
        # Contamos filas con "NO COINCIDE"
        errores = len(reporte_anexos[reporte_anexos['Coincidencias'].str.contains('NO COINCIDE', na=False)])
        # El resto son correctas (o errores no críticos)
        # Nota: Un mismo PDF puede generar varias filas de validación. 
        # Si queremos contar DIs con error vs DIs limpias:
        dis_con_error = reporte_anexos[reporte_anexos['Coincidencias'].str.contains('NO COINCIDE', na=False)]['Numero DI'].nunique()
        errores = dis_con_error
        correctas = total_di_procesadas - dis_con_error
    else:
        # Si no hubo reporte pero hubo DIs, algo falló o no hubo cruce
        correctas = total_di_procesadas
    
    return {
        'total_anexos': sum(r['cantidad'] for r in resumen_codigos.values()) if resumen_codigos else 0,
        'total_di': total_di_anexos,
        'total_di_dian': total_di_procesadas,
        'declaraciones_con_errores': errores,
        'declaraciones_correctas': correctas
    }

# =============================================================================
# UI / VISUALIZACIÓN
# =============================================================================

def mostrar_resultados_validacion_formateados(datos_proveedor, resumen_codigos, estadisticas_validacion, validacion_integridad):
    
    # Proveedor
    st.markdown("### 👤 Información del Proveedor")
    st.markdown(f"**📇 NIT:** {datos_proveedor['nit']}  \n**🏢 Nombre:** {datos_proveedor['nombre']}")
    
    # Resumen Códigos
    st.markdown("### 🗒️ Resumen por código:")
    if resumen_codigos:
        for codigo, info in resumen_codigos.items():
            st.markdown(f"• **Código {codigo}:** {info['cantidad']} - {info['nombre']}")
    else:
        st.warning("No se encontraron códigos de anexos.")

    # Integridad
    tiene_problemas_criticos = False
    if validacion_integridad:
        st.markdown("### 🔍 VALIDACIÓN DE INTEGRIDAD:")
        if 'levantes_duplicados' in validacion_integridad:
            st.markdown(f"❌ {validacion_integridad['levantes_duplicados']['cantidad']} Levantes duplicados")
            tiene_problemas_criticos = True
        if 'desbalance' in validacion_integridad:
            info = validacion_integridad['desbalance']
            st.markdown(f"❌ Desbalance: {info['di']} DI vs {info['levantes']} Levantes")
            tiene_problemas_criticos = True
    
    # Análisis
    st.markdown("### 🔍 Análisis de Integridad")
    total_di_anexos = estadisticas_validacion.get('total_di', 0)
    total_di_procesadas = estadisticas_validacion.get('total_di_dian', 0)
    di_faltantes = total_di_anexos - total_di_procesadas
    
    st.markdown(f"**📄 DI en Anexos:** {total_di_anexos}")
    if di_faltantes != 0:
        st.markdown(f"**⚠️ Diferencia:** {di_faltantes}")
    st.markdown(f"**✅ DI Procesadas:** {total_di_procesadas} de {total_di_anexos} totales esperadas")

    # Estado Validación
    st.markdown("### 📋 Estado de la Validación")
    
    # Verificar balance DI (cod 9) vs Levantes (cod 47)
    di_count = resumen_codigos.get('9', {}).get('cantidad', 0) if resumen_codigos else 0
    levantes_count = resumen_codigos.get('47', {}).get('cantidad', 0) if resumen_codigos else 0
    
    if not tiene_problemas_criticos and di_count == levantes_count and di_count > 0:
        st.markdown(f"✅ Balance correcto en anexos: {di_count} DI = {levantes_count} Levantes")
    elif di_count != levantes_count:
        st.markdown(f"❌ Desbalance detectado: {di_count} DI vs {levantes_count} Levantes")
        tiene_problemas_criticos = True

    # Resumen Ejecutivo
    st.markdown("### 🗒️ RESUMEN EJECUTIVO")
    correctas = estadisticas_validacion.get('declaraciones_correctas', 0)
    
    # Evitar división por cero
    denom_eficiencia = total_di_anexos if total_di_anexos > 0 else (total_di_procesadas if total_di_procesadas > 0 else 1)
    eficiencia = (total_di_procesadas / denom_eficiencia * 100)
    
    st.markdown(f"[**DI Procesadas:** {total_di_procesadas}/{total_di_anexos}] [**Validación:** {correctas}✅] [**Eficiencia:** {eficiencia:.1f}%]")
    
    # Estado Final
    st.markdown("### 📋 Estado Final del Proceso")
    if tiene_problemas_criticos or estadisticas_validacion.get('declaraciones_con_errores', 0) > 0:
        st.markdown("🚨 **PROCESO CON DIFERENCIAS**")
    elif di_faltantes > 0:
        st.markdown("⚠️ **PROCESO INCOMPLETO (Faltan DI)**")
    else:
        st.markdown("✅ **PROCESO COMPLETADO EXITOSAMENTE**")
        
    st.markdown(f"📈 {total_di_procesadas} procesadas | ✅ {correctas} correctas | ❌ {estadisticas_validacion.get('declaraciones_con_errores', 0)} con diferencias")

def mostrar_resumen_comparacion(reporte):
    if reporte is None or reporte.empty: return
    
    # Filtrar totales para conteo
    di_reales = reporte[~reporte['4. Número DI'].str.contains("VALORES ACUMULADOS", na=False)]
    
    conformes = len(di_reales[di_reales['Resultado verificación'] == '✅ CONFORME'])
    errores = len(di_reales) - conformes
    
    st.markdown("### 🗒️ Resumen Comparación DIM vs Subpartidas")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total DI", len(di_reales))
    c2.metric("Conformes", conformes)
    c3.metric("Con Diferencias", errores)

# =============================================================================
# MAIN APP
# =============================================================================

def main():
    inicializar_estados()
    st.title("Aplicación de Verificación DIM vs FMM - SmartDIM 🚀")
    
    # Sidebar
    with st.sidebar:
        st.header("🧭 Menú")
        st.markdown("1. Cargue archivos\n2. Ejecute verificación\n3. Descargue resultados")
        
        # BOTÓN LIMPIAR CORREGIDO
        if st.button("🧹 Limpiar Todo", type="secondary", use_container_width=True):
            # Preservar el contador para forzar cambio de ID en file_uploader
            current_counter = st.session_state.uploader_key_counter
            
            # Borrar todo el estado excepto el contador
            for key in list(st.session_state.keys()):
                if key != 'uploader_key_counter':
                    del st.session_state[key]
            
            # Incrementar contador para invalidar caché de carga de archivos
            st.session_state.uploader_key_counter = current_counter + 1
            st.rerun()

    # Carga de Archivos
    st.header("1. Cargar Archivos")
    # Usamos el contador en la key para asegurar que se resetee al limpiar
    key_suffix = st.session_state.uploader_key_counter
    
    dian_pdfs = st.file_uploader("PDFs DIAN", type=['pdf'], accept_multiple_files=True, key=f"pdf_{key_suffix}")
    excel_sub = st.file_uploader("Excel Subpartidas", type=['xlsx', 'xls'], key=f"sub_{key_suffix}")
    excel_anex = st.file_uploader("Excel Anexos", type=['xlsx', 'xls'], key=f"anex_{key_suffix}")
    
    archivos_ok = dian_pdfs and excel_sub and excel_anex
    
    # Botón de Acción
    if archivos_ok:
        if st.session_state.procesamiento_completado:
            st.info("Resultados disponibles.")
        else:
            if st.button("🔄 Ejecutar Verificación", type="primary"):
                with st.spinner("Procesando..."):
                    if procesar_conciliacion(dian_pdfs, excel_sub, excel_anex):
                        st.session_state.procesamiento_completado = True
                        st.rerun()
    else:
        st.warning("Por favor cargue todos los archivos requeridos.")

    # Visualización de Resultados
    if st.session_state.procesamiento_completado:
        st.markdown("---")
        st.header("2. Resultados")
        
        # Mostrar validación FMM
        if st.session_state.datos_proveedor:
            mostrar_resultados_validacion_formateados(
                st.session_state.datos_proveedor,
                st.session_state.resumen_codigos,
                st.session_state.estadisticas_validacion,
                st.session_state.validacion_integridad
            )
        
        st.markdown("---")
        # Mostrar validación Subpartidas
        if st.session_state.reporte_comparacion is not None:
            mostrar_resumen_comparacion(st.session_state.reporte_comparacion)
            
            with st.expander("🔍 Ver Detalle Comparación DIM vs Subpartidas"):
                # Resaltar filas con error
                def highlight_error(row):
                    return ['background-color: #ffcccc'] * len(row) if '❌' in str(row['Resultado verificación']) else [''] * len(row)
                
                # Filtrar solo para visualización limpia
                df_view = st.session_state.reporte_comparacion.copy()
                st.dataframe(df_view.style.apply(highlight_error, axis=1), use_container_width=True)

        # Descargas
        st.markdown("---")
        st.header("3. Descargas")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state.comparacion_data:
                st.download_button("📥 Descargar Comparación DIM-Subpartidas", st.session_state.comparacion_data, "Comparacion_DIM_Subpartidas.xlsx", key=f"dl1_{key_suffix}")
        with c2:
            if st.session_state.anexos_data:
                st.download_button("📥 Descargar Validación Anexos", st.session_state.anexos_data, "Validacion_Anexos.xlsx", key=f"dl2_{key_suffix}")

if __name__ == "__main__":
    main()
