#!/bin/bash
# Mac'te çalıştırmak için
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
  echo "Sanal ortam oluşturuluyor..."
  python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt -q

echo ""
echo "Google Trends Pro başlatılıyor..."
echo "Tarayıcıda açılacak: http://localhost:8501"
echo ""

streamlit run app.py
