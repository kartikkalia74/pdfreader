#!/bin/bash
# Helper script to activate virtual environment and run the bank statement reader

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Creating it now..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "✅ Virtual environment created and dependencies installed"
fi

# Determine which script to use
SCRIPT="bank_reader_pytesseract.py"
METHOD="OCR"

# Check if user wants pdfplumber
if [ "$1" == "--pdfplumber" ] || [ "$1" == "-p" ]; then
    SCRIPT="bank_reader_pdfplumber.py"
    METHOD="pdfplumber"
    shift
elif [ "$1" == "--ai" ] || [ "$1" == "-a" ]; then
    SCRIPT="bank_reader_ai.py"
    METHOD="AI (BERT/RoBERTa)"
    shift
fi

# Run the script if arguments provided
if [ $# -gt 0 ]; then
    echo "🔧 Using ${METHOD} method..."
    if [ "$SCRIPT" == "bank_reader_ai.py" ]; then
        python ${SCRIPT} "$@"
    else
        python ${SCRIPT} "$@"
    fi
else
    echo "Usage: ./run.sh [--pdfplumber|-p|--ai|-a] <pdf-file-path> [options]"
    echo ""
    echo "Examples:"
    echo "  ./run.sh readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf"
    echo "  ./run.sh --pdfplumber readerfiles/Acct\ Statement_XX4230_13102025.pdf"
    echo "  ./run.sh --ai readerfiles/4341XXXXXXXXXX70_22-09-2025_836.pdf"
    echo ""
    echo "Methods:"
    echo "  Default: pytesseract (OCR) - Works with scanned PDFs"
    echo "  --pdfplumber/-p: pdfplumber - Works with text-based PDFs (faster)"
    echo "  --ai/-a: BERT/RoBERTa NER - Intelligent parsing with Named Entity Recognition (fast & efficient)"
fi