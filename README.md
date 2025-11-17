# PDF to Google Sheets Uploader

Extracts transaction data from PhonePe PDF statements and uploads to Google Sheets.

## 📚 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get started in 5 minutes
- **[Complete Documentation](DOCS.md)** - Comprehensive guide covering all features
- **[AI Method](README_AI.md)** - AI-powered extraction using BERT/RoBERTa
- **[PDFPlumber Method](README_PDFPLUMBER.md)** - Fast text-based extraction
- **[OCR Method](README_PYTESSERACT.md)** - OCR-based extraction for scanned PDFs
- **[Web Interface](README_WEB.md)** - Flask web application guide

## Setup

### 1. Create Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. **Enable Google Sheets API:**
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Click "Enable"
4. **Create a Service Account:**
   - Go to "IAM & Admin" → "Service Accounts"
   - Click "Create Service Account"
   - Give it a name (e.g., "pdf-uploader") and click "Create"
   - Skip the optional role selection (click "Continue")
   - Click "Done"
5. **Create and Download Key:**
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" → "Create new key"
   - Choose "JSON" format
   - Click "Create" - the key file will download
6. **Save the key file** to your project directory (e.g., `pdfreader/service-account-key.json`)
7. **Copy the service account email** (looks like: `pdf-uploader@project-name.iam.gserviceaccount.com`)

### 2. Create Google Sheet

1. Go to [Google Sheets](https://sheets.google.com) and create a new sheet
2. **Copy the Sheet ID** from the URL:
   - URL format: `https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit`
   - Example: If URL is `https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit`
   - Sheet ID is: `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms`
3. **Share the sheet** with the service account:
   - Click "Share" button (top right)
   - Paste the service account email you copied earlier
   - Give it "Editor" permission
   - Click "Send"

### 3. Configure Environment Variables

Add to your `.env` file:

```env
GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/path/to/your/service-account-key.json
GOOGLE_SHEET_ID=your_google_sheet_id_here
```

## Usage

### Basic Usage

```bash
node pdfreader/index.js pdfreader/your-statement.pdf
```

### Password-Protected PDFs

If your PDF is password-protected:

```bash
node pdfreader/index.js pdfreader/your-statement.pdf your-password
```

The script will:
1. Automatically detect the PDF format (PhonePe or Bank Statement)
2. Extract all transactions from the PDF
3. Separate domestic and international transactions (for bank statements)
4. Display JSON output in console
5. Upload data to Google Sheets (if configured)

## Output Format

### PhonePe Format

Each transaction includes:
- Date
- Time
- Type (DEBIT/CREDIT)
- Amount
- To/From
- Paid By (account number)
- Transaction ID
- UTR Number

### HDFC Account Statement Format

Each transaction includes:
- Date (DD/MM/YY)
- Narration (full transaction description)
- Reference Number
- Value Date
- Withdrawal Amount (for debits)
- Deposit Amount (for credits)
- Type (DEBIT/CREDIT)
- Closing Balance
- Transaction Type (DOMESTIC/INTERNATIONAL)

### HDFC Credit Card Statement Format

Each transaction includes:
- Date
- Description
- Type (DEBIT/CREDIT/UNKNOWN)
- Amount
- Balance
- Transaction Type (DOMESTIC/INTERNATIONAL)

### Generic Bank Statement Format

Each transaction includes:
- Date
- Description
- Type (DEBIT/CREDIT/UNKNOWN)
- Amount
- Balance
- Transaction Type (DOMESTIC/INTERNATIONAL)

The output will also include a summary with:
- Total transactions count
- Domestic transactions count
- International transactions count
- Detected format type

## Troubleshooting

### Error: "Requested entity was not found"

This error means the script cannot access the Google Sheet. Follow these steps:

1. **Verify Sheet ID is correct:**
   - Open your Google Sheet
   - Copy the ID from URL: `https://docs.google.com/spreadsheets/d/{THIS_IS_THE_SHEET_ID}/edit`
   - Update `GOOGLE_SHEET_ID` in `.env`

2. **Check service account has access:**
   - Run the script once to see the service account email in the output
   - Open your Google Sheet
   - Click "Share" button
   - Make sure the service account email is in the list with "Editor" access
   - If not, add it with "Editor" permission

3. **Verify key file path:**
   - Check that `GOOGLE_SERVICE_ACCOUNT_KEY_FILE` points to the correct JSON file
   - Use absolute path or relative path from project root
   - Example: `/Users/username/project/pdfreader/service-account-key.json`

4. **Enable Google Sheets API:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project
   - Go to "APIs & Services" → "Library"
   - Search for "Google Sheets API"
   - Make sure it's enabled

### Deprecation Warnings

If you see deprecation warnings, they can be ignored - the script uses the latest recommended approach.

---

## AI-Powered Transaction Extraction

The `aireader.js` script uses OCR (Optical Character Recognition) to extract transactions from PDF files and images. This approach converts documents to images and extracts text for flexible transaction parsing.

### Prerequisites

Install required dependencies:

```bash
npm install tesseract.js pdf2pic
```

**System Requirements:**
- ImageMagick and Ghostscript (for PDF to image conversion)
- Install with: `brew install imagemagick ghostscript` (macOS)

### Usage

#### Basic Usage (Default Question)

```bash
node pdfreader/aireader.js path/to/statement.pdf
```

#### Custom Question

You can ask specific questions about the document:

```bash
node pdfreader/aireader.js statement.pdf "List all debit transactions with dates and amounts"
```

#### Image Files

The script also works with image files:

```bash
node pdfreader/aireader.js bank_statement.png
```

### How It Works

1. **PDF Conversion**: If you provide a PDF, it converts each page to an image using `pdf2pic`
2. **AI Analysis**: The AI model uses OCR (Optical Character Recognition) to extract text from document images
3. **Transaction Parsing**: Extracted text is parsed to identify and structure transaction data
4. **Output**: Returns JSON with extracted transactions and metadata

### Output Format

```json
{
  "sourceFile": "path/to/statement.pdf",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "transactions": [
    {
      "page": 1,
      "transactions": [
        {
          "date": "15/01/2025",
          "amount": "1000.00",
          "description": "Payment to merchant",
          "type": "DEBIT"
        }
      ],
      "rawResponse": {...}
    }
  ],
  "metadata": {
    "totalTransactions": 5,
    "extractionMethod": "AI",
    "question": "List all transactions with date, amount, description, and type"
  }
}
```

### Integration as a Module

You can also use it programmatically:

```javascript
const { extractTransactions } = require('./pdfreader/aireader');

async function main() {
    const results = await extractTransactions('statement.pdf', 'List all transactions');
    console.log(results);
}

main();
```

### Supported File Formats

- **PDF**: `.pdf` files (converted to images automatically)
- **Images**: `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`

### Performance Notes

- The first run will download the AI model (~300-500MB) and may take several minutes
- Subsequent runs will be faster as the model is cached locally
- Processing speed depends on document complexity and number of pages
- The model uses OCR to extract text, so accuracy depends on image quality
- Temporary images are automatically cleaned up after processing

### Troubleshooting

If you encounter model download errors:
- Check your internet connection
- Try again later if HuggingFace is experiencing issues
- As an alternative, use the traditional parser (`index.js`) for supported formats

### Comparison: Traditional vs AI Extraction

| Feature | Traditional (`index.js`) | AI-Powered (`aireader.js`) |
|---------|-------------------------|---------------------------|
| Accuracy | High for supported formats | Good for any format |
| Speed | Fast | Slower (initial setup) |
| Setup | Simple | Requires model download |
| Flexibility | Format-specific | Universal |
| Best For | Known formats (PhonePe, HDFC) | 👍 Unknown or custom formats |
