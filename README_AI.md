# Bank Statement Reader using Fine-tuned BERT/RoBERTa

Python script to extract transaction data from bank statement PDFs using Fine-tuned BERT/RoBERTa models for Named Entity Recognition (NER).

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

This will install `transformers`, `torch`, `accelerate`, and `pdfplumber`.

### 2. GPU Setup (Optional but Recommended)

For better performance, install CUDA-enabled PyTorch:

```bash
# For CUDA 11.8
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### 3. Verify Installation

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

## Usage

### Option 1: Using the helper script

```bash
cd pdfreader
./run.sh --ai readerfiles/statement.pdf
```

### Option 2: Direct Python execution

```bash
python bank_reader_ai.py readerfiles/statement.pdf
```

### Option 3: With custom model

```bash
python bank_reader_ai.py readerfiles/statement.pdf microsoft/Phi-3-mini-4k-instruct
```

## How It Works

1. **Text Extraction**: Uses `pdfplumber` to extract text from PDF
2. **Line Detection**: Identifies transaction lines using date patterns
3. **NER Extraction**: Uses BERT/RoBERTa to extract named entities (organizations, locations, dates, money)
4. **Smart Parsing**: Combines NER results with regex patterns for date/time/amount extraction
5. **Structured Output**: Returns consistent JSON format

## Supported Models

- **dslim/bert-base-NER** (default) - Fast, general purpose, ~500MB
- **Jean-Baptiste/roberta-large-ner-english** - Larger model, more accurate, ~1.5GB
- **dbmdz/bert-large-cased-finetuned-conll03-english** - Very accurate, ~1.2GB

## Features

✅ **Intelligent Parsing**: AI understands context and extracts relevant fields  
✅ **Handles Variations**: Works with different date formats, currencies, and layouts  
✅ **Error Recovery**: Falls back to alternative models if primary fails  
✅ **Structured Output**: Returns consistent JSON format  
✅ **GPU Support**: Automatically uses GPU if available  

## Output Format

The script outputs JSON with:
- `sourceFile`: Path to the PDF file
- `timestamp`: Extraction timestamp
- `transactions`: Array with parsed transactions
- `metadata`: 
  - `totalTransactions`: Total number of transactions found
  - `extractionMethod`: "Mistral 7B AI"
  - `format`: Detected statement format
  - `model`: Model name used

## Transaction Fields

Each transaction includes:
- `date`: Transaction date
- `time`: Transaction time (if available)
- `description`: Transaction description/merchant
- `type`: DEBIT or CREDIT
- `amount`: Formatted amount with currency symbol
- `currency`: Currency code (INR, USD, etc.)
- `rawLine`: Original raw text line

## Performance

- **CPU**: ~0.1-0.5 seconds per transaction (much faster than LLMs!)
- **GPU**: ~0.05-0.1 seconds per transaction
- **First Run**: Downloads model (~500MB-1.5GB depending on model)
- **Memory**: ~2-4GB RAM (much more efficient than LLMs)

## Memory Requirements

- **BERT-base**: ~2GB RAM
- **RoBERTa-large**: ~4GB RAM
- **BERT-large**: ~3GB RAM

## Troubleshooting

### Out of Memory Error
- Use smaller model: `dslim/bert-base-NER`
- Process fewer transactions at once
- BERT models are much more memory efficient than LLMs

### Slow Processing
- Enable GPU: Install CUDA-enabled PyTorch
- Use smaller model: bert-base-NER is faster
- BERT models are already optimized for speed

### Model Download Issues
- Ensure you have Hugging Face account and token
- Check internet connection (models are large)
- Try alternative model if one fails

## Example

```bash
python bank_reader_ai.py readerfiles/4341XXXXXXXXXX70_22-09-2025_836.pdf
```

Output:
```json
{
  "date": "15/09/2025",
  "time": "17:38",
  "description": "EMI PRINCIPAL SRI GURU GOBI CHANDIGHAR",
  "type": "DEBIT",
  "amount": "₹45,260.00",
  "currency": "INR",
  "rawLine": "15/09/2025| 17:38 EMI PRINCIPAL SRI GURU GOBI CHANDIGHAR C 45,260.00 l | KARTIK KALIA"
}
```

## Comparison with Other Methods

| Feature | AI (BERT/RoBERTa) | pdfplumber | pytesseract |
|---------|------------------|------------|-------------|
| Accuracy | ⭐⭐⭐⭐⭐ Very High | ⭐⭐⭐⭐ High | ⭐⭐⭐ Good |
| Speed | ⚡ Very Fast | ⚡ Very Fast | 🐌 Slow |
| Handles Variations | ✅ Excellent | ⚠️ Limited | ⚠️ Limited |
| Memory | 🟢 Low (~2-4GB) | 🟢 Low | 🟢 Low |
| Setup Complexity | 🟡 Medium | 🟢 Low | 🟡 Medium |

## Notes

- First run downloads the model (~500MB-1.5GB)
- GPU significantly improves processing speed
- Model stays loaded in memory for batch processing
- Works best with text-based PDFs (not scanned images)
- Much more efficient than LLMs like Mistral 7B

