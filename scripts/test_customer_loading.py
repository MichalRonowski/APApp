import unittest
import os
import sys
from unittest.mock import patch

# Add project root to the path to allow importing from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import _load_customer_names

class TestAppFunctions(unittest.TestCase):

    def setUp(self):
        """Set up a dummy CSV file for testing."""
        self.test_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self.output_dir = os.path.join(self.test_project_root, 'output')
        self.csv_path = os.path.join(self.output_dir, 'NazwyKlienci.csv')
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Use the actual column names from the real CSV file: 'Nr' and 'Nazwa szukana'
        with open(self.csv_path, 'w', encoding='utf-8-sig') as f:
            f.write('Nr,Nazwa szukana\n')
            f.write('N0293,Stacja Paliw ABC\n')
            f.write('N0355,Sklep XYZ\n')

    def tearDown(self):
        """Remove the dummy CSV file after tests."""
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)

    def test_load_customer_names_dev_mode(self):
        """Test loading customer names in development mode."""
        # Simply call the function - it should find the file in output/
        customer_names = _load_customer_names()
        self.assertIsNotNone(customer_names)
        self.assertIsInstance(customer_names, dict)
        self.assertEqual(len(customer_names), 2)
        self.assertEqual(customer_names.get('N0293'), 'Stacja Paliw ABC')
        self.assertEqual(customer_names.get('N0355'), 'Sklep XYZ')

    @patch('sys.frozen', True, create=True)
    def test_load_customer_names_frozen_mode(self):
        """Test loading customer names in frozen (bundled) mode."""
        # The build script places NazwyKlienci.csv in the root of the bundle.
        # The _app_data_root() function should return this path.
        with patch('src.app._app_data_root') as mock_app_data_root:
            mock_app_data_root.return_value = self.test_project_root

            # In frozen mode, the CSV is expected at the root of _MEIPASS
            frozen_csv_path = os.path.join(self.test_project_root, 'NazwyKlienci.csv')
            
            # We need to move our test file to where the frozen app expects it
            os.rename(self.csv_path, frozen_csv_path)

            try:
                customer_names = _load_customer_names()
                self.assertIsNotNone(customer_names)
                self.assertEqual(len(customer_names), 2)
                self.assertEqual(customer_names.get('N0293'), 'Stacja Paliw ABC')
            finally:
                # Move the file back
                os.rename(frozen_csv_path, self.csv_path)


if __name__ == '__main__':
    unittest.main()
