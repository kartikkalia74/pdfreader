# Bank Statement Reader using pdfplumber

Python script to extract transaction data from bank statement PDFs using pdfplumber (text-based extraction). This is faster and more accurate than OCR for text-based PDFs.

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

This will install `pdfplumber` along with other dependencies.

### 2. Verify Installation

```bash
python -c "import pdfplumber; print('pdfplumber installed successfully')"
```

## Usage

### Option 1: Using the helper script (Recommended)

```bash
# Make sure you're in the pdfreader directory
cd pdfreader

# Run with pdfplumber method
./run.sh --pdfplumber readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf

# Or use short flag
./run.sh -p readerfiles/Acct\ Statement_XX4230_13102025.pdf
```

### Option 2: Manual activation

```bash
# Activate virtual environment
source venv/bin/activate

# Run the script
python bank_reader_pdfplumber.py <pdf-file-path>
```

### Examples

```bash
# Process a bank statement PDF (text-based)
./run.sh -p readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf

# Process HDFC account statement
./run.sh --pdfplumber readerfiles/Acct\ Statement_XX4230_13102025.pdf

# Direct Python execution
python bank_reader_pdfplumber.py readerfiles/4341XXXXXXXXXX70_22-09-2025_836.pdf
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
  - `rawText`: Raw extracted text
- `metadata`: 
  - `totalTransactions`: Total number of transactions found
  - `extractionMethod`: "pdfplumber"
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
- `time`: Transaction time (if available)
- `description`: Transaction description
- `type`: DEBIT or CREDIT
- `amount`: Transaction amount
- `balance`: Outstanding balance (if available)
- `transactionType`: DOMESTIC or INTERNATIONAL
- `usdAmount`: USD amount (for international transactions)
- `originalCurrency`: Original currency code
- `convertedAmount`: Converted INR amount

## Advantages of pdfplumber

✅ **Faster**: Direct text extraction is much faster than OCR  
✅ **More Accurate**: No OCR errors with text-based PDFs  
✅ **Better Formatting**: Preserves original text formatting  
✅ **No Dependencies**: No need for Tesseract OCR or image processing libraries  

## When to Use pdfplumber vs pytesseract

### Use pdfplumber when:
- PDF is text-based (not scanned)
- You need faster processing
- You want more accurate text extraction
- PDFs are digitally created (not scanned images)

### Use pytesseract when:
- PDF contains scanned images
- PDF is image-based
- Text cannot be extracted directly
- You need OCR capabilities

## Troubleshooting

### No text extracted
If pdfplumber cannot extract text:
- The PDF might be image-based (scanned)
- Try using the pytesseract method instead: `./run.sh readerfiles/statement.pdf`

### Poor parsing results
- Check the raw text output to see what was extracted
- Verify the PDF format matches supported formats
- Consider using pytesseract for scanned PDFs

## Comparison with pytesseract Version

| Feature | pdfplumber | pytesseract |
|---------|-----------|-------------|
| Speed | ⚡ Very Fast | 🐌 Slower (OCR processing) |
| Accuracy | ✅ High (for text PDFs) | ⚠️ Good (OCR dependent) |
| Scanned PDFs | ❌ No | ✅ Yes |
| Text PDFs | ✅ Excellent | ✅ Good |
| Dependencies | Minimal | Requires Tesseract + poppler |

## Notes

- pdfplumber works best with text-based PDFs
- For scanned PDFs, use the pytesseract version
- Both scripts use the same parsing logic for consistency
- Results format is identical between both methods

