import pandas as pd
import os

def convert_customer_names():
    """
    Reads an Excel file masquerading as a CSV from the 'data' directory
    and saves it as a proper CSV file in the 'output' directory.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    source_path = os.path.join(project_root, 'data', 'NazwyKlienci.csv')
    destination_path = os.path.join(project_root, 'output', 'NazwyKlienci.csv')

    if not os.path.exists(source_path):
        print(f"BŁĄD: Plik źródłowy nie został znaleziony w {source_path}")
        print("Upewnij się, że plik 'NazwyKlienci.csv' (który jest plikiem Excela) znajduje się w folderze 'data'.")
        return

    try:
        # Odczytaj plik jako Excel, ponieważ jest to plik .xlsx z błędnym rozszerzeniem
        df = pd.read_excel(source_path)
        
        # Zapisz go jako poprawny plik CSV z kodowaniem UTF-8
        df.to_csv(destination_path, index=False, encoding='utf-8-sig')
        
        print(f"Pomyślnie przekonwertowano {source_path} na {destination_path}")

    except Exception as e:
        print(f"Wystąpił błąd podczas konwersji: {e}")

if __name__ == "__main__":
    # Upewnij się, że katalog 'output' istnieje
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))
    os.makedirs(output_dir, exist_ok=True)
    
    convert_customer_names()
