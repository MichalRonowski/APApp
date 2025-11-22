# Generator raportów PDF

Aplikacja webowa (Flask) i skrypt CLI do generowania raportów PDF na podstawie `ex_input.csv`.

- Wybierasz `Nr źródła` (kol. 7) w UI.
- System generuje raporty PDF per `Nr dokumentu` znaleziony w wybranych źródłach.

## Wymagania
- Python 3.10+

## Instalacja (Windows PowerShell)
```powershell
# (opcjonalnie) utwórz i aktywuj wirtualne środowisko
py -3 -m venv .venv; .\.venv\Scripts\Activate.ps1

# zainstaluj zależności
pip install -r requirements.txt
```

## Uruchomienie aplikacji webowej
```powershell
$env:FLASK_APP = "src/app.py"; python src/app.py
# Otwórz przeglądarkę: http://127.0.0.1:5000
```

## Generowanie raportu (CLI)
```powershell
# Wszystkie dokumenty z danego źródła
python generate_sample.py --source N3222

# Konkretny dokument z danego źródła
python generate_sample.py --source N3222 --doc WD/25/31995
```

## Konfiguracja nagłówków/stopki
Edytuj `config.json` aby zmienić:
- `company_header` – linie adresowe w nagłówku
- `title` – tytuł dokumentu
- `footer_texts` – teksty na końcu dokumentu

## Założenia agregacji
- Raport jest generowany per `Nr dokumentu`.
- Sumujemy w ramach dokumentu tylko wiersze, które mają identyczne: `Nazwa` + `Nr partii` + `Data ważności` (+ `Jednostka miary`).
- Preferujemy wiersze `Wydanie sprzedaży` (lub ujemne ilości). Ilość podajemy jako wartość bezwzględną.
- Daty w PDF są w formacie `dd.mm.yyyy`.
- Kolumna „Jednostka miary”: jeśli nie ma w CSV, staramy się ją rozpoznać heurystycznie z nazwy produktu (np. `kg`, `l`, `szt`).

W razie potrzeby dopasujemy format PDF (układ, kolumny) dokładniej do przykładu.
