"""
API helper functions for PDF processing and caching
"""
import os
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from bank_reader_ai import BankStatementReaderAI

# Paths
READERFILES_DIR = Path(__file__).parent / 'readerfiles'
CACHE_DIR = Path(__file__).parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

# Subscription detection heuristics
SUBSCRIPTION_KEYWORDS = [
    'SUBSCRIPTION',
    'SUBSCR',
    'MEMBERSHIP',
    'RENEWAL',
    'AUTO PAY',
    'AUTOPAY',
    'AUTO-DEBIT',
    'RECURRING',
    'MONTHLY PLAN',
    'MONTHLY FEE',
    'MONTHLY CHARGES',
    'PLAN FEE',
    'UPI AUTOPAY',
    'UPI-AUTOPAY',
    'SI-HDFC',
    'STANDING INSTRUCTION',
    'MANDATE',
    'E-NACH',
    'ENACH',
    'SI BILLDESK',
    'AUTO PAYMENT',
    'AUTO PAYMENT',
    'AUTOMATIC PAYMENT',
    'AUTO-RENEW',
    'AUTO RENEW',
]

SUBSCRIPTION_MERCHANTS = [
    'NETFLIX',
    'SPOTIFY',
    'YOUTUBE',
    'GOOGLE STORAGE',
    'GOOGLE ONE',
    'AMAZON PRIME',
    'PRIME VIDEO',
    'HOTSTAR',
    'SONYLIV',
    'ZEE5',
    'APPLE.COM',
    'APPLE BILL',
    'ICLOUD',
    'MICROSOFT',
    'OFFICE 365',
    'OFFICE365',
    'GITHUB',
    'FIGMA',
    'ADOBE',
    'NOTION',
    'ZOOM',
    'DROPBOX',
    'CANVA',
    'OPENAI',
    'ANTHROPIC',
    'CLAUDE.AI',
    'CURSOR',
    'SLACK',
    'ATLASSIAN',
    'JIRA',
    'SWIGGY ONE',
    'BIGBASKET BBSTAR',
    'URBANCLAP PLUS',
    'CRED PRIME',
    'PHONEPE PASS',
    'SPOTIFY AB',
    'QUILLBOT',
    'SUBSTACK',
    'MIRROR AI',
]

SUBSCRIPTION_REGEXES = [
    re.compile(r'\bUPI[-\s]?AUTO(?:PAY| DEBIT)\b', re.IGNORECASE),
    re.compile(r'\bAUTO[-\s]?RENEW(AL)?\b', re.IGNORECASE),
    re.compile(r'\bRECURRING\s+PAYMENT\b', re.IGNORECASE),
    re.compile(r'\bSI\s*/\s*ACH\b', re.IGNORECASE),
    re.compile(r'\bAUTH\s*MANDATE\b', re.IGNORECASE),
]

DEFAULT_CATEGORY_DEFS = [
    {'value': 'foods', 'label': 'Foods & Dining'},
    {'value': 'fuel', 'label': 'Fuel'},
    {'value': 'recharge', 'label': 'Recharge & Utilities'},
    {'value': 'mutual_fund', 'label': 'Mutual Fund'},
    {'value': 'credit_bills', 'label': 'Credit Bills'},
    {'value': 'income', 'label': 'Income'},
    {'value': 'others', 'label': 'Others'},
]

CATEGORY_KEYWORDS = {
    'foods': [
        'SWIGGY', 'ZOMATO', 'FOOD', 'DINING', 'RESTAURANT', 'PIZZA', 'CAFE',
        'DOMINOS', 'EATS', 'BBQ NATION', 'KFC', 'MCDONALD'
    ],
    'fuel': [
        'FUEL', 'PETROL', 'DIESEL', 'HPCL', 'IOCL', 'BPCL', 'SHELL', 'ESSAR',
        'FILLING STATION', 'AUTOFUEL', 'HP PAY'
    ],
    'recharge': [
        'RECHARGE', 'FASTAG', 'MOBILE', 'PREPAID', 'POSTPAID', 'DTH', 'BROADBAND',
        'AIRTEL', 'JIO', 'VODAFONE', 'VI ', 'BSNL', 'DATA CARD'
    ],
    'mutual_fund': [
        'MUTUAL FUND', 'SIP', 'SYSTEMATIC INVEST', 'AMC', 'CAMS', 'KFINTECH',
        'MFU', 'GROWW', 'ZERODHA COIN', 'CLEARFUNDS', 'INVESTMENT SERVICES'
    ],
    'credit_bills': [
        'CREDIT CARD PAYMENT', 'CARD PAYMENT', 'CC PAYMENT', 'HDFC BANK CARD',
        'ICICI CREDIT CARD', 'BILLDESK', 'STATEMENT PAYMENT', 'CARDSETTLEMENT',
        'HDFCBANKCC', 'PAYTM CREDIT CARD'
    ],
    'income': [
        'SALARY', 'PAYROLL', 'NEFT CR', 'REFUND', 'INTEREST', 'DIVIDEND',
        'REIMBURSEMENT', 'CREDITED BY', 'CREDIT FROM', 'PAYMENT RECEIVED'
    ]
}
CUSTOM_CATEGORIES_PATH = CACHE_DIR / 'custom_categories.json'
CATEGORY_OVERRIDES_PATH = CACHE_DIR / 'category_overrides.json'


def _prepare_detection_text(transaction: Dict) -> str:
    """Combine relevant fields into a single uppercase string for detection."""
    parts: List[str] = []
    for field in ('description', 'narration', 'rawLine', 'details', 'merchant', 'to', 'paidBy'):
        value = transaction.get(field)
        if value:
            parts.append(str(value))

    combined = ' '.join(parts)
    combined = re.sub(r'\s+', ' ', combined).strip()
    return combined.upper()


def detect_subscription(transaction: Dict) -> Tuple[bool, str]:
    """
    Detect whether a transaction looks like a subscription charge.

    Returns:
        Tuple[bool, str]: (is_subscription, reason_for_detection)
    """
    text = _prepare_detection_text(transaction)
    if not text:
        return False, ''

    for keyword in SUBSCRIPTION_KEYWORDS:
        if keyword in text:
            return True, f"keyword:{keyword.lower()}"

    for pattern in SUBSCRIPTION_REGEXES:
        if pattern.search(text):
            return True, f"pattern:{pattern.pattern}"

    for merchant in SUBSCRIPTION_MERCHANTS:
        if merchant in text:
            return True, f"merchant:{merchant.lower()}"

    # Additional heuristics
    if 'AUTO' in text and ('PAY' in text or 'DEBIT' in text):
        return True, 'heuristic:autopay'
    if 'SI/' in text or 'STANDING INST' in text:
        return True, 'heuristic:standing_instruction'
    if 'SUB ' in text or 'SUB-' in text:
        return True, 'heuristic:subscription_shorthand'

    return False, ''


def collect_tags(transactions: List[Dict]) -> List[str]:
    """Collect unique tags from a list of transactions preserving order."""
    seen: List[str] = []
    for tx in transactions:
        for tag in tx.get('tags', []):
            if tag not in seen:
                seen.append(tag)
    return seen


def load_category_overrides() -> Dict[str, str]:
    """Load persisted manual category overrides."""
    if CATEGORY_OVERRIDES_PATH.exists():
        try:
            with open(CATEGORY_OVERRIDES_PATH, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception as exc:
            print(f"Error loading category overrides: {exc}")
    return {}


def save_category_overrides(overrides: Dict[str, str]) -> None:
    """Persist manual category overrides."""
    CATEGORY_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CATEGORY_OVERRIDES_PATH, 'w', encoding='utf-8') as fp:
        json.dump(overrides, fp, indent=2, ensure_ascii=False)


def load_custom_categories() -> List[Dict[str, str]]:
    """Load user-defined custom categories."""
    if not CUSTOM_CATEGORIES_PATH.exists():
        return []

    try:
        with open(CUSTOM_CATEGORIES_PATH, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            categories: List[Dict[str, str]] = []
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    value = str(item.get('value', '')).strip().lower()
                    label = str(item.get('label', '')).strip()
                    if value and label:
                        categories.append({'value': value, 'label': label})
            return categories
    except Exception as exc:
        print(f"Error loading custom categories: {exc}")
        return []


def save_custom_categories(categories: List[Dict[str, str]]) -> None:
    """Persist custom category definitions."""
    CUSTOM_CATEGORIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CUSTOM_CATEGORIES_PATH, 'w', encoding='utf-8') as fp:
        json.dump(categories, fp, indent=2, ensure_ascii=False)


def get_category_options() -> List[Dict[str, str]]:
    """Return combined list of default and custom category options."""
    options = list(DEFAULT_CATEGORY_DEFS)
    custom = load_custom_categories()
    # Avoid duplicates by value (custom overrides defaults if duplicated)
    seen = {item['value'] for item in options}
    for item in custom:
        if item['value'] not in seen:
            options.append(item)
            seen.add(item['value'])
    return options


def get_category_label_map() -> Dict[str, str]:
    """Return mapping of category value to display label."""
    label_map: Dict[str, str] = {}
    for item in get_category_options():
        label_map[item['value']] = item['label']
    return label_map


def slugify_category_label(label: str) -> str:
    """Generate slug/identifier from label."""
    normalized = re.sub(r'[^a-z0-9]+', '_', label.lower())
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    return normalized


def add_custom_category(label: str) -> Dict[str, str]:
    """Create a new custom category and persist it."""
    if not label or not label.strip():
        raise ValueError("Category name is required")

    cleaned_label = label.strip()
    slug = slugify_category_label(cleaned_label)
    if not slug:
        raise ValueError("Category name must include letters or numbers")

    label_map = get_category_label_map()
    if slug in label_map:
        raise ValueError("Category already exists")

    custom_categories = load_custom_categories()
    custom_categories.append({'value': slug, 'label': cleaned_label})
    save_custom_categories(custom_categories)
    return {'value': slug, 'label': cleaned_label}


def set_category_override(group_key: str, category: Optional[str]) -> Dict[str, str]:
    """Set or remove a manual category override for a duplicate group."""
    if not group_key:
        raise ValueError("groupKey is required")

    overrides = load_category_overrides()

    label_map = get_category_label_map()

    if not category or category == 'auto':
        overrides.pop(group_key, None)
    else:
        normalized = category.strip().lower()
        if normalized not in label_map:
            raise ValueError(f"Invalid category: {category}")
        overrides[group_key] = normalized

    save_category_overrides(overrides)
    return overrides


def get_category_configuration() -> Dict[str, Dict]:
    """Return category metadata and overrides."""
    return {
        'options': get_category_options(),
        'overrides': load_category_overrides()
    }


def auto_categorize_transaction(transaction: Dict) -> str:
    """Heuristic-based auto categorization of a transaction."""
    text = _prepare_detection_text(transaction)
    tx_type = (transaction.get('type') or '').upper()
    is_credit = tx_type == 'CREDIT'

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'income' and not is_credit:
            continue
        for keyword in keywords:
            if keyword in text:
                return category

    if is_credit:
        return 'income'

    return 'others'


def resolve_transaction_category(group_key: str, transaction: Dict, overrides: Dict[str, str]) -> Tuple[str, str]:
    """Determine the category and its source for a transaction."""
    manual = overrides.get(group_key)
    label_map = get_category_label_map()

    if manual in label_map:
        return manual, 'manual'

    auto = auto_categorize_transaction(transaction)
    if auto not in label_map:
        auto = 'others'
    return auto, 'auto'


def get_cache_path(filename: str) -> Path:
    """Get cache file path for a given PDF filename"""
    cache_filename = filename.replace('.pdf', '.json')
    return CACHE_DIR / cache_filename


def is_cache_valid(file_path: Path, cache_path: Path) -> bool:
    """Check if cache exists and is newer than the PDF file"""
    if not cache_path.exists():
        return False
    
    if not file_path.exists():
        return False
    
    cache_mtime = cache_path.stat().st_mtime
    pdf_mtime = file_path.stat().st_mtime
    
    return cache_mtime >= pdf_mtime


def get_cached_result(filename: str) -> Optional[Dict]:
    """Load cached result if it exists and is valid"""
    file_path = READERFILES_DIR / filename
    cache_path = get_cache_path(filename)
    
    if not is_cache_valid(file_path, cache_path):
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading cache: {e}")
        return None


def save_to_cache(filename: str, data: Dict) -> bool:
    """Save processed results to cache"""
    cache_path = get_cache_path(filename)
    
    try:
        # Add cache metadata
        data['_cache_metadata'] = {
            'cached_at': datetime.now().isoformat(),
            'source_file': filename
        }
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving cache: {e}")
        return False


def process_pdf(file_path: str, use_cache: bool = True) -> Dict:
    """
    Process a PDF file using BankStatementReaderAI
    
    Args:
        file_path: Path to PDF file
        use_cache: Whether to use cached results if available
        
    Returns:
        Dictionary with transaction data
    """
    filename = os.path.basename(file_path)
    
    # Check cache first
    if use_cache:
        cached = get_cached_result(filename)
        if cached is not None:
            print(f"Using cached result for {filename}")
            return cached
    
    # Process PDF
    print(f"Processing {filename}...")
    reader = BankStatementReaderAI()
    result = reader.extract_transactions(file_path)
    
    # Save to cache
    save_to_cache(filename, result)
    
    return result


def scan_readerfiles_folder() -> List[Dict]:
    """Scan readerfiles folder and return list of PDF files"""
    pdf_files = []
    
    if not READERFILES_DIR.exists():
        return pdf_files
    
    for file_path in READERFILES_DIR.glob('*.pdf'):
        stat = file_path.stat()
        pdf_files.append({
            'filename': file_path.name,
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'has_cache': get_cache_path(file_path.name).exists()
        })
    
    return sorted(pdf_files, key=lambda x: x['modified'], reverse=True)


def combine_all_transactions(force_refresh: bool = False) -> Dict:
    """
    Combine transactions from all PDFs in readerfiles folder
    
    Args:
        force_refresh: If True, reprocess all files even if cache exists
        
    Returns:
        Dictionary with all transactions combined
    """
    all_transactions = []
    file_summaries = []
    
    pdf_files = scan_readerfiles_folder()
    
    for pdf_info in pdf_files:
        filename = pdf_info['filename']
        file_path = READERFILES_DIR / filename
        
        if not file_path.exists():
            continue
        
        try:
            result = process_pdf(str(file_path), use_cache=not force_refresh)
            
            # Extract transactions from result structure
            transactions_list = []
            if isinstance(result.get('transactions'), list):
                for page_data in result['transactions']:
                    if isinstance(page_data, dict) and 'transactions' in page_data:
                        transactions_list.extend(page_data['transactions'])
            
            # Add source file info to each transaction
            for tx in transactions_list:
                tx['sourceFile'] = filename
                tx['sourceFileMetadata'] = {
                    'format': result.get('metadata', {}).get('format', 'unknown'),
                    'processedAt': result.get('timestamp', '')
                }

                normalized_date = BankStatementReaderAI.normalize_date_string(
                    tx.get('date') or tx.get('originalDate') or ''
                )
                if normalized_date:
                    tx['date'] = normalized_date

                amount_value = tx.get('amountValue')
                if amount_value is None:
                    amount_value = BankStatementReaderAI.normalize_amount_value(tx.get('amount'))
                    if amount_value is not None:
                        tx['amountValue'] = amount_value

                tags = tx.get('tags') if isinstance(tx.get('tags'), list) else []
                detected_subscription, reason = detect_subscription(tx)
                if detected_subscription:
                    if 'subscription' not in tags:
                        tags.append('subscription')
                    tx['isSubscription'] = True
                    tx['subscriptionReason'] = reason
                else:
                    tx['isSubscription'] = False
                    if 'subscription' in tags:
                        tags = [tag for tag in tags if tag != 'subscription']
                    tx['subscriptionReason'] = ''

                tx['tags'] = tags
            
            all_transactions.extend(transactions_list)
            
            file_summaries.append({
                'filename': filename,
                'count': len(transactions_list),
                'format': result.get('metadata', {}).get('format', 'unknown')
            })
            
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            file_summaries.append({
                'filename': filename,
                'count': 0,
                'error': str(e)
            })
    
    category_overrides = load_category_overrides()
    duplicate_groups = {}

    for idx, tx in enumerate(all_transactions):
        date_key = BankStatementReaderAI.normalize_date_string(
            tx.get('date') or tx.get('originalDate') or ''
        )

        amount_value = tx.get('amountValue')
        if amount_value is None:
            amount_value = BankStatementReaderAI.normalize_amount_value(tx.get('amount'))
            if amount_value is not None:
                tx['amountValue'] = amount_value

        if date_key and amount_value is not None:
            rounded_amount = round(float(amount_value), 2)
            group_key = f"{date_key}:{rounded_amount:.2f}"
        else:
            group_key = f"__ungrouped__{idx}"

        tx['duplicateGroupKey'] = group_key
        category_value, category_source = resolve_transaction_category(group_key, tx, category_overrides)
        tx['category'] = category_value
        tx['categorySource'] = category_source
        duplicate_groups.setdefault(group_key, []).append(tx)

    duplicate_groups_list = []
    duplicate_transaction_count = 0
    duplicates_collapsed = 0

    for group_key, txs in duplicate_groups.items():
        if len(txs) > 1:
            duplicate_transaction_count += len(txs)
            duplicates_collapsed += len(txs) - 1
            duplicate_groups_list.append({
                'groupKey': group_key,
                'date': txs[0].get('date'),
                'amount': txs[0].get('amountValue'),
                'transactions': [
                    {
                        'sourceFile': tx.get('sourceFile'),
                        'description': tx.get('description'),
                        'type': tx.get('type'),
                        'time': tx.get('time'),
                        'rawLine': tx.get('rawLine')
                    }
                    for tx in txs
                ]
            })

    collapsed_transactions: List[Dict] = []

    for group_key, txs in duplicate_groups.items():
        if not txs:
            continue

        representative = txs[0]
        unique_sources = sorted({tx.get('sourceFile', '') or '' for tx in txs if tx.get('sourceFile')})
        source_display = ''
        if len(unique_sources) == 0:
            source_display = representative.get('sourceFile', '')
        elif len(unique_sources) == 1:
            source_display = unique_sources[0]
        else:
            source_display = f"Multiple ({len(unique_sources)} files)"

        tags = collect_tags(txs)
        is_subscription = any(tx.get('isSubscription') for tx in txs)
        subscription_reasons = [tx.get('subscriptionReason') for tx in txs if tx.get('subscriptionReason')]
        category_values = [tx.get('category') for tx in txs if tx.get('category')]
        category_sources = [tx.get('categorySource') for tx in txs if tx.get('categorySource')]
        representative_category = category_values[0] if category_values else representative.get('category', 'others')
        representative_category_source = category_sources[0] if category_sources else representative.get('categorySource', 'auto')

        collapsed_transactions.append({
            'duplicateGroupKey': group_key,
            'duplicateCount': len(txs),
            'date': representative.get('date', ''),
            'originalDate': representative.get('originalDate', ''),
            'time': representative.get('time', ''),
            'description': representative.get('description', ''),
            'type': representative.get('type', 'UNKNOWN'),
            'amount': representative.get('amount', ''),
            'amountValue': representative.get('amountValue'),
            'currency': representative.get('currency', 'INR'),
            'rawLine': representative.get('rawLine'),
            'sourceFile': source_display,
            'sourceFiles': unique_sources if unique_sources else ([representative.get('sourceFile')] if representative.get('sourceFile') else []),
            'tags': tags,
            'isSubscription': is_subscription,
            'subscriptionReason': subscription_reasons[0] if subscription_reasons else representative.get('subscriptionReason', ''),
             'category': representative_category,
             'categorySource': representative_category_source,
            'transactions': [
                {
                    'date': tx.get('date', ''),
                    'originalDate': tx.get('originalDate', ''),
                    'time': tx.get('time', ''),
                    'description': tx.get('description', ''),
                    'type': tx.get('type', 'UNKNOWN'),
                    'amount': tx.get('amount', ''),
                    'amountValue': tx.get('amountValue'),
                    'currency': tx.get('currency', 'INR'),
                    'sourceFile': tx.get('sourceFile'),
                    'rawLine': tx.get('rawLine'),
                    'tags': tx.get('tags', []),
                    'isSubscription': tx.get('isSubscription', False),
                    'subscriptionReason': tx.get('subscriptionReason', ''),
                    'category': tx.get('category', 'others'),
                    'categorySource': tx.get('categorySource', 'auto'),
                    'duplicateGroupKey': tx.get('duplicateGroupKey')
                }
                for tx in txs
            ]
        })

    return {
        'transactions': all_transactions,
        'collapsedTransactions': collapsed_transactions,
        'duplicateGroups': duplicate_groups_list,
        'summary': {
            'totalTransactions': len(all_transactions),
            'collapsedTransactionCount': len(collapsed_transactions),
            'duplicateGroupCount': len(duplicate_groups_list),
            'duplicateTransactionCount': duplicate_transaction_count,
            'duplicatesCollapsed': duplicates_collapsed,
            'totalFiles': len(pdf_files),
            'processedFiles': len(file_summaries),
            'files': file_summaries,
            'timestamp': datetime.now().isoformat()
        }
    }

