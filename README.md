# Marathi Property Data Extractor Dashboard

An entirely open-source, local, and API-free data refinery app built in Python and Streamlit. It parses unstructured regional language real estate metadata text fields (such as Sub-Registrar Index II document copies) into clean, ready-for-analysis English column models.

## App Capabilities
- **Automated Column Discovery:** Automatically scans row 1 headers for variations of "Property Description".
- **Deterministic Field Extraction:** Extracts Project Identity, Wings/Towers, Carpet Area, Balconies, Utilities, and Parking allocations.
- **Pure Python Speed Architecture:** Zero API reliance means processing thousands of rows finishes in seconds at zero cost.
- **Downstream Verification Protection:** Computes total areas directly via Python math formulas to block data discrepancies.

## Local Installation Steps

1. Clone this repository onto your machine:
```bash
git clone <your-github-repo-url>
cd <your-repo-folder-name>
