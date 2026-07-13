import sys
import os
import streamlit as st
import pandas as pd
import io

# Ensure the app can find parser_engine in the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from parser_engine import locate_column_by_keywords, extract_marathi_property_details

st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("📊 Marathi Property Data Extractor Dashboard")
st.subheader("Transform unstructured regional language descriptions into clean English metrics instantly.")

uploaded_file = st.file_uploader("Upload your property Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        st.markdown("### 🛠️ Data Import Settings")
        
        has_header = st.checkbox(
            "File has valid column headers on Row 1 (Uncheck if Row 1 contains actual row data)", 
            value=False
        )
        
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=0 if has_header else None)
        else:
            df = pd.read_excel(uploaded_file, header=0 if has_header else None)
        
        if not has_header:
            df.columns = [f"Column_{i}" for i in range(len(df.columns))]
            
        st.success(f"Successfully loaded file: {uploaded_file.name} ({len(df)} rows found)")
        
        # --- ROBUST COLUMN DETECTION LOGIC ---
        all_columns = [str(c) for c in df.columns]
        
        desc_col_guess = locate_column_by_keywords(df, ['property description', 'description', 'वर्णन', 'मालमत्ता'])
        proj_col_guess = locate_column_by_keywords(df, ['project', 'प्रकल्प', 'नाव', 'building name'])
        tower_col_guess = locate_column_by_keywords(df, ['tower', 'wing', 'बिल्डिंग', 'विंग', 'इमारत'])
        unit_col_guess = locate_column_by_keywords(df, ['unit', 'flat', 'सदनिका', 'फ्लॅट', 'शॉप', 'नं'])

        def get_column_index(detected_col, columns_list, fallback=0):
            if detected_col and str(detected_col) in columns_list:
                return columns_list.index(str(detected_col))
            return fallback

        st.markdown("### 🔍 Column Target Mapping Settings")
        st.write("Match up your spreadsheet columns below. The tool uses direct column mapping for Project, Tower, and Unit properties for 100% data reliability.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            selected_desc_column = st.selectbox(
                "1. Raw Property Description Column (Calculates Areas/Parking):",
                options=all_columns,
                index=get_column_index(desc_col_guess, all_columns, 0)
            )
            selected_proj_column = st.selectbox(
                "2. Project Name Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(proj_col_guess, all_columns, 0) if proj_col_guess else 0
            )

        with col2:
            selected_tower_column = st.selectbox(
                "3. Tower / Wing Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(tower_col_guess, all_columns, 0) if tower_col_guess else 0
            )
            selected_unit_column = st.selectbox(
                "4. Unit / Flat Number Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(unit_col_guess, all_columns, 0) if unit_col_guess else 0
            )
        
        if st.button("🚀 Process and Segregate Data", type="primary"):
            processed_rows = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                raw_text = str(row[selected_desc_column])
                
                extracted_metrics = extract_marathi_property_details(
                    raw_text=raw_text, 
                    row_context=row,
                    project_col=selected_proj_column,
                    tower_col=selected_tower_column,
                    unit_col=selected_unit_column
                )
                processed_rows.append(extracted_metrics)
                
                if idx % max(1, total_rows // 20) == 0 or idx == total_rows - 1:
                    progress_percent = int(((idx + 1) / total_rows) * 100)
                    progress_bar.progress(progress_percent)
                    status_text.text(f"Processing row {idx + 1} of {total_rows}...")
            
            extracted_df = pd.DataFrame(processed_rows)
            st.session_state['processed_data'] = extracted_df
            status_text.text("Processing Complete!")
            st.balloons()
        
        if 'processed_data' in st.session_state:
            output_df = st.session_state['processed_data']
            st.markdown("---")
            st.subheader("📋 Extracted Data Preview")
            
            target_columns = [
                'Project Name', 'Tower/Wing', 'Floor Number', 'Unit Number', 
                'Carpet Area (sq ft)', 'Balcony Area (sq ft)', 'Utility Area (sq ft)', 
                'Total Area (sq ft)', 'Parking Space'
            ]
            
            columns_to_show = [col for col in target_columns if col in output_df.columns]
            st.dataframe(output_df[columns_to_show].head(15), use_container_width=True)
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                output_df.to_excel(writer, index=False, sheet_name='Summary English Report')
            buffer.seek(0)
            
            st.markdown("### 💾 Download Isolated Results")
            st.download_button(
                label="Download Isolated Clean Excel File",
                data=buffer,
                file_name=f"Clean_Summary_{uploaded_file.name.split('.')[0]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    except Exception as e:
        st.error(f"An unexpected data processing error occurred: {e}")
