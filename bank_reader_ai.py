#!/usr/bin/env python3
"""
Bank Statement Reader using Fine-tuned BERT/RoBERTa
Reads bank statement PDFs and uses AI to parse transactions from raw text
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import pdfplumber
    from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
    import torch
except ImportError as e:
    print(f"❌ Missing required package: {e}")
    print("\nPlease install required packages:")
    print("  pip install pdfplumber transformers torch")
    sys.exit(1)


class BankStatementReaderAI:
    """Read and parse bank statements using Fine-tuned BERT/RoBERTa"""
    
    def __init__(self, model_name: str = "dslim/bert-base-NER"):
        """
        Initialize the bank statement reader with BERT/RoBERTa model
        
        Args:
            model_name: Hugging Face model name
            Options:
            - "dslim/bert-base-NER" - BERT for Named Entity Recognition
            - "Jean-Baptiste/roberta-large-ner-english" - RoBERTa for NER
            - "dbmdz/bert-large-cased-finetuned-conll03-english" - BERT large for NER
        """
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.ner_pipeline = None
        self.device = 0 if torch.cuda.is_available() else -1
        print(f"🖥️  Using device: {'GPU' if self.device == 0 else 'CPU'}")
        
    @staticmethod
    def normalize_date_string(date_str: str) -> Optional[str]:
        """Normalize a date string to ISO format (YYYY-MM-DD)."""
        if not date_str:
            return None

        cleaned = date_str.strip()
        if not cleaned:
            return None

        # Remove ordinal suffixes like 1st, 2nd, 3rd
        cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.replace('Sept', 'Sep')

        date_formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%d/%m/%y",
            "%d-%m-%y",
            "%d.%m.%y",
            "%b %d, %Y",
            "%b %d,%Y",
            "%B %d, %Y",
            "%B %d,%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%d-%b-%Y",
            "%d-%b-%y",
            "%d/%b/%Y",
            "%d/%b/%y",
        ]

        for fmt in date_formats:
            try:
                parsed = datetime.strptime(cleaned, fmt)

                # Handle two-digit years assuming 2000s for values < 1950
                if "%y" in fmt and parsed.year < 1950:
                    parsed = parsed.replace(year=parsed.year + 2000)

                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        return None

    @staticmethod
    def normalize_amount_value(amount_str: Optional[str]) -> Optional[float]:
        """Normalize an amount string to a float with two decimal places."""
        if amount_str in (None, '', 'N/A'):
            return None

        cleaned = re.sub(r'[^\d\.\-]', '', str(amount_str))

        if cleaned in {'', '-', '.', '-.'}:
            return None

        try:
            return round(float(cleaned), 2)
        except ValueError:
            return None

    def load_model(self):
        """Load the BERT/RoBERTa model and tokenizer"""
        if self.ner_pipeline is None:
            print(f"🤖 Loading BERT/RoBERTa model: {self.model_name}")
            try:
                self.ner_pipeline = pipeline(
                    "ner",
                    model=self.model_name,
                    tokenizer=self.model_name,
                    device=self.device,
                    aggregation_strategy="simple"
                )
                print("✅ Model loaded successfully\n")
            except Exception as e:
                print(f"❌ Error loading model: {e}")
                print("\nTrying alternative model: dbmdz/bert-large-cased-finetuned-conll03-english")
                try:
                    self.model_name = "dbmdz/bert-large-cased-finetuned-conll03-english"
                    self.ner_pipeline = pipeline(
                        "ner",
                        model=self.model_name,
                        tokenizer=self.model_name,
                        device=self.device,
                        aggregation_strategy="simple"
                    )
                    print("✅ Alternative model loaded successfully\n")
                except Exception as e2:
                    print(f"❌ Error loading alternative model: {e2}")
                    raise
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text using NER model
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with entity types as keys and values as lists
        """
        if self.ner_pipeline is None:
            self.load_model()
        
        try:
            # Run NER on the text
            entities = self.ner_pipeline(text)
            
            # Organize entities by type
            result = {
                'ORG': [],      # Organizations/merchants
                'PER': [],      # Person names
                'LOC': [],      # Locations
                'MISC': [],     # Miscellaneous
                'DATE': [],     # Dates
                'MONEY': []     # Money amounts
            }
            
            for entity in entities:
                entity_type = entity.get('entity_group', '')
                entity_text = entity.get('word', '').strip()
                
                if entity_type in result:
                    result[entity_type].append(entity_text)
                elif entity_type.startswith('B-') or entity_type.startswith('I-'):
                    # Handle BIO tagging format
                    clean_type = entity_type[2:]  # Remove B- or I- prefix
                    if clean_type in result:
                        result[clean_type].append(entity_text)
            
            return result
        except Exception as e:
            print(f"⚠️  Error extracting entities: {e}")
            return {}
    
    def parse_with_ai(self, raw_line: str, previous_balance: Optional[float] = None) -> Optional[Dict]:
        """
        Parse a transaction line using BERT/RoBERTa NER
        
        Args:
            raw_line: Raw transaction line from PDF
            
        Returns:
            Parsed transaction dictionary or None
        """
        if not raw_line or len(raw_line.strip()) < 10:
            return None
        
        # Skip statement summary lines
        # Check for summary keywords that indicate this is a summary line, not a transaction
        raw_line_upper = raw_line.upper()
        summary_keywords = [
            'STATEMENTSUMMARY',
            'STATEMENT SUMMARY',
            'OPENINGBALANCE',
            'OPENING BALANCE',
            'CLOSINGBALANCE',
            'CLOSING BALANCE',
        ]
        # If line contains summary keywords, skip it
        if any(keyword in raw_line_upper for keyword in summary_keywords):
            return None
        
        # Also check for summary patterns: multiple amounts with summary keywords
        # Pattern: Has "DRCOUNT", "CRCOUNT", "DEBITS", "CREDITS" together
        if ('DRCOUNT' in raw_line_upper or 'CRCOUNT' in raw_line_upper) and \
           ('DEBITS' in raw_line_upper or 'CREDITS' in raw_line_upper):
            return None
        
        try:
            # Extract entities
            entities = self.extract_entities(raw_line)
            
            # Extract date using regex (more reliable than NER for dates)
            date_patterns = [
                r'(\d{2}[\/\-]\d{2}[\/\-]\d{4})',  # DD/MM/YYYY or DD-MM-YYYY
                r'(\d{2}\/\d{2}\/\d{2})',           # DD/MM/YY
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}',  # PhonePe format: Oct 11, 2025
            ]
            date = None
            for pattern in date_patterns:
                match = re.search(pattern, raw_line, re.IGNORECASE)
                if match:
                    date = match.group(0)
                    break
            
            # Extract time (format: "05:49 pm" or "17:38")
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))', raw_line)
            if not time_match:
                time_match = re.search(r'(\d{2}:\d{2})', raw_line)
            time = time_match.group(1) if time_match else ''
            
            # Extract amount (look for currency symbols and numbers)
            # Prioritize amounts that come after DEBIT/CREDIT
            amount = None
            
            # First, check if this is PhonePe format
            # Split by | to only look at the first part (before transaction details)
            first_part = raw_line.split('|')[0] if '|' in raw_line else raw_line
            
            if 'DEBIT' in first_part.upper() or 'CREDIT' in first_part.upper():
                # PhonePe format: Extract amount after DEBIT/CREDIT
                # Pattern: "DEBIT ₹470" or "CREDIT ₹500"
                type_amount_pattern = r'\b(DEBIT|CREDIT)\s+[₹]\s*([\d,]+\.?\d*)'
                type_amount_match = re.search(type_amount_pattern, first_part, re.IGNORECASE)
                if type_amount_match:
                    amount_str = type_amount_match.group(2).replace(',', '')
                    # Validate it's a reasonable amount (not part of date/time)
                    try:
                        amount_val = float(amount_str)
                        # Exclude if it's suspiciously small (might be from date like "18")
                        if amount_val >= 1.0:
                            amount = amount_str
                    except ValueError:
                        pass
            
            # If not found, check for HDFC account statement format (no currency symbols)
            # Format: "DD/MM/YY Description RefNo DD/MM/YY WithdrawalAmt DepositAmt Balance"
            # Structure: All transactions have withdrawal and deposit columns, but one is empty
            # Withdrawal has value → DEBIT, Deposit has value → CREDIT
            if not amount:
                hdfc_date_pattern = r'\b\d{2}/\d{2}/\d{2}\b'
                if re.search(hdfc_date_pattern, raw_line):
                    # Find value date (second date) to locate withdrawal/deposit positions
                    date_matches = list(re.finditer(hdfc_date_pattern, raw_line))
                    hdfc_amount_pattern = r'[\d,]+\.\d{2}'
                    amount_matches = list(re.finditer(hdfc_amount_pattern, raw_line))
                    
                    if len(date_matches) >= 2 and len(amount_matches) >= 2:
                        value_date_pos = date_matches[1].end()
                        
                        # Find amounts after value date (withdrawal, deposit, balance positions)
                        amounts_after_value_date = []
                        for amt_match in amount_matches:
                            if amt_match.start() > value_date_pos:
                                try:
                                    amt_val = float(amt_match.group().replace(',', ''))
                                    if 1.0 <= amt_val <= 10000000.0:
                                        amounts_after_value_date.append({
                                            'pos': amt_match.start(),
                                            'value': amt_match.group(),
                                            'num': amt_val
                                        })
                                except ValueError:
                                    continue
                        
                        # Sort by position
                        amounts_after_value_date.sort(key=lambda x: x['pos'])
                        
                        # Determine withdrawal and deposit positions
                        # Position 0 = withdrawal, Position 1 = deposit, Position 2 = balance
                        if len(amounts_after_value_date) >= 3:
                            # Has both withdrawal and deposit columns
                            withdrawal = amounts_after_value_date[0]
                            deposit = amounts_after_value_date[1]
                            
                            # Withdrawal has value → DEBIT, Deposit has value → CREDIT
                            if withdrawal['num'] > 0:
                                amount = withdrawal['value'].replace(',', '')
                            elif deposit['num'] > 0:
                                amount = deposit['value'].replace(',', '')
                        elif len(amounts_after_value_date) == 2:
                            # Only 2 amounts: either withdrawal+balance or deposit+balance
                            # First amount is transaction amount (withdrawal or deposit)
                            # Second amount is balance
                            amount = amounts_after_value_date[0]['value'].replace(',', '')
                        elif len(amounts_after_value_date) == 1:
                            # Only balance found
                            pass
            
            # If not found, try general patterns with currency symbols (but avoid matching transaction IDs)
            if not amount:
                amount_patterns = [
                    r'[₹]\s*([\d,]+\.?\d*)',        # ₹280 or ₹1,400
                    r'[₹]\s*([\d,]+)',              # ₹280 (no decimal)
                ]
                
                for pattern in amount_patterns:
                    match = re.search(pattern, first_part)
                    if match:
                        amount_str = match.group(1).replace(',', '')
                        # Exclude if it looks like part of a transaction ID (too many digits)
                        # Also exclude suspiciously small amounts that might be from dates
                        try:
                            amount_val = float(amount_str)
                            if len(amount_str.replace('.', '')) <= 8 and amount_val >= 1.0:
                                amount = amount_str
                                break
                        except ValueError:
                            pass
                
                # Last resort: look for decimal amounts with currency symbol (but be very careful)
                if not amount:
                    decimal_match = re.search(r'[₹]\s*([\d,]+\.\d{2})', first_part)
                    if decimal_match:
                        amount_str = decimal_match.group(1).replace(',', '')
                        # Exclude very small amounts that might be from IDs or dates
                        try:
                            amount_val = float(amount_str)
                            if amount_val >= 10.0:  # Higher threshold for decimal amounts
                                amount = amount_str
                        except ValueError:
                            pass
            
            # Ensure we don't use NER MONEY entities if we found a better match
            # The regex extraction above should be prioritized
            # If NER found MONEY entities, validate them against our regex result
            if amount and entities.get('MONEY'):
                # Check if NER MONEY entities match our regex result
                ner_money_values = []
                for money_entity in entities['MONEY']:
                    # Extract numeric value from NER entity
                    money_match = re.search(r'(\d+\.?\d*)', str(money_entity))
                    if money_match:
                        ner_money_values.append(money_match.group(1))
                
                # If our regex amount doesn't match any NER amount, prefer regex (it's more reliable)
                if ner_money_values and amount not in ner_money_values:
                    # Regex amount is different from NER - trust regex for PhonePe format
                    if 'DEBIT' in raw_line.upper() or 'CREDIT' in raw_line.upper():
                        # Keep regex amount (already set above)
                        pass
                    else:
                        # For other formats, could consider NER, but let's stick with regex
                        pass
            
            # Extract description - prioritize full extraction over NER entities
            description = ''
            
            # For HDFC account statement format: "DD/MM/YY Description RefNo DD/MM/YY Amount Balance AdditionalInfo"
            # Extract text between first date and reference number (long number)
            hdfc_date_pattern = r'\b\d{2}/\d{2}/\d{2}\b'
            if re.search(hdfc_date_pattern, raw_line):
                # Find first date
                first_date_match = re.search(hdfc_date_pattern, raw_line)
                if first_date_match:
                    # Look for reference number pattern (10+ digits, often starting with 0)
                    # Pattern: long number (10+ digits) that appears after description
                    ref_no_pattern = r'\b(0\d{9,}|\d{12,})\b'
                    ref_no_match = re.search(ref_no_pattern, raw_line[first_date_match.end():])
                    
                    if ref_no_match:
                        # Extract description between first date and reference number
                        desc_start = first_date_match.end()
                        desc_end = first_date_match.end() + ref_no_match.start()
                        description = raw_line[desc_start:desc_end].strip()
                        
                        # Clean up: remove extra spaces
                        description = re.sub(r'\s+', ' ', description).strip()
                        
                        # Also check if there's additional description info after the balance
                        # Format: ... Balance AdditionalInfo
                        # Look for text after the last amount (balance) that looks like description
                        amount_pattern = r'[\d,]+\.\d{2}'
                        amount_matches = list(re.finditer(amount_pattern, raw_line))
                        if len(amount_matches) >= 2:
                            # Last amount is balance, check if there's text after it
                            balance_end = amount_matches[-1].end()
                            additional_info = raw_line[balance_end:].strip()
                            
                            # If additional info exists and looks like description (has letters, not just numbers/symbols)
                            if additional_info and re.search(r'[A-Za-z]{3,}', additional_info):
                                # Extract meaningful parts (remove transaction IDs, UTRs, etc.)
                                # Keep parts that look like names/descriptions
                                additional_clean = re.sub(r'[A-Z0-9]{10,}', '', additional_info)  # Remove long IDs
                                additional_clean = re.sub(r'-[A-Z0-9-]+', '', additional_clean)  # Remove ID patterns
                                additional_clean = re.sub(r'\s+', ' ', additional_clean).strip()
                                
                                # Combine with main description if meaningful
                                if additional_clean and len(additional_clean) > 3:
                                    # Extract key parts (names, email-like patterns)
                                    name_pattern = r'[A-Z][A-Za-z]+'
                                    names = re.findall(name_pattern, additional_clean)
                                    if names:
                                        # Combine main description with extracted names
                                        description = f"{description} {' '.join(names[:2])}".strip()
            
            # For PhonePe format: "Paid to [MERCHANT NAME] DEBIT/CREDIT"
            # Extract text between "Paid to" and transaction type
            if not description and '|' in raw_line:
                first_part = raw_line.split('|')[0]
                paid_to_match = re.search(r'Paid to\s+(.+?)\s+(DEBIT|CREDIT)', first_part, re.IGNORECASE)
                if paid_to_match:
                    description = paid_to_match.group(1).strip()
            
            # If not PhonePe format or pattern didn't match, try other patterns
            if not description:
                # Try pattern: "Paid to [MERCHANT NAME]" or "To [MERCHANT NAME]"
                paid_patterns = [
                    r'Paid to\s+(.+?)(?:\s+DEBIT|\s+CREDIT|\s*[₹\$]|\s*\d{1,2}:\d{2}|\s*$)',
                    r'To\s+(.+?)(?:\s+DEBIT|\s+CREDIT|\s*[₹\$]|\s*\d{1,2}:\d{2}|\s*$)',
                    r'Paid\s+(.+?)(?:\s+DEBIT|\s+CREDIT|\s*[₹\$]|\s*\d{1,2}:\d{2}|\s*$)',
                ]
                
                for pattern in paid_patterns:
                    match = re.search(pattern, raw_line, re.IGNORECASE)
                    if match:
                        description = match.group(1).strip()
                        # Remove date if it got included
                        if date and date in description:
                            description = description.replace(date, '').strip()
                        if description:
                            break
            
            # If still no description, use NER entities but combine them better
            if not description:
                description_parts = []
                
                # Extract merchant/organization names from entities
                if entities.get('ORG'):
                    # Join all ORG entities together
                    org_desc = ' '.join(entities['ORG'])
                    if org_desc:
                        description_parts.append(org_desc)
                if entities.get('MISC'):
                    misc_desc = ' '.join(entities['MISC'])
                    if misc_desc:
                        description_parts.append(misc_desc)
                
                if description_parts:
                    description = ' '.join(description_parts)
            
            # Last resort: extract manually by removing date, time, amount, and transaction details
            if not description:
                desc_line = raw_line.split('|')[0] if '|' in raw_line else raw_line
                
                # Remove date
                if date:
                    desc_line = desc_line.replace(date, '')
                
                # Remove time
                if time:
                    desc_line = desc_line.replace(time, '')
                
                # Remove amount
                if amount:
                    desc_line = re.sub(r'[₹\$]?\s*[\d,]+\.?\d*', '', desc_line)
                
                # Remove transaction type keywords
                desc_line = re.sub(r'\b(DEBIT|CREDIT|PAID TO|TO)\b', '', desc_line, flags=re.IGNORECASE)
                
                # Clean up
                desc_line = re.sub(r'[|\[\]]', '', desc_line).strip()
                desc_line = re.sub(r'\s+', ' ', desc_line)
                
                # Get meaningful words (words that are not too short and not all digits)
                words = desc_line.split()
                important_words = [w for w in words if len(w) > 1 and not w.isdigit() and not re.match(r'^\d+:\d+', w)]
                
                if important_words:
                    description = ' '.join(important_words)
                else:
                    # Fallback: take first 100 chars of raw line (before | separator)
                    description = desc_line[:100].strip() if desc_line.strip() else raw_line.split('|')[0][:100].strip() if '|' in raw_line else raw_line[:100].strip()
            
            # Clean up description
            description = re.sub(r'[|\[\]]', '', description).strip()
            description = re.sub(r'\s+', ' ', description)
            
            # Determine transaction type
            tx_type = 'UNKNOWN'
            line_upper = raw_line.upper()
            
            # For HDFC account statements, determine type based on column structure
            # Format: Date | Description | RefNo | ValueDate | WithdrawalAmt | DepositAmt | Balance
            # All transactions have this structure, but one column (withdrawal or deposit) is empty
            hdfc_date_pattern = r'\b\d{2}/\d{2}/\d{2}\b'
            if re.search(hdfc_date_pattern, raw_line):
                # First, check for explicit credit/debit indicators in description
                # ACHC- = ACH Credit, ACHD- = ACH Debit
                if 'ACHC-' in line_upper or 'ACH C-' in line_upper:
                    tx_type = 'CREDIT'
                elif 'ACHD-' in line_upper or 'ACH D-' in line_upper:
                    tx_type = 'DEBIT'
                
                # If type not determined yet, analyze amounts structure
                if tx_type == 'UNKNOWN':
                    # Find all dates and amounts
                    date_matches = list(re.finditer(hdfc_date_pattern, raw_line))
                    hdfc_amount_pattern = r'[\d,]+\.\d{2}'
                    amount_matches = list(re.finditer(hdfc_amount_pattern, raw_line))
                    
                    if len(date_matches) >= 2 and len(amount_matches) >= 2:
                        # Find value date (second date)
                        value_date_pos = date_matches[1].end() if len(date_matches) >= 2 else None
                        
                        if value_date_pos:
                            # Look for amounts after value date
                            amounts_after_value_date = []
                            for amt_match in amount_matches:
                                if amt_match.start() > value_date_pos:
                                    try:
                                        amt_val = float(amt_match.group().replace(',', ''))
                                        if 1.0 <= amt_val <= 10000000.0:
                                            amounts_after_value_date.append({
                                                'pos': amt_match.start(),
                                                'value': amt_match.group(),
                                                'num': amt_val
                                            })
                                    except ValueError:
                                        continue
                            
                            # Sort by position
                            amounts_after_value_date.sort(key=lambda x: x['pos'])
                            
                            # In HDFC format: after value date, positions are:
                            # Position 0 = Withdrawal column
                            # Position 1 = Deposit column  
                            # Position 2 = Balance column
                            # Withdrawal has value → DEBIT, Deposit has value → CREDIT
                            
                            if len(amounts_after_value_date) >= 3:
                                # Has both withdrawal and deposit columns visible
                                withdrawal = amounts_after_value_date[0]  # First position = withdrawal
                                deposit = amounts_after_value_date[1]     # Second position = deposit
                                
                                # Check which column has value
                                if withdrawal['num'] > 0:
                                    tx_type = 'DEBIT'  # Withdrawal has value = DEBIT
                                elif deposit['num'] > 0:
                                    tx_type = 'CREDIT'  # Deposit has value = CREDIT
                            elif len(amounts_after_value_date) == 2:
                                # Only 2 amounts: transaction amount + balance
                                # First amount is in either withdrawal or deposit position
                                # In HDFC PDFs, when a column is empty, values can shift left,
                                # so spacing alone is not reliable. We need to use other indicators.
                                
                                first_amount_pos = amounts_after_value_date[0]['pos']
                                second_amount_pos = amounts_after_value_date[1]['pos']
                                
                                # Calculate spacing from value date to first amount
                                spacing_from_value_date = first_amount_pos - value_date_pos
                                
                                # Check for credit indicators in description
                                line_lower = raw_line.lower()
                                credit_keywords = ['credit', 'deposit', 'received', 'refund', 'interest', 'salary', 'dividend', 'acrc-', 'achc-']
                                
                                # Check for patterns that indicate credit transactions
                                # Some UPI transactions can be credits (money received)
                                # Check if description suggests payment received
                                is_likely_credit = False
                                
                                # Check for explicit credit keywords
                                if any(keyword in line_lower for keyword in credit_keywords):
                                    is_likely_credit = True
                                
                                # Check for patterns that might indicate credit (payment received)
                                # These are heuristics based on common patterns
                                credit_patterns = [
                                    'rdacr',  # RD ACR (Recurring Deposit Auto Credit)
                                    'tokyc',  # Sometimes appears in credit transactions
                                    'comp',   # Completion of credit transaction
                                    'rdacrtokyc',  # Combined pattern
                                ]
                                
                                if any(pattern in line_lower for pattern in credit_patterns):
                                    is_likely_credit = True
                                
                                # Debug: Log pattern detection
                                if is_likely_credit:
                                    matched_patterns = [p for p in credit_patterns if p in line_lower]
                                    print(f"  🔍 Credit patterns detected: {matched_patterns}")
                                
                                # Use balance comparison if previous balance is available
                                # This is the most reliable method: if balance increases → CREDIT, decreases → DEBIT
                                current_balance_val = amounts_after_value_date[-1]['num']
                                
                                if previous_balance is not None:
                                    balance_change = current_balance_val - previous_balance
                                    transaction_amount_val = amounts_after_value_date[0]['num']
                                    
                                    # Check if balance change matches transaction amount
                                    # If balance increased by transaction amount → CREDIT
                                    # If balance decreased by transaction amount → DEBIT
                                    if abs(abs(balance_change) - transaction_amount_val) < 0.01:  # Allow small rounding differences
                                        if balance_change > 0:
                                            tx_type = 'CREDIT'
                                            print(f"  ✅ Transaction classified as CREDIT (balance increased from {previous_balance:,.2f} to {current_balance_val:,.2f})")
                                        else:
                                            tx_type = 'DEBIT'
                                            print(f"  ✅ Transaction classified as DEBIT (balance decreased from {previous_balance:,.2f} to {current_balance_val:,.2f})")
                                    else:
                                        # Balance change doesn't match transaction amount - use other indicators
                                        if spacing_from_value_date > 40:
                                            tx_type = 'CREDIT'
                                        elif is_likely_credit:
                                            tx_type = 'CREDIT'
                                            print(f"  ✅ Transaction classified as CREDIT based on patterns")
                                        else:
                                            tx_type = 'DEBIT'
                                            print(f"  ⚠️  Transaction classified as DEBIT (default)")
                                else:
                                    # No previous balance available - use other indicators
                                    if spacing_from_value_date > 40:
                                        tx_type = 'CREDIT'
                                    elif is_likely_credit:
                                        # Has credit indicators → amount is in deposit position
                                        tx_type = 'CREDIT'
                                        print(f"  ✅ Transaction classified as CREDIT based on patterns")
                                    else:
                                        # Default: first amount is in withdrawal position (debit)
                                        # But be cautious - if spacing is ambiguous, we might be wrong
                                        tx_type = 'DEBIT'
                                        print(f"  ⚠️  Transaction classified as DEBIT (default, no previous balance)")
                            elif len(amounts_after_value_date) == 1:
                                # Only balance found, check raw line for type indicators
                                line_lower = raw_line.lower()
                                if any(keyword in line_lower for keyword in ['credit', 'deposit', 'received', 'refund', 'interest', 'achc-']):
                                    tx_type = 'CREDIT'
                                else:
                                    tx_type = 'DEBIT'
                    
                    # Fallback: if we couldn't determine, check amount count
                    if tx_type == 'UNKNOWN':
                        valid_amounts = []
                        for amt_str in [m.group() for m in amount_matches]:
                            try:
                                amt_val = float(amt_str.replace(',', ''))
                                if 1.0 <= amt_val <= 10000000.0:
                                    valid_amounts.append(amt_str)
                            except ValueError:
                                continue
                        
                        if len(valid_amounts) >= 3:
                            # Has withdrawal, deposit, balance columns
                            # Position -3 = withdrawal, Position -2 = deposit, Position -1 = balance
                            withdrawal_str = valid_amounts[-3]
                            deposit_str = valid_amounts[-2]
                            
                            try:
                                withdrawal_val = float(withdrawal_str.replace(',', ''))
                                deposit_val = float(deposit_str.replace(',', ''))
                                
                                # Withdrawal has value → DEBIT, Deposit has value → CREDIT
                                if withdrawal_val > 0:
                                    tx_type = 'DEBIT'
                                elif deposit_val > 0:
                                    tx_type = 'CREDIT'
                            except ValueError:
                                pass
                        elif len(valid_amounts) == 2:
                            # Only 2 amounts: transaction amount + balance
                            # Check raw line for credit indicators to determine if amount is in withdrawal or deposit position
                            line_lower = raw_line.lower()
                            credit_keywords = ['credit', 'deposit', 'received', 'refund', 'interest', 'salary', 'dividend', 'acrc-', 'achc-']
                            debit_keywords = ['debit', 'withdrawal', 'payment', 'upi-', 'achd-', 'ach d-']
                            
                            if any(keyword in line_lower for keyword in credit_keywords):
                                # Has credit keywords → amount is in deposit position → CREDIT
                                tx_type = 'CREDIT'
                            elif any(keyword in line_lower for keyword in debit_keywords):
                                # Has debit keywords → amount is in withdrawal position → DEBIT
                                tx_type = 'DEBIT'
                            else:
                                # Default: amount is in withdrawal position → DEBIT
                                tx_type = 'DEBIT'
            
            # Fallback to keyword-based detection
            if tx_type == 'UNKNOWN':
                # Check for credit keywords first (ACHC = ACH Credit)
                if any(keyword in line_upper for keyword in ['CREDIT', 'DEPOSIT', 'RECEIVED', 'REFUND', 'ACH C-', 'ACHC-', 'INTEREST', 'SALARY', 'DIVIDEND']):
                    tx_type = 'CREDIT'
                elif any(keyword in line_upper for keyword in ['DEBIT', 'WITHDRAWAL', 'PURCHASE', 'PAYMENT', 'AUTOPAY', 'EMI', 'UPI-', 'ACH D-', 'ACHD-']):
                    tx_type = 'DEBIT'
                else:
                    # Default: most transactions are debits
                    tx_type = 'DEBIT'
            
            # Determine currency
            currency = 'INR'
            if '$' in raw_line or 'USD' in raw_line.upper():
                currency = 'USD'
            elif 'EUR' in raw_line.upper():
                currency = 'EUR'
            
            # Reconstruct rawLine with explicit withdrawal/deposit columns for HDFC format
            # Format: Date | Description | RefNo | ValueDate | WithdrawalAmt | DepositAmt | Balance
            # Show empty values explicitly to make credits/debits easily recognizable
            reconstructed_raw_line = raw_line
            hdfc_date_pattern = r'\b\d{2}/\d{2}/\d{2}\b'
            if re.search(hdfc_date_pattern, raw_line) and tx_type in ['DEBIT', 'CREDIT']:
                date_matches = list(re.finditer(hdfc_date_pattern, raw_line))
                hdfc_amount_pattern = r'[\d,]+\.\d{2}'
                amount_matches = list(re.finditer(hdfc_amount_pattern, raw_line))
                
                if len(date_matches) >= 2 and len(amount_matches) >= 2:
                    value_date_pos = date_matches[1].end()
                    
                    # Find amounts after value date
                    amounts_after_value_date = []
                    for amt_match in amount_matches:
                        if amt_match.start() > value_date_pos:
                            try:
                                amt_val = float(amt_match.group().replace(',', ''))
                                if 1.0 <= amt_val <= 10000000.0:
                                    amounts_after_value_date.append({
                                        'pos': amt_match.start(),
                                        'value': amt_match.group(),
                                        'num': amt_val
                                    })
                            except ValueError:
                                continue
                    
                    amounts_after_value_date.sort(key=lambda x: x['pos'])
                    
                    # Reconstruct with explicit withdrawal/deposit columns
                    if len(amounts_after_value_date) >= 2:
                        # Find value date position
                        value_date_end = date_matches[1].end()
                        
                        # Extract parts before value date
                        before_value_date = raw_line[:value_date_end].rstrip()
                        
                        # Get balance (last amount) and find text after balance
                        balance = amounts_after_value_date[-1]['value']
                        balance_match = amount_matches[-1]  # Last amount match is balance
                        after_balance = raw_line[balance_match.end():].strip() if balance_match.end() < len(raw_line) else ""
                        
                        # Determine withdrawal and deposit values based on transaction type and amount positions
                        if len(amounts_after_value_date) >= 3:
                            # Has both withdrawal and deposit columns visible
                            withdrawal_amt = amounts_after_value_date[0]['value'] if amounts_after_value_date[0]['num'] > 0 else ""
                            deposit_amt = amounts_after_value_date[1]['value'] if amounts_after_value_date[1]['num'] > 0 else ""
                        else:
                            # Only 2 amounts: transaction amount + balance
                            transaction_amount = amounts_after_value_date[0]['value']
                            
                            if tx_type == 'DEBIT':
                                # Debit: withdrawal has value, deposit is empty
                                withdrawal_amt = transaction_amount
                                deposit_amt = ""  # Empty
                            else:  # CREDIT
                                # Credit: withdrawal is empty, deposit has value
                                withdrawal_amt = ""  # Empty
                                deposit_amt = transaction_amount
                        
                        # Reconstruct rawLine with explicit columns
                        # Format: ... ValueDate | WithdrawalAmt | DepositAmt | Balance | AdditionalInfo
                        # Show empty values explicitly
                        withdrawal_display = withdrawal_amt if withdrawal_amt else "[empty]"
                        deposit_display = deposit_amt if deposit_amt else "[empty]"
                        
                        # Build reconstructed line
                        reconstructed_parts = [
                            before_value_date,
                            f"Withdrawal: {withdrawal_display}",
                            f"Deposit: {deposit_display}",
                            f"Balance: {balance}"
                        ]
                        
                        # Add additional info after balance if exists
                        if after_balance:
                            reconstructed_parts.append(after_balance)
                        
                        reconstructed_raw_line = " | ".join(reconstructed_parts)
            
            # Build result
            normalized_date = self.normalize_date_string(date)
            amount_value = self.normalize_amount_value(amount)

            result = {
                'date': normalized_date or (date or ''),
                'originalDate': date or '',
                'time': time,
                'description': description,
                'type': tx_type,
                'amount': amount or '',  # Use regex-extracted amount, not NER entities
                'currency': currency,
                'amountValue': amount_value,
                'rawLine': reconstructed_raw_line  # Use reconstructed rawLine with explicit withdrawal/deposit
            }
            
            # Debug: Log if amount seems wrong
            if amount and '|' in raw_line:
                first_part = raw_line.split('|')[0]
                if 'DEBIT' in first_part.upper() or 'CREDIT' in first_part.upper():
                    expected_match = re.search(r'\b(DEBIT|CREDIT)\s+[₹]\s*([\d,]+\.?\d*)', first_part, re.IGNORECASE)
                    if expected_match and expected_match.group(2).replace(',', '') != amount:
                        print(f"⚠️  Warning: Amount mismatch. Expected: {expected_match.group(2)}, Got: {amount}")
            
            return result if (date or amount or description) else None
                
        except Exception as e:
            print(f"❌ Error parsing with AI: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def format_amount(self, amount: str, currency: str = "INR") -> str:
        """Format amount string with proper commas and decimal places"""
        if not amount or amount == 'N/A':
            return amount
        
        try:
            cleaned = re.sub(r'[₹\$\£\€\s]', '', str(amount))
            cleaned = cleaned.replace(',', '')
            num_amount = float(cleaned)
            formatted = f"{num_amount:,.2f}"
            
            if currency == "INR":
                return f'₹{formatted}'
            elif currency == "USD":
                return f'${formatted}'
            else:
                return f'{currency} {formatted}'
        except (ValueError, AttributeError):
            return str(amount)
    
    def detect_format(self, text: str) -> str:
        """Detect bank statement format"""
        text_upper = text.upper()
        
        if 'TRANSACTION STATEMENT' in text_upper and 'PHONEPE' in text_upper:
            return 'phonepe'
        if 'HDFC BANK' in text_upper and 'STATEMENT OF ACCOUNT' in text_upper:
            if re.search(r'\d{2}/\d{2}/\d{2}', text):
                return 'hdfc_account_statement'
        if 'HDFC' in text_upper and ('CREDIT CARD' in text_upper or 'CREDIT CARD STATEMENT' in text_upper):
            return 'hdfc_credit_statement'
        if 'STATEMENT' in text_upper or 'ACCOUNT STATEMENT' in text_upper:
            return 'bank_statement'
        
        return 'unknown'
    
    def extract_transaction_lines(self, text: str, format_type: str) -> List[str]:
        """Extract raw transaction lines from text"""
        lines = text.split('\n')
        transaction_lines = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip header lines
            if any(keyword in line.upper() for keyword in ['DATE', 'TIME', 'TRANSACTION', 'DESCRIPTION', 'AMOUNT', 'STATEMENT', 'PAGE']):
                continue
            
            # Skip statement summary lines
            # Check for summary keywords that indicate this is a summary line, not a transaction
            line_upper = line.upper()
            summary_keywords = [
                'STATEMENTSUMMARY',
                'STATEMENT SUMMARY',
                'OPENINGBALANCE',
                'OPENING BALANCE',
                'CLOSINGBALANCE',
                'CLOSING BALANCE',
            ]
            # If line contains summary keywords, skip it
            if any(keyword in line_upper for keyword in summary_keywords):
                continue
            
            # Also check for summary patterns: multiple amounts with summary keywords
            # Pattern: Has "DRCOUNT", "CRCOUNT", "DEBITS", "CREDITS" together
            if ('DRCOUNT' in line_upper or 'CRCOUNT' in line_upper) and \
               ('DEBITS' in line_upper or 'CREDITS' in line_upper):
                continue
            
            # For PhonePe format, look for lines with date pattern
            if format_type == 'phonepe':
                # PhonePe format: "Oct 11, 2025 Paid to DEEP GARMENTS DEBIT ₹1,400"
                date_pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}'
                if re.search(date_pattern, line, re.IGNORECASE):
                    # Collect the transaction block (date line + time + transaction ID + UTR + Paid by)
                    transaction_block = [line]
                    j = i + 1
                    # Collect up to 4 more lines
                    while j < len(lines) and j < i + 5:
                        next_line = lines[j].strip()
                        if not next_line:
                            break
                        # Stop if next line starts with a date (new transaction)
                        if re.search(date_pattern, next_line, re.IGNORECASE):
                            break
                        transaction_block.append(next_line)
                        j += 1
                    
                    # Skip if this is a statement summary line (check after assembly)
                    assembled_line = ' | '.join(transaction_block)
                    assembled_upper = assembled_line.upper()
                    if any(keyword in assembled_upper for keyword in ['STATEMENTSUMMARY', 'STATEMENT SUMMARY', 'OPENINGBALANCE', 'OPENING BALANCE']):
                        continue
                    if ('DRCOUNT' in assembled_upper or 'CRCOUNT' in assembled_upper) and \
                       ('DEBITS' in assembled_upper or 'CREDITS' in assembled_upper):
                        continue
                    
                    transaction_lines.append(assembled_line)
            else:
                # For HDFC account statements and other formats, check for date pattern
                date_patterns = [
                    r'^\d{2}[\/\-]\d{2}[\/\-]\d{4}',
                    r'^\d{2}\/\d{2}\/\d{2}',
                ]
                
                for pattern in date_patterns:
                    if re.match(pattern, line):
                        # Check if this line contains multiple transactions (multiple date patterns)
                        # HDFC format can have multiple transactions on the same line
                        # Pattern: DD/MM/YY Description RefNo DD/MM/YY Amount Balance DD/MM/YY Description...
                        if format_type == 'hdfc_account_statement':
                            # Find all date patterns in the line
                            hdfc_date_pattern = r'\b\d{2}/\d{2}/\d{2}\b'
                            date_matches = list(re.finditer(hdfc_date_pattern, line))
                            amount_pattern = r'[\d,]+\.\d{2}'
                            
                            # If we have multiple dates, check if they represent different transactions
                            # A transaction has: date1 ... date1 ... amount ... balance date2 ...
                            # A new transaction starts when we see a DIFFERENT date value
                            if len(date_matches) >= 2:
                                transaction_starts = []
                                first_date_value = None
                                
                                for match in date_matches:
                                    date_value = match.group()
                                    pos = match.start()
                                    
                                    # First date is always a transaction start
                                    if first_date_value is None:
                                        transaction_starts.append(pos)
                                        first_date_value = date_value
                                    # If we see a different date value, it's a new transaction
                                    elif date_value != first_date_value:
                                        # Check if we've already added this date as a start
                                        # (to avoid adding value dates as transaction starts)
                                        if not transaction_starts or transaction_starts[-1] != pos:
                                            # Verify this looks like a transaction start:
                                            # Should have amounts before it (from previous transaction)
                                            # and description-like text after it
                                            prev_segment = line[transaction_starts[-1]:pos] if transaction_starts else ''
                                            next_segment = line[pos:pos+30]
                                            
                                            # If previous segment has amounts and next segment has description, it's a new transaction
                                            if re.search(amount_pattern, prev_segment) and re.match(r'^\d{2}/\d{2}/\d{2}\s+[A-Z]', next_segment):
                                                transaction_starts.append(pos)
                                
                                # If we found multiple transaction starts, split the line
                                if len(transaction_starts) > 1:
                                    for idx, start_pos in enumerate(transaction_starts):
                                        # End position is start of next transaction or end of line
                                        if idx + 1 < len(transaction_starts):
                                            end_pos = transaction_starts[idx + 1]
                                            transaction_line = line[start_pos:end_pos].strip()
                                        else:
                                            transaction_line = line[start_pos:].strip()
                                        
                                        # Only add if it's a valid transaction (has amount pattern)
                                        if transaction_line and re.search(amount_pattern, transaction_line):
                                            # Skip summary lines
                                            tx_line_upper = transaction_line.upper()
                                            if not any(keyword in tx_line_upper for keyword in ['STATEMENTSUMMARY', 'STATEMENT SUMMARY', 'OPENINGBALANCE', 'OPENING BALANCE']):
                                                if not (('DRCOUNT' in tx_line_upper or 'CRCOUNT' in tx_line_upper) and \
                                                       ('DEBITS' in tx_line_upper or 'CREDITS' in tx_line_upper)):
                                                    transaction_lines.append(transaction_line)
                                    break
                        
                        # Single transaction on line (or non-HDFC format)
                        transaction_line = line
                        j = i + 1
                        
                        # Look ahead for continuation
                        while j < len(lines) and j < i + 4:
                            next_line = lines[j].strip()
                            if not next_line:
                                break
                            # Stop if next line starts with a date (new transaction)
                            if re.match(r'^\d{2}[\/\-]\d{2}[\/\-]\d{4}', next_line) or \
                               re.match(r'^\d{2}\/\d{2}\/\d{2}', next_line):
                                break
                            transaction_line += ' ' + next_line
                            j += 1
                        
                        # Skip if this is a statement summary line (check after assembly)
                        tx_line_upper = transaction_line.upper()
                        if any(keyword in tx_line_upper for keyword in ['STATEMENTSUMMARY', 'STATEMENT SUMMARY', 'OPENINGBALANCE', 'OPENING BALANCE']):
                            # Skip this transaction, continue to next line
                            break
                        if ('DRCOUNT' in tx_line_upper or 'CRCOUNT' in tx_line_upper) and \
                           ('DEBITS' in tx_line_upper or 'CREDITS' in tx_line_upper):
                            # Skip this transaction, continue to next line
                            break
                        
                        transaction_lines.append(transaction_line)
                        break
        
        return transaction_lines
    
    def extract_transactions(self, file_path: str) -> Dict:
        """Main function to extract transactions from PDF using AI"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        results = {
            'sourceFile': file_path,
            'timestamp': datetime.now().isoformat(),
            'transactions': [],
            'metadata': {
                'totalTransactions': 0,
                'extractionMethod': 'BERT/RoBERTa NER',
                'format': 'unknown',
                'model': self.model_name
            }
        }
        
        print(f"📄 Reading PDF: {file_path}")
        
        all_text = []
        try:
            with pdfplumber.open(file_path) as pdf:
                print(f"  ✓ PDF opened successfully ({len(pdf.pages)} pages)\n")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    print(f"📄 Processing page {page_num} of {len(pdf.pages)}")
                    
                    text = page.extract_text()
                    
                    if text:
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
        
        # Extract transaction lines
        print("🔍 Extracting transaction lines...")
        all_transaction_lines = []
        for page_data in all_text:
            lines = self.extract_transaction_lines(page_data['text'], format_type)
            all_transaction_lines.extend(lines)
        
        print(f"  ✓ Found {len(all_transaction_lines)} transaction lines\n")
        
        # Load model before processing
        print("🤖 Loading AI model...")
        self.load_model()
        print("✅ Model ready\n")
        
        # Parse each transaction line with AI
        print("🤖 Parsing transactions with BERT/RoBERTa NER...\n")
        
        parsed_transactions = []
        previous_balance = None  # Track previous balance to determine transaction type
        
        for idx, raw_line in enumerate(all_transaction_lines, 1):
            print(f"  [{idx}/{len(all_transaction_lines)}] Parsing: {raw_line[:80]}...")
            
            parsed = self.parse_with_ai(raw_line, previous_balance)
            
            if parsed:
                # Extract current balance for next iteration from original raw_line
                # Balance is the last amount in HDFC format
                current_balance = None
                import re
                hdfc_amount_pattern = r'[\d,]+\.\d{2}'
                amount_matches = list(re.finditer(hdfc_amount_pattern, raw_line))
                if len(amount_matches) >= 1:
                    # Last amount is balance
                    balance_str = amount_matches[-1].group()
                    try:
                        balance_val = float(balance_str.replace(',', ''))
                        # Reasonable balance: between ₹0 and ₹100,000,000
                        if 0.0 <= balance_val <= 100000000.0:
                            current_balance = balance_val
                    except ValueError:
                        pass
                
                formatted_transaction = {
                    'date': parsed.get('date', ''),
                    'originalDate': parsed.get('originalDate', parsed.get('date', '')),
                    'time': parsed.get('time', ''),
                    'description': parsed.get('description', ''),
                    'type': parsed.get('type', 'UNKNOWN'),
                    'amount': self.format_amount(parsed.get('amount', ''), parsed.get('currency', 'INR')),
                    'currency': parsed.get('currency', 'INR'),
                    'amountValue': parsed.get('amountValue'),
                    'rawLine': parsed.get('rawLine', raw_line)  # Use reconstructed rawLine if available
                }
                
                parsed_transactions.append(formatted_transaction)
                
                # Update previous balance for next transaction
                if current_balance is not None:
                    previous_balance = current_balance
                
                print(f"       ✓ Parsed: {formatted_transaction['description'][:50]}... - {formatted_transaction['amount']} ({formatted_transaction['type']})\n")
            else:
                print(f"       ⚠️  Failed to parse\n")
        
        # Organize by page
        results['transactions'] = [{
            'page': 1,
            'transactions': parsed_transactions,
            'rawText': combined_text[:1000] + '...' if len(combined_text) > 1000 else combined_text
        }]
        
        results['metadata']['totalTransactions'] = len(parsed_transactions)
        
        return results


def main():
    """Command line interface"""
    if len(sys.argv) < 2:
        print('Usage: python bank_reader_ai.py <pdf-file-path> [model-name]')
        print('\nExamples:')
        print('  python bank_reader_ai.py statement.pdf')
        print('  python bank_reader_ai.py statement.pdf dslim/bert-base-NER')
        print('  python bank_reader_ai.py statement.pdf Jean-Baptiste/roberta-large-ner-english')
        print('\nAvailable Models:')
        print('  - dslim/bert-base-NER (default) - Fast, general purpose')
        print('  - Jean-Baptiste/roberta-large-ner-english - Larger, more accurate')
        print('  - dbmdz/bert-large-cased-finetuned-conll03-english - Very accurate')
        print('\nNote:')
        print('  - First run will download the model (~500MB-1.5GB)')
        print('  - GPU recommended for faster processing')
        print('  - CPU will work fine (BERT models are efficient)')
        sys.exit(1)
    
    file_path = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "dslim/bert-base-NER"
    
    try:
        reader = BankStatementReaderAI(model_name=model_name)
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
        print(f"AI Model: {results['metadata']['model']}")
        print('=' * 80 + '\n')
        
    except Exception as e:
        print(f'\n❌ Extraction failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
