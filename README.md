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
 - Kolumna „Jednostka miary”: ignorowana przy wczytywaniu. Jednostki NIE są już wykrywane heurystycznie z nazwy. Zawsze pochodzą wyłącznie z zewnętrznego pliku `output/Jednostki.csv`.

### Jedyny źródłowy plik jednostek: `output/Jednostki.csv`
Jednostki w raportach pochodzą **wyłącznie** z pliku `output/Jednostki.csv` (kolumny: `Nr` oraz kolumna zawierająca słowo `jednostka`, np. `Podst. jednostka miary`).

Brak heurystyki ani danych z `ex_input.csv` – jeśli kod `Nr zapasu` nie występuje w `Jednostki.csv`, pole jednostki w PDF będzie puste.

Normalizacja skrótów obejmuje: `KG`, `SZT`, `L`, `G`, `ML` (inne wartości przechodzą w formie uppercase bez zmian).

Plik jest dołączany do wersji desktopowej (PyInstaller) poprzez `build.ps1` (`--add-data output/Jednostki.csv;output`). Aby zaktualizować jednostki u klienta, zaktualizuj zawartość `output/Jednostki.csv` i przebuduj lub podmień plik obok EXE.

W razie potrzeby dopasujemy format PDF (układ, kolumny) dokładniej do przykładu.

## Instalacja u klienta (Windows) — krok po kroku

Poniższe kroki zakładają czyste środowisko Windows z zainstalowanym Pythonem 3.10+.

1) Przygotowanie katalogu aplikacji
- Skopiuj cały folder projektu (z plikami `src/`, `templates/`, `static/`, `config.json`, `ex_input.csv`, `requirements.txt`) na komputerze klienta, np. do `C:\APApp`.

2) Utworzenie wirtualnego środowiska i instalacja zależności
```powershell
Set-Location C:\APApp
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

3) Pliki wejściowe i konfiguracja
- Upewnij się, że w katalogu głównym jest `ex_input.csv` (plik źródłowy danych).
- W razie potrzeby edytuj `config.json` (nagłówek firmy, tytuł, stopka, marginesy).
- Katalog `output/` zostanie utworzony automatycznie przy generowaniu raportów.

4) Uruchomienie aplikacji webowej (lokalnie na stanowisku)
```powershell
Set-Location C:\APApp
.\.venv\Scripts\Activate.ps1
python src/app.py
# Aplikacja działa pod adresem: http://127.0.0.1:5000
```
- W UI wybierz jeden lub więcej "Nr źródła" i wygeneruj raporty (PDF-y pojawią się w `output/`).

5) Uruchomienie generatora z linii poleceń (CLI)
```powershell
Set-Location C:\APApp
.\.venv\Scripts\Activate.ps1
# Wszystkie dokumenty z danego źródła
python generate_sample.py --source N3222
# Konkretny dokument z danego źródła
python generate_sample.py --source N3222 --doc WD/25/31995
```

6) Użycie w sieci lokalnej (opcjonalnie)
- Domyślnie aplikacja nasłuchuje tylko lokalnie (`127.0.0.1`).
- Aby udostępnić ją w sieci, można zmienić uruchomienie na adres `0.0.0.0` i/lub skorzystać z serwera produkcyjnego (np. `waitress`). Najprościej:
	- Edytuj `src/app.py` i uruchamiaj z `app.run(host='0.0.0.0', port=5000, debug=False)`.
	- Upewnij się, że zapora systemu Windows zezwala na ruch na porcie 5000.

7) Typowe problemy
- Brak polskich znaków w PDF: aplikacja próbuje użyć czcionek Windows (Arial/Segoe UI) lub `static/fonts/DejaVuSans*.ttf`. Jeśli PDF nie renderuje znaków, dołóż te pliki do `static/fonts/`.
- Błędy importu pakietów: aktywuj wirtualne środowisko (`.\.venv\Scripts\Activate.ps1`) i ponownie `pip install -r requirements.txt`.

8) Aktualizacja wersji na stanowisku klienta
- Podmień katalog projektu (poza `ex_input.csv`/danymi klienta), aktywuj `.venv` i uruchom `pip install -r requirements.txt`.

To wszystko — po wykonaniu kroków 1–5 klient może lokalnie generować raporty przez przeglądarkę lub CLI.

## Tryb aplikacji desktopowej (klikana ikona)

Chcesz uruchamiać aplikację jako okno desktopowe, bez przeglądarki? Projekt zawiera wrapper `desktop_app.py` (pywebview + Flask).

Uruchom lokalnie bez pakowania:
```powershell
Set-Location C:\APApp
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
python desktop_app.py
```

Uwagi:
- Okno jest renderowane przez `pywebview` (na Windows korzysta z WebView2; w razie braku system poprosi o instalację WebView2 Runtime).
- Raporty i dane zachowują bez zmian tę samą lokalizację (`ex_input.csv` w katalogu aplikacji, PDF-y w `output/`).

## Budowanie EXE i instalatora (Windows)

Szybki build EXE (PyInstaller) oraz opcjonalnie instalator (Inno Setup):

```powershell
Set-Location C:\APApp
./build.ps1                 # buduje EXE do folderu dist/APApp
./build.ps1 -Installer      # dodatkowo buduje instalator (wymaga Inno Setup 6)
```

Co powstaje:
- `dist\APApp\APApp.exe` – pojedynczy plik wykonywalny (bez konsoli).
- `dist_installer\APApp-Setup.exe` – instalator tworzący skrót na pulpicie (opcjonalnie).

Własna ikona (opcjonalnie):
- Umieść `static\app.ico` i uruchom `build.ps1` – zostanie użyta jako ikona EXE.
