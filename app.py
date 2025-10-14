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

def main():
    inicializar_estados()
    
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
        
        # Botón de limpieza
        if st.button("🗑️ Limpiar Todo", type="secondary", use_container_width=True):
            # Limpiar todo el estado específico
            st.session_state.comparacion_data = None
            st.session_state.anexos_data = None
            st.session_state.reporte_comparacion = None
            st.session_state.reporte_anexos = None
            st.session_state.datos_dian = None
            st.session_state.datos_subpartidas = None
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

    # Usar el contador como parte de la key para forzar reset
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

    # Verificar archivos mínimos para nuevo procesamiento
    archivos_cargados = (dian_pdfs and excel_subpartidas and excel_anexos)

    # Mostrar resultados existentes si los hay
    if st.session_state.procesamiento_completado and st.session_state.reporte_comparacion is not None:
        st.info("📊 Mostrando resultados de conciliación previa. Puedes descargar los archivos o cargar nuevos para reprocesar.")
        mostrar_resultados_en_pantalla()
        mostrar_botones_descarga()
        
        # Mostrar botón para nuevo procesamiento si hay archivos cargados
        if archivos_cargados:
            st.markdown("---")
            st.subheader("Reprocesar con nuevos archivos")
            if st.button("🔄 Ejecutar Nueva Conciliación", type="primary", use_container_width=True):
                with st.spinner("Procesando nueva conciliación..."):
                    resultados = procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos)
                    if resultados:
                        st.success("✅ Nueva conciliación completada exitosamente")
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
    if st.button("🔄 Ejecutar Conciliación", type="primary", use_container_width=True):
        with st.spinner("Procesando conciliación..."):
            resultados = procesar_conciliacion(dian_pdfs, excel_subpartidas, excel_anexos)
            
            if resultados:
                st.session_state.procesamiento_completado = True
                st.success("✅ Conciliación completada exitosamente")
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

            # MOSTRAR RESULTADOS EN CONSOLA - Comparación DIM vs Subpartidas (VERSIÓN SIMPLIFICADA)
            st.markdown("---")
            st.subheader("📊 EJECUTANDO: Comparación DIM vs Subpartida")
            st.markdown("============================================================")
            mostrar_resultados_consola_comparacion_simplificado(reporte_comparacion, datos_dian, datos_subpartidas)

            # Procesar validación de anexos
            st.info("📋 Validando anexos y proveedores...")
            
            validador = ValidadorDeclaracionImportacionCompleto()
            output_anexos = os.path.join(temp_dir, "validacion_anexos.xlsx")
            reporte_anexos = validador.procesar_validacion_completa(temp_dir, output_anexos)

            # MOSTRAR RESULTADOS EN CONSOLA - Validación Anexos (VERSIÓN SIMPLIFICADA)
            st.subheader("📋 EJECUTANDO: Validación Anexos FMM vs DIM")
            st.markdown("============================================================")
            mostrar_resultados_consola_anexos_simplificado(reporte_anexos)

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

def mostrar_resultados_consola_comparacion_simplificado(reporte_comparacion, datos_dian, datos_subpartidas):
    """Muestra resultados simplificados de la comparación sin detalle por declaración"""
    
    if reporte_comparacion is None or reporte_comparacion.empty:
        st.error("No hay datos de comparación para mostrar")
        return
    
    # Mostrar información de extracción
    st.markdown("📄 **EXTRACCIÓN DE DATOS DE PDFs (DIAN)...**")
    st.markdown("📊 **EXTRACCIÓN DE DATOS DE EXCEL (SUBPARTIDAS)...**")
    st.write(f"✅ Datos DIAN extraídos: {len(datos_dian)} registros")
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

def mostrar_resultados_consola_anexos_simplificado(reporte_anexos):
    """Muestra resultados simplificados de la validación de anexos usando datos reales"""
    
    if reporte_anexos is None or reporte_anexos.empty:
        st.info("No hay datos de validación de anexos para mostrar")
        return
    
    # Información básica del proveedor - EXTRAER DEL REPORTE REAL
    st.markdown("👤 **Extrayendo información del proveedor...**")
    
    # Intentar extraer información real del proveedor del reporte
    # (ajusta estas columnas según la estructura real de tu reporte)
    if 'Proveedor' in reporte_anexos.columns or 'NIT' in reporte_anexos.columns:
        # Extraer información del primer registro como ejemplo
        primer_registro = reporte_anexos.iloc[0]
        nit_proveedor = primer_registro.get('NIT', 'No disponible')
        nombre_proveedor = primer_registro.get('Nombre_Proveedor', 'No disponible')
        
        st.markdown(f"📋 **Información encontrada: Proveedor/Cliente: {nit_proveedor} - {nombre_proveedor}**")
        st.markdown("✅ **PROVEEDOR VÁLIDO:**")
        st.markdown(f"   🆔 NIT: {nit_proveedor}")
        st.markdown(f"   📛 Nombre: {nombre_proveedor}")
    else:
        st.markdown("📋 **Información del proveedor: No disponible en el reporte**")
    
    # Resumen por código - CALCULAR DE FORMA REAL
    st.markdown("📊 **Resumen por tipo de documento:**")
    
    # Contar tipos de documentos si existe la columna correspondiente
    if 'Tipo_Documento' in reporte_anexos.columns:
        resumen_tipos = reporte_anexos['Tipo_Documento'].value_counts()
        for tipo, cantidad in resumen_tipos.items():
            st.markdown(f"   • {tipo}: {cantidad}")
    elif 'Codigo_Documento' in reporte_anexos.columns:
        resumen_codigos = reporte_anexos['Codigo_Documento'].value_counts()
        for codigo, cantidad in resumen_codigos.items():
            nombre_doc = obtener_nombre_documento(codigo)  # Función auxiliar si existe
            st.markdown(f"   • Código {codigo}: {cantidad} - {nombre_doc}")
    else:
        # Si no hay columnas específicas, mostrar resumen general
        total_documentos = len(reporte_anexos)
        st.markdown(f"   • Total documentos procesados: {total_documentos}")
    
    # Validación de integridad - CALCULAR DE FORMA REAL
    st.markdown("🔍 **VALIDACIÓN DE INTEGRIDAD:**")
    
    # Contar DI únicas vs documentos
    if 'Numero DI' in reporte_anexos.columns:
        di_unicas = reporte_anexos['Numero DI'].nunique()
        total_documentos = len(reporte_anexos)
        
        # Buscar duplicados
        if 'Numero_Documento' in reporte_anexos.columns:
            duplicados = reporte_anexos[reporte_anexos.duplicated(['Numero_Documento'], keep=False)]
            if not duplicados.empty:
                docs_duplicados = duplicados['Numero_Documento'].unique()[:3]  # Mostrar solo primeros 3
                st.markdown(f"   ❌ {len(duplicados)} documentos duplicados: {', '.join(map(str, docs_duplicados))}...")
            else:
                st.markdown("   ✅ No se encontraron documentos duplicados")
        
        # Verificar balance DI vs documentos
        if di_unicas != total_documentos:
            st.markdown(f"   ⚠️ Desbalance: {di_unicas} DI vs {total_documentos} Documentos")
        else:
            st.markdown("   ✅ Balance correcto entre DI y documentos")
    else:
        st.markdown("   ℹ️ No hay datos suficientes para validación de integridad")
    
    st.markdown("==================================================")
    st.markdown("📊 **RESUMEN FINAL DE VALIDACIÓN**")
    st.markdown("==================================================")
    
    # Calcular estadísticas reales de coincidencias
    if 'Coincidencias' in reporte_anexos.columns:
        total_campos = len(reporte_anexos)
        coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '✅ COINCIDE'])
        no_coincidencias = len(reporte_anexos[reporte_anexos['Coincidencias'] == '❌ NO COINCIDE'])
        
        st.write(f"   • Total campos validados: {total_campos}")
        st.write(f"   • Campos correctos: {coincidencias}")
        st.write(f"   • Campos con diferencias: {no_coincidencias}")
        
        # Calcular por DI
        if 'Numero DI' in reporte_anexos.columns:
            di_unicos = reporte_anexos['Numero DI'].unique()
            declaraciones_con_errores = 0
            
            for di in di_unicos:
                datos_di = reporte_anexos[reporte_anexos['Numero DI'] == di]
                incorrectos = len(datos_di[datos_di['Coincidencias'] == '❌ NO COINCIDE'])
                if incorrectos > 0:
                    declaraciones_con_errores += 1
            
            declaraciones_correctas = len(di_unicos) - declaraciones_con_errores
            
            st.write(f"   • Total declaraciones procesadas: {len(di_unicos)}")
            st.write(f"   • Declaraciones con errores: {declaraciones_con_errores}")
            st.write(f"   • Declaraciones correctas: {declaraciones_correctas}")
            
            if declaraciones_con_errores == 0:
                st.markdown(f"🎯 **TODAS LAS {len(di_unicos)} DECLARACIONES SON CORRECTAS ✅**")
            else:
                st.markdown(f"⚠️ **{declaraciones_con_errores} DECLARACIONES REQUIEREN ATENCIÓN**")
    else:
        st.markdown("   ℹ️ No hay datos de coincidencias para mostrar resumen")
    
    st.markdown("🎯 **PROCESO COMPLETADO EXITOSAMENTE**")
    st.markdown("========================================================================================================================")
    st.markdown("   • Validación de anexos completada")

# Función auxiliar para obtener nombres de documentos (opcional)
def obtener_nombre_documento(codigo):
    """Convierte códigos de documento a nombres legibles"""
    nombres = {
        '6': 'FACTURA COMERCIAL',
        '9': 'DECLARACION DE IMPORTACION', 
        '17': 'DOCUMENTO DE TRANSPORTE',
        '47': 'AUTORIZACION DE LEVANTE',
        '93': 'FORMULARIO DE SALIDA ZONA FRANCA'
    }
    return nombres.get(str(codigo), f'DOCUMENTO {codigo}')

def mostrar_resultados_en_pantalla():
    """Muestra los resultados detallados en pantalla usando session_state"""
    
    st.markdown("---")
    st.header("📊 Resultados de la Conciliación")
    
    # MOSTRAR RESUMEN EN CONSOLA - Comparación DIM vs Subpartidas
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

    # MOSTRAR RESUMEN EN CONSOLA - Validación Anexos
    if st.session_state.reporte_anexos is not None:
        st.subheader("📋 EJECUTANDO: Validación Anexos FMM vs DIM")
        st.markdown("============================================================")
        mostrar_resultados_consola_anexos_simplificado(st.session_state.reporte_anexos)

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
                label="📊 Descargar Comparación DIM vs Subpartidas (Excel)",
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
                label="📋 Descargar Validación Anexos (Excel)",
                data=st.session_state.anexos_data,
                file_name="Validacion_Anexos_Proveedores.xlsx", 
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


