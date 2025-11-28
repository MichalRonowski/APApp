from __future__ import annotations
import os
import sys
from typing import List, Dict, Any

from flask import Flask, render_template, request, send_from_directory, redirect, url_for, flash
from werkzeug.utils import secure_filename

import pandas as pd

try:
    # When imported as a package (e.g., from desktop wrapper / PyInstaller)
    from .report import (
        load_config,
        load_csv,
        unique_sources,
        filter_by_sources,
        load_uom_lookup,
        apply_uom_lookup,
        ReportBuilder,
        ReportRow,
        CSV_COLUMNS,
        _parse_date_any,
    )
except Exception:  # fallback for running as a script: python src/app.py
    from report import (
        load_config,
        load_csv,
        unique_sources,
        filter_by_sources,
        load_uom_lookup,
        apply_uom_lookup,
        ReportBuilder,
        ReportRow,
        CSV_COLUMNS,
        _parse_date_any,
    )

def _bundle_root() -> str:
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _app_data_root() -> str:
    """Get the application's data root directory."""
    if getattr(sys, 'frozen', False):
        # Running in a bundle
        return sys._MEIPASS
    else:
        # Running in a normal Python environment
        # This should be the project root, so we go up one level from src
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def _resource_path(*parts: str) -> str:
    return os.path.join(_bundle_root(), *parts)

BASE_DIR = _app_data_root()
INPUT_CSV = os.path.join(BASE_DIR, 'ex_input.csv')
CONFIG_JSON = os.path.join(BASE_DIR, 'config.json')
BASE_CUSTOMERS_JSON = os.path.join(BASE_DIR, 'base_customers.json')
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
TEMPLATES_DIR = _resource_path('templates')
STATIC_DIR = _resource_path('static')

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR, static_url_path='/static')
app.secret_key = 'dev-secret-key'  # replace via env for production

# Ensure essential data files exist next to the EXE; if missing, seed from bundled copies
def _ensure_data_files() -> None:
    os.makedirs(BASE_DIR, exist_ok=True)
    # Seed config.json
    if not os.path.exists(CONFIG_JSON):
        src = _resource_path('config.json')
        if os.path.exists(src):
            try:
                import shutil
                shutil.copyfile(src, CONFIG_JSON)
            except Exception:
                pass
    # Seed ex_input.csv
    if not os.path.exists(INPUT_CSV):
        src = _resource_path('ex_input.csv')
        if os.path.exists(src):
            try:
                import shutil
                shutil.copyfile(src, INPUT_CSV)
            except Exception:
                pass
    # Optional: seed logo.png if present in bundle and missing externally
    logo_dst = os.path.join(BASE_DIR, 'logo.png')
    if not os.path.exists(logo_dst):
        src = _resource_path('logo.png')
        if os.path.exists(src):
            try:
                import shutil
                shutil.copyfile(src, logo_dst)
            except Exception:
                pass
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _load_customer_names() -> Dict[str, str]:
    """Loads customer name mapping from NazwyKlienci.csv"""
    # Path is now relative to the app data root
    path = os.path.join(_app_data_root(), 'NazwyKlienci.csv')
    if not os.path.exists(path):
        # Fallback for dev environment where it might be in output
        path = os.path.join(_app_data_root(), 'output', 'NazwyKlienci.csv')
        if not os.path.exists(path):
            return {}
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        # Check for actual column names in the CSV file
        if 'Nr' in df.columns and 'Nazwa szukana' in df.columns:
            return dict(zip(df['Nr'], df['Nazwa szukana']))
        else:
            return {}
    except Exception:
        return {}

def _load_base_customers() -> List[str]:
    """Loads list of base customer IDs from base_customers.json"""
    if not os.path.exists(BASE_CUSTOMERS_JSON):
        return []
    try:
        import json
        with open(BASE_CUSTOMERS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('base_customers', [])
    except Exception:
        return []

def _save_base_customers(customer_ids: List[str]) -> None:
    """Saves list of base customer IDs to base_customers.json"""
    try:
        import json
        with open(BASE_CUSTOMERS_JSON, 'w', encoding='utf-8') as f:
            json.dump({'base_customers': customer_ids}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Call once on import
_ensure_data_files()

# Load data at startup
CONFIG: Dict[str, Any] = load_config(CONFIG_JSON)
DF: pd.DataFrame = load_csv(INPUT_CSV)
# Apply UOM lookup from output/Jednostki.csv if present
_uom_lookup_path = os.path.join(OUTPUT_DIR, 'Jednostki.csv')
DF = apply_uom_lookup(DF, load_uom_lookup(_uom_lookup_path))
SOURCES: List[str] = unique_sources(DF)
CUSTOMER_NAMES: Dict[str, str] = _load_customer_names()
BASE_CUSTOMERS: List[str] = _load_base_customers()
REPORTER = ReportBuilder(CONFIG)


def _reload_data() -> None:
    global CONFIG, DF, SOURCES, REPORTER, CUSTOMER_NAMES, BASE_CUSTOMERS
    CONFIG = load_config(CONFIG_JSON)
    DF = load_csv(INPUT_CSV)
    _uom_lookup_path = os.path.join(OUTPUT_DIR, 'Jednostki.csv')
    DF = apply_uom_lookup(DF, load_uom_lookup(_uom_lookup_path))
    SOURCES = unique_sources(DF)
    CUSTOMER_NAMES = _load_customer_names()
    BASE_CUSTOMERS = _load_base_customers()
    REPORTER = ReportBuilder(CONFIG)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        selected: List[str] = request.form.getlist('sources')
        if not selected:
            flash('Wybierz co najmniej jeden "Nr źródła".')
            return redirect(url_for('index'))
        # Redirect to preview instead of generating PDFs directly
        return redirect(url_for('preview', sources=','.join(selected)))

    # Filter sources based on base customers (if defined)
    filtered_sources = SOURCES
    if BASE_CUSTOMERS:
        filtered_sources = [s for s in SOURCES if s in BASE_CUSTOMERS]
    
    source_names = {s: CUSTOMER_NAMES.get(s, s) for s in filtered_sources}
    return render_template('index.html', sources=filtered_sources, source_names=source_names)


@app.route('/preview', methods=['GET'])
def preview():
    """Preview all tables before generating PDFs."""
    sources_param = request.args.get('sources', '')
    if not sources_param:
        flash('Brak wybranych źródeł.')
        return redirect(url_for('index'))
    
    selected = [s.strip() for s in sources_param.split(',') if s.strip()]
    if not selected:
        flash('Brak wybranych źródeł.')
        return redirect(url_for('index'))
    
    # Generate preview data for all documents
    df_sources = filter_by_sources(DF, selected)
    doc_col = CSV_COLUMNS["doc_no"]
    source_col = CSV_COLUMNS["source_no"]
    
    documents = []
    for doc_no, df_doc in df_sources.groupby(doc_col):
        rows = REPORTER.build_rows_for_document(df_doc)
        _, doc_date = REPORTER.infer_doc_header(df_doc)
        
        # Get customer name from source number mapping
        customer_name = ""
        if source_col in df_doc.columns:
            source_no = next((str(v).strip() for v in df_doc[source_col].tolist() if str(v).strip()), "")
            customer_name = CUSTOMER_NAMES.get(source_no, source_no)
        
        # Convert rows to dict format for JSON/template
        rows_data = []
        for r in rows:
            # Special handling for z00155: show "nie dotyczy"
            if r.item_no.lower() == "z00155":
                exp_str = 'nie dotyczy'
            else:
                exp_str = REPORTER._format_date_pl(r.expiry) if r.expiry else ''
            rows_data.append({
                'lp': r.lp,
                'name': r.name,
                'qty': REPORTER._format_qty_pl(r.qty),
                'uom': r.uom,
                'lot_no': r.lot_no,
                'expiry': exp_str,
                'item_no': r.item_no
            })
        
        documents.append({
            'doc_no': doc_no,
            'doc_date': doc_date,
            'customer_name': customer_name,
            'rows': rows_data
        })
    
    return render_template('preview.html', documents=documents, sources=sources_param)


@app.route('/generate-final', methods=['POST'])
def generate_final():
    """Generate PDFs from edited table data."""
    data = request.get_json()
    if not data or 'documents' not in data:
        return {'success': False, 'error': 'Brak danych'}, 400
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files: List[str] = []
    
    try:
        for doc_data in data['documents']:
            doc_no = doc_data.get('doc_no', '')
            doc_date = doc_data.get('doc_date', '')
            customer_name = doc_data.get('customer_name', '')
            rows_data = doc_data.get('rows', [])
            
            # Convert back to ReportRow objects
            rows = []
            for r in rows_data:
                # Parse quantity back from Polish format
                qty_str = str(r.get('qty', '0')).replace('\u202f', '').replace(',', '.').strip()
                try:
                    qty = float(qty_str) if qty_str else 0.0
                except:
                    qty = 0.0
                
                # Parse date
                exp_str = r.get('expiry', '').strip()
                expiry = None
                if exp_str:
                    try:
                        expiry = _parse_date_any(exp_str)
                    except:
                        pass
                
                rows.append(ReportRow(
                    lp=r.get('lp', 0),
                    name=r.get('name', ''),
                    qty=qty,
                    uom=r.get('uom', ''),
                    lot_no=r.get('lot_no', ''),
                    expiry=expiry,
                    item_no=r.get('item_no', '')
                ))
            
            # Generate PDF
            header = {
                "document_no": doc_no, 
                "document_date": doc_date,
                "customer_name": customer_name
            }
            
            # Create filename: "Atest do dostawy [nazwa klienta] [data dokumentu] [nr dokumentu].pdf"
            # Sanitize customer name and doc_no for filename
            safe_customer = customer_name.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            safe_doc = doc_no.replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            safe_date = doc_date.replace('/', '_').replace('\\', '_').replace(':', '_')
            
            filename = f"Atest do dostawy {safe_customer} {safe_date} {safe_doc}.pdf"
            out_path = os.path.join(OUTPUT_DIR, filename)
            REPORTER.generate_pdf(out_path, rows, header)
            files.append(filename)
        
        return {'success': True, 'files': files, 'count': len(files)}
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


@app.route('/define-base-customers', methods=['GET', 'POST'])
def define_base_customers():
    if request.method == 'POST':
        selected: List[str] = request.form.getlist('customers')
        _save_base_customers(selected)
        global BASE_CUSTOMERS
        BASE_CUSTOMERS = selected
        flash(f'Zapisano {len(selected)} bazowych klientów.')
        return redirect(url_for('index'))
    
    # Show ALL customers from NazwyKlienci.csv
    # Sort: first by whether they're selected (checked first), then alphabetically by name
    all_customer_ids = list(CUSTOMER_NAMES.keys())
    
    # Sort by: 1) checked status (True first), 2) customer name alphabetically
    all_customer_ids.sort(key=lambda cid: (
        cid not in BASE_CUSTOMERS,  # False (checked) comes before True (unchecked)
        CUSTOMER_NAMES.get(cid, cid).upper()  # Then alphabetically by name
    ))
    
    source_names = {s: CUSTOMER_NAMES.get(s, s) for s in all_customer_ids}
    return render_template('define_base_customers.html', 
                         sources=all_customer_ids, 
                         source_names=source_names,
                         base_customers=BASE_CUSTOMERS)

@app.route('/upload', methods=['POST'])
def upload():
    f = request.files.get('input_file')
    if not f or f.filename == '':
        flash('Wybierz plik .xlsx lub .csv do wgrania.')
        return redirect(url_for('index'))
    filename = secure_filename(f.filename)
    name_lower = filename.lower()
    tmp_path = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    try:
        if name_lower.endswith('.xlsx') or name_lower.endswith('.xls'):
            # Read Excel and convert to canonical CSV expected by pipeline
            df_x = pd.read_excel(f, dtype=str)
            # Normalize NaNs to empty strings for parity with load_csv()
            df_x = df_x.fillna('')
            df_x.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
        elif name_lower.endswith('.csv'):
            # Save/replace canonical CSV
            f.save(tmp_path)
            # Re-encode to UTF-8-SIG to avoid BOM/encoding issues
            try:
                df_c = pd.read_csv(tmp_path, dtype=str, keep_default_na=False, encoding='utf-8-sig')
            except UnicodeDecodeError:
                # Fallback common on Windows exports
                df_c = pd.read_csv(tmp_path, dtype=str, keep_default_na=False, encoding='cp1250')
            df_c.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
        else:
            flash('Nieobsługiwany format. Wgraj .xlsx lub .csv')
            return redirect(url_for('index'))
        flash('Plik został wgrany. Lista źródeł odświeżona.')
        _reload_data()
    except Exception as e:
        flash(f'Błąd wgrywania pliku: {e}')
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    return redirect(url_for('index'))


@app.route('/result', methods=['GET', 'POST'])
def show_results():
    """Display result page with generated files."""
    if request.method == 'POST':
        files = request.form.getlist('files')
        count = request.form.get('count', len(files))
    else:
        files = request.args.getlist('files')
        count = request.args.get('count', len(files))
    return render_template('result.html', files=files, count=count)


@app.route('/download/<path:filename>')
def download(filename: str):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
