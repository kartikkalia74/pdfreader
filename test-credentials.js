const fs = require('fs');
const {google} = require('googleapis');
require('dotenv').config();

async function testCredentials() {
    console.log('\n🔍 Testing Google Sheets Credentials...\n');

    // Step 1: Check environment variables
    console.log('Step 1: Checking environment variables...');
    const keyFile = process.env.GOOGLE_SERVICE_ACCOUNT_KEY_FILE;
    const sheetId = process.env.GOOGLE_SHEET_ID;

    if (!keyFile) {
        console.error('❌ GOOGLE_SERVICE_ACCOUNT_KEY_FILE is not set in .env');
        process.exit(1);
    }
    console.log('✅ GOOGLE_SERVICE_ACCOUNT_KEY_FILE is set:', keyFile);

    if (!sheetId) {
        console.error('❌ GOOGLE_SHEET_ID is not set in .env');
        process.exit(1);
    }
    console.log('✅ GOOGLE_SHEET_ID is set:', sheetId);

    // Step 2: Check if key file exists
    console.log('\nStep 2: Checking if key file exists...');
    if (!fs.existsSync(keyFile)) {
        console.error('❌ Key file not found at:', keyFile);
        process.exit(1);
    }
    console.log('✅ Key file exists');

    // Step 3: Parse credentials
    console.log('\nStep 3: Parsing service account credentials...');
    let credentials;
    try {
        const keyFileContent = fs.readFileSync(keyFile, 'utf8');
        credentials = JSON.parse(keyFileContent);
        console.log('✅ Key file is valid JSON');
    } catch (error) {
        console.error('❌ Error parsing key file:', error.message);
        process.exit(1);
    }

    // Step 4: Verify required fields
    console.log('\nStep 4: Verifying credential fields...');
    const requiredFields = ['client_email', 'private_key', 'project_id'];
    for (const field of requiredFields) {
        if (!credentials[field]) {
            console.error(`❌ Missing required field: ${field}`);
            process.exit(1);
        }
        if (field === 'client_email') {
            console.log(`✅ ${field}:`, credentials[field]);
        } else if (field === 'project_id') {
            console.log(`✅ ${field}:`, credentials[field]);
        } else if (field === 'private_key') {
            const keyPreview = credentials[field].substring(0, 50) + '...';
            console.log(`✅ ${field}: ${keyPreview}`);
            console.log(`   Key length: ${credentials[field].length} characters`);
            console.log(`   Starts with: ${credentials[field].startsWith('-----BEGIN PRIVATE KEY-----') ? '✅ Valid format' : '❌ Invalid format'}`);
        }
    }

    // Step 5: Test authentication
    console.log('\nStep 5: Testing authentication...');
    try {
        // Method 1: Using GoogleAuth with credentials object
        const auth = new google.auth.GoogleAuth({
            credentials: credentials,
            scopes: ['https://www.googleapis.com/auth/spreadsheets']
        });

        const client = await auth.getClient();
        console.log('✅ Successfully authenticated with Google');
        console.log('   Auth method: GoogleAuth with credentials object');
    } catch (error) {
        console.error('❌ Authentication failed:', error.message);
        console.error('\nTrying alternative method...\n');

        try {
            // Method 2: Using JWT directly
            const jwtClient = new google.auth.JWT({
                email: credentials.client_email,
                key: credentials.private_key,
                scopes: ['https://www.googleapis.com/auth/spreadsheets']
            });

            await jwtClient.authorize();
            console.log('✅ Successfully authenticated with Google (using JWT)');
        } catch (error2) {
            console.error('❌ JWT authentication also failed:', error2.message);
            process.exit(1);
        }
    }

    // Step 6: Test Google Sheets API access
    console.log('\nStep 6: Testing Google Sheets API access...');
    try {
        const auth = new google.auth.GoogleAuth({
            credentials: credentials,
            scopes: ['https://www.googleapis.com/auth/spreadsheets']
        });

        const client = await auth.getClient();
        const sheets = google.sheets({ version: 'v4', auth: client });

        // Try to get spreadsheet metadata
        const response = await sheets.spreadsheets.get({
            spreadsheetId: sheetId,
        });

        console.log('✅ Successfully accessed Google Sheet');
        console.log('   Sheet Title:', response.data.properties.title);
        console.log('   Sheet URL: https://docs.google.com/spreadsheets/d/' + sheetId);

        if (response.data.sheets && response.data.sheets.length > 0) {
            console.log('   Available sheets:');
            response.data.sheets.forEach(sheet => {
                console.log(`   - ${sheet.properties.title}`);
            });
        }
    } catch (error) {
        console.error('❌ Failed to access Google Sheet:', error.message);

        if (error.message.includes('not found')) {
            console.error('\n💡 Possible causes:');
            console.error('   1. Sheet ID is incorrect');
            console.error('   2. Sheet has not been shared with the service account');
            console.error(`   3. Share the sheet with: ${credentials.client_email}`);
        } else if (error.message.includes('permission')) {
            console.error('\n💡 The service account needs Editor access to the sheet');
            console.error(`   Share the sheet with: ${credentials.client_email}`);
        }
        process.exit(1);
    }

    // Step 7: Test write permissions
    console.log('\nStep 7: Testing write permissions...');
    try {
        const auth = new google.auth.GoogleAuth({
            credentials: credentials,
            scopes: ['https://www.googleapis.com/auth/spreadsheets']
        });

        const client = await auth.getClient();
        const sheets = google.sheets({ version: 'v4', auth: client });

        // Try to read from Sheet1 (or create a test)
        await sheets.spreadsheets.values.get({
            spreadsheetId: sheetId,
            range: 'Sheet1!A1',
        });

        console.log('✅ Read permission confirmed');
        console.log('✅ Service account has access to write data');
    } catch (error) {
        if (error.message.includes('not found')) {
            console.log('⚠️  Sheet1 not found, but that\'s okay for a new sheet');
        } else if (error.message.includes('permission')) {
            console.error('❌ Service account lacks write permission');
            console.error(`   Make sure ${credentials.client_email} has Editor access`);
            process.exit(1);
        } else {
            console.error('⚠️  Warning:', error.message);
        }
    }

    console.log('\n✅ All tests passed! Your credentials are configured correctly.\n');
    console.log('You can now run the PDF reader script:');
    console.log('node pdfreader/index.js pdfreader/your-file.pdf\n');
}

testCredentials().catch(error => {
    console.error('\n❌ Unexpected error:', error);
    process.exit(1);
});
