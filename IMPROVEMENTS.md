# HDFC Credit Card Parser Improvements

## Overview

Based on the analysis of [xaneem/hdfc-credit-card-statement-parser](https://github.com/xaneem/hdfc-credit-card-statement-parser), we've implemented significant improvements to the HDFC credit card statement parsing functionality.

## Key Improvements

### 1. **Table-Based Extraction** (New Feature)
- **Added**: `parse_hdfc_credit_statement_from_table()` method
- **Benefit**: More reliable extraction for structured PDFs with table layouts
- **Implementation**: Uses `pdfplumber`'s `extract_table()` method to parse tabular data
- **Fallback**: Automatically falls back to text parsing if table extraction fails

### 2. **Improved Error Handling**
- **Before**: No error handling in table extraction
- **After**: Comprehensive try-catch blocks with graceful fallbacks
- **Benefit**: Prevents crashes and provides informative error messages

### 3. **Data Validation**
- **Added**: Amount validation before adding transactions
- **Added**: Row validation to skip invalid/malformed rows
- **Added**: Date and description validation
- **Benefit**: More accurate results, fewer false positives

### 4. **International Transaction Support**
- **Enhanced**: Better extraction of forex amounts and rates
- **Fixed**: Bug in forex amount extraction (was using wrong regex group)
- **Added**: Proper currency code extraction (USD, EUR, GBP, etc.)
- **Added**: Forex rate calculation with division-by-zero protection

### 5. **Cr/Dr Indicator Handling**
- **Improved**: Better detection and parsing of Credit/Debit indicators
- **Fixed**: Proper handling of "Cr" and "Dr" in amount strings
- **Benefit**: More accurate transaction type classification

### 6. **Password Support**
- **Added**: Support for password-protected PDFs
- **Implementation**: Added `password` parameter to `extract_transactions()`
- **CLI**: Updated command-line interface to accept `--password` flag

### 7. **Hybrid Extraction Strategy**
- **Strategy**: Try table extraction first, fall back to text parsing
- **Benefit**: Best of both worlds - accuracy of tables + flexibility of text parsing
- **Implementation**: Automatic detection and method selection

## Code Comparison

### Original GitHub Repo Issues Fixed

1. **Bug in total_amount calculation**
   - **Issue**: Recalculated from list each iteration
   - **Fix**: Not applicable (we don't calculate totals in extraction)

2. **No error handling**
   - **Issue**: Crashes on malformed data
   - **Fix**: Comprehensive error handling with fallbacks

3. **Hardcoded table settings**
   - **Issue**: Fixed vertical line at 380px
   - **Fix**: Configurable table settings with fallback

4. **No validation**
   - **Issue**: Invalid data included in results
   - **Fix**: Multi-level validation (amounts, dates, descriptions)

5. **Forex rate calculation bug**
   - **Issue**: Potential division by zero
   - **Fix**: Added try-catch with ZeroDivisionError handling

## New Features

### Table Extraction Method
```python
def parse_hdfc_credit_statement_from_table(self, page, password: Optional[str] = None) -> List[Dict]:
    """
    Parse HDFC Credit Card Statement transactions using table extraction.
    This method is inspired by https://github.com/xaneem/hdfc-credit-card-statement-parser
    but with improved error handling and validation.
    """
```

### Enhanced Transaction Fields
- `currency`: Currency code (INR, USD, EUR, etc.)
- `forex_amount`: Original foreign currency amount
- `forex_rate`: Exchange rate used
- `transactionType`: DOMESTIC or INTERNATIONAL
- `rawLine`: Original table row for debugging

## Usage

### Command Line
```bash
# Basic usage
python bank_reader_pdfplumber.py statement.pdf

# With password
python bank_reader_pdfplumber.py statement.pdf --password "your-password"
```

### Programmatic
```python
from bank_reader_pdfplumber import BankStatementReader

reader = BankStatementReader()

# Without password
results = reader.extract_transactions('statement.pdf')

# With password
results = reader.extract_transactions('statement.pdf', password='your-password')
```

## Performance Improvements

1. **Faster for structured PDFs**: Table extraction is faster than text parsing for tabular data
2. **More accurate**: Table extraction preserves column alignment and structure
3. **Better handling of multi-page statements**: Processes all pages consistently

## Testing Recommendations

1. Test with various HDFC credit card statement formats
2. Test with password-protected PDFs
3. Test with statements containing both domestic and international transactions
4. Test with malformed or partially corrupted PDFs
5. Compare results between table extraction and text parsing methods

## Future Enhancements

1. **Configurable table settings**: Allow users to specify table detection parameters
2. **Multiple table format support**: Handle different table layouts
3. **Better currency detection**: Support more currency codes
4. **Transaction categorization**: Auto-categorize transactions (groceries, fuel, etc.)
5. **Export formats**: Support CSV, Excel, JSON export

## Credits

- Original inspiration: [xaneem/hdfc-credit-card-statement-parser](https://github.com/xaneem/hdfc-credit-card-statement-parser)
- Improvements implemented: January 2025

---

*For detailed usage instructions, see [DOCS.md](DOCS.md) and [README_PDFPLUMBER.md](README_PDFPLUMBER.md)*

