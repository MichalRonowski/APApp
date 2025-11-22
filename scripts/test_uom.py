import os
import sys

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.report import load_csv, CSV_COLUMNS, load_uom_lookup, apply_uom_lookup, ReportBuilder


def main():
    base = ROOT
    input_csv = os.path.join(base, 'ex_input.csv')
    lookup_csv = os.path.join(base, 'output', 'Jednostki.csv')

    df = load_csv(input_csv)
    lookup = load_uom_lookup(lookup_csv)
    apply_uom_lookup(df, lookup)

    doc = 'WD/25/31995'
    col_doc = CSV_COLUMNS['doc_no']
    sub = df[df[col_doc] == doc].copy()
    rb = ReportBuilder({'title': 't'})
    rows = rb.build_rows_for_document(sub)
    print('rows:', len(rows))
    print('lookup size:', len(lookup))
    print('first 5:', [(r.name[:25], r.uom) for r in rows[:5]])


if __name__ == '__main__':
    main()
