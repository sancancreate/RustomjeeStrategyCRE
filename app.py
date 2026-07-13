import sys
import os
import streamlit as st
import pandas as pd
import io

# Ensure the app can find parser_engine in the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from parser_engine import locate_description_column, extract_marathi_property_details

st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("📊 Marathi Property Data Extractor")

uploaded_file = st.file_uploader("Upload your property Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        # --- HEADER CONTROL ---
        # Default to False if you find errors, to treat the first row as data
        has_header = st.checkbox("File has valid column headers (row 1)", value=False)
        
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=0 if has_header else None)
        else:
            df = pd.read_excel(uploaded_file, header=0 if has_header else None)
        
        # If we treat the first row as data, assign generic column names
        if not has_header:
            df.columns = [f"Column_{i}" for i in range(len(df.columns))]
            
        st.success(f"File loaded: {uploaded_file.name} ({len(df)} rows)")
        
        # --- CRASH-PROOF COLUMN DETECTION ---
        all_columns = [str(c) for c in df.columns]
        detected_col = locate_description_column(df)
        
        # Safely find the index
        default_idx = 0
        if detected_col:
            for i, col in enumerate(all_columns):
                # Using a loose check to avoid 'is not in list' errors
                if str(detected_col) in col:
                    default_idx = i
                    break
        else:
            st.warning("Could not auto-detect column. Please select it manually below.")
            
        st.markdown("### 🔍 Select the Description Column")
        selected_column = st.selectbox(
            "Which column contains the Property Description?",
            options=all_columns,
            index=default_idx
        )
        
        st.info(f"Active Extraction Target: **'{selected_column}'**")
        
        if st.button("🚀 Process Data", type="primary"):
            processed_rows = []
            total_rows = len(df)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, row in df.iterrows():
                # Extract using the column name selected by the user
                raw_text = str(row[selected_column])
                extracted_metrics = extract_marathi_property_details(raw_text, row_context=row)
                processed_rows.append(extracted_metrics)
                
                if idx % 5 == 0:
                    progress_bar.progress((idx + 1) / total_rows)
                    status_text.text(f"Processing row {idx + 1} of {total_rows}...")
            
            extracted_df = pd.DataFrame(processed_rows)
            st.session_state['processed_data'] = extracted_df
            st.balloons()
            st.success("Processing Complete!")
        
        if 'processed_data' in st.session_state:
            st.dataframe(st.session_state['processed_data'].head(10))
            
            # Download Logic
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                st.session_state['processed_data'].to_excel(writer, index=False)
            buffer.seek(0)
            
            st.download_button("Download Clean Excel", buffer, "Clean_Summary.xlsx", "application/vnd.ms-excel")
            
    except Exception as e:
        st.error(f"Error: {e}")
