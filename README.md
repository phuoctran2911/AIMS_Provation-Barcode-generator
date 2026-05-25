# Provation Barcode Label Generator v2

A4 web app with 8 labels per page, AI extraction, `.env` key support, and improved spacing so the barcode text does not touch the barcode.

## Run

```bash
cd ~/Downloads/provation_barcode_app_A4_8_AI_v2_spacing
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
touch .env
open -a TextEdit .env
# add: OPENAI_API_KEY=sk-...
./run.sh
```

Open: http://localhost:8000
