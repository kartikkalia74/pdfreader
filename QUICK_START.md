# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### 1. Setup (One-time)

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install system dependencies (for OCR)
brew install tesseract poppler  # macOS
# OR
sudo apt-get install tesseract-ocr poppler-utils  # Linux
```

### 2. Process Your First PDF

```bash
# Place PDF in readerfiles/ folder
cp your-statement.pdf readerfiles/

# Process using helper script (recommended)
./run.sh readerfiles/your-statement.pdf

# Or use specific method:
./run.sh --pdfplumber readerfiles/your-statement.pdf  # Fast for text PDFs
./run.sh --ai readerfiles/your-statement.pdf           # Best accuracy
```

### 3. Use Web Interface

```bash
# Start web server
python app.py

# Open browser
open http://localhost:5001
```

---

## 📋 Common Commands

### Command Line

```bash
# Process single PDF (OCR - default)
./run.sh readerfiles/statement.pdf

# Process with text extraction (faster)
./run.sh -p readerfiles/statement.pdf

# Process with AI (most accurate)
./run.sh -a readerfiles/statement.pdf

# Direct Python execution
source venv/bin/activate
python bank_reader_ai.py readerfiles/statement.pdf
```

### Web Interface

1. **Start server**: `python app.py`
2. **Upload PDF**: Click "Choose File" → Select PDF → "Upload & Process"
3. **Filter**: Use filters panel to narrow down transactions
4. **Group**: Select grouping option (Date, Week, Month, etc.)
5. **Export**: Copy JSON from browser console or use API

---

## 🎯 Which Method to Use?

| Your PDF Type | Recommended Method | Command |
|---------------|-------------------|---------|
| Text-based PDF | pdfplumber | `./run.sh -p file.pdf` |
| Scanned PDF | pytesseract (OCR) | `./run.sh file.pdf` |
| Unknown format | AI (BERT/RoBERTa) | `./run.sh -a file.pdf` |
| PhonePe/HDFC | Any method | All work well |

---

## 📁 File Organization

```
readerfiles/     → Put your PDFs here
cache/          → Auto-generated cache (don't edit)
temp_images/    → Temporary OCR images (auto-cleaned)
```

---

## 🔧 Troubleshooting

**Problem**: Module not found
```bash
source venv/bin/activate
pip install -r requirements.txt
```

**Problem**: Tesseract not found
```bash
brew install tesseract  # macOS
```

**Problem**: Slow processing
- Use `--pdfplumber` for text PDFs
- Use `--ai` for better accuracy
- Enable GPU for AI method

**Problem**: Web server won't start
- Check if port 5001 is available
- Change port in `app.py` if needed

---

## 📊 Output Format

All methods output JSON with this structure:

```json
{
  "sourceFile": "statement.pdf",
  "timestamp": "2025-01-15T10:30:00",
  "transactions": [
    {
      "page": 1,
      "transactions": [
        {
          "date": "15/01/2025",
          "type": "DEBIT",
          "amount": "₹1,000.00",
          "description": "Transaction description"
        }
      ]
    }
  ],
  "metadata": {
    "totalTransactions": 50,
    "extractionMethod": "Mistral 7B AI",
    "format": "hdfc_account_statement"
  }
}
```

---

## 🆘 Need More Help?

- **Full Documentation**: See `DOCS.md`
- **Method-specific**: See `README_AI.md`, `README_PDFPLUMBER.md`, `README_PYTESSERACT.md`
- **Web Interface**: See `README_WEB.md`

---

## 💡 Pro Tips

1. **Use caching**: Process once, view many times (automatic)
2. **Batch processing**: Put all PDFs in `readerfiles/` and use web interface
3. **Duplicate detection**: Web interface automatically groups duplicates
4. **Filter before grouping**: Faster performance
5. **Use AI method**: Best for unknown formats or highest accuracy needs

---

*For detailed information, see `DOCS.md`*

