from pathlib import Path
import argparse
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Preview and optionally convert the NazwyKlienci Excel file misnamed as .csv")
    parser.add_argument("--path", default=str(Path(__file__).resolve().parents[1] / "data" / "NazwyKlienci.csv"), help="Path to the file (Excel content, .csv extension)")
    parser.add_argument("--sheet", default=None, help="Sheet name to load (defaults to the first sheet)")
    parser.add_argument("--rows", type=int, default=10, help="Number of rows to preview")
    parser.add_argument("--to-csv", dest="to_csv", default=None, help="Optional output CSV path to save the selected sheet")
    args = parser.parse_args()

    p = Path(args.path)
    if not p.exists():
        raise SystemExit(f"File not found: {p}")

    print(f"Reading Excel content from: {p}")
    xl = pd.ExcelFile(p, engine="openpyxl")
    print("Sheets:", ", ".join(xl.sheet_names))

    sheet = args.sheet or xl.sheet_names[0]
    print(f"\nLoading sheet: {sheet}")
    df = xl.parse(sheet)
    print("\nColumns:")
    print(list(df.columns))

    n = min(args.rows, len(df))
    print(f"\nPreview (first {n} rows):")
    if n > 0:
        print(df.head(n).to_string(index=False))
    else:
        print("<empty sheet>")

    if args.to_csv:
        out = Path(args.to_csv)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        print(f"\nSaved sheet '{sheet}' to CSV: {out}")


if __name__ == "__main__":
    main()
