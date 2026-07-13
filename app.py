import sys
import os
import streamlit as st
import pandas as pd
import io

# Ensure the app can find parser_engine in the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from parser_engine import locate_description_column, extract_marathi_property_details

st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("📊 Marathi Property Data Extractor Dashboard")
st.subheader("Transform unstructured regional language descriptions into clean English metrics instantly.")

st.markdown("""
This tool automatically parses uploaded property spreadsheets. It targets Marathi legal descriptions, isolates vital metrics like project identity, wings, floor levels, unit numbers, component areas, and parking allocations, and builds an aggregate summary spreadsheet ready for instant download.
""")

uploaded_file = st.file_uploader("Upload your property Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        st.markdown("### 🛠️ Data Import Settings")
        
        # Defaulting to False because property sheets often contain raw text on row 1
        has_header = st.checkbox(
            "File has valid column headers on Row 1 (Uncheck if Row 1 contains actual data text)", 
            value=False
        )
        
        # Load the file based on header settings
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, header=0 if has_header else None)
        else:
            df = pd.read_excel(uploaded_file, header=0 if has_header else None)
        
        # If we treat the first row as raw data, assign generic tracking column names
        if not has_header:
            df.columns = [f"Column_{i}" for i in range(len(df.columns))]
            
        st.success(f"Successfully loaded file: {uploaded_file.name} ({len(df)} rows found)")
        
        # --- ROBUST COLUMN DETECTION ---
        all_columns = [str(c) for c in df.columns]
        detected_col = locate_description_column(df)
        
        # Find index safely using safe list matching loops to prevent UI crashes
        default_idx = 0
        if detected_col:
            for i, col in enumerate(all_columns):
                if str(detected_col) in col:
                    default_idx = i
                    break
        else:
            st.warning("Could not auto-detect the description column. Please select it manually below.")
            
        st.markdown("### 🔍 Column Target Settings")
        selected_column = st.selectbox(
            "Select the specific column containing the Marathi property descriptions:",
            options=all_columns,
            index=default_idx
        )
        
        st.info(f"Active Extraction Target Column: **'{selected_column}'**")
        
        if st.button("🚀 Process and Segregate Data", type="primary"):
            processed_rows = []
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_rows = len(df)
            
            for idx, row in df.iterrows():
                # Convert raw text to string explicitly to protect parser integrity
                raw_text = str(row[selected_column])
                extracted_metrics = extract_marathi_property_details(raw_text, row_context=row)
                processed_rows.append(extracted_metrics)
                
                # Update progress tracking UI incrementally
                if idx % max(1, total_rows // 20) == 0 or idx == total_rows - 1:
                    progress_percent = int(((idx + 1) / total_rows) * 100)
                    progress_bar.progress(progress_percent)
                    status_text.text(f"Processing row {idx + 1} of {total_rows}...")
            
            extracted_df = pd.DataFrame(processed_rows)
            st.session_state['processed_data'] = extracted_df
            status_text.text("Processing Complete!")
            st.balloons()
        
        # --- DISPLAY RESULTS AND PREVIEW ---
        if 'processed_data' in st.session_state:
            output_df = st.session_state['processed_data']
            
            st.markdown("---")
            st.subheader("📋 Extracted Data Preview")
            
            # Master target list matching the keys from your updated parser engine
            target_columns = [
                'Project Name', 'Tower Number', 'Floor Number', 'Unit Number', 
                'Carpet Area (sq ft)', 'Balcony Area (sq ft)', 'Utility Area (sq ft)', 
                'Total Area (sq ft)', 'Parking Space'
            ]
            
            # Filter safely to prevent KeyErrors if any structural deviations happen
            columns_to_show = [col for col in target_columns if col in output_df.columns]
            st.dataframe(output_df[columns_to_show].head(15), use_container_width=True)
            
            # Compile file for downstream download using openpyxl
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
