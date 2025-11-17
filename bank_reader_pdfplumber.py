#!/usr/bin/env python3
"""
Bank Statement Reader using pdfplumber
Reads bank statement PDFs and extracts transaction data using pdfplumber (text-based extraction)
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    import pdfplumber
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nPlease install required packages:")
    print("  pip install pdfplumber")
    sys.exit(1)


class BankStatementReader:
    """Read and parse bank statements using pdfplumber"""
    
    def __init__(self):
        """Initialize the bank statement reader"""
        pass
    
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
        
        # Remove any existing currency symbols and whitespace
        cleaned = re.sub(r'[₹\$\£\€\s]', '', str(amount))
        
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
            cleaned_amount = re.sub(r'^[₹\$\£\€\s]+', '', str(amount).strip())
            
            # Try to add commas if it's a long number
            if re.match(r'^\d+$', cleaned_amount):
                formatted = f"{int(cleaned_amount):,}"
                return f'₹{formatted}.00'
            elif re.match(r'^\d+\.\d+$', cleaned_amount):
                parts = cleaned_amount.split('.')
                integer_part = f"{int(parts[0]):,}"
                decimal_part = parts[1][:2].ljust(2, '0')
                return f'₹{integer_part}.{decimal_part}'
            
            # Fallback: just add ₹ if not already present
            if not cleaned_amount.startswith('₹'):
                return f'₹{cleaned_amount}'
            return cleaned_amount
    
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
                date_start = date_match.start()
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
                    desc_line = re.sub(r'[₹]\s*[\d,]+\.?\d*', '', desc_line).strip()
                
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
                
                # Extract reference number
                ref_match = re.search(r'\b(0\d{12,}|\d{12,})\b', line_without_balance)
                if ref_match:
                    ref_no = ref_match.group(1)
                
                # Extract value date
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
    
    def parse_hdfc_credit_statement_from_table(self, page, password: Optional[str] = None) -> List[Dict]:
        """
        Parse HDFC Credit Card Statement transactions using table extraction.
        This method is inspired by https://github.com/xaneem/hdfc-credit-card-statement-parser
        but with improved error handling and validation.
        
        Args:
            page: pdfplumber page object
            password: Optional PDF password
            
        Returns:
            List of transaction dictionaries
        """
        transactions = []
        page_text = page.extract_text() or ""
        
        # Check if page contains transaction tables
        has_domestic = "Domestic Transactions" in page_text
        has_international = "International Transactions" in page_text
        
        if not (has_domestic or has_international):
            return []  # No transactions on this page
        
        try:
            # Process Domestic Transactions
            if has_domestic:
                try:
                    table = page.extract_table()
                    if table and len(table) > 1:  # Has header + data rows
                        for index, row in enumerate(table):
                            if index == 0:  # Skip header
                                continue
                            
                            # Validate row has required fields
                            if not row or len(row) < 2:
                                continue
                            
                            date = (row[0] or "").replace("null", "").strip()
                            description = (row[1] or "").strip()
                            
                            # Skip empty rows
                            if not date or not description:
                                continue
                            
                            # Get amount from second-to-last column (usually)
                            amount_index = len(row) - 2
                            if amount_index < 0:
                                amount_index = len(row) - 1
                            
                            amount_str = (row[amount_index] or "").strip()
                            
                            # Extract Cr/Dr indicator
                            tx_type = "Dr"
                            if "Cr" in amount_str:
                                tx_type = "Cr"
                                amount_str = amount_str.replace("Cr", "").strip()
                            elif "Dr" in amount_str:
                                amount_str = amount_str.replace("Dr", "").strip()
                            
                            # Clean amount
                            amount_str = amount_str.replace(",", "").strip()
                            
                            # Validate amount
                            try:
                                float(amount_str)
                            except (ValueError, TypeError):
                                continue  # Skip invalid amounts
                            
                            transactions.append({
                                "date": date,
                                "description": description,
                                "currency": "INR",
                                "forex_amount": "",
                                "forex_rate": "",
                                "amount": self.format_amount(amount_str),
                                "type": "CREDIT" if tx_type == "Cr" else "DEBIT",
                                "transactionType": "DOMESTIC",
                                "rawLine": " | ".join([str(cell or "") for cell in row])
                            })
                except Exception as e:
                    print(f"  ⚠️  Error parsing domestic transactions table: {e}")
            
            # Process International Transactions
            if has_international:
                try:
                    # Use table settings to split currency column
                    table_settings = {
                        "explicit_vertical_lines": [380]  # Split the currency column
                    }
                    table = page.extract_table(table_settings=table_settings)
                    
                    if table and len(table) > 1:
                        for index, row in enumerate(table):
                            if index == 0:  # Skip header
                                continue
                            
                            if not row or len(row) < 3:
                                continue
                            
                            date = (row[0] or "").replace("null", "").strip()
                            description = (row[1] or "").strip()
                            currency_info = (row[2] or "").strip() if len(row) > 2 else ""
                            
                            if not date or not description:
                                continue
                            
                            # Extract currency and forex amount
                            currency = "USD"
                            forex_amount = ""
                            
                            if currency_info:
                                # Format: "USD 123.45" or "USD123.45"
                                currency_match = re.match(r'([A-Z]{3})\s*([\d,]+\.?\d*)', currency_info)
                                if currency_match:
                                    currency = currency_match.group(1)
                                    forex_amount = currency_match.group(2).replace(",", "")
                            
                            # Get amount from second-to-last column
                            amount_index = len(row) - 2
                            if amount_index < 0:
                                amount_index = len(row) - 1
                            
                            amount_str = (row[amount_index] or "").strip()
                            
                            # Extract Cr/Dr
                            tx_type = "Dr"
                            if "Cr" in amount_str:
                                tx_type = "Cr"
                                amount_str = amount_str.replace("Cr", "").strip()
                            elif "Dr" in amount_str:
                                amount_str = amount_str.replace("Dr", "").strip()
                            
                            # Clean amount
                            amount_str = amount_str.replace(",", "").replace(" ", "").strip()
                            
                            # Calculate forex rate
                            forex_rate = ""
                            try:
                                inr_amount = float(amount_str)
                                if forex_amount:
                                    forex_amt = float(forex_amount)
                                    if forex_amt > 0:
                                        forex_rate = f"{inr_amount / forex_amt:.2f}"
                            except (ValueError, ZeroDivisionError):
                                pass
                            
                            # Validate amount
                            try:
                                float(amount_str)
                            except (ValueError, TypeError):
                                continue
                            
                            transactions.append({
                                "date": date,
                                "description": description,
                                "currency": currency,
                                "forex_amount": self.format_amount(forex_amount) if forex_amount else "",
                                "forex_rate": forex_rate,
                                "amount": self.format_amount(amount_str),
                                "type": "CREDIT" if tx_type == "Cr" else "DEBIT",
                                "transactionType": "INTERNATIONAL",
                                "rawLine": " | ".join([str(cell or "") for cell in row])
                            })
                except Exception as e:
                    print(f"  ⚠️  Error parsing international transactions table: {e}")
        
        except Exception as e:
            print(f"  ⚠️  Error in table extraction: {e}")
        
        return transactions
    
    def parse_hdfc_credit_statement(self, text: str) -> List[Dict]:
        """Parse HDFC Credit Card Statement transactions using text parsing"""
        transactions = []
        lines = text.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for date pattern like "22/09/2025]" or "22/09/2025 | 13:52" or "22-09-2025"
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
                    
                    # Extract time if present
                    time_match = re.search(r'\]?\s*(\d{2}:\d{2})', rest_of_line)
                    time = time_match.group(1) if time_match else ''
                    
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
                while j < len(lines) and j < i + 5:
                    next_line = lines[j].strip()
                    
                    if not next_line:
                        j += 1
                        continue
                    
                    # Check if next line is a date
                    next_date_match = re.match(r'^(\d{2}[\/\-]\d{2}[\/\-]\d{4})', next_line)
                    if next_date_match:
                        break
                    
                    # Check if line contains an amount pattern
                    amount_pattern = re.search(r'(USD\s*[\d,]+\.?\d*|[₹\$£€2R]?\s?[\d,]+\s*\d{2}|[₹\$£€2R]?\s?[\d,]+\.[\d]{2}|\d{6,})', next_line)
                    if amount_pattern and not description_lines:
                        amount_line = next_line
                        j += 1
                        break
                    elif amount_pattern:
                        amount_line = next_line
                        j += 1
                        break
                    else:
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
                
                # Check for USD amount
                usd_match = re.search(r'USD\s*([\d,]+\.?\d*)', search_text, re.IGNORECASE)
                if usd_match:
                    usd_amount = usd_match.group(1).replace(',', '')
                    transaction_type = 'INTERNATIONAL'
                
                # Extract INR amounts
                inr_patterns = [
                    r'[₹2]\s*([\d,]+)\s+(\d{2})\b',
                    r'[₹2]\s*([\d,]+\.\d{2})\b',
                    r'[₹2]\s*([\d,]+)\b',
                ]
                
                for pattern in inr_patterns:
                    inr_match = re.search(pattern, search_text)
                    if inr_match:
                        if len(inr_match.groups()) == 2:
                            inr_amount = inr_match.group(1).replace(',', '') + '.' + inr_match.group(2)
                        else:
                            inr_amount = inr_match.group(1).replace(',', '')
                        break
                
                # If no INR found and amounts not already extracted, try general patterns
                if not inr_amount and not amounts:
                    amount_patterns = [
                        r'([\$₹£€2R])\s*([\d,]+)\s+(\d{2})',
                        r'([\$₹£€2R])\s*([\d,]+\.\d{2})',
                        r'([\$₹£€2R])\s*([\d,]+)',
                        r'([\d,]+\.\d{2})',  # Match amounts like "45,260.00"
                        r'(\d{6,})',
                    ]
                    
                    for pattern in amount_patterns:
                        matches = re.findall(pattern, search_text)
                        if matches:
                            for match in matches:
                                if isinstance(match, tuple):
                                    if len(match) == 3:
                                        amount_str = match[1].replace(',', '') + '.' + match[2]
                                        amounts.append(amount_str)
                                    elif len(match) == 2:
                                        if match[0] in ['2', 'R', '₹', '$', '£', '€']:
                                            amounts.append(match[1])
                                        else:
                                            amounts.append(''.join(match))
                                else:
                                    # For string matches like "45,260.00", remove commas
                                    cleaned_match = match.replace(',', '') if isinstance(match, str) else match
                                    amounts.append(cleaned_match)
                            break
                    
                    if len(amounts) >= 2:
                        amount = amounts[-2]
                        balance = amounts[-1]
                    elif len(amounts) == 1:
                        amount = amounts[0]
                elif inr_amount:
                    amount = inr_amount
                
                # Determine transaction type
                if any(keyword in description.upper() for keyword in ['DEBIT', 'WITHDRAWAL', 'PURCHASE', 'PAYMENT', 'AUTOPAY']):
                    tx_type = 'DEBIT'
                elif any(keyword in description.upper() for keyword in ['CREDIT', 'DEPOSIT', 'RECEIVED', 'REFUND']):
                    tx_type = 'CREDIT'
                else:
                    tx_type = 'DEBIT'
                
                # Build raw line
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
    
    def extract_transactions(self, file_path: str, password: Optional[str] = None) -> Dict:
        """
        Main function to extract transactions from PDF
        
        Args:
            file_path: Path to PDF file
            password: Optional password for password-protected PDFs
            
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
                'extractionMethod': 'pdfplumber',
                'format': 'unknown'
            }
        }
        
        print(f"📄 Reading PDF: {file_path}")
        
        all_pages = []
        all_text = []
        try:
            with pdfplumber.open(file_path, password=password) as pdf:
                print(f"  ✓ PDF opened successfully ({len(pdf.pages)} pages)\n")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"📄 Processing page {page_num} of {len(pdf.pages)}")
                    
                    # Extract text from page
                    text = page.extract_text()
                    
                    if text:
                        all_pages.append({
                            'page': page_num,
                            'page_obj': page,
                            'text': text
                        })
                        all_text.append({
                            'page': page_num,
                            'text': text
                        })
                        print(f"  ✓ Extracted {len(text)} characters from page {page_num}\n")
                    else:
                        print(f"  ⚠️  No text found on page {page_num}\n")
        
        except Exception as e:
            print(f"❌ Error reading PDF: {e}")
            raise
        
        # Combine all text
        combined_text = '\n'.join([page['text'] for page in all_text])
        
        # Detect format
        format_type = self.detect_format(combined_text)
        print(f"\n📄 Detected format: {format_type.upper()}\n")
        results['metadata']['format'] = format_type
        
        # Parse transactions from each page
        for page_data in all_pages:
            transactions = []
            
            # For HDFC credit card statements, try table extraction first
            if format_type == 'hdfc_credit_statement':
                try:
                    table_transactions = self.parse_hdfc_credit_statement_from_table(page_data['page_obj'])
                    if table_transactions:
                        print(f"  ✓ Extracted {len(table_transactions)} transactions using table extraction")
                        transactions = table_transactions
                    else:
                        # Fall back to text parsing
                        print(f"  ⚠️  Table extraction returned no results, falling back to text parsing")
                        transactions = self.parse_transactions(page_data['text'], format_type)
                except Exception as e:
                    print(f"  ⚠️  Table extraction failed: {e}, falling back to text parsing")
                    transactions = self.parse_transactions(page_data['text'], format_type)
            else:
                # Use text parsing for other formats
                transactions = self.parse_transactions(page_data['text'], format_type)
            
            results['transactions'].append({
                'page': page_data['page'],
                'transactions': transactions,
                'rawText': page_data['text']
            })
        
        # Count total transactions
        results['metadata']['totalTransactions'] = sum(
            len(page['transactions']) for page in results['transactions']
        )
        
        return results


def main():
    """Command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract transactions from bank statement PDFs')
    parser.add_argument('file_path', help='Path to PDF file')
    parser.add_argument('--password', type=str, default=None, help='Password for password-protected PDFs')
    args = parser.parse_args()
    
    file_path = args.file_path
    password = args.password
    
    try:
        reader = BankStatementReader()
        results = reader.extract_transactions(file_path, password=password)
        
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
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

