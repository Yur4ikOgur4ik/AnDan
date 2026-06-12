$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m ipykernel install --user --name moneto4ka-cbr --display-name "Python (Moneto4ka CBR)"
.\.venv\Scripts\python.exe -m notebook notebooks\analysis_cbr_currency_rates.ipynb

