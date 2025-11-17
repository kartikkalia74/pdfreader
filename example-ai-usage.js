/**
 * Example usage of AI-powered transaction extraction
 * 
 * This script demonstrates how to use the aireader.js module
 * to extract transactions from PDF files and images.
 */

const { extractTransactions } = require('./aireader');

async function exampleUsage() {
    try {
        console.log('🚀 AI-Powered Transaction Extraction Examples\n');
        console.log('=' .repeat(80) + '\n');

        // Example 1: Extract from PDF with default question
        console.log('Example 1: Extract from PDF (Default Question)\n');
        const results1 = await extractTransactions(
            'readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf'
        );
        console.log(`✅ Found ${results1.metadata.totalTransactions} transactions\n`);

        // Example 2: Extract from PDF with custom question
        console.log('Example 2: Extract from PDF (Custom Question)\n');
        const results2 = await extractTransactions(
            'readerfiles/PhonePe_Statement_Jul2025_Oct2025.pdf',
            'List all credit transactions with their amounts and dates'
        );
        console.log(`✅ Found ${results2.metadata.totalTransactions} transactions\n`);

        // Example 3: Process multiple files
        console.log('Example 3: Process Multiple Files\n');
        const files = [
            'readerfiles/4341XXXXXXXXXX70_22-09-2025_836.pdf',
            'readerfiles/Acct Statement_XX4230_13102025.pdf'
        ];

        for (const file of files) {
            try {
                const results = await extractTransactions(file);
                console.log(`📄 ${file}: ${results.metadata.totalTransactions} transactions`);
            } catch (error) {
                console.error(`❌ Error processing ${file}: ${error.message}`);
            }
        }

        console.log('\n' + '='.repeat(80));
        console.log('✅ Examples completed successfully!');
        console.log('='.repeat(80) + '\n');

    } catch (error) {
        console.error('\n❌ Error:', error.message);
        console.error('\nMake sure you have:');
        console.error('1. Installed dependencies: npm install @xenova/transformers pdf2pic');
        console.error('2. PDF files in the readerfiles directory');
        console.error('3. Sufficient disk space (model download ~500MB)');
    }
}

// Run examples if this file is executed directly
if (require.main === module) {
    exampleUsage();
}

module.exports = { exampleUsage };

