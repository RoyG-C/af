import streamlit as st
import pandas as pd
import pdfplumber
import re
import unicodedata

def normalize_name(name):
    nfkd = unicodedata.normalize('NFKD', str(name))
    only_ascii = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z0-9 ]', '', only_ascii).lower().strip()

# --- Custom CSS for colors ---
st.markdown("""
    <style>
        .main {background-color: #f5f5e6;}
        .stApp {background-color: #f5f5e6;}
        h1, h2, h3, h4, h5, h6 {color: #7a9e7e;}
        .css-1d391kg {color: #7a9e7e;}
        .stButton>button {background-color: #7a9e7e; color: white;}
        .stDataFrame {background-color: #f5f5e6;}
    </style>
""", unsafe_allow_html=True)

st.image("logo.png", width=200)

st.title("Insurance PDF/Excel Chatbot")

st.write("Upload your Excel and multiple PDFs to get the price per kg for each client.")

excel_file = st.file_uploader("Upload Excel file", type=["xlsx"])
pdf_files = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

if excel_file and pdf_files:
    df = pd.read_excel(excel_file, header=1)
    df['NormalizedName'] = df['Titular DUN'].apply(normalize_name)

    results = []
    manual_review = []

    for pdf_file in pdf_files:
        client_name = pdf_file.name
        file_match = re.match(r'[A-Z]?\d+(?:-\d+)?\s+(.+)\.pdf', client_name, re.IGNORECASE)
        if not file_match:
            st.error(f"PDF filename format not recognized: {client_name}")
            continue
        client_name_extracted = file_match.group(1)
        st.write(f"Detected client name: **{client_name_extracted}**")
        matches = df[df['NormalizedName'] == normalize_name(client_name_extracted)]
        if matches.empty:
            st.warning(f"No matching client found in Excel for {client_name_extracted}.")
            continue
        total_kgs_excel = matches['TOT KGS'].sum()
        st.write(f"Total KGS from Excel: {total_kgs_excel}")
        with pdfplumber.open(pdf_file) as pdf:
            prod_text = pdf.pages[-1].extract_text()
            section_match = re.search(r'RESUMEN GENERAL PARCELAS(.*)', prod_text, re.DOTALL | re.IGNORECASE)
            if section_match:
                resumen_text = section_match.group(1)
                prod_match = re.search(r'produccion.*?(\d[\d,.]*)\s*kg', resumen_text, re.IGNORECASE)
                if not prod_match:
                    st.error(f"Could not find production (kg) in PDF section for {client_name_extracted}.")
                    continue
                total_kgs_pdf = float(prod_match.group(1).replace('.', '').replace(',', '.'))
                st.write(f"Total KGS from PDF: {total_kgs_pdf}")
                if abs(total_kgs_excel - total_kgs_pdf) > 1:
                    st.warning(f"Excel and PDF total KGS do not match for {client_name_extracted}.")
                    continue
                page2_text = pdf.pages[1].extract_text()
                importe_match = re.search(r'importe domiciliado.*?(\d[\d,.]*)', page2_text, re.IGNORECASE)
                coste_match = re.search(r'total coste tomador.*?(\d[\d,.]*)', page2_text, re.IGNORECASE)
                if importe_match and coste_match:
                    importe = float(importe_match.group(1).replace('.', '').replace(',', '.'))
                    coste = float(coste_match.group(1).replace('.', '').replace(',', '.'))
                    st.write(f"Importe domiciliado: {importe}")
                    st.write(f"Total coste tomador: {coste}")
                    if abs(importe - coste) > 0.01:
                        manual_review.append(client_name_extracted)
                        st.warning(f"Importe and Coste do not match for {client_name_extracted}. Manual review needed.")
                        continue
                    precio_kg = round(importe / total_kgs_pdf, 6)
                    results.append({'Nom': client_name_extracted, 'Preu/kg': precio_kg})
                    st.success(f"Price per kg for {client_name_extracted}: **{precio_kg}**")
                else:
                    st.error(f"Could not find financial data in PDF for {client_name_extracted}.")
            else:
                st.error(f"Section 'RESUMEN GENERAL PARCELAS' not found in PDF for {client_name_extracted}.")

    if results:
        df_results = pd.DataFrame(results)
        df_results['Preu/kg'] = df_results['Preu/kg'].map(lambda x: f"{x:.6f}")
        st.write("Summary Table:")
        st.dataframe(df_results)
    if manual_review:
        st.warning(f"Manual review needed for: {', '.join(manual_review)}")
