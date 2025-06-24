import pytest
import sys

if __name__ == "__main__":
    result_code = pytest.main(["-q", "tests/"])
    if result_code == 0:
        print("Todas las pruebas pasaron exitosamente.")
    else:
        print("Algunas pruebas fallaron. Código de salida:", result_code)
    sys.exit(result_code)
