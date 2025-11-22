import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.report import load_config, load_csv, CSV_COLUMNS, load_uom_lookup, apply_uom_lookup, ReportBuilder


def main():
    base = ROOT
    input_csv = os.path.join(base, 'ex_input.csv')
    config_json = os.path.join(base, 'config.json')
    output_dir = os.path.join(base, 'output')
    os.makedirs(output_dir, exist_ok=True)

    cfg = load_config(config_json)
    df = load_csv(input_csv)

    # Apply units mapping from output/Jednostki.csv when available
    lookup_csv = os.path.join(output_dir, 'Jednostki.csv')
    apply_uom_lookup(df, load_uom_lookup(lookup_csv))

    doc = 'WD/25/31995'
    col_doc = CSV_COLUMNS['doc_no']
    sub = df[df[col_doc] == doc].copy()
    rb = ReportBuilder(cfg)
    rows = rb.build_rows_for_document(sub)

    out_pdf = os.path.join(output_dir, 'raport_TEST.pdf')
    header = {"document_no": doc, "document_date": rb.infer_doc_header(sub)[1]}
    rb.generate_pdf(out_pdf, rows, header)
    print('Generated:', out_pdf)


if __name__ == '__main__':
    main()
