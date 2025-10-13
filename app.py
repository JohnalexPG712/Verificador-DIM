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

# Estilos CSS
st.markdown("""
<style>
    .upload-section {
        border: 2px dashed #cccccc;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 10px 0;
        background-color: #f9f9f9;
    }
    .file-info {
        background-color: #e9ecef;
        border-radius: 5px;
        padding: 8px;
        margin: 5px 0;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

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
        5. **Descargar Resultados**
        """)
        
        if st.button("🗑️ Limpiar Todo", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # Sección de carga de archivos
    st.header("Cargar Archivos")

    # Declaraciones PDF (DIAN)
    st.subheader("Declaraciones PDF (DIAN)")
    with st.container():
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        dian_pdfs = st.file_uploader(
            "Arrastre y suelte archivos PDF de DIAN aquí",
            type=['pdf'],
            accept_multiple_files=True,
            key="dian_pdfs",
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Límite: 200 MB por archivo • PDF")

    if dian_pdfs:
        st.markdown("**Archivos cargados:**")
        for pdf in dian_pdfs:
            st.markdown(f'<div class="file-info">📄 {pdf.name} ({pdf.size / 1024 / 1024:.1f} MB)</div>', 
                       unsafe_allow_html=True)

    # Excel de Subpartidas
    st.subheader("Archivo Excel (Subpartidas)")
    with st.container():
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        excel_subpartidas = st.file_uploader(
            "Arrastre y suelte Excel de subpartidas aquí",
            type=['xlsx', 'xls'],
            key="excel_subpartidas",
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Formatos soportados: XLSX, XLS")

    if excel_subpartidas:
        st.markdown(f'<div class="file-info">📊 {excel_subpartidas.name} ({excel_subpartidas.size / 1024:.1f} KB)</div>', 
                   unsafe_allow_html=True)

    # Excel de Anexos/Proveedores
    st.subheader("Archivo Excel (Anexos y Proveedores)")
    with st.container():
        st.markdown('<div class="upload-section">', unsafe_allow_html=True)
        excel_anexos = st.file_uploader(
            "Arrastre y suelte Excel de anexos/proveedores aquí",
            type=['xlsx', 'xls'],
            key="excel_anexos", 
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
        st.caption("Formatos soportados: XLSX, XLS")

    if excel_anexos:
        st.markdown(f'<div class="file-info">📋 {excel_anexos.name} ({excel_anexos.size / 1024:.1f} KB)</div>', 
                   unsafe_allow_html=True)

    st.markdown("---")

    # Proceso de conciliación
    st.header("Proceso: Conciliación")

    # Verificar archivos mínimos
    archivos_cargados = (
        st.session_state.get('dian_pdfs') and 
        st.session_state.get('excel_subpartidas') and
        st.session_state.get('excel_anexos')
    )

    if not archivos_cargados:
        st.warning("⚠️ Cargue todos los archivos requeridos para continuar")
        return

    # Mostrar resumen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("PDFs DIAN", len(st.session_state.dian_pdfs))
    with col2:
        st.metric("Excel Subpartidas", "✓" if st.session_state.excel_subpartidas else "✗")
    with col3:
        st.metric("Excel Anexos", "✓" if st.session_state.excel_anexos else "✗")

    # Botón de procesamiento
    if st.button("🔄 Ejecutar Conciliación", type="primary", use_container_width=True):
        with st.spinner("Procesando conciliación..."):
            resultados = procesar_conciliacion()
            
            if resultados:
                st.success("✅ Conciliación completada exitosamente")
                mostrar_resultados(resultados)

def procesar_conciliacion():
    """Procesa la conciliación con los archivos cargados"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Guardar archivos en temporal
            for pdf in st.session_state.dian_pdfs:
                with open(os.path.join(temp_dir, pdf.name), "wb") as f:
                    f.write(pdf.getbuffer())
            
            excel_sub_path = os.path.join(temp_dir, st.session_state.excel_subpartidas.name)
            with open(excel_sub_path, "wb") as f:
                f.write(st.session_state.excel_subpartidas.getbuffer())
            
            excel_anexos_path = os.path.join(temp_dir, st.session_state.excel_anexos.name)  
            with open(excel_anexos_path, "wb") as f:
                f.write(st.session_state.excel_anexos.getbuffer())

            # Procesar comparación DIM vs Subpartidas
            st.info("🔍 Comparando DIM vs Subpartidas...")
            
            extractor_dian = ExtractorDIANSimplificado()
            datos_dian = extractor_dian.procesar_multiples_dis(temp_dir)
            
            extractor_subpartidas = ExtractorSubpartidas()
            datos_subpartidas = extractor_subpartidas.extraer_y_estandarizar(temp_dir)
            
            comparador = ComparadorDatos()
            output_comparacion = os.path.join(temp_dir, "comparacion_dim_subpartidas.xlsx")
            reporte_comparacion = comparador.generar_reporte_comparacion(
                datos_dian, datos_subpartidas, output_comparacion
            )

            # Procesar validación de anexos
            st.info("📋 Validando anexos y proveedores...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            reporte_anexos = validador.procesar_validacion_completa(temp_dir, output_anexos)

            # Guardar resultados para descarga
            with open(output_comparacion, "rb") as f:
                st.session_state.comparacion_data = f.read()
            
            with open(output_anexos, "rb") as f:
                st.session_state.anexos_data = f.read()

            return {
                'comparacion': reporte_comparacion is not None,
                'anexos': reporte_anexos is not None
            }

        except Exception as e:
            st.error(f"❌ Error en el procesamiento: {str(e)}")
            return None

def mostrar_resultados(resultados):
    """Muestra los resultados y botones de descarga"""
    
    st.markdown("---")
    st.header("📥 Descargar Resultados")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if resultados['comparacion'] and 'comparacion_data' in st.session_state:
            st.download_button(
                label="📊 Descargar Comparación DIM vs Subpartidas",
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
        if resultados['anexos'] and 'anexos_data' in st.session_state:
            st.download_button(
                label="📋 Descargar Validación Anexos",
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
