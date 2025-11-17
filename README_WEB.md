# Bank Statement Web Interface

A Flask-based web application for processing, filtering, sorting, and grouping bank statement PDFs using AI-powered transaction extraction.

## Features

- **PDF Processing**: Automatically processes all PDFs in the `readerfiles/` folder
- **Caching**: Stores processed results in JSON files for fast subsequent loads
- **Filtering**: Filter by date range, amount range, transaction type, description, and source file
- **Sorting**: Sort by date, amount, description, or transaction type
- **Grouping**: Group transactions by date, week, month, type, merchant, or source file
- **File Upload**: Upload new PDFs via the web interface
- **Statistics Dashboard**: View total transactions, debits, credits, and net amount

## Setup

1. **Install Dependencies**:
   ```bash
   cd pdfreader
   pip install -r requirements.txt
   ```

2. **Start the Flask Server**:
   ```bash
   python app.py
   ```

3. **Access the Web Interface**:
   Open your browser and navigate to: `http://localhost:5000`

## Usage

### Processing PDFs

- The application automatically scans the `readerfiles/` folder for PDF files
- Click "Refresh All" to process all PDFs (or it will load from cache if available)
- Processed results are cached in the `cache/` directory

### Filtering Transactions

- **Date Range**: Select start and end dates to filter transactions
- **Amount Range**: Enter minimum and maximum amounts
- **Transaction Type**: Select DEBIT, CREDIT, or All
- **Description**: Search for keywords in transaction descriptions
- **Source File**: Filter by specific PDF files (multi-select)

### Sorting

- Choose sort field: Date, Amount, Description, or Type
- Choose sort order: Ascending or Descending

### Grouping

- Group transactions by:
  - Date (individual dates)
  - Week (weekly groups)
  - Month (monthly groups)
  - Type (DEBIT/CREDIT)
  - Merchant (description)
  - Source File

### Uploading Files

1. Click "Choose File" and select a PDF
2. Click "Upload & Process"
3. The file will be saved to `readerfiles/` and processed automatically
4. Transactions will refresh automatically

## API Endpoints

- `GET /api/scan` - List all PDFs in readerfiles folder
- `GET /api/process-all` - Process all PDFs (use cache if available)
- `GET /api/process-file/<filename>` - Process single PDF
- `POST /api/upload` - Upload and process new PDF
- `GET /api/transactions` - Get all transactions
- `GET /api/transactions/<filename>` - Get transactions for specific file
- `POST /api/refresh` - Force refresh (reprocess all, ignore cache)

## Cache Management

- Cache files are stored in `cache/` directory
- Cache is automatically invalidated if PDF file is newer than cache
- Use "Refresh All" button to force reprocessing

## File Structure

```
pdfreader/
├── app.py                    # Flask backend server
├── api.py                    # API helper functions
├── bank_reader_ai.py         # PDF processing engine
├── cache/                    # JSON cache files (auto-created)
├── readerfiles/              # PDF files to process
├── templates/
│   └── index.html           # Web interface
└── static/
    └── style.css            # Stylesheet
```

## Notes

- First run will download AI models (~500MB-1.5GB)
- Processing can take time depending on PDF size and number of transactions
- Cache improves performance on subsequent loads
- All processing happens server-side

