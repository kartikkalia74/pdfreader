#!/usr/bin/env python3
"""
Bank Statement Reader using pytesseract OCR
Reads bank statement PDFs and extracts transaction data using OCR
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nPlease install required packages:")
    print("  pip install pytesseract pdf2image pillow")
    print("\nAlso ensure Tesseract OCR is installed:")
    print("  macOS: brew install tesseract")
    print("  Ubuntu: sudo apt-get install tesseract-ocr")
    print("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
    sys.exit(1)


class BankStatementReader:
    """Read and parse bank statements using OCR"""
    
    def __init__(self, tesseract_cmd: Optional[str] = None, image_dpi: int = 200):
        """
        Initialize the bank statement reader
        
        Args:
            tesseract_cmd: Path to tesseract executable (if not in PATH)
            image_dpi: DPI for PDF to image conversion (default: 200)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
        self.image_dpi = image_dpi
        self.temp_dir = Path(__file__).parent / 'temp_images'
        self.temp_dir.mkdir(exist_ok=True)
    
    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy for rupee symbols and decimal points
        
        Args:
            image: PIL Image object
            
        Returns:
            Preprocessed PIL Image
        """
        # Convert to grayscale if needed
        if image.mode != 'L':
            image = image.convert('L')
        
        # Enhance contrast (important for decimal points)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)  # Increased for better decimal detection
        
        # Enhance sharpness (helps with small characters like decimal points)
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)  # Increased for better decimal detection
        
        # Apply slight denoising (but not too much to preserve decimal points)
        image = image.filter(ImageFilter.MedianFilter(size=3))
        
        return image
    
    def fix_rupee_symbol_ocr_errors(self, text: str) -> str:
        """
        Fix common OCR errors where rupee symbol (₹) is misread as other characters
        
        Args:
            text: OCR extracted text
            
        Returns:
            Text with rupee symbol errors fixed
        """
        # Common patterns where ₹ is misread:
        # - "2" followed by numbers (₹123 -> 2123 or ₹123 -> 2 123)
        # - "R" or "Rs" followed by numbers
        # - Empty space before numbers
        
        # Fix: DEBIT/CREDIT followed by "2" and numbers (₹ misread as 2)
        # This is the most common pattern: "DEBIT 2 1,234.56"
        text = re.sub(r'\b(DEBIT|CREDIT)\s+2\s+([\d,]+\.?\d*)', r'\1 ₹\2', text, flags=re.IGNORECASE)
        
        # Fix: "Paid 2" or "Received 2" followed by numbers
        text = re.sub(r'\b(Paid|Received)\s+2\s+([\d,]+\.?\d*)', r'\1 ₹\2', text, flags=re.IGNORECASE)
        
        # Fix: Amount patterns like "2123.45" where first 2 should be ₹
        # Pattern: DEBIT/CREDIT/Paid/Received followed by 2 then digits with decimal
        text = re.sub(r'\b(DEBIT|CREDIT|Paid|Received|Amount|Amt)\s+2([\d,]+\.\d{2})\b', r'\1 ₹\2', text, flags=re.IGNORECASE)
        
        # Fix: Standalone "2" followed by space and numbers (not part of larger number)
        # Only if it's clearly a currency context (after keywords or at start of amount-like patterns)
        text = re.sub(r'\b2\s+([\d,]+\.[\d]{2})\b', r'₹\1', text)
        
        # Fix: "R" or "Rs" followed by numbers
        text = re.sub(r'\bR[s]?\s+([\d,]+\.?\d*)', r'₹\1', text)
        
        # Fix: "Rs." followed by numbers
        text = re.sub(r'\bRs\.\s*([\d,]+\.?\d*)', r'₹\1', text)
        
        # Fix: "INR" followed by numbers
        text = re.sub(r'\bINR\s+([\d,]+\.?\d*)', r'₹\1', text)
        
        return text
    
    def correct_amount_ocr_errors(self, amount: str) -> str:
        """
        Correct common OCR errors in amounts:
        - Missing decimal points (4526000 -> 45260.00)
        - Leading "2" that should be ₹ symbol (24526000 -> 45260.00)
        - Extra digits at the end
        
        Args:
            amount: Amount string from OCR
            
        Returns:
            Corrected amount string
        """
        if not amount or amount == 'N/A':
            return amount
        
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[₹\$\£\€\s]', '', str(amount))
        cleaned = cleaned.replace(',', '')
        
        # If it's already a valid float with decimal, return as is
        if '.' in cleaned and re.match(r'^\d+\.\d+$', cleaned):
            return cleaned
        
        # If it's a pure number without decimal, check if it needs correction
        if re.match(r'^\d+$', cleaned):
            num_str = cleaned
            
            # Check if it starts with "2" and the resulting number would be suspiciously large
            # Common pattern: "24526000" where "2" is ₹ and should be "45260.00"
            if len(num_str) > 6 and num_str.startswith('2'):
                # Try removing leading "2" and adding decimal
                without_leading_2 = num_str[1:]
                
                # If the number without leading 2 is more reasonable (less than 1 crore)
                if len(without_leading_2) <= 7:  # Less than 10 million
                    # Try adding decimal 2 places from right
                    if len(without_leading_2) >= 2:
                        corrected = without_leading_2[:-2] + '.' + without_leading_2[-2:]
                        try:
                            num_val = float(corrected)
                            # If corrected value is reasonable (< 1 crore), use it
                            if num_val < 10000000:
                                return corrected
                        except ValueError:
                            pass
            
            # If number is suspiciously large (> 1 crore) and has no decimal, try to infer decimal
            try:
                num_val = int(num_str)
                if num_val > 10000000:  # Greater than 1 crore (100 lakhs)
                    # Most bank transactions are under 1 crore
                    # Try inserting decimal 2 places from right
                    if len(num_str) >= 2:
                        corrected = num_str[:-2] + '.' + num_str[-2:]
                        corrected_val = float(corrected)
                        # If corrected value seems more reasonable, use it
                        if corrected_val < 10000000:
                            return corrected
            except ValueError:
                pass
            
            # If number is very long (> 8 digits) without decimal, likely missing decimal
            if len(num_str) > 8:
                # Try adding decimal 2 places from right
                corrected = num_str[:-2] + '.' + num_str[-2:]
                return corrected
        
        return cleaned
    
    def format_amount(self, amount: str) -> str:
        """
        Format amount string with proper commas and decimal places
        
        Args:
            amount: Amount string (may contain ₹ symbol, commas, or be plain number)
            
        Returns:
            Formatted amount string with ₹ symbol and proper formatting
        """
        if not amount or amount == 'N/A':
            return amount
        
        # First correct OCR errors
        corrected = self.correct_amount_ocr_errors(amount)
        
        # Remove any existing currency symbols and whitespace
        cleaned = re.sub(r'[₹\$\£\€\s]', '', str(corrected))
        
        # Remove commas for processing
        cleaned = cleaned.replace(',', '')
        
        try:
            # Try to parse as float
            num_amount = float(cleaned)
            
            # Format with 2 decimal places and add commas
            formatted = f"{num_amount:,.2f}"
            
            # Add rupee symbol at the beginning
            return f'₹{formatted}'
        except (ValueError, AttributeError):
            # If parsing fails, try to preserve original format but add ₹
            # Remove any leading currency symbols first
            cleaned_amount = re.sub(r'^[₹\$\£\€\s]+', '', str(corrected).strip())
            
            # Try to add commas if it's a long number
            if re.match(r'^\d+$', cleaned_amount):
                # Add commas every 3 digits from right
                formatted = f"{int(cleaned_amount):,}"
                return f'₹{formatted}.00'
            elif re.match(r'^\d+\.\d+$', cleaned_amount):
                # Has decimal, add commas
                parts = cleaned_amount.split('.')
                integer_part = f"{int(parts[0]):,}"
                decimal_part = parts[1][:2].ljust(2, '0')  # Ensure 2 decimal places
                return f'₹{integer_part}.{decimal_part}'
            
            # Fallback: just add ₹ if not already present
            if not cleaned_amount.startswith('₹'):
                return f'₹{cleaned_amount}'
            return cleaned_amount
        
    def pdf_to_images(self, pdf_path: str) -> List[str]:
        """
        Convert PDF pages to images
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of image file paths
        """
        print(f"📄 Converting PDF to images: {pdf_path}")
        
        try:
            images = convert_from_path(
                pdf_path,
                dpi=self.image_dpi,
                fmt='png'
            )
            
            image_paths = []
            for i, image in enumerate(images):
                image_path = self.temp_dir / f"page_{i+1}.png"
                image.save(image_path, 'PNG')
                image_paths.append(str(image_path))
                print(f"  ✓ Page {i+1} converted: {image_path}")
            
            print(f"✅ Converted {len(image_paths)} pages to images\n")
            return image_paths
            
        except Exception as e:
            print(f"❌ Error converting PDF: {e}")
            raise
    
    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from image using OCR
        
        Args:
            image_path: Path to image file
            
        Returns:
            Extracted text string with rupee symbol errors fixed
        """
        print(f"🔍 Extracting text from: {Path(image_path).name}")
        
        try:
            # Load and preprocess image
            image = Image.open(image_path)
            processed_image = self.preprocess_image(image)
            
            # Try multiple OCR configurations for better accuracy
            # First try: PSM 6 (single uniform block) - good for structured text
            config1 = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_image, config=config1)
            
            # If we get suspicious amounts (very large numbers without decimals), try PSM 11
            # PSM 11: Sparse text - better for finding decimal points in numbers
            if re.search(r'\b\d{8,}\b', text):  # Very long numbers without decimals
                print(f"  ⚠️  Detected suspicious large numbers, trying alternative OCR config...")
                config2 = r'--oem 3 --psm 11'
                text2 = pytesseract.image_to_string(processed_image, config=config2)
                # Use the version with more decimal points if available
                if text2.count('.') > text.count('.'):
                    text = text2
                    print(f"  ✓ Using alternative OCR config with better decimal detection\n")
            
            # Fix common OCR errors for rupee symbols
            text = self.fix_rupee_symbol_ocr_errors(text)
            
            print(f"  ✓ OCR extraction complete\n")
            return text
            
        except Exception as e:
            print(f"  ❌ Error extracting from image: {e}")
            raise
    
    def detect_format(self, text: str) -> str:
        """
        Detect bank statement format from text
        
        Args:
            text: Extracted text from PDF
            
        Returns:
            Format identifier string
        """
        text_upper = text.upper()
        
        # Check for PhonePe format
        if 'TRANSACTION STATEMENT' in text_upper and 'PHONEPE' in text_upper:
            return 'phonepe'
        
        # Check for HDFC Account Statement format
        if 'HDFC BANK' in text_upper and 'STATEMENT OF ACCOUNT' in text_upper:
            if re.search(r'\d{2}/\d{2}/\d{2}', text):
                return 'hdfc_account_statement'
        
        # Check for HDFC Credit Card statement format
        if 'HDFC' in text_upper and ('CREDIT CARD' in text_upper or 'CREDIT CARD STATEMENT' in text_upper):
            return 'hdfc_credit_statement'
        
        # Check for generic bank statement format
        if 'STATEMENT' in text_upper or 'ACCOUNT STATEMENT' in text_upper or 'TRANSACTION HISTORY' in text_upper:
            return 'bank_statement'
        
        return 'unknown'
    
    def parse_phonepe_transactions(self, text: str) -> List[Dict]:
        """Parse PhonePe transaction statements"""
        transactions = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # PhonePe format: "Oct 11, 2025 Paid to DEEP GARMENTS DEBIT ₹1,400"
            # Date pattern can be at start or after other text
            date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}'
            date_match = re.search(date_pattern, line, re.IGNORECASE)
            
            if date_match:
                date = date_match.group(0)
                date_end = date_match.end()
                
                # Extract the rest of the line after date
                rest_of_line = line[date_end:].strip()
                
                # Get time (next line - format: "05:49 pm" or "05:49 PM")
                time = ''
                if i + 1 < len(lines):
                    time_line = lines[i + 1].strip()
                    time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))', time_line)
                    if time_match:
                        time = time_match.group(1)
                    elif re.match(r'^\d{1,2}:\d{2}', time_line):
                        # Just time without am/pm
                        time = time_line.split()[0]
                
                # Parse transaction details from rest_of_line
                # Format: "Paid to DEEP GARMENTS DEBIT ₹1,400"
                # or: "Received from XXX CREDIT ₹500"
                
                type_str = 'UNKNOWN'
                amount = ''
                description = ''
                to_from = ''
                
                # Extract transaction type (DEBIT or CREDIT)
                if re.search(r'\bDEBIT\b', rest_of_line, re.IGNORECASE):
                    type_str = 'DEBIT'
                elif re.search(r'\bCREDIT\b', rest_of_line, re.IGNORECASE):
                    type_str = 'CREDIT'
                
                # Extract amount (₹ symbol followed by number with optional comma)
                # Make sure we only match amounts that come after DEBIT/CREDIT and before separator or transaction details
                amount_match = None
                
                # First try: Amount immediately after DEBIT/CREDIT
                if type_str != 'UNKNOWN':
                    # Pattern: "DEBIT ₹280" or "CREDIT ₹500"
                    type_amount_pattern = r'\b' + type_str + r'\s+[₹]\s*([\d,]+\.?\d*)'
                    type_amount_match = re.search(type_amount_pattern, rest_of_line, re.IGNORECASE)
                    if type_amount_match:
                        amount_match = type_amount_match
                
                # Second try: Amount with ₹ symbol anywhere in rest_of_line (but before | separator)
                if not amount_match:
                    # Split by | to avoid matching amounts from transaction IDs
                    first_part = rest_of_line.split('|')[0]
                    amount_match = re.search(r'[₹]\s*([\d,]+\.?\d*)', first_part)
                    if not amount_match:
                        # Try with "2" misread as ₹
                        amount_match = re.search(r'[2]\s*([\d,]+\.?\d*)', first_part)
                
                # Third try: Amount without currency symbol
                if not amount_match:
                    # Only match if it looks like a reasonable amount (not part of transaction ID)
                    first_part = rest_of_line.split('|')[0]
                    amount_match = re.search(r'\b([\d,]+\.?\d{2})\b', first_part)
                    # But exclude if it looks like a transaction ID pattern (too many digits)
                    if amount_match and len(amount_match.group(1).replace(',', '').replace('.', '')) > 6:
                        amount_match = None
                
                if amount_match:
                    amount = amount_match.group(1).replace(',', '')
                else:
                    amount = ''
                
                # Extract description (everything before type and amount)
                # Remove type and amount from rest_of_line to get description
                desc_line = rest_of_line
                if type_str != 'UNKNOWN':
                    desc_line = re.sub(r'\b' + type_str + r'\b', '', desc_line, flags=re.IGNORECASE).strip()
                if amount_match:
                    desc_line = re.sub(r'[₹2]\s*[\d,]+\.?\d*', '', desc_line).strip()
                
                description = desc_line.strip()
                
                # Extract "to" or "from" information
                if 'Paid to' in description:
                    to_from = description.replace('Paid to', '').strip()
                elif 'Received from' in description:
                    to_from = description.replace('Received from', '').strip()
                elif 'Payment to' in description:
                    to_from = description.replace('Payment to', '').strip()
                elif 'recharged' in description.lower():
                    to_from = description
                else:
                    to_from = description
                
                # Get Transaction ID (next line after time)
                txn_id = ''
                utr_no = ''
                paid_by = ''
                
                # Time is on line i+1, so Transaction ID should be on line i+2 or later
                line_idx = i + 2 if time else i + 1
                
                # Look for Transaction ID in next few lines
                found_txn_id = False
                for check_idx in range(line_idx, min(line_idx + 3, len(lines))):
                    txn_id_line = lines[check_idx].strip()
                    txn_id_match = re.search(r'Transaction ID\s+(.+)', txn_id_line, re.IGNORECASE)
                    if txn_id_match:
                        txn_id = txn_id_match.group(1)
                        i = check_idx + 1
                        found_txn_id = True
                        break
                
                if not found_txn_id:
                    i = line_idx
                
                # Get UTR No (next line after Transaction ID)
                if i < len(lines):
                    utr_line = lines[i].strip()
                    utr_match = re.search(r'UTR No\.\s+(.+)', utr_line, re.IGNORECASE)
                    if utr_match:
                        utr_no = utr_match.group(1)
                        i += 1
                
                # Get Paid by / Credited to (next line after UTR)
                if i < len(lines):
                    paid_by_line = lines[i].strip()
                    if 'Paid by' in paid_by_line:
                        paid_by = paid_by_line.replace('Paid by', '').strip()
                        i += 1
                    elif 'Credited to' in paid_by_line:
                        paid_by = paid_by_line.replace('Credited to', '').strip()
                        i += 1
                
                # Only add transaction if we have essential data
                if date and (amount or description):
                    transactions.append({
                        'date': date,
                        'time': time,
                        'type': type_str,
                        'amount': self.format_amount(amount) if amount else 'N/A',
                        'description': description,
                        'to': to_from,
                        'paidBy': paid_by,
                        'transactionId': txn_id,
                        'utrNo': utr_no
                    })
            else:
                i += 1
        
        return transactions
    
    def parse_hdfc_account_statement(self, text: str) -> List[Dict]:
        """Parse HDFC Account Statement transactions"""
        transactions = []
        lines = text.split('\n')
        
        for i in range(len(lines)):
            line = lines[i].strip()
            
            # Look for date pattern at start: DD/MM/YY
            date_match = re.match(r'^(\d{2}/\d{2}/\d{2})\s+(.+)', line)
            
            if date_match:
                date = date_match.group(1)
                rest_of_line = date_match.group(2)
                
                # Extract all numbers (amounts) - format: 1,234.56 or 234.56
                number_pattern = r'[\d,]+\.\d{2}'
                numbers = re.findall(number_pattern, rest_of_line)
                
                withdrawal = ''
                deposit = ''
                balance = ''
                ref_no = ''
                value_date = ''
                narration = ''
                
                # Last number is always balance
                if numbers:
                    balance = numbers[-1]
                
                # Remove balance from the line to get remaining info
                line_without_balance = rest_of_line
                if balance:
                    balance_index = rest_of_line.rfind(balance)
                    line_without_balance = rest_of_line[:balance_index].strip()
                
                # Extract reference number - typically 10+ digits starting with 0000
                ref_match = re.search(r'\b(0\d{12,}|\d{12,})\b', line_without_balance)
                if ref_match:
                    ref_no = ref_match.group(1)
                
                # Extract value date (second occurrence of date pattern)
                value_date_matches = re.findall(r'\d{2}/\d{2}/\d{2}', line_without_balance)
                if value_date_matches:
                    value_date = value_date_matches[0]
                
                # Extract amounts
                amounts = re.findall(number_pattern, line_without_balance)
                
                if len(amounts) == 1:
                    tx_amount = amounts[0]
                    lower_narration = line_without_balance.lower()
                    if any(keyword in lower_narration for keyword in ['withdrawal', 'ach d-', 'autopay', 'payment to']):
                        withdrawal = tx_amount
                    elif any(keyword in lower_narration for keyword in ['received', 'deposit', 'credit']):
                        deposit = tx_amount
                    else:
                        withdrawal = tx_amount
                elif len(amounts) >= 2:
                    tx_amount = amounts[-1]
                    lower_narration = line_without_balance.lower()
                    if any(keyword in lower_narration for keyword in ['received', 'deposit', 'credit']):
                        deposit = tx_amount
                    else:
                        withdrawal = tx_amount
                
                # Extract narration
                if ref_no:
                    narration = line_without_balance.split(ref_no)[0].strip()
                else:
                    narration = line_without_balance.strip()
                
                # Check for international transactions
                transaction_type = 'DOMESTIC'
                if any(keyword in narration.upper() for keyword in ['INTERNATIONAL', 'FOREIGN', 'USD', 'EUR', 'GBP', 'FOREX']):
                    transaction_type = 'INTERNATIONAL'
                
                # Determine transaction type based on amounts
                tx_type = 'UNKNOWN'
                amount = ''
                if withdrawal and not deposit:
                    tx_type = 'DEBIT'
                    amount = withdrawal
                elif deposit and not withdrawal:
                    tx_type = 'CREDIT'
                    amount = deposit
                elif withdrawal:
                    tx_type = 'DEBIT'
                    amount = withdrawal
                
                # Check if next line(s) are continuation of narration
                full_narration = narration
                j = i + 1
                while j < len(lines) and lines[j].strip() and not re.match(r'^\d{2}/\d{2}/\d{2}', lines[j].strip()):
                    next_line = lines[j].strip()
                    if not any(keyword in next_line for keyword in ['Page No', '--', 'STATEMENT SUMMARY', 'Generated On', 'Generated By']):
                        if not re.match(r'^\d+ of \d+', next_line):
                            full_narration += ' ' + next_line
                    j += 1
                
                # Skip summary lines
                if any(keyword in full_narration for keyword in ['STATEMENT SUMMARY', 'Opening Balance', 'Generated On']):
                    continue
                
                # Fix transaction type for interest
                if 'interest paid' in full_narration.lower() or 'interest credit' in full_narration.lower():
                    tx_type = 'CREDIT'
                    if withdrawal:
                        deposit = withdrawal
                        withdrawal = ''
                        amount = deposit
                
                if full_narration.strip() and balance:
                    transactions.append({
                        'date': date,
                        'narration': full_narration.strip(),
                        'description': full_narration.strip(),
                        'refNo': ref_no,
                        'valueDate': value_date,
                        'withdrawal': self.format_amount(withdrawal) if withdrawal else '',
                        'deposit': self.format_amount(deposit) if deposit else '',
                        'type': tx_type,
                        'amount': self.format_amount(amount) if amount else 'N/A',
                        'balance': self.format_amount(balance) if balance else '',
                        'transactionType': transaction_type
                    })
        
        return transactions
    
    def parse_hdfc_credit_statement(self, text: str) -> List[Dict]:
        """Parse HDFC Credit Card Statement transactions"""
        transactions = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for date pattern like "22/09/2025]" or "22/09/2025 | 13:52" or "22-09-2025" or "22 Sep 2025"
            # Handle cases where date ends with ] bracket or has | separator
            # Pattern 1: "27/08/2025 | 13:52" format (international transactions)
            date_match = re.match(r'^(\d{2}[\/\-]\d{2}[\/\-]\d{4})\s*\|\s*(\d{2}:\d{2})', line)
            if date_match:
                date = date_match.group(1)
                time = date_match.group(2)
                rest_of_line = line[date_match.end():].strip()
            else:
                # Pattern 2: "22/09/2025]" or "22/09/2025" format (domestic transactions)
                date_match = re.match(r'^(\d{2}[\/\-]\d{2}[\/\-]\d{4})\]?\s*(\d{2}:\d{2})?', line)
                if not date_match:
                    date_match = re.match(r'^(\d{2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})', line)
                
                if date_match:
                    date = date_match.group(1)
                    rest_of_line = line[date_match.end():].strip()
                    
                    # Extract time if present (format: "17:38" or "] 17:38")
                    time_match = re.search(r'\]?\s*(\d{2}:\d{2})', rest_of_line)
                    time = time_match.group(1) if time_match else ''
                    
                    # Remove time from rest_of_line
                    if time_match:
                        rest_of_line = rest_of_line[:time_match.start()] + rest_of_line[time_match.end():].strip()
                else:
                    date = ''
                    time = ''
                    rest_of_line = line
            
            if date:
                
                description = ''
                tx_type = ''
                amount = ''
                balance = ''
                transaction_type = 'DOMESTIC'
                
                # Look ahead for description and amount on next lines
                description_lines = []
                amount_line = ''
                j = i + 1
                
                # Skip empty lines and collect description lines
                while j < len(lines) and j < i + 5:  # Check up to 5 lines ahead
                    next_line = lines[j].strip()
                    
                    # Skip empty lines
                    if not next_line:
                        j += 1
                        continue
                    
                    # Check if next line is a date (start of new transaction)
                    next_date_match = re.match(r'^(\d{2}[\/\-]\d{2}[\/\-]\d{4})', next_line)
                    if next_date_match:
                        break
                    
                    # Check if line contains an amount pattern (USD, INR, or large numbers)
                    amount_pattern = re.search(r'(USD\s*[\d,]+\.?\d*|[₹\$£€2R]?\s?[\d,]+\s*\d{2}|[₹\$£€2R]?\s?[\d,]+\.[\d]{2}|\d{6,})', next_line)
                    if amount_pattern and not description_lines:
                        # This might be the amount line
                        amount_line = next_line
                        j += 1
                        break
                    elif amount_pattern:
                        # Amount found after description
                        amount_line = next_line
                        j += 1
                        break
                    else:
                        # Likely description line
                        if not any(keyword in next_line.upper() for keyword in ['DATE', 'TIME', 'TRANSACTION', 'DESCRIPTION', 'AMOUNT', 'DOMESTIC', 'INTERNATIONAL']):
                            description_lines.append(next_line)
                        j += 1
                
                # First check if amount is in rest_of_line itself (single line format)
                # Pattern: "EMI PRINCIPAL SRI GURU GOBI CHANDIGHAR C 45,260.00 l | KARTIK KALIA"
                single_line_amount_match = re.search(r'([\d,]+\.\d{2})', rest_of_line)
                
                # Extract amounts
                amounts = []
                usd_amount = ''
                inr_amount = ''
                search_text = amount_line if amount_line else rest_of_line
                
                # If amount is found in rest_of_line, extract it first
                if single_line_amount_match and not amount_line:
                    # Extract amount from rest_of_line
                    amount_match = re.search(r'([\d,]+\.\d{2})', rest_of_line)
                    if amount_match:
                        # Remove amount from description
                        amount_pos = amount_match.start()
                        description_part = rest_of_line[:amount_pos].strip()
                        # Clean up description - remove trailing characters like "C", "l", etc.
                        description_part = re.sub(r'\s+[A-Za-z]\s*$', '', description_part).strip()
                        
                        # Extract amount
                        amount_str = amount_match.group(1).replace(',', '')
                        amounts.append(amount_str)
                        
                        # Use description_part as description
                        if description_part:
                            description = description_part
                        else:
                            # Fallback to looking ahead
                            if description_lines:
                                description = ' '.join(description_lines)
                            else:
                                description = rest_of_line
                    else:
                        # No amount in rest_of_line, use normal logic
                        if description_lines:
                            description = ' '.join(description_lines)
                        elif rest_of_line:
                            description = rest_of_line
                else:
                    # Normal multi-line processing
                    if description_lines:
                        description = ' '.join(description_lines)
                    elif rest_of_line:
                        description = rest_of_line
                
                # Clean up description - remove time patterns, pipe separators, and trailing account names
                description = re.sub(r'\]?\s*\d{2}:\d{2}', '', description).strip()
                # Remove trailing parts after pipe if they look like account names
                description = re.sub(r'\s*\|\s*[A-Z\s]+$', '', description).strip()
                
                # Check for international transactions
                full_text = (description + ' ' + search_text).upper()
                if any(keyword in full_text for keyword in ['INTERNATIONAL', 'FOREIGN', 'USD', 'EUR', 'GBP', 'FCY']):
                    transaction_type = 'INTERNATIONAL'
                
                # Also check next line for INR amount if USD was found (sometimes on separate lines)
                if not amount_line and i + 1 < len(lines):
                    next_line_check = lines[i + 1].strip()
                    if re.search(r'USD', search_text, re.IGNORECASE) and not re.search(r'[₹2]\s*[\d,]', search_text):
                        # USD found but no INR on same line, check next line
                        search_text = search_text + ' ' + next_line_check
                
                # First check for international transaction format: "USD 23.60" and "₹ 2,072.32"
                usd_match = re.search(r'USD\s*([\d,]+\.?\d*)', search_text, re.IGNORECASE)
                if usd_match:
                    usd_amount = usd_match.group(1).replace(',', '')
                    transaction_type = 'INTERNATIONAL'
                
                # Extract INR amounts (₹ symbol or misread as "2")
                # Check both on same line and on next line if USD was found
                inr_patterns = [
                    r'[₹2]\s*([\d,]+)\s+(\d{2})\b',        # "2 2,072 32" or "₹ 2,072 32" format
                    r'[₹2]\s*([\d,]+\.\d{2})\b',            # "2 2,072.32" or "₹ 2,072.32" format
                    r'[₹2]\s*([\d,]+)\b',                    # "2 2,072" or "₹ 2,072" format
                ]
                
                for pattern in inr_patterns:
                    inr_match = re.search(pattern, search_text)
                    if inr_match:
                        if len(inr_match.groups()) == 2:
                            # Format: "2 2,072 32" -> "2,072.32"
                            inr_amount = inr_match.group(1).replace(',', '') + '.' + inr_match.group(2)
                        else:
                            inr_amount = inr_match.group(1).replace(',', '')
                        break
                
                # If USD found but INR not found, check if amount_line has multiple lines
                if usd_amount and not inr_amount and amount_line:
                    # Check next line after amount_line
                    if j < len(lines):
                        next_amount_line = lines[j].strip()
                        for pattern in inr_patterns:
                            inr_match = re.search(pattern, next_amount_line)
                            if inr_match:
                                if len(inr_match.groups()) == 2:
                                    inr_amount = inr_match.group(1).replace(',', '') + '.' + inr_match.group(2)
                                else:
                                    inr_amount = inr_match.group(1).replace(',', '')
                                break
                
                # If no USD but INR found, or if INR not found, try general patterns
                if not inr_amount and not amounts:
                    # Pattern for amounts: "2 45,260 00" or "2 45,260.00" or "₹45,260.00"
                    amount_patterns = [
                        r'([\$₹£€2R])\s*([\d,]+)\s+(\d{2})',  # "2 45,260 00" format
                        r'([\$₹£€2R])\s*([\d,]+\.\d{2})',      # "2 45,260.00" format
                        r'([\$₹£€2R])\s*([\d,]+)',              # "2 45,260" format
                        r'([\d,]+\.\d{2})',                     # "45,260.00" format
                        r'(\d{6,})',                            # Long numbers
                    ]
                    
                    for pattern in amount_patterns:
                        matches = re.findall(pattern, search_text)
                        if matches:
                            for match in matches:
                                if isinstance(match, tuple):
                                    # Handle tuple matches like ("2", "45,260", "00")
                                    if len(match) == 3:
                                        # Format: "2 45,260 00" -> "45,260.00"
                                        amount_str = match[1].replace(',', '') + '.' + match[2]
                                        amounts.append(amount_str)
                                    elif len(match) == 2:
                                        # Format: "2 45,260.00" or "₹45,260.00"
                                        if match[0] in ['2', 'R', '₹', '$', '£', '€']:
                                            amounts.append(match[1])
                                        else:
                                            amounts.append(''.join(match))
                                else:
                                    # For string matches like "45,260.00", remove commas
                                    cleaned_match = match.replace(',', '') if isinstance(match, str) else match
                                    amounts.append(cleaned_match)
                            break
                    
                    # If no amounts found, try extracting from parts
                    if not amounts:
                        parts = search_text.split()
                        for part in parts:
                            if re.match(r'^[\$₹£€2R]?[\d,]+\.?\d*$', part):
                                cleaned_part = re.sub(r'^([2R])([\d,]+\.?\d*)$', r'\2', part)
                                amounts.append(cleaned_part)
                    
                    # Assign amounts
                    if len(amounts) >= 2:
                        amount = amounts[-2]
                        balance = amounts[-1]
                    elif len(amounts) == 1:
                        amount = amounts[0]
                elif inr_amount:
                    amount = inr_amount
                elif amounts:
                    # Amounts already extracted from single-line format
                    if len(amounts) >= 1:
                        amount = amounts[0]
                
                # Set USD amount if found
                if usd_amount:
                    # USD amount will be stored separately
                    pass
                
                # Determine transaction type
                if any(keyword in description.upper() for keyword in ['DEBIT', 'WITHDRAWAL', 'PURCHASE', 'PAYMENT', 'AUTOPAY']):
                    tx_type = 'DEBIT'
                elif any(keyword in description.upper() for keyword in ['CREDIT', 'DEPOSIT', 'RECEIVED', 'REFUND']):
                    tx_type = 'CREDIT'
                else:
                    # Default: most credit card transactions are debits
                    tx_type = 'DEBIT'
                
                # Build raw line for debugging
                raw_parts = [line]
                if description_lines:
                    raw_parts.extend(description_lines)
                if amount_line:
                    raw_parts.append(amount_line)
                raw_line = ' | '.join(raw_parts)
                
                if description or amount:
                    transaction_data = {
                        'date': date,
                        'time': time,
                        'description': description or rest_of_line,
                        'type': tx_type or 'UNKNOWN',
                        'amount': self.format_amount(amount) if amount else 'N/A',
                        'balance': self.format_amount(balance) if balance else '',
                        'transactionType': transaction_type,
                        'rawLine': raw_line
                    }
                    
                    # Add USD amount for international transactions
                    if usd_amount:
                        # Format USD amount properly
                        try:
                            usd_num = float(usd_amount)
                            formatted_usd = f"USD {usd_num:.2f}"
                        except ValueError:
                            formatted_usd = f"USD {usd_amount}"
                        transaction_data['usdAmount'] = formatted_usd
                        transaction_data['originalCurrency'] = 'USD'
                        transaction_data['convertedAmount'] = self.format_amount(amount) if amount else 'N/A'
                    
                    transactions.append(transaction_data)
                
                # Skip to the line after amount
                i = j if j > i else i + 1
            else:
                i += 1
        
        return transactions
    
    def parse_transactions(self, text: str, format_type: str) -> List[Dict]:
        """
        Parse transactions based on detected format
        
        Args:
            text: Extracted text from PDF
            format_type: Detected format type
            
        Returns:
            List of transaction dictionaries
        """
        if format_type == 'phonepe':
            return self.parse_phonepe_transactions(text)
        elif format_type == 'hdfc_account_statement':
            return self.parse_hdfc_account_statement(text)
        elif format_type == 'hdfc_credit_statement':
            return self.parse_hdfc_credit_statement(text)
        elif format_type == 'bank_statement':
            return self.parse_hdfc_credit_statement(text)
        else:
            print(f"⚠️  Unknown format: {format_type}. Attempting generic parsing...")
            return self.parse_hdfc_account_statement(text)
    
    def extract_transactions(self, file_path: str) -> Dict:
        """
        Main function to extract transactions from PDF
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dictionary containing extracted transactions and metadata
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        results = {
            'sourceFile': file_path,
            'timestamp': datetime.now().isoformat(),
            'transactions': [],
            'metadata': {
                'totalTransactions': 0,
                'extractionMethod': 'pytesseract OCR',
                'format': 'unknown'
            }
        }
        
        # Convert PDF to images
        image_paths = self.pdf_to_images(file_path)
        
        if not image_paths:
            raise ValueError('No pages found in PDF or conversion failed')
        
        # Extract text from all pages
        all_text = []
        for i, image_path in enumerate(image_paths):
            print(f"\n📄 Processing page {i + 1} of {len(image_paths)}")
            text = self.extract_text_from_image(image_path)
            all_text.append({
                'page': i + 1,
                'text': text
            })
        
        # Combine all text
        combined_text = '\n'.join([page['text'] for page in all_text])
        
        # Detect format
        format_type = self.detect_format(combined_text)
        print(f"\n📄 Detected format: {format_type.upper()}\n")
        results['metadata']['format'] = format_type
        
        # Parse transactions from each page
        for page_data in all_text:
            transactions = self.parse_transactions(page_data['text'], format_type)
            results['transactions'].append({
                'page': page_data['page'],
                'transactions': transactions,
                'rawText': page_data['text']
            })
        
        # Cleanup temporary images
        print('\n🗑️  Cleaning up temporary images...')
        for img_path in image_paths:
            try:
                os.remove(img_path)
            except Exception as e:
                print(f"  ⚠️  Could not remove {img_path}: {e}")
        print('✅ Cleanup complete\n')
        
        # Count total transactions
        results['metadata']['totalTransactions'] = sum(
            len(page['transactions']) for page in results['transactions']
        )
        
        return results


def main():
    """Command line interface"""
    if len(sys.argv) < 2:
        print('Usage: python bank_reader_pytesseract.py <pdf-file-path> [tesseract-cmd-path]')
        print('\nExamples:')
        print('  python bank_reader_pytesseract.py statement.pdf')
        print('  python bank_reader_pytesseract.py bank_statement.pdf')
        print('  python bank_reader_pytesseract.py statement.pdf /usr/local/bin/tesseract')
        print('\nNote: Make sure Tesseract OCR is installed on your system')
        sys.exit(1)
    
    file_path = sys.argv[1]
    tesseract_cmd = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        reader = BankStatementReader(tesseract_cmd=tesseract_cmd)
        results = reader.extract_transactions(file_path)
        
        print('\n' + '=' * 80)
        print('📊 EXTRACTION RESULTS')
        print('=' * 80 + '\n')
        
        print(json.dumps(results, indent=2))
        
        # Summary
        print('\n' + '=' * 80)
        print('📈 SUMMARY')
        print('=' * 80)
        print(f"Total transactions found: {results['metadata']['totalTransactions']}")
        print(f"Source file: {results['sourceFile']}")
        print(f"Detected format: {results['metadata']['format']}")
        print(f"Extraction method: {results['metadata']['extractionMethod']}")
        print('=' * 80 + '\n')
        
    except Exception as e:
        print(f'\n❌ Extraction failed: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()

