import streamlit as st
import pandas as pd
import os
import tempfile
from datetime import datetime
import io

# Importar las clases del código unificado
from unificado_verificacion import (
    ExtractorDIANSimplificado, 
    ComparadorDatos, 
    ExtractorSubpartidas,
    ValidadorDeclaracionImportacionCompleto
)

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(
    page_title="Sistema de Verificación DIM vs FMM", 
    page_icon="📊", 
    layout="wide"
)

# --- FUNCIONES AUXILIARES ---
def limpiar_directorio_temporal():
    """Limpia archivos temporales antiguos"""
    temp_dir = tempfile.gettempdir()
    for filename in os.listdir(temp_dir):
        if filename.startswith("temp_") and filename.endswith(".pdf"):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                pass

def guardar_archivos_subidos(archivos, tipo):
    """Guarda archivos subidos en directorio temporal"""
    temp_files = []
    temp_dir = tempfile.gettempdir()
    
    for archivo in archivos:
        # Crear nombre de archivo temporal único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        temp_filename = f"temp_{tipo}_{timestamp}_{archivo.name}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        # Guardar archivo
        with open(temp_path, "wb") as f:
            f.write(archivo.getvalue())
        
        temp_files.append(temp_path)
    
    return temp_files

def procesar_verificacion_dim_fmm(archivos_pdf, archivo_excel=None, carpeta_temporal=None):
    """Procesa la verificación DIM vs FMM"""
    
    resultados = {
        'comparacion_dim_subpartida': None,
        'validacion_anexos': None,
        'errores': []
    }
    
    try:
        # =============================================================================
        # EJECUTAR: Comparación DIM vs Subpartida
        # =============================================================================
        
        if archivos_pdf and (archivo_excel or carpeta_temporal):
            st.info("🔍 Iniciando comparación DIM vs Subpartida...")
            
            # Paso 1: Extraer datos de PDFs (DIAN)
            extractor_dian = ExtractorDIANSimplificado()
            
            # Procesar cada PDF individualmente y combinar resultados
            todos_datos_dian = []
            for pdf_path in archivos_pdf:
                datos_pdf = extractor_dian.procesar_multiples_dis(os.path.dirname(pdf_path))
                if datos_pdf is not None and not datos_pdf.empty:
                    todos_datos_dian.append(datos_pdf)
            
            # Combinar todos los datos DIAN
            if todos_datos_dian:
                datos_dian = pd.concat(todos_datos_dian, ignore_index=True)
                st.success(f"✅ Datos DIAN extraídos: {len(datos_dian)} registros")
            else:
                datos_dian = None
                st.warning("⚠️ No se pudieron extraer datos DIAN de los PDFs")
            
            # Paso 2: Extraer datos de Excel (Subpartidas)
            extractor_subpartidas = ExtractorSubpartidas()
            
            if archivo_excel:
                # Usar archivo Excel específico
                carpeta_excel = os.path.dirname(archivo_excel[0])
            else:
                # Usar carpeta temporal
                carpeta_excel = carpeta_temporal
            
            datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(carpeta_excel)
            
            if not datos_subpartidas.empty:
                st.success(f"✅ Datos Subpartidas extraídos: {len(datos_subpartidas)} registros")
            else:
                st.warning("⚠️ No se pudieron extraer datos de subpartidas")
            
            # Paso 3: Comparar datos si tenemos ambos
            if datos_dian is not None and not datos_dian.empty and not datos_subpartidas.empty:
                comparador = ComparadorDatos()
                
                # Crear archivo temporal para el reporte
                temp_dir = tempfile.gettempdir()
                output_path = os.path.join(temp_dir, "temp_comparacion_dim_subpartida.xlsx")
                
                reporte_comparacion = comparador.generar_reporte_comparacion(
                    datos_dian, datos_subpartidas, output_path
                )
                
                if reporte_comparacion is not None and not reporte_comparacion.empty:
                    resultados['comparacion_dim_subpartida'] = reporte_comparacion
                    st.success("✅ Comparación DIM vs Subpartida completada")
                else:
                    resultados['errores'].append("No se pudo generar el reporte de comparación")
            else:
                resultados['errores'].append("Datos insuficientes para comparación DIM vs Subpartida")
        
        # =============================================================================
        # EJECUTAR: Validación Anexos FMM
        # =============================================================================
        
        if archivos_pdf:
            st.info("🔍 Iniciando validación de anexos FMM...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            
            # Crear carpeta temporal para procesamiento
            temp_dir = tempfile.gettempdir()
            carpeta_procesamiento = os.path.join(temp_dir, f"procesamiento_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(carpeta_procesamiento, exist_ok=True)
            
            # Copiar archivos PDF a la carpeta temporal
            for pdf_path in archivos_pdf:
                nombre_archivo = os.path.basename(pdf_path)
                nuevo_path = os.path.join(carpeta_procesamiento, nombre_archivo)
                # En una implementación real, aquí copiaríamos el archivo
            
            # Buscar formulario FMM en los archivos Excel subidos
            if archivo_excel:
                for excel_path in archivo_excel:
                    nombre_excel = os.path.basename(excel_path).lower()
                    if any(palabra in nombre_excel for palabra in ['formulario', 'fmm', 'rpt_impresion']):
                        # Copiar formulario a carpeta temporal
                        formulario_destino = os.path.join(carpeta_procesamiento, os.path.basename(excel_path))
                        # En implementación real, copiaríamos el archivo
            
            # Crear archivo de salida temporal
            output_anexos = os.path.join(temp_dir, "temp_validacion_anexos.xlsx")
            
            # Ejecutar validación
            try:
                resultados_anexos = validador.procesar_validacion_completa(carpeta_procesamiento, output_anexos)
                
                if resultados_anexos is not None and not resultados_anexos.empty:
                    resultados['validacion_anexos'] = resultados_anexos
                    st.success("✅ Validación de anexos FMM completada")
                else:
                    st.warning("⚠️ No se pudieron generar resultados de validación de anexos")
                    
            except Exception as e:
                resultados['errores'].append(f"Error en validación de anexos: {str(e)}")
                st.error(f"❌ Error en validación de anexos: {str(e)}")
        
    except Exception as e:
        resultados['errores'].append(f"Error general en procesamiento: {str(e)}")
        st.error(f"❌ Error general: {str(e)}")
    
    return resultados

# --- INTERFAZ STREAMLIT ---
def main():
    st.title("📊 Sistema de Verificación DIM vs FMM")
    st.markdown("---")
    
    # Inicializar session state
    if 'resultados_verificacion' not in st.session_state:
        st.session_state.resultados_verificacion = None
    if 'procesamiento_completado' not in st.session_state:
        st.session_state.procesamiento_completado = False
    if 'uploader_key_counter' not in st.session_state:
        st.session_state.uploader_key_counter = 0
    
    # Limpiar archivos temporales al inicio
    limpiar_directorio_temporal()
    
    # Sidebar para carga de archivos
    with st.sidebar:
        st.header("📂 Cargar Archivos")
        
        # File uploaders
        archivos_pdf = st.file_uploader(
            "Archivos PDF (Declaraciones de Importación)", 
            type="pdf", 
            accept_multiple_files=True,
            key=f"pdf_uploader_{st.session_state.uploader_key_counter}",
            help="Suba los archivos PDF de las Declaraciones de Importación"
        )
        
        archivos_excel = st.file_uploader(
            "Archivos Excel (Subpartidas y Formularios)", 
            type=["xlsx", "xls"], 
            accept_multiple_files=True,
            key=f"excel_uploader_{st.session_state.uploader_key_counter}",
            help="Suba archivos Excel con datos de subpartidas y formularios FMM"
        )
        
        # Opciones de procesamiento
        st.header("⚙️ Opciones de Procesamiento")
        
        procesar_comparacion = st.checkbox(
            "Comparación DIM vs Subpartida", 
            value=True,
            help="Comparar datos de Declaraciones de Importación con subpartidas arancelarias"
        )
        
        procesar_anexos = st.checkbox(
            "Validación Anexos FMM", 
            value=True,
            help="Validar anexos del Formulario de Movimiento de Mercancías"
        )
        
        if st.button("🚀 Ejecutar Verificación", type="primary"):
            if archivos_pdf:
                with st.spinner("Procesando archivos..."):
                    try:
                        # Guardar archivos en temporal
                        temp_pdf_files = guardar_archivos_subidos(archivos_pdf, "pdf")
                        temp_excel_files = guardar_archivos_subidos(archivos_excel, "excel") if archivos_excel else None
                        
                        # Crear carpeta temporal para procesamiento
                        temp_dir = tempfile.gettempdir()
                        carpeta_temporal = os.path.join(temp_dir, f"procesamiento_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                        os.makedirs(carpeta_temporal, exist_ok=True)
                        
                        # Procesar verificación
                        resultados = procesar_verificacion_dim_fmm(
                            temp_pdf_files, 
                            temp_excel_files, 
                            carpeta_temporal
                        )
                        
                        st.session_state.resultados_verificacion = resultados
                        st.session_state.procesamiento_completado = True
                        st.success("✅ Verificación completada")
                        
                    except Exception as e:
                        st.error(f"❌ Error en procesamiento: {str(e)}")
            else:
                st.warning("⚠️ Debes cargar al menos archivos PDF")
    
    # Botón de limpieza
    if st.sidebar.button("🗑️ Limpiar Todo", type="secondary"):
        # Limpiar estado
        st.session_state.resultados_verificacion = None
        st.session_state.procesamiento_completado = False
        st.session_state.uploader_key_counter += 1
        
        # Limpiar archivos temporales
        limpiar_directorio_temporal()
        
        st.sidebar.success("✅ Todo ha sido limpiado. Puedes cargar nuevos archivos.")
        st.rerun()
    
    # Mostrar resultados si existen
    if st.session_state.get('resultados_verificacion') is not None:
        resultados = st.session_state.resultados_verificacion
        
        st.header("📊 Resultados de Verificación")
        
        # Mostrar errores si existen
        if resultados.get('errores'):
            st.error("❌ Se encontraron errores durante el procesamiento:")
            for error in resultados['errores']:
                st.write(f"• {error}")
        
        # Mostrar comparación DIM vs Subpartida
        if resultados.get('comparacion_dim_subpartida') is not None:
            st.subheader("📈 Comparación DIM vs Subpartida")
            
            df_comparacion = resultados['comparacion_dim_subpartida']
            
            # Formatear DataFrame para mejor visualización
            df_mostrar = df_comparacion.copy()
            
            # Resaltar filas con diferencias
            def resaltar_filas(row):
                if '❌' in str(row.get('Resultado verificación', '')):
                    return ['background-color: #ffcccc'] * len(row)
                elif '✅' in str(row.get('Resultado verificación', '')):
                    return ['background-color: #ccffcc'] * len(row)
                return [''] * len(row)
            
            st.dataframe(
                df_mostrar.style.apply(resaltar_filas, axis=1),
                use_container_width=True,
                height=400
            )
            
            # Estadísticas de comparación
            if 'Resultado verificación' in df_comparacion.columns:
                conteo_estados = df_comparacion['Resultado verificación'].value_counts()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total DI", len(df_comparacion))
                col2.metric("✅ Conformes", conteo_estados.get('✅ CONFORME', 0))
                col3.metric("❌ Con Diferencias", conteo_estados.get('❌ CON DIFERENCIAS', 0))
        
        # Mostrar validación de anexos FMM
        if resultados.get('validacion_anexos') is not None:
            st.subheader("📋 Validación Anexos FMM")
            
            df_anexos = resultados['validacion_anexos']
            
            # Formatear para visualización
            df_mostrar_anexos = df_anexos.copy()
            
            # Resaltar filas según coincidencias
            def resaltar_coincidencias(row):
                if '❌' in str(row.get('Coincidencias', '')):
                    return ['background-color: #ffcccc'] * len(row)
                elif '✅' in str(row.get('Coincidencias', '')):
                    return ['background-color: #ccffcc'] * len(row)
                return [''] * len(row)
            
            st.dataframe(
                df_mostrar_anexos.style.apply(resaltar_coincidencias, axis=1),
                use_container_width=True,
                height=400
            )
            
            # Estadísticas de validación
            if 'Coincidencias' in df_anexos.columns:
                conteo_coincidencias = df_anexos['Coincidencias'].value_counts()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Campos", len(df_anexos))
                col2.metric("✅ Coinciden", conteo_coincidencias.get('✅ COINCIDE', 0))
                col3.metric("❌ No Coinciden", conteo_coincidencias.get('❌ NO COINCIDE', 0))
        
        # Botones de exportación
        st.subheader("💾 Exportar Resultados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if resultados.get('comparacion_dim_subpartida') is not None:
                # Crear Excel para comparación
                excel_buffer_comparacion = io.BytesIO()
                with pd.ExcelWriter(excel_buffer_comparacion, engine='openpyxl') as writer:
                    resultados['comparacion_dim_subpartida'].to_excel(
                        writer, 
                        index=False, 
                        sheet_name='Comparación_DIM_Subpartida'
                    )
                excel_buffer_comparacion.seek(0)
                
                st.download_button(
                    label="📥 Descargar Comparación DIM vs Subpartida",
                    data=excel_buffer_comparacion,
                    file_name="comparacion_dim_subpartida.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col2:
            if resultados.get('validacion_anexos') is not None:
                # Crear Excel para validación anexos
                excel_buffer_anexos = io.BytesIO()
                with pd.ExcelWriter(excel_buffer_anexos, engine='openpyxl') as writer:
                    resultados['validacion_anexos'].to_excel(
                        writer, 
                        index=False, 
                        sheet_name='Validacion_Anexos_FMM'
                    )
                excel_buffer_anexos.seek(0)
                
                st.download_button(
                    label="📥 Descargar Validación Anexos FMM",
                    data=excel_buffer_anexos,
                    file_name="validacion_anexos_fmm.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
    # Mensaje cuando no hay resultados
    elif st.session_state.get('procesamiento_completado', False):
        st.info("💡 Usa el botón 'Limpiar Todo' para comenzar una nueva verificación")
    
    # Información de uso
    with st.expander("ℹ️ Instrucciones de uso"):
        st.markdown("""
        **📋 Cómo usar el sistema de verificación DIM vs FMM:**
        
        1. **Cargar archivos PDF**: Sube las Declaraciones de Importación (DIM) en formato PDF
        2. **Cargar archivos Excel**: Sube los archivos con datos de subpartidas y formularios FMM
        3. **Seleccionar procesos**: Elige qué verificaciones ejecutar
        4. **Ejecutar**: Haz clic en 'Ejecutar Verificación'
        5. **Revisar resultados**: Los resultados se mostrarán en tablas interactivas
        6. **Exportar**: Descarga los resultados en Excel si es necesario
        7. **Limpiar**: Usa 'Limpiar Todo' para borrar TODO y empezar de nuevo
        
        **🔍 Procesos disponibles:**
        - **Comparación DIM vs Subpartida**: Verifica que los datos de las Declaraciones de Importación 
          coincidan con las subpartidas arancelarias
        - **Validación Anexos FMM**: Valida que los anexos del Formulario de Movimiento de Mercancías 
          sean consistentes con las declaraciones
        
        **📊 Resultados:**
        - ✅ **Verde**: Campos que coinciden correctamente
        - ❌ **Rojo**: Campos con diferencias que requieren revisión
        - 📈 **Métricas**: Resumen estadístico de la verificación
        
        **💡 Consejos:**
        - Asegúrate de que los archivos PDF sean legibles
        - Verifica que los archivos Excel tengan el formato esperado
        - Revisa las diferencias identificadas antes de tomar acciones
        """)

if __name__ == "__main__":
    main()
