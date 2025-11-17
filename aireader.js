const { fromPath } = require('pdf2pic');
const tesseract = require('tesseract.js');
const fs = require('fs');
const path = require('path');

// Configuration
const DEFAULT_QUESTION = 'List all transactions with date, amount, description, and type (debit/credit)';
const IMAGE_OUTPUT_DIR = path.join(__dirname, 'temp_images');

// Create temp directory for images if it doesn't exist
if (!fs.existsSync(IMAGE_OUTPUT_DIR)) {
    fs.mkdirSync(IMAGE_OUTPUT_DIR, { recursive: true });
}

/**
 * Convert PDF to images
 * @param {string} pdfPath - Path to PDF file
 * @param {number} density - Image density/quality (default: 200)
 * @returns {Promise<string[]>} Array of image paths
 */
async function convertPDFToImages(pdfPath, density = 200) {
    console.log(`📄 Converting PDF to images: ${pdfPath}`);
    
    const converter = fromPath(pdfPath, {
        density: density,
        saveFilename: 'page',
        savePath: IMAGE_OUTPUT_DIR,
        format: 'png'
    });

    const imagePaths = [];
    let pageNum = 1;
    let hasMorePages = true;

    while (hasMorePages) {
        try {
            const result = await converter(pageNum);
            if (result && result.path) {
                imagePaths.push(result.path);
                console.log(`  ✓ Page ${pageNum} converted: ${result.path}`);
                pageNum++;
            } else {
                hasMorePages = false;
            }
        } catch (error) {
            if (error.message.includes('Invalid page number')) {
                hasMorePages = false;
            } else {
                console.error(`Error converting page ${pageNum}:`, error.message);
                hasMorePages = false;
            }
        }
    }

    console.log(`✅ Converted ${imagePaths.length} pages to images\n`);
    return imagePaths;
}

/**
 * Initialize OCR worker
 * @returns {Promise<Object>} Tesseract worker
 */
async function initializeOCR() {
    console.log('🤖 Initializing OCR engine...\n');
    try {
        const worker = await tesseract.createWorker('eng');
        console.log('✅ OCR engine loaded successfully\n');
        return worker;
    } catch (error) {
        console.error('\n❌ Failed to initialize OCR:', error.message);
        throw error;
    }
}

/**
 * Extract transactions from an image using AI
 * @param {string} imagePath - Path to image file
 * @param {string} question - Question context (for future use with QA models)
 * @returns {Promise<Object>} AI analysis result with extracted text
 */
async function extractFromImage(imagePath, worker) {
    console.log(`🔍 Extracting text from: ${path.basename(imagePath)}`);
    
    try {
        const { data: { text } } = await worker.recognize(imagePath);
        console.log(`  ✓ OCR extraction complete\n`);
        
        return {
            text: text,
            extracted: true
        };
    } catch (error) {
        console.error(`  ❌ Error extracting from image:`, error.message);
        throw error;
    }
}

/**
 * Parse AI response to extract structured transactions
 * @param {string} answer - AI model answer text
 * @returns {Array} Array of transaction objects
 */
function parseTransactions(text) {
    const transactions = [];
    
    if (!text || !text.trim()) {
        return transactions;
    }

    // Split text into lines
    const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    
    // PhonePe transaction patterns
    const phonePeDatePattern = /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}$/i;
    
    // Bank statement patterns
    const bankDatePattern = /^(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})/;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        
        // Check for PhonePe date pattern
        if (phonePeDatePattern.test(line)) {
            const date = line;
            let time = '';
            let type = '';
            let amount = '';
            let description = '';
            
            if (i + 1 < lines.length) time = lines[i + 1];
            if (i + 2 < lines.length) {
                const typeAmountLine = lines[i + 2];
                if (/DEBIT/i.test(typeAmountLine)) type = 'DEBIT';
                else if (/CREDIT/i.test(typeAmountLine)) type = 'CREDIT';
                
                const amountMatch = typeAmountLine.match(/[₹]\s*([\d,]+\.?\d*)/);
                if (amountMatch) amount = amountMatch[1];
                
                description = typeAmountLine;
            }
            
            transactions.push({
                date: date,
                time: time || 'N/A',
                type: type || 'UNKNOWN',
                amount: amount ? `₹${amount}` : 'N/A',
                description: description
            });
            
            i += 2;
        }
        // Check for bank statement date pattern
        else if (bankDatePattern.test(line)) {
            const dateMatch = line.match(bankDatePattern);
            if (dateMatch) {
                const amountPattern = /[₹]\s*([\d,]+\.\d{2})/g;
                const amounts = [...line.matchAll(amountPattern)];
                
                let type = 'UNKNOWN';
                let amount = 'N/A';
                
                if (line.toLowerCase().includes('debit') || line.toLowerCase().includes('withdrawal')) {
                    type = 'DEBIT';
                } else if (line.toLowerCase().includes('credit') || line.toLowerCase().includes('deposit')) {
                    type = 'CREDIT';
                }
                
                if (amounts.length > 0) {
                    amount = `₹${amounts[0][1]}`;
                }
                
                let description = line.replace(bankDatePattern, '').trim();
                description = description.replace(/[₹]\s*[\d,]+\.\d{2}/g, '').trim();
                
                transactions.push({
                    date: dateMatch[1],
                    type: type,
                    amount: amount,
                    description: description || line
                });
            }
        }
    }
    
    return transactions;
}

/**
 * Main function to extract transactions from PDF or image
 * @param {string} filePath - Path to PDF or image file
 * @param {string} question - Custom question for the AI model (optional)
 * @returns {Promise<Object>} Extracted transactions and metadata
 */
async function extractTransactions(filePath, question = DEFAULT_QUESTION) {
    try {
        // Check if file exists
        if (!fs.existsSync(filePath)) {
            throw new Error(`File not found: ${filePath}`);
        }

        const fileExt = path.extname(filePath).toLowerCase();
        const results = {
            sourceFile: filePath,
            timestamp: new Date().toISOString(),
            transactions: [],
            metadata: {
                totalTransactions: 0,
                extractionMethod: 'OCR',
                question: question
            }
        };

        let imagePaths = [];

        // Initialize OCR worker once for all processing
        const worker = await initializeOCR();

        // Determine if input is PDF or image
        if (fileExt === '.pdf') {
            // Convert PDF to images
            imagePaths = await convertPDFToImages(filePath);
            
            if (imagePaths.length === 0) {
                throw new Error('No pages found in PDF or conversion failed');
            }

            // Process each page
            for (let i = 0; i < imagePaths.length; i++) {
                console.log(`\n📄 Processing page ${i + 1} of ${imagePaths.length}`);
                
                const result = await extractFromImage(imagePaths[i], worker);
                
                // Parse the OCR text to extract transactions
                const extractedText = result?.text || '';
                const parsed = parseTransactions(extractedText);
                results.transactions.push({
                    page: i + 1,
                    transactions: parsed,
                    rawText: extractedText
                });
            }

            // Cleanup temporary images
            console.log('\n🗑️  Cleaning up temporary images...');
            for (const imgPath of imagePaths) {
                if (fs.existsSync(imgPath)) {
                    fs.unlinkSync(imgPath);
                }
            }
            console.log('✅ Cleanup complete\n');

        } else if (['.png', '.jpg', '.jpeg', '.gif', '.bmp'].includes(fileExt)) {
            // Process image directly
            console.log(`\n🖼️  Processing image file: ${path.basename(filePath)}\n`);
            
            const result = await extractFromImage(filePath, worker);
            
            const extractedText = result?.text || '';
            const parsed = parseTransactions(extractedText);
            results.transactions = [{
                page: 1,
                transactions: parsed,
                rawText: extractedText
            }];
        } else {
            throw new Error(`Unsupported file format: ${fileExt}`);
        }

        // Terminate worker
        await worker.terminate();

        // Count total transactions
        results.metadata.totalTransactions = results.transactions.reduce((sum, page) => {
            return sum + (page.transactions || []).length;
        }, 0);

        return results;
    } catch (error) {
        console.error('\n❌ Error:', error.message);
        throw error;
    }
}

// Command line interface
if (require.main === module) {
    const filePath = process.argv[2];
    const question = process.argv[3] || DEFAULT_QUESTION;

    if (!filePath) {
        console.log('Usage: node aireader.js <pdf-or-image-path> [question]');
        console.log('\nExamples:');
        console.log('  node aireader.js statement.pdf');
        console.log('  node aireader.js bank_statement.png');
        console.log('  node aireader.js statement.pdf "List all debit transactions with dates and amounts"');
        console.log('\nDefault question:', DEFAULT_QUESTION);
        process.exit(1);
    }

    extractTransactions(filePath, question)
        .then(results => {
            console.log('\n' + '='.repeat(80));
            console.log('📊 EXTRACTION RESULTS');
            console.log('='.repeat(80) + '\n');
            
            console.log(JSON.stringify(results, null, 2));
            
            // Summary
            console.log('\n' + '='.repeat(80));
            console.log('📈 SUMMARY');
            console.log('='.repeat(80));
            console.log(`Total transactions found: ${results.metadata.totalTransactions}`);
            console.log(`Source file: ${results.sourceFile}`);
            console.log(`Extraction method: ${results.metadata.extractionMethod}`);
            console.log('='.repeat(80) + '\n');
        })
        .catch(error => {
            console.error('\n❌ Extraction failed:', error.message);
            process.exit(1);
        });
}

module.exports = {
    extractTransactions,
    convertPDFToImages,
    extractFromImage,
    parseTransactions
};

