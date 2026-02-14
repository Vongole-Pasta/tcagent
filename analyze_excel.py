
import pandas as pd
import os

file_path = "GYDX-COM-TE-D262-_DB_구조_개선_통합테스트_VOD__20230825.xlsx"

try:
    xl = pd.ExcelFile(file_path)
    print(f"Sheet names: {xl.sheet_names}")
    
    target_sheets = ['시나리오', 'VOD']
    for sheet in target_sheets:
        if sheet in xl.sheet_names:
            print(f"\n--- Sheet: {sheet} (Raw Data Inspection) ---")
            # Read first 15 rows without header assumption
            df = xl.parse(sheet, header=None, nrows=15)
            # Print row index and content for visual mapping
            for idx, row in df.iterrows():
                # Filter out NaN values for cleaner output
                compact_row = {k: v for k, v in row.to_dict().items() if pd.notna(v)}
                print(f"Row {idx}: {compact_row}")
except Exception as e:
    print(f"Error reading excel file: {e}")
