import re
import pandas as pd

def locate_description_column(df):
    """
    Scans the column headers of an uploaded dataframe to automatically
    detect variations of the 'Property Description' header.
    """
    possible_targets = [
        'property description', 'property_description', 'description', 
        'property details', 'property_details', 'वर्णन', 'मालमत्ता वर्णन'
    ]
    
    # Normalize column names to lowercase strings for matching
    for col in df.columns:
        normalized_col = str(col).strip().lower()
        if normalized_col in possible_targets or any(target in normalized_col for target in possible_targets):
            return col
            
    # Fallback to looking for index 21 (Column V) if explicit text matching fails
    if len(df.columns) > 21:
        return df.columns[21]
        
    return None

def extract_marathi_property_details(text):
    """
    Parses unstructured Marathi Index II legal descriptions into structured English fields.
    """
    if pd.isna(text):
        return {
            'Project Name': 'Not Mentioned',
            'Tower Number': 'Not Mentioned',
            'Carpet Area (sq ft)': 0.0,
            'Balcony Area (sq ft)': 0.0,
            'Utility Area (sq ft)': 0.0,
            'Total Area (sq ft)': 0.0,
            'Parking Space': '0'
        }
    
    text = str(text).strip()
    
    # 1. Project Name Extraction
    # Catches name variations sitting between "वरील / येथील" (above/at) and "प्रोजेक्ट / प्रकल्प" (project)
    project_match = re.search(r'(?:वरील|येथील)\s+(.*?)\s+(?:प्रोजेक्ट|प्रकल्प)', text)
    project_name = project_match.group(1).strip() if project_match else "Not Mentioned"
    
    # 2. Tower / Building Extraction
    # Catches building numbers and building name markers
    tower_match = re.search(r'(?:बिल्डिंग\s+नं\.|इमारत\s+क्र\.)\s*([0-9\w\-]+),(.*?)\s+(?:बिल्डिंग|इमारत)', text)
    if tower_match:
        tower = f"Building {tower_match.group(1).strip()} ({tower_match.group(2).strip()})"
    else:
        # Alt check for standalone Wing or Tower text
        alt_tower = re.search(r'([A-Za-z0-9\s\-]+)\s*(?:विंग|टॉवर|टॉवर नं)', text)
        tower = alt_tower.group(0).strip() if alt_tower else "Not Mentioned"
        
    # 3. Area Extraction (Extracts the float directly preceding Marathi area markers)
    # Carpet Area
    carpet_match = re.search(r'(?:क्षेत्रफळ|चटईक्षेत्र)\s*([0-9.]+)\s*चौ\.\s*फु\.', text)
    carpet_area = float(carpet_match.group(1)) if carpet_match else 0.0
    
    # Balcony Area
    balcony_match = re.search(r'\+\s*([0-9.]+)\s*चौ\.\s*फु\..*?(?:बाल्कनी|गॅलरी)', text)
    balcony_area = float(balcony_match.group(1)) if balcony_match else 0.0
    
    # Utility Area
    utility_match = re.search(r'\+\s*([0-9.]+)\s*चौ\.\s*फु\..*?(?:युटिलिटी|ड्राय)', text)
    utility_area = float(utility_match.group(1)) if utility_match else 0.0
    
    # 4. Mathematical Area Aggregation (Guarantees absolute math integrity)
    total_area = carpet_area + balcony_area + utility_area
    
    # 5. Parking Space Count Extraction
    # Evaluates explicit counts or keywords indicating space allocation
    parking_match = re.search(r'\+\s*(\d+)\s+(?:पोडीयम|पार्किंग|वाहनाचा)', text)
    if parking_match:
        parking_desc = str(parking_match.group(1))
    elif "पार्किंग स्पेस सहित" in text or "पार्किंग" in text:
        parking_desc = "1"
    else:
        parking_desc = "0"

    return {
        'Project Name': project_name,
        'Tower Number': tower,
        'Carpet Area (sq ft)': carpet_area,
        'Balcony Area (sq ft)': balcony_area,
        'Utility Area (sq ft)': utility_area,
        'Total Area (sq ft)': total_area,
        'Parking Space': parking_desc
    }
