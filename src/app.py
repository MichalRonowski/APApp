from __future__ import annotations
import os
from typing import List, Dict, Any

from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash

import pandas as pd

from report import load_config, load_csv, unique_sources, filter_by_sources, ReportBuilder, CSV_COLUMNS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_CSV = os.path.join(BASE_DIR, 'ex_input.csv')
CONFIG_JSON = os.path.join(BASE_DIR, 'config.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = 'dev-secret-key'  # replace via env for production

# Load data at startup
CONFIG: Dict[str, Any] = load_config(CONFIG_JSON)
DF: pd.DataFrame = load_csv(INPUT_CSV)
SOURCES: List[str] = unique_sources(DF)
REPORTER = ReportBuilder(CONFIG)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        selected: List[str] = request.form.getlist('sources')
        if not selected:
            flash('Wybierz co najmniej jeden "Nr źródła".')
            return redirect(url_for('index'))

        # Generate PDFs per document for selected sources
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        files: List[str] = []
        # Filter to selected sources first
        df_sources = filter_by_sources(DF, selected)
        # Group by document number
        doc_col = CSV_COLUMNS["doc_no"]
        for doc_no, df_doc in df_sources.groupby(doc_col):
            rows = REPORTER.build_rows_for_document(df_doc)
            _, doc_date = REPORTER.infer_doc_header(df_doc)
            header = {"document_no": doc_no, "document_date": doc_date}
            safe_doc = str(doc_no).replace('/', '_')
            filename = f"raport_{safe_doc}.pdf"
            out_path = os.path.join(OUTPUT_DIR, filename)
            REPORTER.generate_pdf(out_path, rows, header)
            files.append(filename)
        return render_template('result.html', files=files, count=len(files))

    return render_template('index.html', sources=SOURCES)


@app.route('/download/<path:filename>')
def download(filename: str):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
