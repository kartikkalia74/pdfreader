# Bank Statement Reader using pytesseract

Python script to extract transaction data from bank statement PDFs using OCR (pytesseract).

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

**Note:** On macOS, you may also need to install poppler for PDF to image conversion:
```bash
brew install poppler
```

### 3. Verify Installation

```bash
tesseract --version
```

## Usage

### Option 1: Using the helper script (Recommended)

```bash
# Make sure you're in the pdfreader directory
cd pdfreader

# Run the script (it will activate venv automatically)
./run.sh readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf
```

### Option 2: Manual activation

```bash
# Activate virtual environment
source venv/bin/activate

# Run the script
python bank_reader_pytesseract.py <pdf-file-path>
```

### Examples

```bash
# Process a bank statement PDF
./run.sh readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf

# Process HDFC account statement
./run.sh readerfiles/Acct\ Statement_XX4230_13102025.pdf

# Specify custom tesseract path (if not in PATH)
python bank_reader_pytesseract.py statement.pdf /usr/local/bin/tesseract
```

## Supported Formats

The script automatically detects and supports:

1. **PhonePe Statements** - Transaction statements from PhonePe
2. **HDFC Account Statements** - Savings/Current account statements
3. **HDFC Credit Card Statements** - Credit card transaction statements
4. **Generic Bank Statements** - Attempts to parse other bank formats

## Output Format

The script outputs JSON with:
- `sourceFile`: Path to the PDF file
- `timestamp`: Extraction timestamp
- `transactions`: Array of pages, each containing:
  - `page`: Page number
  - `transactions`: Array of parsed transactions
  - `rawText`: Raw OCR text
- `metadata`: 
  - `totalTransactions`: Total number of transactions found
  - `extractionMethod`: "pytesseract OCR"
  - `format`: Detected statement format

## Transaction Fields

### PhonePe Format
- `date`: Transaction date
- `time`: Transaction time
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount (₹)
- `to`: Recipient/sender information
- `paidBy`: Payment method
- `transactionId`: Transaction ID
- `utrNo`: UTR number

### HDFC Account Statement Format
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

### HDFC Credit Card Format
- `date`: Transaction date
- `description`: Transaction description
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount
- `balance`: Outstanding balance
- `transactionType`: DOMESTIC or INTERNATIONAL

## Troubleshooting

### Tesseract not found
If you get an error about Tesseract not being found:
1. Verify Tesseract is installed: `tesseract --version`
2. If installed but not in PATH, provide the path as second argument:
   ```bash
   python bank_reader_pytesseract.py statement.pdf /path/to/tesseract
   ```

### PDF conversion errors
If PDF to image conversion fails:
- On macOS: Install poppler: `brew install poppler`
- On Linux: Install poppler-utils: `sudo apt-get install poppler-utils`
- On Windows: Download poppler from: https://github.com/oschwartz10612/poppler-windows/releases

### Poor OCR accuracy
- Ensure PDF is high quality (not scanned at low resolution)
- Try increasing DPI in the script (default: 200)
- Pre-process PDFs to improve image quality before OCR

## Comparison with JavaScript Version

This Python version offers:
- ✅ More accurate OCR with pytesseract
- ✅ Better handling of complex bank statement layouts
- ✅ More robust parsing logic
- ✅ Better error handling

## Notes

- Temporary images are saved in `temp_images/` directory and cleaned up automatically
- The script processes all pages in the PDF
- OCR accuracy depends on PDF quality and layout complexity

