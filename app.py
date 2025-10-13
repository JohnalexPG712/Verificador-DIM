import streamlit as st
import pandas as pd
import os
import tempfile
import sys
from io import BytesIO

# Configuración de la página
st.set_page_config(
    page_title="Verificación DIM vs FMM",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .upload-section {
        border: 2px dashed #cccccc;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
        background-color: #f9f9f9;
    }
    .file-info {
        background-color: #e9ecef;
        border-radius: 5px;
        padding: 0.5rem;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .process-section {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Header principal
    st.markdown('<h1 class="main-header">Verificación DIM vs FMM</h1>', unsafe_allow_html=True)
    st.markdown("**Verificador de datos Declaración de Importación vs Formulario de Movimiento de Mercancías**")
    
    # Sidebar con instrucciones
    with st.sidebar:
        st.markdown("### 📋 Instrucciones de Uso")
        st.markdown("""
        1. **Cargar Archivos**: Sube los PDFs de DIAN y el Excel de subpartidas
        2. **Procesar**: Ejecuta la verificación de datos
        3. **Descargar**: Obtén los reportes en Excel
        
        **Formatos soportados:**
        - PDF: Declaraciones de Importación (DIAN)
        - XLSX: Archivo de subpartidas
        - PDF: Formularios FMM
        """)
        
        st.markdown("---")
        if st.button("🔄 Limpiar Todo", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Pestañas para organizar las funcionalidades
    tab1, tab2 = st.tabs(["📤 Cargar Archivos", "⚙️ Procesar Datos"])
    
    with tab1:
        render_upload_section()
    
    with tab2:
        render_processing_section()

def render_upload_section():
    st.markdown('<h2 class="sub-header">Cargar Archivos</h2>', unsafe_allow_html=True)
    
    # Sección para PDFs de DIAN
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📄 Declaraciones PDF (DIAN)")
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        dian_pdfs = st.file_uploader(
            "Arrastre y suelte archivos PDF de DIAN aquí",
            type=['pdf'],
            accept_multiple_files=True,
            key="dian_pdfs"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Límite: 200MB por archivo PDF")
        
        if dian_pdfs:
            st.markdown(f"**📁 {len(dian_pdfs)} archivo(s) PDF cargado(s):**")
            for pdf in dian_pdfs:
                st.markdown(f'<div class="file-info">📄 {pdf.name} ({pdf.size / 1024 / 1024:.2f} MB)</div>', 
                           unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📊 Archivo Excel (Subpartidas)")
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        excel_file = st.file_uploader(
            "Arrastre y suelte archivo Excel de subpartidas aquí",
            type=['xlsx', 'xls'],
            key="excel_file"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Formatos soportados: XLSX, XLS")
        
        if excel_file:
            st.markdown(f"**📁 Archivo Excel cargado:**")
            st.markdown(f'<div class="file-info">📊 {excel_file.name} ({excel_file.size / 1024 / 1024:.2f} MB)</div>', 
                       unsafe_allow_html=True)
    
    # Sección para formularios FMM
    st.markdown("### 📋 Formularios PDF (FMM)")
    st.markdown('<div class="upload-section">', unsafe_allow_html=True)
    fmm_pdfs = st.file_uploader(
        "Arrastre y suelte archivos PDF de formularios FMM aquí",
        type=['pdf'],
        accept_multiple_files=True,
        key="fmm_pdfs"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("Límite: 200MB por archivo PDF")
    
    if fmm_pdfs:
        st.markdown(f"**📁 {len(fmm_pdfs)} archivo(s) FMM cargado(s):**")
        for pdf in fmm_pdfs:
            st.markdown(f'<div class="file-info">📋 {pdf.name} ({pdf.size / 1024 / 1024:.2f} MB)</div>', 
                       unsafe_allow_html=True)

def render_processing_section():
    st.markdown('<h2 class="sub-header">Procesar Datos</h2>', unsafe_allow_html=True)
    
    # Verificar que hay archivos cargados
    has_dian_pdfs = 'dian_pdfs' in st.session_state and st.session_state.dian_pdfs
    has_excel_file = 'excel_file' in st.session_state and st.session_state.excel_file
    has_fmm_pdfs = 'fmm_pdfs' in st.session_state and st.session_state.fmm_pdfs
    
    if not has_dian_pdfs and not has_excel_file and not has_fmm_pdfs:
        st.warning("⚠️ Por favor, carga archivos en la pestaña 'Cargar Archivos' antes de procesar.")
        return
    
    # Mostrar resumen de archivos cargados
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("PDFs DIAN", len(st.session_state.dian_pdfs) if has_dian_pdfs else 0)
    with col2:
        st.metric("Excel Subpartidas", 1 if has_excel_file else 0)
    with col3:
        st.metric("PDFs FMM", len(st.session_state.fmm_pdfs) if has_fmm_pdfs else 0)
    
    # Selector de proceso
    st.markdown('<div class="process-section">', unsafe_allow_html=True)
    process_option = st.radio(
        "Selecciona el proceso a ejecutar:",
        [
            "🔍 Comparación DIM vs Subpartida", 
            "📋 Validación Anexos FMM vs DIM",
            "⚡ Proceso Completo (Ambos)"
        ],
        index=2
    )
    
    # Botón de procesamiento
    if st.button("🚀 Ejecutar Proceso", type="primary", use_container_width=True):
        process_data(process_option)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Mostrar resultados si existen
    show_download_buttons()

def process_data(process_option):
    """Ejecuta el procesamiento de datos según la opción seleccionada"""
    
    # Crear carpeta temporal para procesamiento
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Guardar archivos en carpeta temporal
            if st.session_state.dian_pdfs:
                for pdf in st.session_state.dian_pdfs:
                    with open(os.path.join(temp_dir, pdf.name), "wb") as f:
                        f.write(pdf.getbuffer())
            
            if st.session_state.excel_file:
                excel_path = os.path.join(temp_dir, st.session_state.excel_file.name)
                with open(excel_path, "wb") as f:
                    f.write(st.session_state.excel_file.getbuffer())
            
            if st.session_state.fmm_pdfs:
                for pdf in st.session_state.fmm_pdfs:
                    with open(os.path.join(temp_dir, pdf.name), "wb") as f:
                        f.write(pdf.getbuffer())
            
            # Importar el módulo de verificación
            from verificacion_dim import (
                ExtractorDIANSimplificado,
                ComparadorDatos,
                ExtractorSubpartidas,
                ValidadorDeclaracionImportacionCompleto
            )
            
            # Ejecutar procesos según la opción seleccionada
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            if "Comparación DIM" in process_option or "Completo" in process_option:
                status_text.text("🔍 Ejecutando comparación DIM vs Subpartida...")
                result1 = run_comparison_dian_subpartida(temp_dir)
                progress_bar.progress(50)
                
                if result1 is not None:
                    st.session_state.comparison_result = result1
                    st.markdown('<div class="success-box">✅ Comparación DIM vs Subpartida completada</div>', 
                               unsafe_allow_html=True)
                else:
                    st.error("❌ Error en comparación DIM vs Subpartida")
            
            if "Validación Anexos" in process_option or "Completo" in process_option:
                status_text.text("📋 Ejecutando validación de anexos FMM...")
                result2 = run_validation_anexos(temp_dir)
                progress_bar.progress(100)
                
                if result2 is not None:
                    st.session_state.validation_result = result2
                    st.markdown('<div class="success-box">✅ Validación de anexos FMM completada</div>', 
                               unsafe_allow_html=True)
                else:
                    st.error("❌ Error en validación de anexos FMM")
            
            status_text.text("✅ Proceso completado")
            
        except Exception as e:
            st.error(f"❌ Error durante el procesamiento: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

def run_comparison_dian_subpartida(temp_dir):
    """Ejecuta la comparación DIM vs Subpartida"""
    try:
        from verificacion_dim import ExtractorDIANSimplificado, ComparadorDatos, ExtractorSubpartidas
        
        # Extraer datos DIAN
        extractor_dian = ExtractorDIANSimplificado()
        datos_dian = extractor_dian.procesar_multiples_dis(temp_dir)
        
        if datos_dian is None or datos_dian.empty:
            st.warning("No se pudieron extraer datos de los PDFs de DIAN")
            return None
        
        # Extraer datos subpartidas
        extractor_subpartidas = ExtractorSubpartidas()
        datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(temp_dir)
        
        if datos_subpartidas.empty:
            st.warning("No se pudieron extraer datos del archivo de subpartidas")
            return None
        
        # Comparar datos
        comparador = ComparadorDatos()
        
        # Crear archivo de salida temporal
        output_path = os.path.join(temp_dir, "comparison_result.xlsx")
        reporte = comparador.generar_reporte_comparacion(
            datos_dian, datos_subpartidas, output_path
        )
        
        if reporte is not None and not reporte.empty:
            # Guardar en session state para descarga
            with open(output_path, "rb") as f:
                st.session_state.comparison_excel_data = f.read()
            return reporte
        
        return None
        
    except Exception as e:
        st.error(f"Error en comparación DIM vs Subpartida: {str(e)}")
        return None

def run_validation_anexos(temp_dir):
    """Ejecuta la validación de anexos FMM"""
    try:
        from verificacion_dim import ValidadorDeclaracionImportacionCompleto
        
        validador = ValidadorDeclaracionImportacionCompleto()
        
        # Crear archivo de salida temporal
        output_path = os.path.join(temp_dir, "validation_result.xlsx")
        
        # Ejecutar validación
        resultado = validador.procesar_validacion_completa(temp_dir, output_path)
        
        if resultado is not None:
            # Guardar en session state para descarga
            with open(output_path, "rb") as f:
                st.session_state.validation_excel_data = f.read()
            return resultado
        
        return None
        
    except Exception as e:
        st.error(f"Error en validación de anexos: {str(e)}")
        return None

def show_download_buttons():
    """Muestra botones de descarga para los resultados"""
    if 'comparison_excel_data' in st.session_state or 'validation_excel_data' in st.session_state:
        st.markdown("---")
        st.markdown("### 📥 Descargar Resultados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'comparison_excel_data' in st.session_state:
                st.download_button(
                    label="📊 Descargar Comparación DIM vs Subpartida",
                    data=st.session_state.comparison_excel_data,
                    file_name="Resultado_Validacion_Subpartida_vs_DIM.xlsx",
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
            if 'validation_excel_data' in st.session_state:
                st.download_button(
                    label="📋 Descargar Validación Anexos FMM",
                    data=st.session_state.validation_excel_data,
                    file_name="Resultado_Validacion_Anexos_FMM_vs_DIM.xlsx",
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

