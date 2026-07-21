import io
import logging
import os
import sys
import time

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from parser_engine import (
    auto_detect_description_column,
    locate_column_by_keywords,
    parse_property_description,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("igr_app")

st.set_page_config(page_title="Marathi Property Data Extractor", layout="wide")

st.title("📊 Marathi Property Data Extractor Dashboard")
st.subheader("Transform unstructured regional language descriptions into clean, structured metrics — v2 engine.")

uploaded_file = st.file_uploader("Upload your property Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        st.markdown("### 🛠️ Data Import Settings")

        has_header = st.checkbox(
            "File has valid column headers on Row 1 (Uncheck if Row 1 contains actual row data)",
            value=True,
        )

        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, header=0 if has_header else None)
        else:
            df = pd.read_excel(uploaded_file, header=0 if has_header else None, engine="calamine")

        if not has_header:
            df.columns = [f"Column_{i}" for i in range(len(df.columns))]

        st.success(f"Successfully loaded file: {uploaded_file.name} ({len(df)} rows found)")

        all_columns = [str(c) for c in df.columns]

        # Automatic column detection (keyword-based, with a text-density
        # fallback for the free-text description column — no hardcoded
        # "Column V" assumption).
        desc_col_guess = auto_detect_description_column(df)
        proj_col_guess = locate_column_by_keywords(df, ["project", "प्रकल्प", "नाव", "building name"])
        tower_col_guess = locate_column_by_keywords(df, ["tower", "wing", "बिल्डिंग", "विंग", "इमारत"])
        unit_col_guess = locate_column_by_keywords(df, ["unit", "flat", "सदनिका", "फ्लॅट", "शॉप", "नं"])

        def get_column_index(detected_col, columns_list, fallback=0):
            if detected_col and str(detected_col) in columns_list:
                return columns_list.index(str(detected_col))
            return fallback

        st.markdown("### 🔍 Column Target Mapping Settings")
        st.write(
            "Auto-detected columns are pre-selected below — override any of them if the guess is wrong. "
            "Project, Tower and Unit can either come directly from a column, or be extracted from the description text."
        )

        col1, col2 = st.columns(2)

        with col1:
            selected_desc_column = st.selectbox(
                "1. Raw Property Description Column (Calculates Areas/Parking):",
                options=all_columns,
                index=get_column_index(desc_col_guess, all_columns, 0),
            )
            selected_proj_column = st.selectbox(
                "2. Project Name Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(proj_col_guess, all_columns, 0) if proj_col_guess else 0,
            )

        with col2:
            selected_tower_column = st.selectbox(
                "3. Tower / Wing Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(tower_col_guess, all_columns, 0) if tower_col_guess else 0,
            )
            selected_unit_column = st.selectbox(
                "4. Unit / Flat Number Column:",
                options=["Extract from Description text instead"] + all_columns,
                index=get_column_index(unit_col_guess, all_columns, 0) if unit_col_guess else 0,
            )

        include_debug_report = st.checkbox(
            "Generate parser_debug_report.csv (recommended — shows detected pattern, "
            "confidence, and any validation warnings for every row)",
            value=True,
        )

        if st.button("🚀 Process and Segregate Data", type="primary"):
            processed_rows = []
            debug_rows = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_rows = len(df)
            start_time = time.time()

            success_count = partial_count = failed_count = 0

            for idx, row in df.iterrows():
                raw_text = row[selected_desc_column]

                result = parse_property_description(
                    raw_text=raw_text,
                    row_context=row,
                    project_col=selected_proj_column,
                    tower_col=selected_tower_column,
                    unit_col=selected_unit_column,
                )
                processed_rows.append(result.as_output_row())
                if include_debug_report:
                    debug_rows.append(result.debug_row())

                if result.parse_status == "Success":
                    success_count += 1
                elif result.parse_status == "Partial":
                    partial_count += 1
                else:
                    failed_count += 1

                step = max(1, total_rows // 20)
                if idx % step == 0 or idx == total_rows - 1:
                    progress_percent = int(((idx + 1) / total_rows) * 100)
                    progress_bar.progress(progress_percent)
                    status_text.text(f"Processing row {idx + 1} of {total_rows}...")

            elapsed = time.time() - start_time
            extracted_df = pd.DataFrame(processed_rows)
            st.session_state["processed_data"] = extracted_df
            st.session_state["debug_data"] = pd.DataFrame(debug_rows) if include_debug_report else None

            avg_conf = extracted_df["Confidence"].mean() if "Confidence" in extracted_df else 0

            logger.info(
                "Processed %d rows in %.2fs | Success=%d Partial=%d Failed=%d | Avg confidence=%.1f",
                total_rows, elapsed, success_count, partial_count, failed_count, avg_conf,
            )

            status_text.text("Processing Complete!")
            st.balloons()

            st.markdown("### 📈 Parsing Summary")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Total Rows", total_rows)
            m2.metric("Successful", success_count)
            m3.metric("Partial", partial_count)
            m4.metric("Failed", failed_count)
            m5.metric("Avg. Confidence", f"{avg_conf:.1f}")

            if "Detected Pattern" in extracted_df.columns:
                pattern_counts = extracted_df["Detected Pattern"].value_counts()
                st.markdown("**Parser (format) used per row:**")
                st.bar_chart(pattern_counts)

        if "processed_data" in st.session_state:
            output_df = st.session_state["processed_data"]
            st.markdown("---")
            st.subheader("📋 Extracted Data Preview")

            target_columns = [
                "Project Name", "Tower/Wing", "Unit Number",
                "Carpet Area (Sq M)", "Attached Area (Sq M)", "Balcony Area (Sq M)",
                "Utility Area (Sq M)", "Total Area (Sq M)", "Total Area (Sq Ft)",
                "Parking", "Detected Pattern", "Confidence", "Parse Status",
            ]
            columns_to_show = [col for col in target_columns if col in output_df.columns]
            st.dataframe(output_df[columns_to_show].head(15), use_container_width=True)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                # Never overwrite the original description: keep the source
                # sheet's raw data alongside the parsed output.
                original_with_desc = df.copy()
                original_with_desc.to_excel(writer, index=False, sheet_name="Original Data")
                output_df.to_excel(writer, index=False, sheet_name="Summary English Report")
            buffer.seek(0)

            st.markdown("### 💾 Download Results")
            dl1, dl2 = st.columns(2)
            with dl1:
                st.download_button(
                    label="Download Clean Excel File",
                    data=buffer,
                    file_name=f"Clean_Summary_{uploaded_file.name.split('.')[0]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with dl2:
                debug_df = st.session_state.get("debug_data")
                if debug_df is not None:
                    debug_buffer = io.StringIO()
                    debug_df.to_csv(debug_buffer, index=False)
                    st.download_button(
                        label="Download parser_debug_report.csv",
                        data=debug_buffer.getvalue(),
                        file_name="parser_debug_report.csv",
                        mime="text/csv",
                    )

    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected error while processing upload")
        st.error(f"An unexpected data processing error occurred: {e}")
