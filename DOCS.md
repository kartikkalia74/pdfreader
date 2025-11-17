# PDF Reader - Complete Documentation

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Installation & Setup](#installation--setup)
4. [Usage Guide](#usage-guide)
5. [API Documentation](#api-documentation)
6. [File Structure](#file-structure)
7. [Methods Comparison](#methods-comparison)
8. [Supported Formats](#supported-formats)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)

---

## Project Overview

PDF Reader is a comprehensive system for extracting transaction data from bank statement PDFs. It supports multiple extraction methods and provides both command-line and web interfaces for processing financial documents.

### Key Features

- **Multiple Extraction Methods**: Choose from OCR, text extraction, or AI-powered parsing
- **Format Detection**: Automatically detects PhonePe, HDFC, and generic bank statement formats
- **Web Interface**: Flask-based web application with filtering, sorting, and grouping capabilities
- **Caching System**: Intelligent caching to speed up repeated processing
- **Duplicate Detection**: Identifies and groups duplicate transactions across files
- **Google Sheets Integration**: Optional upload to Google Sheets (JavaScript version)

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    PDF Reader System                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   JavaScript │  │   Python     │  │   Web App    │  │
│  │   Parser     │  │   Extractors │  │   (Flask)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                  │           │
│         └─────────────────┼──────────────────┘           │
│                           │                              │
│  ┌────────────────────────┴──────────────────────────┐  │
│  │         Extraction Methods                        │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  • Traditional Parsing (index.js)                 │  │
│  │  • OCR (pytesseract)                              │  │
│  │  • Text Extraction (pdfplumber)                   │  │
│  │  • AI NER (BERT/RoBERTa)                          │  │
│  └──────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Output Formats                            │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  • JSON (structured transaction data)             │  │
│  │  • Google Sheets (optional)                       │  │
│  │  • Web Interface (filtered/sorted/grouped)        │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Input**: PDF file(s) placed in `readerfiles/` directory
2. **Processing**: Selected extraction method processes the PDF
3. **Parsing**: Format-specific parsers extract transaction data
4. **Caching**: Results cached in `cache/` directory (JSON format)
5. **Output**: Structured JSON with transaction data
6. **Web Interface**: Optional web UI for filtering, sorting, grouping

---

## Installation & Setup

### Prerequisites

- **Python 3.8+** (for Python scripts)
- **Node.js 14+** (for JavaScript scripts)
- **Virtual Environment** (recommended for Python)

### Step 1: Clone/Setup Project

```bash
cd /path/to/pdfreader
```

### Step 2: Python Environment Setup

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 3: System Dependencies

#### For OCR Method (pytesseract)

**macOS:**
```bash
brew install tesseract poppler
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

**Windows:**
- Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
- Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases

#### For JavaScript Version

```bash
npm install pdf-parse googleapis dotenv
```

### Step 4: Verify Installation

```bash
# Check Python packages
python -c "import pdfplumber, pytesseract, transformers; print('✅ All packages installed')"

# Check Tesseract
tesseract --version

# Check Node.js packages (if using JS version)
node -e "require('pdf-parse'); console.log('✅ Node packages OK')"
```

### Step 5: Optional - Google Sheets Setup

1. Create a Google Cloud project
2. Enable Google Sheets API
3. Create a service account
4. Download JSON key file
5. Set environment variables:
   ```bash
   export GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/path/to/key.json
   export GOOGLE_SHEET_ID=your_sheet_id
   ```

---

## Usage Guide

### Command Line Usage

#### Using Helper Script (Recommended)

The `run.sh` script automatically activates the virtual environment and runs the appropriate extractor:

```bash
# Default: OCR method (pytesseract)
./run.sh readerfiles/statement.pdf

# Use pdfplumber (faster for text-based PDFs)
./run.sh --pdfplumber readerfiles/statement.pdf
# OR
./run.sh -p readerfiles/statement.pdf

# Use AI method (BERT/RoBERTa NER)
./run.sh --ai readerfiles/statement.pdf
# OR
./run.sh -a readerfiles/statement.pdf
```

#### Direct Python Execution

```bash
# Activate virtual environment first
source venv/bin/activate

# OCR method
python bank_reader_pytesseract.py readerfiles/statement.pdf

# Text extraction method
python bank_reader_pdfplumber.py readerfiles/statement.pdf

# AI method
python bank_reader_ai.py readerfiles/statement.pdf

# AI with custom model
python bank_reader_ai.py readerfiles/statement.pdf microsoft/Phi-3-mini-4k-instruct
```

#### JavaScript Version

```bash
# Basic usage
node index.js readerfiles/statement.pdf

# Password-protected PDF
node index.js readerfiles/statement.pdf your-password
```

### Web Interface Usage

#### Starting the Web Server

```bash
# Activate virtual environment
source venv/bin/activate

# Start Flask server
python app.py
```

The server will start on `http://localhost:5001` (default port).

#### Web Interface Features

1. **File Upload**: Upload PDFs via the web interface
2. **Auto-Processing**: Automatically processes all PDFs in `readerfiles/` folder
3. **Filtering**: Filter by date range, amount, type, description, source file
4. **Sorting**: Sort by date, amount, description, or type
5. **Grouping**: Group by date, week, month, type, merchant, or source file
6. **Statistics**: View total transactions, debits, credits, net amount
7. **Duplicate Detection**: Automatically identifies duplicate transactions

---

## API Documentation

### Flask API Endpoints

#### `GET /`
Serves the main HTML page.

**Response**: HTML page

---

#### `GET /api/scan`
Scans the `readerfiles/` folder and returns list of PDF files.

**Response:**
```json
{
  "success": true,
  "files": [
    {
      "filename": "statement.pdf",
      "size": 123456,
      "modified": "2025-01-15T10:30:00",
      "has_cache": true
    }
  ],
  "count": 1
}
```

---

#### `GET /api/process-all`
Processes all PDFs in the `readerfiles/` folder. Uses cache if available.

**Query Parameters:**
- `force` (optional): Set to `true` to force reprocessing

**Response:**
```json
{
  "success": true,
  "data": {
    "transactions": [...],
    "collapsedTransactions": [...],
    "duplicateGroups": [...],
    "summary": {
      "totalTransactions": 100,
      "collapsedTransactionCount": 95,
      "duplicateGroupCount": 5,
      "totalFiles": 3,
      "processedFiles": 3,
      "files": [...]
    }
  }
}
```

---

#### `GET /api/process-file/<filename>`
Processes a single PDF file.

**Query Parameters:**
- `force` (optional): Set to `true` to force reprocessing

**Response:**
```json
{
  "success": true,
  "data": {
    "sourceFile": "statement.pdf",
    "timestamp": "2025-01-15T10:30:00",
    "transactions": [
      {
        "page": 1,
        "transactions": [...],
        "rawText": "..."
      }
    ],
    "metadata": {
      "totalTransactions": 50,
      "extractionMethod": "Mistral 7B AI",
      "format": "hdfc_account_statement"
    }
  }
}
```

---

#### `POST /api/upload`
Uploads and processes a new PDF file.

**Request:**
- `file`: PDF file (multipart/form-data)

**Response:**
```json
{
  "success": true,
  "data": {...},
  "filename": "uploaded_statement.pdf"
}
```

---

#### `GET /api/transactions`
Gets all transactions from all processed files.

**Query Parameters:**
- `force` (optional): Set to `true` to force reprocessing

**Response:**
```json
{
  "success": true,
  "data": {
    "transactions": [...],
    "collapsedTransactions": [...],
    "summary": {...}
  }
}
```

---

#### `GET /api/transactions/<filename>`
Gets transactions for a specific file.

**Query Parameters:**
- `force` (optional): Set to `true` to force reprocessing

**Response:**
```json
{
  "success": true,
  "data": {
    "transactions": [...],
    "metadata": {...},
    "sourceFile": "statement.pdf"
  }
}
```

---

#### `POST /api/refresh`
Forces refresh - reprocesses all PDFs ignoring cache.

**Response:**
```json
{
  "success": true,
  "data": {...},
  "message": "All files reprocessed successfully"
}
```

---

### Python API Functions

#### `api.process_pdf(file_path, use_cache=True)`

Processes a PDF file using the AI extraction method.

**Parameters:**
- `file_path` (str): Path to PDF file
- `use_cache` (bool): Whether to use cached results

**Returns:**
- `dict`: Transaction data dictionary

**Example:**
```python
from api import process_pdf

result = process_pdf('readerfiles/statement.pdf', use_cache=True)
print(result['metadata']['totalTransactions'])
```

---

#### `api.combine_all_transactions(force_refresh=False)`

Combines transactions from all PDFs in the `readerfiles/` folder.

**Parameters:**
- `force_refresh` (bool): If True, reprocess all files even if cache exists

**Returns:**
- `dict`: Combined transaction data with duplicate detection

**Example:**
```python
from api import combine_all_transactions

all_data = combine_all_transactions(force_refresh=False)
print(f"Total transactions: {all_data['summary']['totalTransactions']}")
```

---

#### `api.scan_readerfiles_folder()`

Scans the `readerfiles/` folder and returns list of PDF files.

**Returns:**
- `list`: List of file information dictionaries

**Example:**
```python
from api import scan_readerfiles_folder

files = scan_readerfiles_folder()
for file_info in files:
    print(f"{file_info['filename']} - {file_info['size']} bytes")
```

---

## File Structure

```
pdfreader/
├── README.md                    # Main project README
├── DOCS.md                      # This documentation file
├── requirements.txt             # Python dependencies
├── run.sh                       # Helper script for running extractors
│
├── Python Extractors
│   ├── bank_reader_ai.py        # AI-powered extraction (BERT/RoBERTa)
│   ├── bank_reader_pdfplumber.py # Text-based extraction
│   ├── bank_reader_pytesseract.py # OCR-based extraction
│   ├── api.py                    # API helper functions
│   └── app.py                    # Flask web server
│
├── JavaScript Extractors
│   ├── index.js                 # Main JavaScript parser
│   ├── aireader.js              # AI-powered JavaScript extractor
│   └── example-ai-usage.js      # Example usage
│
├── Web Interface
│   ├── templates/
│   │   └── index.html           # Web UI template
│   └── static/
│       └── style.css            # Stylesheet
│
├── Data Directories
│   ├── readerfiles/             # Input PDF files
│   ├── cache/                   # Cached processing results (JSON)
│   └── temp_images/             # Temporary OCR images (auto-cleaned)
│
└── Configuration
    ├── personal-products-*.json  # Google service account key (if used)
    └── .env                      # Environment variables (if used)
```

---

## Methods Comparison

### Extraction Methods

| Method | Speed | Accuracy | Best For | Setup Complexity |
|--------|-------|----------|----------|------------------|
| **pdfplumber** | ⚡⚡⚡ Very Fast | ⭐⭐⭐⭐ High | Text-based PDFs | 🟢 Low |
| **AI (BERT/RoBERTa)** | ⚡⚡ Fast | ⭐⭐⭐⭐⭐ Very High | Any PDF format | 🟡 Medium |
| **pytesseract (OCR)** | 🐌 Slow | ⭐⭐⭐ Good | Scanned PDFs | 🟡 Medium |
| **JavaScript Parser** | ⚡⚡⚡ Very Fast | ⭐⭐⭐⭐ High | Known formats | 🟢 Low |

### Detailed Comparison

#### pdfplumber
- **Pros:**
  - Fastest method for text-based PDFs
  - High accuracy (no OCR errors)
  - Minimal dependencies
  - Preserves formatting
- **Cons:**
  - Doesn't work with scanned PDFs
  - Requires text-based PDFs
- **Use When:** PDF is digitally created (not scanned)

#### AI (BERT/RoBERTa NER)
- **Pros:**
  - Highest accuracy
  - Handles format variations
  - Context-aware extraction
  - Works with any PDF format
  - GPU acceleration support
- **Cons:**
  - Requires model download (~500MB-1.5GB)
  - Slightly slower than pdfplumber
  - Higher memory usage (~2-4GB)
- **Use When:** Need highest accuracy or unknown formats

#### pytesseract (OCR)
- **Pros:**
  - Works with scanned PDFs
  - Handles image-based documents
  - Good for legacy documents
- **Cons:**
  - Slowest method
  - OCR accuracy depends on image quality
  - Requires Tesseract installation
- **Use When:** PDF is scanned or image-based

#### JavaScript Parser
- **Pros:**
  - Fast execution
  - Google Sheets integration
  - Good for known formats
- **Cons:**
  - Format-specific parsing
  - Limited to supported formats
- **Use When:** Processing PhonePe or HDFC statements with Google Sheets upload

---

## Supported Formats

### PhonePe Statements

**Detection:** Contains "TRANSACTION STATEMENT" and "PHONEPE"

**Fields Extracted:**
- `date`: Transaction date
- `time`: Transaction time
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount (₹)
- `to`: Recipient/sender information
- `paidBy`: Payment method/account
- `transactionId`: Transaction ID
- `utrNo`: UTR number

**Example:**
```json
{
  "date": "Oct 11, 2025",
  "time": "14:30",
  "type": "DEBIT",
  "amount": "₹1,000.00",
  "to": "Merchant Name",
  "paidBy": "UPI",
  "transactionId": "TXN123456",
  "utrNo": "UTR789012"
}
```

---

### HDFC Account Statements

**Detection:** Contains "HDFC BANK" and "STATEMENT OF ACCOUNT"

**Fields Extracted:**
- `date`: Transaction date (DD/MM/YY)
- `narration`: Transaction description
- `description`: Same as narration
- `refNo`: Reference number
- `valueDate`: Value date
- `withdrawal`: Withdrawal amount
- `deposit`: Deposit amount
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount
- `balance`: Closing balance
- `transactionType`: DOMESTIC or INTERNATIONAL

**Example:**
```json
{
  "date": "15/09/2025",
  "narration": "EMI PRINCIPAL SRI GURU GOBI CHANDIGHAR",
  "type": "DEBIT",
  "amount": "₹45,260.00",
  "balance": "₹1,234,567.89",
  "transactionType": "DOMESTIC"
}
```

---

### HDFC Credit Card Statements

**Detection:** Contains "HDFC BANK" and credit card indicators

**Fields Extracted:**
- `date`: Transaction date
- `time`: Transaction time (if available)
- `description`: Transaction description
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount
- `balance`: Outstanding balance
- `transactionType`: DOMESTIC or INTERNATIONAL
- `usdAmount`: USD amount (for international)
- `originalCurrency`: Original currency code
- `convertedAmount`: Converted INR amount

**Example:**
```json
{
  "date": "22/09/2025",
  "description": "AMAZON PAYMENTS",
  "type": "DEBIT",
  "amount": "₹2,500.00",
  "balance": "₹50,000.00",
  "transactionType": "DOMESTIC"
}
```

---

### Generic Bank Statements

**Detection:** Fallback for unrecognized formats

**Fields Extracted:**
- `date`: Transaction date
- `description`: Transaction description
- `type`: DEBIT, CREDIT, or UNKNOWN
- `amount`: Transaction amount
- `balance`: Account balance (if available)
- `transactionType`: DOMESTIC or INTERNATIONAL

---

## Examples

### Example 1: Process Single PDF (Command Line)

```bash
# Using helper script with AI method
./run.sh --ai readerfiles/statement.pdf

# Output will be JSON printed to console
```

### Example 2: Process Multiple PDFs (Web Interface)

1. Place PDFs in `readerfiles/` folder
2. Start web server: `python app.py`
3. Open `http://localhost:5001`
4. Click "Refresh All" to process all PDFs
5. Use filters to find specific transactions

### Example 3: Programmatic Usage (Python)

```python
from api import process_pdf, combine_all_transactions

# Process single file
result = process_pdf('readerfiles/statement.pdf')
print(f"Found {result['metadata']['totalTransactions']} transactions")

# Process all files
all_data = combine_all_transactions()
print(f"Total: {all_data['summary']['totalTransactions']} transactions")
print(f"From {all_data['summary']['totalFiles']} files")
```

### Example 4: Filter Transactions (Web Interface)

1. Open web interface
2. Set date range: `2025-01-01` to `2025-12-31`
3. Set amount range: `1000` to `10000`
4. Select type: `DEBIT`
5. Search description: `AMAZON`
6. Results update automatically

### Example 5: Group Transactions

1. Open web interface
2. Select grouping: `Month`
3. View transactions grouped by month
4. See totals per month

---

## Troubleshooting

### Common Issues

#### 1. Virtual Environment Not Activated

**Error:** `ModuleNotFoundError: No module named 'pdfplumber'`

**Solution:**
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

#### 2. Tesseract Not Found

**Error:** `TesseractNotFoundError`

**Solution:**
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr

# Verify
tesseract --version
```

---

#### 3. PDF to Image Conversion Fails

**Error:** `pdf2image.exceptions.PDFInfoNotInstalledError`

**Solution:**
```bash
# macOS
brew install poppler

# Ubuntu
sudo apt-get install poppler-utils
```

---

#### 4. Model Download Fails (AI Method)

**Error:** `OSError: Unable to load weights`

**Solution:**
- Check internet connection
- Verify Hugging Face access
- Try alternative model:
  ```bash
  python bank_reader_ai.py statement.pdf dslim/bert-base-NER
  ```

---

#### 5. Out of Memory (AI Method)

**Error:** `RuntimeError: CUDA out of memory`

**Solution:**
- Use smaller model: `dslim/bert-base-NER`
- Process fewer files at once
- Use CPU instead of GPU

---

#### 6. Cache Issues

**Problem:** Old cached data showing

**Solution:**
```bash
# Force refresh via API
curl -X POST http://localhost:5001/api/refresh

# Or delete cache manually
rm -rf cache/*.json
```

---

#### 7. Web Server Port Already in Use

**Error:** `OSError: [Errno 48] Address already in use`

**Solution:**
```python
# Edit app.py, change port
app.run(debug=True, host='0.0.0.0', port=5002)  # Use different port
```

---

#### 8. Google Sheets Upload Fails

**Error:** `Requested entity was not found`

**Solution:**
1. Verify `GOOGLE_SHEET_ID` is correct
2. Share sheet with service account email
3. Check service account has "Editor" permission
4. Verify Google Sheets API is enabled

---

### Performance Tips

1. **Use pdfplumber for text-based PDFs** - Fastest method
2. **Use AI method for unknown formats** - Most accurate
3. **Enable caching** - Speeds up repeated processing
4. **Use GPU for AI method** - Significantly faster
5. **Process files in batches** - Avoid memory issues

---

### Getting Help

1. Check existing README files:
   - `README.md` - Main overview
   - `README_AI.md` - AI method details
   - `README_PDFPLUMBER.md` - Text extraction details
   - `README_PYTESSERACT.md` - OCR method details
   - `README_WEB.md` - Web interface details

2. Review error messages - They often contain helpful hints

3. Check cache files in `cache/` directory to see what was extracted

4. Enable debug mode in Flask:
   ```python
   app.run(debug=True)
   ```

---

## License

[Add your license information here]

---

## Contributing

[Add contribution guidelines here]

---

## Changelog

### Version 1.0.0
- Initial release
- Support for PhonePe, HDFC Account, and HDFC Credit Card statements
- Multiple extraction methods (OCR, text extraction, AI)
- Web interface with filtering, sorting, grouping
- Caching system
- Duplicate detection

---

*Last updated: January 2025*

