import pdfplumber
import pandas as pd
import sys
import os

def parse_pdf_to_csv(pdf_path, output_path):
    all_data = []
    headers = None
    
    print(f"Opening {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}")
        
        # Start parsing from page 2 (index 1) to the end
        for i in range(1, total_pages):
            page = pdf.pages[i]
            print(f"Processing page {i+1}/{total_pages}...", end='\r')
            
            # extract_table automatically ignores text outside drawn tables
            table = page.extract_table()
            
            if table:
                for row in table:
                    # Remove newline characters that might be inside cells due to text wrapping
                    clean_row = [str(cell).replace('\n', ' ').strip() if cell is not None else "" for cell in row]
                    
                    # Identify the header
                    # Usually the header is 'DATE', 'SHARE_CODE', etc.
                    if clean_row[0] == "DATE" and clean_row[1] == "SHARE_CODE":
                        if headers is None:
                            headers = clean_row
                        continue # Skip appending header repeatedly
                    
                    # Ignore empty rows
                    if not any(clean_row):
                        continue
                        
                    all_data.append(clean_row)
            else:
                print(f"\nNo table found on page {i+1}")
                
    print("\nExtraction complete.")
    
    if not all_data:
        print("No data extracted.")
        return
        
    if headers is None:
        headers = [f"Col_{i}" for i in range(len(all_data[0]))]
        
    df = pd.DataFrame(all_data, columns=headers)
    print(f"Dataframe shape: {df.shape}")
    
    df.to_csv(output_path, index=False)
    print(f"Successfully saved parsed data to {output_path}")

if __name__ == "__main__":
    # PDF dari IDX Keterbukaan Informasi: "Pemegang Saham di atas 1% (KSEI) [Semua Emiten Saham]"
    pdf_file = r"C:\Users\mifta\Desktop\Project\finance\data\20260303_Pemegang_Saham_1persen_KSEI.pdf"
    csv_out = r"C:\Users\mifta\Desktop\Project\finance\data\20260303_Pemegang_Saham_1persen_KSEI.csv"
    parse_pdf_to_csv(pdf_file, csv_out)
