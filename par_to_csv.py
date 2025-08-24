import pandas as pd
import os

# Define the input and output file paths
input_parquet_file = r"data\sessions\S03_SUBJ001_20250814\raw\polar_h10_raw.parquet"
output_csv_file = r"data\sessions\S03_SUBJ001_20250814\raw\polar_h10_raw.csv"

# Make sure the output directory exists
output_dir = os.path.dirname(output_csv_file)
if not os.path.exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Created directory: {output_dir}")

# Read the parquet file into a pandas DataFrame
try:
    df = pd.read_parquet(input_parquet_file)
    print("Parquet file loaded successfully.")

    # Convert the rr_ms_list column to a string representation
    df['rr_ms_list'] = df['rr_ms_list'].astype(str)

    # Convert the DataFrame to a CSV file
    df.to_csv(output_csv_file, index=False)
    print(f"Data successfully converted and saved to {output_csv_file}")

except Exception as e:
    print(f"An error occurred: {e}")