"""
Parser untuk dokumen IDX Keterbukaan Informasi:
"Kepemilikan Efek Diatas 5% Berdasarkan SID (Publik) [Semua Emiten Saham]"

Mengekstrak tabel dari halaman 2 sampai halaman terakhir,
mengabaikan noise teks di luar tabel.
"""

import pdfplumber
import pandas as pd
import re


def parse_kepemilikan_5persen(pdf_path, output_path):
    """
    Parse PDF "Kepemilikan Efek Diatas 5% Berdasarkan SID (Publik)"
    dari IDX Keterbukaan Informasi ke file CSV.

    Args:
        pdf_path: Path ke file PDF sumber
        output_path: Path output file CSV
    """
    all_data = []
    headers_found = False

    # Header tabel ini terdiri dari 2 baris (merged cells):
    # Baris 1: No | Kode Efek | Nama Emiten | ... | Kepemilikan Per DD-MMM-YYYY | (None) | (None) | Kepemilikan Per DD-MMM-YYYY | (None) | (None) | Perubahan
    # Baris 2: (None)*11 | Jumlah Saham | Saham Gabungan Per Investor | Persentase ... | Jumlah Saham | Saham Gabungan Per Investor | Persentase ... | (None)
    #
    # Kita gabungkan menjadi satu baris header yang flat.

    # Noise patterns yang harus di-skip
    noise_patterns = [
        "KEPEMILIKAN EFEK",
        "Keterangan",
        "* Font:",
        "Hitam =",
        "Biru =",
        "tidak ada perubahan",
        "persentase kepemilikan",
    ]

    print(f"Opening {pdf_path}...")
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"Total pages: {total_pages}")

        # Parse dari halaman 2 (index 1)
        for i in range(1, total_pages):
            page = pdf.pages[i]
            print(f"Processing page {i+1}/{total_pages}...", end='\r')

            table = page.extract_table()

            if not table:
                print(f"\nNo table found on page {i+1}")
                continue

            for row in table:
                # Bersihkan newline dalam cell
                clean_row = [
                    str(cell).replace('\n', ' ').strip() if cell is not None else ""
                    for cell in row
                ]

                # Skip baris yang sepenuhnya kosong
                if not any(clean_row):
                    continue

                # Skip noise text
                row_text = ' '.join(clean_row)
                if any(noise in row_text for noise in noise_patterns):
                    continue

                # Deteksi header row 1: kolom pertama = "No", kolom kedua = "Kode Efek"
                if clean_row[0] == "No" and clean_row[1] == "Kode Efek":
                    if not headers_found:
                        # Ini header baris 1, simpan sementara
                        header_row_1 = clean_row
                    continue

                # Deteksi header row 2: mengandung "Jumlah Saham"
                if "Jumlah Saham" in clean_row:
                    if not headers_found:
                        header_row_2 = clean_row
                        # Gabungkan 2 baris header
                        headers = _merge_header_rows(header_row_1, header_row_2)
                        headers_found = True
                    continue

                # Data row
                all_data.append(clean_row)

    print("\nExtraction complete.")

    if not all_data:
        print("No data extracted.")
        return

    if not headers_found:
        headers = [f"Col_{i}" for i in range(len(all_data[0]))]

    # Pastikan jumlah kolom konsisten
    max_cols = len(headers)
    normalized_data = []
    for row in all_data:
        if len(row) < max_cols:
            row.extend([""] * (max_cols - len(row)))
        elif len(row) > max_cols:
            row = row[:max_cols]
        normalized_data.append(row)

    df = pd.DataFrame(normalized_data, columns=headers)
    print(f"Dataframe shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")

    # Preview
    print("\n--- Preview (first 5 rows) ---")
    print(df.head().to_string())

    df.to_csv(output_path, index=False)
    print(f"\nSuccessfully saved parsed data to {output_path}")


def _merge_header_rows(row1, row2):
    """
    Gabungkan 2 baris header yang memiliki merged cells.

    Row 1: [No, Kode Efek, ..., Kepemilikan Per 04-MAR-2026, '', '', Kepemilikan Per 05-MAR-2026, '', '', Perubahan]
    Row 2: ['', '', ..., Jumlah Saham, Saham Gabungan Per Investor, Persentase ..., Jumlah Saham, ...]

    Hasil: kolom-kolom yang jelas dan unik.
    """
    merged = []
    last_parent = ""

    for i in range(len(row1)):
        top = row1[i].strip() if i < len(row1) and row1[i] else ""
        bot = row2[i].strip() if i < len(row2) and row2[i] else ""

        if top:
            last_parent = top

        if top and not bot:
            # Kolom biasa (tidak di-merge), misal: No, Kode Efek, Nama Emiten
            merged.append(top)
        elif top and bot:
            # Kolom parent + child, misal: Kepemilikan Per ... + Jumlah Saham
            merged.append(f"{top} - {bot}")
        elif not top and bot:
            # Child tanpa parent (lanjutan dari merged cell di atasnya)
            # Gunakan parent terakhir sebagai prefix
            # Cari apakah parent terakhir mengandung tanggal
            if "Kepemilikan" in last_parent:
                merged.append(f"{last_parent} - {bot}")
            else:
                merged.append(bot)
        else:
            # Keduanya kosong
            merged.append(f"Col_{i}")

    return merged


if __name__ == "__main__":
    # PDF dari IDX Keterbukaan Informasi:
    # "Kepemilikan Efek Diatas 5% Berdasarkan SID (Publik) [Semua Emiten Saham]"
    pdf_file = r"C:\Users\mifta\Desktop\Project\finance\data\20260306_Semua Emiten Saham_Pengumuman Bursa_32041440_lamp1.pdf"
    csv_out = r"C:\Users\mifta\Desktop\Project\finance\data\20260306_Kepemilikan_Efek_5persen_SID.csv"
    parse_kepemilikan_5persen(pdf_file, csv_out)
