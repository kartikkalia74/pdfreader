"""
Flask backend server for bank statement PDF processing
"""
import os
from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from pathlib import Path
from api import (
    scan_readerfiles_folder,
    process_pdf,
    combine_all_transactions,
    READERFILES_DIR,
    get_category_configuration,
    set_category_override,
    add_custom_category
)

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = READERFILES_DIR
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Serve main HTML page"""
    return render_template('index.html')


@app.route('/api/scan', methods=['GET'])
def scan_files():
    """Scan and list all PDFs in readerfiles folder"""
    try:
        files = scan_readerfiles_folder()
        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/process-all', methods=['GET'])
def process_all():
    """Process all PDFs in readerfiles folder (use cache if available)"""
    try:
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        result = combine_all_transactions(force_refresh=force_refresh)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/process-file/<filename>', methods=['GET'])
def process_file(filename):
    """Process a single PDF file"""
    try:
        file_path = READERFILES_DIR / secure_filename(filename)
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        result = process_pdf(str(file_path), use_cache=not force_refresh)
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload and process a new PDF file"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only PDF files are allowed.'
            }), 400
        
        # Save file
        filename = secure_filename(file.filename)
        file_path = READERFILES_DIR / filename
        file.save(file_path)
        
        # Process file
        result = process_pdf(str(file_path), use_cache=False)
        
        return jsonify({
            'success': True,
            'data': result,
            'filename': filename
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions (from cache or process)"""
    try:
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        result = combine_all_transactions(force_refresh=force_refresh)
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/transactions/<filename>', methods=['GET'])
def get_file_transactions(filename):
    """Get transactions for a specific file"""
    try:
        file_path = READERFILES_DIR / secure_filename(filename)
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        force_refresh = request.args.get('force', 'false').lower() == 'true'
        result = process_pdf(str(file_path), use_cache=not force_refresh)
        
        # Extract transactions
        transactions_list = []
        if isinstance(result.get('transactions'), list):
            for page_data in result['transactions']:
                if isinstance(page_data, dict) and 'transactions' in page_data:
                    transactions_list.extend(page_data['transactions'])
        
        return jsonify({
            'success': True,
            'data': {
                'transactions': transactions_list,
                'metadata': result.get('metadata', {}),
                'sourceFile': filename
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories', methods=['GET', 'POST'])
def categories_route():
    """Return available categories or create new ones."""
    if request.method == 'GET':
        try:
            data = get_category_configuration()
            return jsonify({
                'success': True,
                'data': data
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # POST - create new category
    try:
        payload = request.get_json(force=True) or {}
        label = payload.get('label', '')
        new_category = add_custom_category(label)
        data = get_category_configuration()
        return jsonify({
            'success': True,
            'data': data,
            'newCategory': new_category
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/categories/assign', methods=['POST'])
def assign_category():
    """Manually assign a category to a duplicate transaction group."""
    try:
        payload = request.get_json(force=True) or {}
        group_key = payload.get('groupKey')
        category = payload.get('category')

        set_category_override(group_key, category)

        return jsonify({
            'success': True,
            'groupKey': group_key,
            'category': category
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_all():
    """Force refresh - reprocess all PDFs ignoring cache"""
    try:
        result = combine_all_transactions(force_refresh=True)
        return jsonify({
            'success': True,
            'data': result,
            'message': 'All files reprocessed successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Ensure directories exist
    READERFILES_DIR.mkdir(exist_ok=True)
    
    print("Starting Flask server...")
    print(f"Reader files directory: {READERFILES_DIR}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print("\nAccess the web interface at: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5001)

