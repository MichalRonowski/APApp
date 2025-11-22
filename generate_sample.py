from __future__ import annotations
import os
from typing import List, Dict, Any

from src.report import (
    load_config,
    load_csv,
    filter_by_sources,
    ReportBuilder,
    CSV_COLUMNS,
    load_uom_lookup,
    apply_uom_lookup,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(BASE_DIR, 'ex_input.csv')
CONFIG_JSON = os.path.join(BASE_DIR, 'config.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='Nr źródła, np. N3222')
    ap.add_argument('--doc', required=False, help='Nr dokumentu; jeśli nie podasz, wygenerujemy dla wszystkich dokumentów z wybranego źródła')
    args = ap.parse_args()

    cfg = load_config(CONFIG_JSON)
    df = load_csv(INPUT_CSV)
    # Apply unit mapping from output/Jednostki.csv if present
    uom_lookup_path = os.path.join(OUTPUT_DIR, 'Jednostki.csv')
    df = apply_uom_lookup(df, load_uom_lookup(uom_lookup_path))
    df_s = filter_by_sources(df, [args.source])
    reporter = ReportBuilder(cfg)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    doc_col = CSV_COLUMNS["doc_no"]
    if args.doc:
        if doc_col not in df_s.columns:
            raise SystemExit("Brak kolumny 'Nr dokumentu' w CSV")
        df_doc = df_s[df_s[doc_col] == args.doc]
        rows = reporter.build_rows_for_document(df_doc)
        _, doc_date = reporter.infer_doc_header(df_doc)
        header = {"document_no": args.doc, "document_date": doc_date}
        safe_doc = str(args.doc).replace('/', '_')
        out = os.path.join(OUTPUT_DIR, f'raport_{safe_doc}.pdf')
        reporter.generate_pdf(out, rows, header)
        print(f'Wygenerowano: {out}')
    else:
        count = 0
        for doc_no, df_doc in df_s.groupby(doc_col):
            rows = reporter.build_rows_for_document(df_doc)
            _, doc_date = reporter.infer_doc_header(df_doc)
            header = {"document_no": doc_no, "document_date": doc_date}
            safe_doc = str(doc_no).replace('/', '_')
            out = os.path.join(OUTPUT_DIR, f'raport_{safe_doc}.pdf')
            reporter.generate_pdf(out, rows, header)
            print(f'Wygenerowano: {out}')
            count += 1
        print(f'Łącznie plików: {count}')
