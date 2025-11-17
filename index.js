const fs = require('fs');
const {PDFParse: pdf} = require('pdf-parse');
const {google} = require('googleapis');
require('dotenv').config();

function parsePhonePeTransactions(text) {
    const transactions = [];
    const lines = text.split('\n');

    let i = 0;
    while (i < lines.length) {
        const line = lines[i].trim();

        // Check if line matches date pattern (e.g., "Oct 11, 2025" or "Sept 27, 2025")
        if (/^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}$/.test(line)) {
            const date = line;
            i++;

            // Get time (next line)
            const time = lines[i]?.trim() || '';
            i++;

            // Get transaction type and amount + details
            const typeAmountLine = lines[i]?.trim() || '';
            i++;

            // Parse type, amount, and details
            const typeMatch = typeAmountLine.match(/(DEBIT|CREDIT)\s+₹([\d,\.]+)\s+(.+)/);
            if (typeMatch) {
                const [, type, amount, details] = typeMatch;

                // Extract "to" or "from" information
                let toFrom = '';
                if (details.includes('Paid to')) {
                    toFrom = details.replace('Paid to', '').trim();
                } else if (details.includes('Received from')) {
                    toFrom = details.replace('Received from', '').trim();
                } else if (details.includes('Payment to')) {
                    toFrom = details.replace('Payment to', '').trim();
                } else if (details.includes('recharged')) {
                    toFrom = details;
                }

                // Get Transaction ID
                const txnIdLine = lines[i]?.trim() || '';
                const txnIdMatch = txnIdLine.match(/Transaction ID\s+(.+)/);
                const transactionId = txnIdMatch ? txnIdMatch[1] : '';
                i++;

                // Get UTR No
                const utrLine = lines[i]?.trim() || '';
                const utrMatch = utrLine.match(/UTR No\.\s+(.+)/);
                const utrNo = utrMatch ? utrMatch[1] : '';
                i++;

                // Get Paid by / Credited to
                let paidBy = '';
                const paidByLine = lines[i]?.trim() || '';
                if (paidByLine.includes('Paid by')) {
                    paidBy = paidByLine.replace('Paid by', '').trim();
                    i++;
                } else if (paidByLine.includes('Credited to')) {
                    paidBy = paidByLine.replace('Credited to', '').trim();
                    i++;
                }

                transactions.push({
                    date,
                    time,
                    type,
                    amount: `₹${amount}`,
                    to: toFrom,
                    paidBy,
                    transactionId,
                    utrNo
                });
            }
        } else {
            i++;
        }
    }

    return transactions;
}

function parseHDFCCreditStatementTransactions(text) {
    const transactions = [];
    const lines = text.split('\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        // Look for date pattern like "22/09/2025" or "22-09-2025" or "22 Sep 2025"
        const dateMatch = line.match(/^(\d{2}[\/\-]\d{2}[\/\-]\d{4}|\d{2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})/);

        if (dateMatch) {
            const date = dateMatch[0];
            const restOfLine = line.substring(dateMatch[0].length).trim();

            // Try to parse the transaction details
            // Format can vary but typically: Date | Description | Debit/Credit | Amount | Balance

            // Check for common patterns
            let description = '';
            let type = '';
            let amount = '';
            let balance = '';
            let transactionType = ''; // Domestic or International

            // Look for keywords to identify transaction type
            if (restOfLine.includes('INTERNATIONAL') || restOfLine.includes('FOREIGN') ||
                restOfLine.includes('USD') || restOfLine.includes('EUR') || restOfLine.includes('GBP')) {
                transactionType = 'INTERNATIONAL';
            } else {
                transactionType = 'DOMESTIC';
            }

            // Try to extract amount - look for patterns like "1,234.56" or "₹1,234.56" or "$1,234.56"
            const amountMatch = restOfLine.match(/([\$₹£€]?\s?[\d,]+\.?\d*)/g);

            // Extract description (everything before the amounts)
            const parts = restOfLine.split(/\s+/);
            let descriptionParts = [];
            let amounts = [];

            for (const part of parts) {
                if (/^[\$₹£€]?[\d,]+\.?\d*$/.test(part)) {
                    amounts.push(part);
                } else if (amounts.length === 0) {
                    descriptionParts.push(part);
                }
            }

            description = descriptionParts.join(' ');

            // Determine if it's debit or credit based on keywords
            if (description.includes('DEBIT') || description.includes('WITHDRAWAL') ||
                description.includes('PURCHASE') || description.includes('PAYMENT')) {
                type = 'DEBIT';
            } else if (description.includes('CREDIT') || description.includes('DEPOSIT') ||
                       description.includes('RECEIVED')) {
                type = 'CREDIT';
            }

            // Assign amounts (typically last two numbers are amount and balance)
            if (amounts.length >= 2) {
                amount = amounts[amounts.length - 2];
                balance = amounts[amounts.length - 1];
            } else if (amounts.length === 1) {
                amount = amounts[0];
            }

            if (description || amount) {
                transactions.push({
                    date,
                    description: description || restOfLine,
                    type: type || 'UNKNOWN',
                    amount: amount || 'N/A',
                    balance: balance || '',
                    transactionType: transactionType,
                    rawLine: line
                });
            }
        }
    }

    return transactions;
}

function parseHDFCAccountStatementTransactions(text) {
    const transactions = [];
    const lines = text.split('\n');

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        // Look for date pattern at start: DD/MM/YY
        const dateMatch = line.match(/^(\d{2}\/\d{2}\/\d{2})\s+(.+)/);

        if (dateMatch) {
            const date = dateMatch[1];
            let restOfLine = dateMatch[2];

            // Parse the transaction line
            // Format: Date Narration Ref.No ValueDate WithdrawalAmt DepositAmt ClosingBalance

            // Extract all numbers (amounts) - format: 1,234.56 or 234.56
            const numberPattern = /[\d,]+\.\d{2}/g;
            const numbers = restOfLine.match(numberPattern) || [];

            let withdrawal = '';
            let deposit = '';
            let balance = '';
            let refNo = '';
            let valueDate = '';
            let narration = '';

            // Last number is always balance
            if (numbers.length >= 1) {
                balance = numbers[numbers.length - 1];
            }

            // Remove balance from the line to get remaining info
            let lineWithoutBalance = restOfLine;
            if (balance) {
                const balanceIndex = restOfLine.lastIndexOf(balance);
                lineWithoutBalance = restOfLine.substring(0, balanceIndex).trim();
            }

            // Extract reference number - typically 10+ digits starting with 0000
            const refMatch = lineWithoutBalance.match(/\b(0\d{12,}|\d{12,})\b/);
            if (refMatch) {
                refNo = refMatch[1];
            }

            // Extract value date (second occurrence of date pattern)
            const valueDateMatches = lineWithoutBalance.match(/\d{2}\/\d{2}\/\d{2}/g);
            if (valueDateMatches && valueDateMatches.length > 0) {
                valueDate = valueDateMatches[0];
            }

            // Extract amounts (could be withdrawal, deposit, or both)
            // In HDFC format: there are usually 2 or 3 numbers:
            // - If 2 numbers: amount + balance (need to check if debit/credit)
            // - If 3 numbers: withdrawal + deposit (one will be empty in data) + balance
            const amounts = lineWithoutBalance.match(numberPattern) || [];

            if (amounts.length === 1) {
                // Only one amount found before balance - this IS the transaction amount
                // Need to determine if withdrawal or deposit by context
                const txAmount = amounts[0];

                // Check if it's a debit keyword
                const lowerNarration = lineWithoutBalance.toLowerCase();
                if (lowerNarration.includes('withdrawal') || lowerNarration.includes('ach d-') ||
                    lowerNarration.includes('autopay') || lowerNarration.includes('payment to')) {
                    withdrawal = txAmount;
                } else {
                    // Check balance movement to determine transaction type
                    // If we can't determine, check common patterns
                    if (lowerNarration.includes('received') || lowerNarration.includes('deposit') ||
                        lowerNarration.includes('credit')) {
                        deposit = txAmount;
                    } else {
                        // Default to withdrawal for UPI payments
                        withdrawal = txAmount;
                    }
                }
            } else if (amounts.length >= 2) {
                // Multiple amounts - likely withdrawal and/or deposit
                // The format typically has: [value_date_if_amount] withdrawal deposit balance
                // Or just: withdrawal balance OR deposit balance
                const txAmount = amounts[amounts.length - 1]; // Last amount before balance

                // Determine type based on keywords
                const lowerNarration = lineWithoutBalance.toLowerCase();
                if (lowerNarration.includes('received') || lowerNarration.includes('deposit') ||
                    lowerNarration.includes('credit') || lineWithoutBalance.includes('Deposit')) {
                    deposit = txAmount;
                } else {
                    withdrawal = txAmount;
                }
            }

            // Extract narration - everything before reference number
            if (refNo) {
                narration = lineWithoutBalance.split(refNo)[0].trim();
            } else {
                narration = lineWithoutBalance.trim();
            }

            // Check for international transactions
            let transactionType = 'DOMESTIC';
            if (narration.includes('INTERNATIONAL') || narration.includes('FOREIGN') ||
                narration.includes('USD') || narration.includes('EUR') || narration.includes('GBP') ||
                narration.includes('FOREX')) {
                transactionType = 'INTERNATIONAL';
            }

            // Determine transaction type based on amounts
            let type = 'UNKNOWN';
            let amount = '';
            if (withdrawal && !deposit) {
                type = 'DEBIT';
                amount = withdrawal;
            } else if (deposit && !withdrawal) {
                type = 'CREDIT';
                amount = deposit;
            } else if (withdrawal) {
                type = 'DEBIT';
                amount = withdrawal;
            }

            // Check if next line(s) are continuation of narration (no date at start)
            let fullNarration = narration;
            let j = i + 1;
            while (j < lines.length && lines[j].trim() && !lines[j].trim().match(/^\d{2}\/\d{2}\/\d{2}/)) {
                const nextLine = lines[j].trim();
                // Skip headers, page markers, and summary sections
                if (!nextLine.includes('Page No') && !nextLine.includes('--') &&
                    !nextLine.match(/^\d+ of \d+/) && !nextLine.includes('STATEMENT SUMMARY') &&
                    !nextLine.includes('Generated On') && !nextLine.includes('Generated By')) {
                    fullNarration += ' ' + nextLine;
                }
                j++;
            }

            // Skip summary lines
            if (fullNarration.includes('STATEMENT SUMMARY') || fullNarration.includes('Opening Balance') ||
                fullNarration.includes('Generated On')) {
                continue;
            }

            // Fix transaction type for interest
            if (fullNarration.toLowerCase().includes('interest paid') ||
                fullNarration.toLowerCase().includes('interest credit')) {
                type = 'CREDIT';
                if (withdrawal) {
                    deposit = withdrawal;
                    withdrawal = '';
                    amount = deposit;
                }
            }

            if (fullNarration.trim() && balance) {
                transactions.push({
                    date: date,
                    narration: fullNarration.trim(),
                    description: fullNarration.trim(),
                    refNo: refNo,
                    valueDate: valueDate,
                    withdrawal: withdrawal,
                    deposit: deposit,
                    type: type,
                    amount: amount,
                    balance: balance,
                    transactionType: transactionType
                });
            }
        }
    }

    return transactions;
}

function detectPDFFormat(text) {
    // Check for PhonePe format
    if (text.includes('Transaction Statement') && text.includes('PhonePe')) {
        return 'phonepe';
    }

    // Check for HDFC Account Statement format
    if (text.includes('HDFC BANK') && text.includes('Statement of account') &&
        text.match(/\d{2}\/\d{2}\/\d{2}/)) {
        return 'hdfc_account_statement';
    }

    // Check for HDFC Credit Card statement format
    if (text.includes('HDFC') && (text.includes('CREDIT CARD') || text.includes('Statement'))) {
        return 'hdfc_credit_statement';
    }

    // Check for generic bank statement format
    if (text.includes('STATEMENT') || text.includes('Account Statement') ||
        text.includes('TRANSACTION HISTORY')) {
        return 'bank_statement';
    }

    return 'unknown';
}

async function uploadToGoogleSheets(transactions, format = 'phonepe') {
    try {
        // Read and parse the service account key file
        const keyFileContent = fs.readFileSync(process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE, 'utf8');
        const credentials = JSON.parse(keyFileContent);

        console.log(`\n📧 Service Account Email: ${credentials.client_email}`);
        console.log(`📄 Attempting to access Sheet ID: ${process.env.GOOGLE_SHEET_ID}`);
        console.log('\n⚠️  Make sure this service account has Editor access to the sheet!\n');

        // Authenticate with Google Sheets using GoogleAuth
        const auth = new google.auth.GoogleAuth({
            credentials: credentials,
            scopes: ['https://www.googleapis.com/auth/spreadsheets']
        });

        const client = await auth.getClient();
        const sheets = google.sheets({ version: 'v4', auth: client });
        const spreadsheetId = process.env.GOOGLE_SHEET_ID;

        // Prepare data based on format
        let headers, rows, sheetName;

        if (format === 'phonepe') {
            sheetName = 'PhonePe';
            headers = ['Date', 'Time', 'Type', 'Amount', 'To/From', 'Paid By', 'Transaction ID', 'UTR No'];
            rows = transactions.map(t => [
                t.date,
                t.time,
                t.type,
                t.amount,
                t.to,
                t.paidBy,
                t.transactionId,
                t.utrNo
            ]);
        } else if (format === 'hdfc_account_statement') {
            sheetName = 'HDFC Account';
            headers = ['Date', 'Narration', 'Ref No', 'Value Date', 'Withdrawal', 'Deposit', 'Type', 'Balance', 'Transaction Type'];
            rows = transactions.map(t => [
                t.date,
                t.narration || t.description,
                t.refNo,
                t.valueDate,
                t.withdrawal,
                t.deposit,
                t.type,
                t.balance,
                t.transactionType || 'DOMESTIC'
            ]);
        } else {
            sheetName = 'Bank Statements';
            headers = ['Date', 'Description', 'Type', 'Amount', 'Balance', 'Transaction Type'];
            rows = transactions.map(t => [
                t.date,
                t.description,
                t.type,
                t.amount,
                t.balance,
                t.transactionType || 'DOMESTIC'
            ]);
        }

        // Check if sheet exists, if not create it
        try {
            const sheetInfo = await sheets.spreadsheets.get({
                spreadsheetId,
                includeGridData: false
            });
            
            const sheetExists = sheetInfo.data.sheets.some(sheet => 
                sheet.properties.title === sheetName
            );
            
            if (!sheetExists) {
                // Create new sheet
                await sheets.spreadsheets.batchUpdate({
                    spreadsheetId,
                    resource: {
                        requests: [{
                            addSheet: {
                                properties: {
                                    title: sheetName
                                }
                            }
                        }]
                    }
                });
                console.log(`✅ Created new sheet: ${sheetName}`);
            }
        } catch (error) {
            console.warn(`Warning: Could not check/create sheet: ${error.message}`);
            // Fallback to default sheet name
            sheetName = 'Sheet1';
        }

        // Get existing data to find the next empty row
        let nextRow = 1;
        try {
            const existingData = await sheets.spreadsheets.values.get({
                spreadsheetId,
                range: `${sheetName}!A:A`,
            });
            
            if (existingData.data.values && existingData.data.values.length > 0) {
                nextRow = existingData.data.values.length + 1;
                
                // Check if headers exist and match
                const firstRow = await sheets.spreadsheets.values.get({
                    spreadsheetId,
                    range: `${sheetName}!1:1`,
                });
                
                const existingHeaders = firstRow.data.values ? firstRow.data.values[0] : [];
                const headersMatch = existingHeaders.length === headers.length && 
                    existingHeaders.every((header, index) => header === headers[index]);
                
                if (!headersMatch && existingHeaders.length > 0) {
                    // Headers don't match, add a separator row and new headers
                    const separatorRow = ['', '--- ' + format.toUpperCase() + ' FORMAT ---', '', '', '', '', '', ''];
                    await sheets.spreadsheets.values.append({
                        spreadsheetId,
                        range: `${sheetName}!A${nextRow}`,
                        valueInputOption: 'RAW',
                        resource: {
                            values: [separatorRow, headers, ...rows],
                        },
                    });
                } else {
                    // Headers match or no existing headers, just append data
                    await sheets.spreadsheets.values.append({
                        spreadsheetId,
                        range: `${sheetName}!A${nextRow}`,
                        valueInputOption: 'RAW',
                        resource: {
                            values: rows,
                        },
                    });
                }
            } else {
                // Sheet is empty, add headers and data
                await sheets.spreadsheets.values.update({
                    spreadsheetId,
                    range: `${sheetName}!A1`,
                    valueInputOption: 'RAW',
                    resource: {
                        values: [headers, ...rows],
                    },
                });
            }
        } catch (error) {
            console.warn(`Warning: Could not check existing data: ${error.message}`);
            // Fallback: append data anyway
            await sheets.spreadsheets.values.append({
                spreadsheetId,
                range: `${sheetName}!A1`,
                valueInputOption: 'RAW',
                resource: {
                    values: [headers, ...rows],
                },
            });
        }

        console.log(`\n✅ Successfully appended ${transactions.length} transactions to ${sheetName} sheet`);
        console.log(`📊 View at: https://docs.google.com/spreadsheets/d/${spreadsheetId}`);
    } catch (error) {
        console.error('\n❌ Error uploading to Google Sheets:', error.message);

        if (error.message.includes('not found')) {
            console.error('\n💡 Troubleshooting steps:');
            console.error('1. Verify GOOGLE_SHEET_ID in .env is correct');
            console.error('2. Share the Google Sheet with the service account email shown above');
            console.error('3. Give the service account "Editor" permission');
            console.error('4. Make sure the Sheet ID is from the URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit\n');
        }

        throw error;
    }
}

async function readPDF(filePath, password = null) {
    try {
        const dataBuffer = fs.readFileSync(filePath);

        // Try to read PDF with password if provided
        const options = {data: dataBuffer};
        if (password) {
            options.password = password;
        }

        let data;
        try {
            data = await new pdf(options).getText();
        } catch (error) {
            if (error.message.includes('password') || error.message.includes('PasswordException')) {
                console.error('\n❌ PDF is password protected. Please provide password as argument:');
                console.error('   node pdfreader/index.js <pdf-file> <password>\n');
                process.exit(1);
            }
            throw error;
        }

        // Detect PDF format
        const format = detectPDFFormat(data.text);
        console.log(`\n📄 Detected format: ${format.toUpperCase()}`);

        let transactions = [];

        // Use appropriate parser based on format
        if (format === 'phonepe') {
            transactions = parsePhonePeTransactions(data.text);
        } else if (format === 'hdfc_account_statement') {
            transactions = parseHDFCAccountStatementTransactions(data.text);
        } else if (format === 'hdfc_credit_statement') {
            transactions = parseHDFCCreditStatementTransactions(data.text);
        } else if (format === 'bank_statement') {
            transactions = parseHDFCCreditStatementTransactions(data.text);
        } else {
            console.log('\n⚠️  Unknown format. Attempting to parse as generic bank statement...');
            transactions = parseHDFCAccountStatementTransactions(data.text);
        }

        // Separate domestic and international transactions if applicable
        const domesticTransactions = transactions.filter(t => !t.transactionType || t.transactionType === 'DOMESTIC');
        const internationalTransactions = transactions.filter(t => t.transactionType === 'INTERNATIONAL');

        const output = {
            summary: {
                totalTransactions: transactions.length,
                domesticTransactions: domesticTransactions.length,
                internationalTransactions: internationalTransactions.length,
                format: format
            },
            transactions: {
                all: transactions,
                domestic: domesticTransactions,
                international: internationalTransactions
            }
        };

        console.log(JSON.stringify(output, null, 2));

        // Upload to Google Sheets if credentials are configured
        if (process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE && process.env.GOOGLE_SHEET_ID) {
            // Validate that key file exists
            if (!fs.existsSync(process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE)) {
                console.error(`\n❌ Service account key file not found: ${process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE}`);
                console.log('Please check the path in your .env file.\n');
            } else {
                // Upload all transactions
                await uploadToGoogleSheets(transactions, format);
            }
        } else {
            console.log('\n⚠️  Google Sheets upload skipped. Set GOOGLE_SERVICE_ACCOUNT_KEY_FILE and GOOGLE_SHEET_ID in .env to enable.');
            console.log('\nExample .env configuration:');
            console.log('GOOGLE_SERVICE_ACCOUNT_KEY_FILE=/path/to/service-account-key.json');
            console.log('GOOGLE_SHEET_ID=your_sheet_id_here\n');
        }

        return output;
    } catch (error) {
        console.error('Error reading PDF:', error.message);
        process.exit(1);
    }
}

// Get file path and optional password from command line arguments
const filePath = process.argv[2];
const password = process.argv[3]; // Optional password for protected PDFs

if (!filePath) {
    console.error('Usage: node index.js <path-to-pdf-file> [password]');
    console.error('\nExamples:');
    console.error('  node pdfreader/index.js statement.pdf');
    console.error('  node pdfreader/index.js protected.pdf mypassword');
    process.exit(1);
}

if (!fs.existsSync(filePath)) {
    console.error(`File not found: ${filePath}`);
    process.exit(1);
}

readPDF(filePath, password);
