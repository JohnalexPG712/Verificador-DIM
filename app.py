import streamlit as st
import pandas as pd
import os
import tempfile
from verificacion_dim import (
    ExtractorDIANSimplificado,
    ComparadorDatos, 
    ExtractorSubpartidas,
    ValidadorDeclaracionImportacionCompleto
)

# Configuración de la página
st.set_page_config(
    page_title="Conciliación DIM vs Subpartidas",
    page_icon="📊",
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

# Inicializar contador para file uploaders si no existe
if 'uploader_key_counter' not in st.session_state:
    st.session_state.uploader_key_counter = 0

def main():
    # Header principal
    st.title("Sistema de Conciliación de Declaraciones de Importación")
    
    # Instrucciones en sidebar
    with st.sidebar:
        st.header("Instrucciones de uso")
        st.markdown("""
        1. **Cargar Declaraciones PDF** (DIAN)
        2. **Cargar Excel de Subpartidas**
        3. **Cargar Excel de Anexos/Proveedores** 
        4. **Ejecutar Conciliación**
        5. **Ver resultados en pantalla y descargar**
        """)
        
        # Botón de limpieza - EXACTAMENTE COMO TU LÓGICA FUNCIONA
        if st.button("🗑️ Limpiar Todo", type="secondary", use_container_width=True):
            # Limpiar todo el estado específico
            st.session_state.comparacion_data = None
            st.session_state.anexos_data = None
            st.session_state.reporte_comparacion = None
            st.session_state.reporte_anexos = None
            
            # Incrementar el contador para forzar nuevos file uploaders
            st.session_state.uploader_key_counter += 1
            
            # Mensaje de confirmación
            st.sidebar.success("✅ Todo ha sido limpiado. Puedes cargar nuevos archivos.")
            
            # Forzar actualización sin recargar toda la página
            st.rerun()

    # Sección de carga de archivos
    st.header("Cargar Archivos")

    # Usar el contador como parte de la key para forzar reset - CLAVE ÚNICA
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
        st.markdown(f'<div class="file-info">📊 {excel_subpartidas.name} ({excel_subpartidas.size / 1024:.1f} KB)</div>', 
                   unsafe_allow_html=True)

    # Excel de Anexos/Proveedores
    st.subheader("Archivo Excel (Anexos y Proveedores)")
    excel_anexos = st.file_uploader(
        "Arrastre y suelte Excel de anexos/proveedores aquí",
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

    # Verificar archivos mínimos
    archivos_cargados = (
        dian_pdfs and 
        excel_subpartidas and
        excel_anexos
    )

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
    if st.button("🔄 Ejecutar Conciliación", type="primary", use_container_width=True):
        with st.spinner("Procesando conciliación..."):
            resultados = procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos)
            
            if resultados:
                st.success("✅ Conciliación completada exitosamente")
                mostrar_resultados_en_pantalla(resultados)
                mostrar_botones_descarga()

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
                st.error("❌ No se pudieron extraer datos de los PDFs de DIAN")
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

            # MOSTRAR RESULTADOS EN CONSOLA - Comparación DIM vs Subpartidas
            st.markdown("---")
            st.subheader("📋 Resultados en Consola - Comparación DIM vs Subpartidas")
            mostrar_resultados_consola_comparacion(reporte_comparacion, datos_dian, datos_subpartidas)

            # Procesar validación de anexos
            st.info("📋 Validando anexos y proveedores...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            reporte_anexos = validador.procesar_validacion_completa(temp_dir, output_anexos)

            # MOSTRAR RESULTADOS EN CONSOLA - Validación Anexos
            st.subheader("📋 Resultados en Consola - Validación Anexos")
            mostrar_resultados_consola_anexos(reporte_anexos)

            # Guardar resultados para descarga
            with open(output_comparacion, "rb") as f:
                st.session_state.comparacion_data = f.read()
                st.session_state.reporte_comparacion = reporte_comparacion
            
            with open(output_anexos, "rb") as f:
                st.session_state.anexos_data = f.read()
                st.session_state.reporte_anexos = reporte_anexos

            return {
                'comparacion': reporte_comparacion is not None,
                'anexos': reporte_anexos is not None,
                'datos_dian': datos_dian,
                'datos_subpartidas': datos_subpartidas,
                'reporte_comparacion': reporte_comparacion,
                'reporte_anexos': reporte_anexos
            }

        except Exception as e:
            st.error(f"❌ Error en el procesamiento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
            return None

def mostrar_resultados_consola_comparacion(reporte_comparacion, datos_dian, datos_subpartidas):
    """Muestra resultados detallados de la comparación en la consola/interface"""
    
    if reporte_comparacion is None or reporte_comparacion.empty:
        st.error("No hay datos de comparación para mostrar")
        return
    
    # Resumen general
    st.markdown("**📊 RESUMEN COMPARACIÓN DIM vs SUBPARTIDAS**")
    
    di_individuales = reporte_comparacion[reporte_comparacion['4. Número DI'] != 'VALORES ACUMULADOS']
    conformes = len(di_individuales[di_individuales['Resultado verificación'] == '✅ CONFORME'])
    con_diferencias = len(di_individuales[di_individuales['Resultado verificación'] == '❌ CON DIFERENCIAS'])
    
    st.write(f"• Total DI procesadas: {len(di_individuales)}")
    st.write(f"• DI conformes: {conformes}")
    st.write(f"• DI con diferencias: {con_diferencias}")
    
    # Detalle por DI
    st.markdown("**🔍 DETALLE POR DECLARACIÓN:**")
    for _, di in di_individuales.iterrows():
        numero_di = di['4. Número DI']
        resultado = di['Resultado verificación']
        st.write(f"  - DI {numero_di}: {resultado}")
        
        # Mostrar campos específicos con problemas si hay diferencias
        if '❌' in resultado:
            campos_problema = []
            for col in di.index:
                if '❌' in str(di[col]):
                    campos_problema.append(col)
            if campos_problema:
                st.write(f"    Campos con diferencias: {', '.join(campos_problema[:3])}...")
    
    # Totales acumulados
    fila_totales = reporte_comparacion[reporte_comparacion['4. Número DI'] == 'VALORES ACUMULADOS']
    if not fila_totales.empty:
        st.markdown("**💰 TOTALES ACUMULADOS:**")
        total_di = fila_totales.iloc[0]
        st.write(f"• Resultado totales: {total_di['Resultado verificación']}")

def mostrar_resultados_consola_anexos(reporte_anexos):
    """Muestra resultados detallados de la validación de anexos en la consola/interface"""
    
    if reporte_anexos is None or reporte_anexos.empty:
        st.info("No hay datos de validación de anexos para mostrar")
        return
    
    # Resumen general
    st.markdown("**📋 RESUMEN VALIDACIÓN ANEXOS**")
    
    total_campos = len(reporte_anexos)
    coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '✅ COINCIDE'])
    no_coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '❌ NO COINCIDE'])
    
    st.write(f"• Total campos validados: {total_campos}")
    st.write(f"• Campos correctos: {coincidencias}")
    st.write(f"• Campos con diferencias: {no_coincidencias}")
    
    # Agrupar por DI
    st.markdown("**📄 DETALLE POR DECLARACIÓN:**")
    di_unicos = reporte_anexos['Numero DI'].unique()
    
    for di in di_unicos:
        datos_di = reporte_anexos[reporte_anexos['Numero DI'] == di]
        correctos = len(datos_di[datos_di['Coincidencias'] == '✅ COINCIDE'])
        incorrectos = len(datos_di[datos_di['Coincidencias'] == '❌ NO COINCIDE'])
        
        st.write(f"  - DI {di}: {correctos}✓ / {incorrectos}✗")
        
        # Mostrar campos específicos con problemas
        if incorrectos > 0:
            campos_incorrectos = datos_di[datos_di['Coincidencias'] == '❌ NO COINCIDE']['Campos DI a Validar'].tolist()
            st.write(f"    Campos incorrectos: {', '.join(campos_incorrectos)}")

def mostrar_resultados_en_pantalla(resultados):
    """Muestra los resultados detallados en pantalla"""
    
    st.markdown("---")
    st.header("📊 Resultados de la Conciliación")
    
    # Resultados de Comparación DIM vs Subpartidas
    st.subheader("🔍 Comparación DIM vs Subpartidas")
    
    if resultados['comparacion'] and 'reporte_comparacion' in st.session_state:
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
        
        # Mostrar tabla de resultados
        st.markdown("**Detalle por Declaración:**")
        st.dataframe(reporte, use_container_width=True)
        
        # Mostrar totales acumulados
        fila_totales = reporte[reporte['4. Número DI'] == 'VALORES ACUMULADOS']
        if not fila_totales.empty:
            st.markdown("**Totales Acumulados:**")
            st.dataframe(fila_totales, use_container_width=True)
    else:
        st.error("No se pudo generar el reporte de comparación")

    # Resultados de Validación de Anexos
    st.subheader("📋 Validación de Anexos y Proveedores")
    
    if resultados['anexos'] and 'reporte_anexos' in st.session_state:
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
            
            # Mostrar tabla de validación
            st.markdown("**Detalle de Validación:**")
            st.dataframe(reporte_anexos, use_container_width=True)
        else:
            st.info("No hay datos de validación de anexos para mostrar")
    else:
        st.error("No se pudo generar el reporte de validación de anexos")

def mostrar_botones_descarga():
    """Muestra los botones para descargar los Excel"""
    
    st.markdown("---")
    st.header("📥 Descargar Resultados Completos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if 'comparacion_data' in st.session_state:
            st.download_button(
                label="📊 Descargar Comparación DIM vs Subpartidas (Excel)",
                data=st.session_state.comparacion_data,
                file_name="Comparacion_DIM_Subpartidas.xlsx",
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        else:
            st.button(
                "📊 Comparación No Disponible",
                disabled=True,
                use_container_width=True
            )
    
    with col2:
        if 'anexos_data' in st.session_state:
            st.download_button(
                label="📋 Descargar Validación Anexos (Excel)",
                data=st.session_state.anexos_data,
                file_name="Validacion_Anexos_Proveedores.xlsx", 
                mime="application/vnd.ms-excel",
                use_container_width=True
            )
        else:
            st.button(
                "📋 Validación No Disponible",
                disabled=True,
                use_container_width=True
            )

if __name__ == "__main__":
    main()

