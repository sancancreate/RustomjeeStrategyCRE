import streamlit as st
import pandas as pd
import io
from parser_engine import locate_description_column, extract_marathi_property_details

st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("📋 Marathi Property Data Extractor Dashboard")
st.subheader("Transform unstructured regional language descriptions into clean English metrics instantly.")

st.markdown("""
This tool automatically parses uploaded property spreadsheets. It targets Marathi legal descriptions, isolates vital metrics like project identity, wings, component areas, and parking allocations, and builds an aggregate summary spreadsheet ready for instant download.
""")

uploaded_file = st.file_uploader("Upload your property Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.success(f"Successfully loaded file: {uploaded_file.name} ({len(df)} rows found)")
        
        target_column = locate_description_column(df)
        
        if target_column is None:
            st.error("Could not automatically locate a 'Property Description' column in the header row. Please verify your file structure.")
        else:
            st.info(f"Targeting Column Identified: **'{target_column}'**")
            
            if st.button("⚡ Process and Segregate Data", type="primary"):
                processed_rows = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                total_rows = len(df)
                
                for idx, row in df.iterrows():
                    raw_text = row[target_column]
                    extracted_metrics = extract_marathi_property_details(raw_text)
                    processed_rows.append(extracted_metrics)
                    
                    if idx % max(1, total_rows // 20) == 0 or idx == total_rows - 1:
                        progress_percent = int(((idx + 1) / total_rows) * 100)
                        progress_bar.progress(progress_percent)
                        status_text.text(f"Processing row {idx + 1} of {total_rows}...")
                
                # Create a fresh isolated dataframe containing ONLY the 7 extracted columns
                extracted_df = pd.DataFrame(processed_rows)
                
                # Store this clean dataframe directly inside the session memory
                st.session_state['processed_data'] = extracted_df
                status_text.text("Processing Complete!")
                st.balloons()
            
            if 'processed_data' in st.session_state:
                output_df = st.session_state['processed_data']
                
                st.markdown("---")
                st.subheader("👀 Extracted Data Preview (Clean English Metrics)")
                columns_to_show = ['Project Name', 'Tower Number', 'Carpet Area (sq ft)', 'Balcony Area (sq ft)', 'Utility Area (sq ft)', 'Total Area (sq ft)', 'Parking Space']
                st.dataframe(output_df[columns_to_show].head(10))
                
                # Generate an Excel engine buffer containing ONLY the clean 7-column data frame
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    output_df.to_excel(writer, index=False, sheet_name='Summary English Report')
                buffer.seek(0)
                
                st.markdown("### 📥 Download Isolated Results")
                st.markdown("This download contains strictly the 7 parameters extracted and parsed from your source document description field.")
                st.download_button(
                    label="Download Isolated Clean Excel File",
                    data=buffer,
                    file_name=f"Clean_Summary_{uploaded_file.name.split('.')[0]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
    except Exception as e:
        st.error(f"An unexpected data processing error occurred: {e}")
