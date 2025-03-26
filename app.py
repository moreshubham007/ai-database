from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, Response
from flask import Response
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId
import os
import csv
import io
from datetime import datetime
from llm import LLMConnector, LLMConfig
from llm.config import ProviderConfig
from llm.utils import check_library_versions
import requests
import threading
import json
import re

app = Flask(__name__)
app.config["MONGO_URI"] = 'mongodb+srv://wQO7zLNOVMMbbJOU:B9BYNLyVR4YgkOv3@vellichormedia.woofq.mongodb.net/company_database?retryWrites=true&w=majority&appName=vellichormedia'
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'csv'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize MongoDB
mongo = PyMongo(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']
        self.email = user_data['email']
        self.role = user_data['role']

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = mongo.db.users.find_one({'username': username})
        
        if user and check_password_hash(user['password'], password):
            user_obj = User(user)
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check if username already exists
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Check if email already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already exists')
            return redirect(url_for('register'))
        
        # Create new user with regular role (not admin)
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': 'user',
            'created_at': datetime.now()
        })
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Dashboard and company management routes
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    """Display the company dashboard."""
    try:
        # Get query parameters
        search_query = request.args.get('search', '')
        search_field = request.args.get('field', 'all')
        
        # Get pagination parameters
        per_page_param = request.args.get('per_page', '10')
        
        # Handle "all" case for per_page
        if per_page_param == 'all':
            per_page = None  # No limit
        else:
            per_page = int(per_page_param)
            
        # Create the query
        query = {}
        if search_query:
            if search_field == 'all':
                # Search in all fields
                query = {
                    '$or': [
                        {'name': {'$regex': search_query, '$options': 'i'}},
                        {'website': {'$regex': search_query, '$options': 'i'}},
                        {'products': {'$regex': search_query, '$options': 'i'}},
                        {'services': {'$regex': search_query, '$options': 'i'}},
                        {'location': {'$regex': search_query, '$options': 'i'}},
                        {'keyword': {'$regex': search_query, '$options': 'i'}}
                    ]
                }
            else:
                # Search in specific field
                query = {search_field: {'$regex': search_query, '$options': 'i'}}
        
        # Get total count for pagination
        total_companies = mongo.db.companies.count_documents(query)
        
        # Get companies for current page
        companies_query = mongo.db.companies.find(query)
        
        # If per_page is None (show all), don't apply pagination limits
        if per_page is None:
            companies = list(companies_query)
            total_companies = len(companies)
            current_page = 1
            total_pages = 1
        else:
            # Apply pagination with limits
            current_page = request.args.get('page', 1, type=int)
            total_pages = (total_companies + per_page - 1) // per_page  # Ceiling division
            companies = list(companies_query.skip((current_page - 1) * per_page).limit(per_page))
        
        # Add AI prompts for the update modal
        ai_prompts = list(mongo.db.ai_prompts.find())
        
        # Get available LLM providers
        llm_connector = LLMConnector()
        llm_providers = llm_connector.get_available_providers()
        
        return render_template(
            'dashboard.html',
            companies=companies,
            total_companies=total_companies,
            current_page=current_page,
            total_pages=total_pages,
            search_query=search_query,
            search_field=search_field,
            per_page=per_page,
            ai_prompts=ai_prompts,
            llm_providers=llm_providers
        )
    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/company/add', methods=['GET', 'POST'])
@login_required
def add_company():
    """Add a new company."""
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        website = request.form.get('website')
        linkedin_url = request.form.get('linkedin_url')
        products = request.form.get('products')
        services = request.form.get('services')
        location = request.form.get('location')
        description = request.form.get('description')
        industry = request.form.get('industry')
        keyword = request.form.get('keyword')
        
        # Create company document
        company = {
            'name': name,
            'website': website,
            'linkedin_url': linkedin_url,
            'products': products,
            'services': services,
            'location': location,
            'description': description,
            'industry': industry,
            'keyword': keyword,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'created_by': current_user.get_id()
        }
        
        # Insert into database
        result = mongo.db.companies.insert_one(company)
        
        if result.inserted_id:
            flash('Company added successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Error adding company.', 'error')
    
    return render_template('add_company.html')

@app.route('/company/edit/<company_id>', methods=['GET', 'POST'])
@login_required
def edit_company(company_id):
    """Edit an existing company."""
    company = mongo.db.companies.find_one({'_id': ObjectId(company_id)})
    
    if not company:
        flash('Company not found.', 'error')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name')
        website = request.form.get('website')
        linkedin_url = request.form.get('linkedin_url')
        products = request.form.get('products')
        services = request.form.get('services')
        location = request.form.get('location')
        description = request.form.get('description')
        industry = request.form.get('industry')
        keyword = request.form.get('keyword')
        
        # Update company document
        result = mongo.db.companies.update_one(
            {'_id': ObjectId(company_id)},
            {'$set': {
                'name': name,
                'website': website,
                'linkedin_url': linkedin_url,
                'products': products,
                'services': services,
                'location': location,
                'description': description,
                'industry': industry,
                'keyword': keyword,
                'updated_at': datetime.now()
            }}
        )
        
        if result.modified_count > 0:
            flash('Company updated successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('No changes made to company.', 'info')
    
    return render_template('edit_company.html', company=company)

@app.route('/company/delete/<company_id>')
@login_required
def delete_company(company_id):
    mongo.db.companies.delete_one({'_id': ObjectId(company_id)})
    flash('Company deleted successfully!')
    return redirect(url_for('dashboard'))

@app.route('/company/upload', methods=['GET', 'POST'])
@login_required
def upload_companies():
    """Upload companies from CSV file."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Read the file contents
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.reader(stream)
            
            # Skip header row
            header = next(csv_input)
            
            # Convert header to lowercase for case-insensitive matching
            header = [h.lower() for h in header]
            
            # Check if website field exists in the header
            if 'website' not in header:
                flash('Website field is required in the CSV file')
                return redirect(request.url)
            
            # Get field indices
            name_idx = header.index('name') if 'name' in header else None
            website_idx = header.index('website')
            products_idx = header.index('products') if 'products' in header else None
            services_idx = header.index('services') if 'services' in header else None
            location_idx = header.index('location') if 'location' in header else None
            keyword_idx = header.index('keyword') if 'keyword' in header else None
            
            companies_added = 0
            companies_skipped = 0
            
            for row in csv_input:
                # Skip empty rows
                if not row:
                    continue
                
                # Ensure the row has enough columns
                if len(row) < len(header):
                    companies_skipped += 1
                    continue
                
                # Check if website field is empty
                website = row[website_idx].strip() if website_idx < len(row) else ''
                if not website:
                    companies_skipped += 1
                    continue
                
                # Get other fields
                name = row[name_idx].strip() if name_idx is not None and name_idx < len(row) else ''
                products = row[products_idx].strip() if products_idx is not None and products_idx < len(row) else ''
                services = row[services_idx].strip() if services_idx is not None and services_idx < len(row) else ''
                location = row[location_idx].strip() if location_idx is not None and location_idx < len(row) else ''
                keyword = row[keyword_idx].strip() if keyword_idx is not None and keyword_idx < len(row) else ''
                
                # Create company object
                company = {
                    'name': name,
                    'website': website,
                    'products': products,
                    'services': services,
                    'location': location,
                    'keyword': keyword,
                    'added_by': current_user.id,
                    'created_at': datetime.now()
                }
                
                # Insert into database
                mongo.db.companies.insert_one(company)
                companies_added += 1
            
            flash(f'Successfully added {companies_added} companies. Skipped {companies_skipped} companies.')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid file type. Please upload a CSV file.')
            return redirect(request.url)
    
    return render_template('upload_companies.html')

# Admin panel routes
@app.route('/admin')
@app.route('/admin/index')
@login_required
def admin_panel():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    users = list(mongo.db.users.find())
    companies_count = mongo.db.companies.count_documents({})
    
    # Add llm_connector to the template context
    return render_template('admin/index.html', 
                          users=users, 
                          companies_count=companies_count,
                          llm_connector=llm_connector)

@app.route('/admin/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)  # Default 10, but now user-configurable
    
    # Ensure per_page is within reasonable limits
    per_page = max(5, min(100, per_page))  # Between 5 and 100
    
    # Get search parameter
    search_query = request.args.get('search', '')
    
    # Build the query
    query = {}
    if search_query:
        query = {
            '$or': [
                {'username': {'$regex': search_query, '$options': 'i'}},
                {'email': {'$regex': search_query, '$options': 'i'}},
                {'role': {'$regex': search_query, '$options': 'i'}}
            ]
        }
    
    # Get total count for pagination
    total_users = mongo.db.users.count_documents(query)
    total_pages = (total_users + per_page - 1) // per_page  # Ceiling division
    
    # Get users for current page
    users = list(mongo.db.users.find(query).skip((page - 1) * per_page).limit(per_page))
    
    return render_template(
        'admin/users.html', 
        users=users,
        search_query=search_query,
        current_page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_users=total_users
    )

@app.route('/admin/user/edit/<user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    
    if not user:
        flash('User not found')
        return redirect(url_for('admin_users'))
    
    if request.method == 'POST':
        updated_user = {
            'username': request.form.get('username'),
            'email': request.form.get('email'),
            'role': request.form.get('role')
        }
        
        # Update password if provided
        if request.form.get('password'):
            updated_user['password'] = generate_password_hash(request.form.get('password'))
        
        mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': updated_user}
        )
        
        flash('User updated successfully!')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/user/delete/<user_id>')
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    flash('User deleted successfully!')
    return redirect(url_for('admin_users'))

@app.route('/admin/create_admin', methods=['GET', 'POST'])
def create_admin():
    # Check if admin already exists
    if mongo.db.users.find_one({'role': 'admin'}):
        flash('Admin already exists')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Create admin user
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': 'admin',
            'created_at': datetime.now()
        })
        
        flash('Admin user created successfully! Please login.')
        return redirect(url_for('login'))
    
    return render_template('admin/create_admin.html')

@app.route('/admin/user/add', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'user')
        
        # Check if username already exists
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists')
            return redirect(url_for('admin_add_user'))
        
        # Check if email already exists
        if mongo.db.users.find_one({'email': email}):
            flash('Email already exists')
            return redirect(url_for('admin_add_user'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_password,
            'role': role,
            'created_at': datetime.now(),
            'created_by': current_user.id
        })
        
        flash('User created successfully!')
        return redirect(url_for('admin_users'))
    
    return render_template('admin/add_user.html')

# Check library versions
check_library_versions()

# Initialize the LLM connector with MongoDB
llm_config = LLMConfig()
llm_connector = LLMConnector(config=llm_config)

# Add a simple caching mechanism
PROVIDER_CACHE = {}
CACHE_TIMEOUT = 300  # 5 minutes in seconds

@app.route('/admin/llm', methods=['GET'])
@login_required
def admin_llm():
    """LLM configuration and management page."""
    if not current_user.role == 'admin':
        flash('You do not have permission to access this page.', 'error')
        return redirect(url_for('dashboard'))
    
    # Get available providers
    providers = llm_connector.config.get_available_providers()
    provider_configs = {}
    
    # For each provider, get its configuration
    for provider in providers:
        provider_configs[provider] = llm_connector.config.get_provider_config(provider)
        
    # Create a display name for each provider that shows both provider and model
    display_names = {}
    for provider in providers:
        config = provider_configs[provider]
        if config.model_name:
            # If it's a compound key (provider_model), use a nice display format
            if '_' in provider:
                base_provider = provider.split('_')[0]
                display_names[provider] = f"{base_provider} ({config.model_name})"
            else:
                display_names[provider] = f"{provider} ({config.model_name})"
        else:
            display_names[provider] = provider
    
    return render_template('admin/llm.html', 
                          providers=providers, 
                          provider_configs=provider_configs,
                          display_names=display_names)

@app.route('/admin/llm/add', methods=['POST'])
@login_required
def admin_llm_add():
    """Add or update an LLM provider configuration."""
    if not current_user.role == 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('dashboard'))
    
    # Extract provider details
    provider_name = request.form.get('provider_name')
    model_name = request.form.get('model_name')
    api_key = request.form.get('api_key')
    base_url = request.form.get('base_url')
    max_tokens = int(request.form.get('max_tokens', 1000))
    temperature = float(request.form.get('temperature', 0.7))
    
    # Get the original provider key for updates
    original_provider_key = request.form.get('original_provider_key')
    
    # Validation
    if not provider_name:
        flash('Provider name is required', 'error')
        return redirect(url_for('admin_llm'))
    
    # If this is for a cloud provider, require API key
    if provider_name not in ['ollama'] and not api_key and not original_provider_key:
        flash('API key is required for this provider', 'error')
        return redirect(url_for('admin_llm'))
    
    # If model name is provided, create a composed key
    provider_key = provider_name
    if model_name:
        provider_key = f"{provider_name}_{model_name.replace('/', '-').replace(':', '-')}"
    
    # If this is an update and the key has changed, delete the old one
    if original_provider_key and original_provider_key != provider_key:
        # Remove old provider
        if original_provider_key in llm_connector.config.providers:
            del llm_connector.config.providers[original_provider_key]
            if llm_connector.config.mongo_db is not None:
                llm_connector.config.mongo_db.llm_configs.delete_one({"provider_name": original_provider_key})
    
    # Get existing config or create new one
    config = None
    if original_provider_key and original_provider_key in llm_connector.config.providers:
        config = llm_connector.config.get_provider_config(original_provider_key)
    
    # Create or update the provider config
    try:
        # For updates, only change API key if provided
        if config and not api_key:
            api_key = config.api_key
            
        # Create a new ProviderConfig object
        provider_config = ProviderConfig(
            api_key=api_key,
            base_url=base_url,
            model_name=model_name,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        # Update the provider config - pass the provider_key and config object
        llm_connector.config.add_provider(provider_key, provider_config)
        
        # Clear any cached instances
        if provider_key in llm_connector.provider_instances:
            del llm_connector.provider_instances[provider_key]
        
        action = "updated" if original_provider_key else "added"
        flash(f'LLM provider {action} successfully!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('admin_llm'))

@app.route('/admin/llm/test', methods=['POST'])
@login_required
def admin_llm_test():
    """Test an LLM provider connection."""
    if not current_user.role == 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('dashboard'))
    
    # Fix parameter name mismatch
    provider_name = request.form.get('provider_name')
    
    # Add a fallback to check both parameter names
    if not provider_name:
        provider_name = request.form.get('provider')  # Check alternative parameter name
    
    if not provider_name:
        return jsonify({
            'success': False,
            'message': 'Provider name parameter is missing'
        }), 400
    
    try:
        # Get provider config
        config = llm_connector.config.get_provider_config(provider_name)
        
        # Special handling for Ollama
        if 'ollama' in provider_name:
            import requests
            from requests.exceptions import Timeout, ConnectionError, ReadTimeout
            
            base_url = config.base_url or "http://localhost:11434"
            model = config.model_name or "llama3"
            
            # First check if API is reachable
            try:
                # Check if Ollama is running
                health_check = requests.get(f"{base_url}/api/version", timeout=5)
                if health_check.status_code != 200:
                    return jsonify({
                        'success': False,
                        'message': f'Ollama server not responding: {health_check.status_code}'
                    })
            except Exception as health_e:
                return jsonify({
                    'success': False,
                    'message': f'Cannot connect to Ollama server: {str(health_e)}'
                })
            
            # Set a shorter timeout for test requests to avoid long waits
            try:
                # Explicitly set stream to false to avoid multiple JSON responses
                # Use a very small prompt for quick testing
                response = requests.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "Hello",  # Very short prompt
                        "stream": False,
                        "max_tokens": 5,    # Very few tokens
                        "temperature": 0.0  # Deterministic for faster response
                    },
                    timeout=10  # Reduced timeout
                )
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        return jsonify({
                            'success': True,
                            'message': f'Connection to {provider_name} was successful.',
                            'response': result.get('response', 'No response')
                        })
                    except Exception as json_error:
                        return jsonify({
                            'success': True,
                            'message': f'Received response from {provider_name} but could not parse JSON.',
                            'response': "Connection is working but returned unexpected format."
                        })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'Connection to {provider_name} failed: {response.status_code} {response.reason}'
                    })
            except ReadTimeout:
                # Handle timeout specifically for Ollama
                return jsonify({
                    'success': False,
                    'message': f'Request timed out. The {model} model might be loading or is too large for quick testing.',
                    'error_details': 'Try running a warm-up command in your terminal: "ollama run {model} -m "hello"" to load the model first.'
                })
            except ConnectionError:
                return jsonify({
                    'success': False,
                    'message': f'Connection to {provider_name} failed. Make sure Ollama is running at {base_url}.'
                })
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Error during Ollama request: {str(e)}'
                })
        else:
            # For other providers, use the LLMConnector
            response = llm_connector.generate_text(
                prompt="Respond with 'Connection successful!' if you can see this message.",
                provider=provider_name,
                max_tokens=20
            )
            
            return jsonify({
                'success': True,
                'message': f'Connection to {provider_name} was successful.',
                'response': response
            })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Connection to {provider_name} failed: {str(e)}'
        })

@app.route('/admin/llm/delete', methods=['POST'])
@login_required
def admin_llm_delete():
    """Delete an LLM provider configuration."""
    if not current_user.role == 'admin':
        flash('You do not have permission to perform this action.', 'error')
        return redirect(url_for('dashboard'))
    
    provider_name = request.form.get('provider_name')
    if not provider_name:
        flash('Provider name is required.', 'error')
        return redirect(url_for('admin_llm'))
    
    # Remove from the config object
    if provider_name in llm_connector.config.providers:
        # Delete from providers dictionary
        del llm_connector.config.providers[provider_name]
        
        # Delete from database if using MongoDB
        if llm_connector.config.mongo_db is not None:
            try:
                llm_connector.config.mongo_db.llm_configs.delete_one({"provider_name": provider_name})
            except Exception as e:
                flash(f'Error deleting from database: {str(e)}', 'error')
        
        # Remove from provider instances if it exists
        if provider_name in llm_connector.provider_instances:
            del llm_connector.provider_instances[provider_name]
        
        flash(f'LLM provider "{provider_name}" has been deleted.', 'success')
    else:
        flash(f'Provider "{provider_name}" not found.', 'error')
    
    return redirect(url_for('admin_llm'))

@app.route('/admin/llm/details/<provider_name>', methods=['GET'])
@login_required
def admin_llm_details(provider_name):
    """Get details of a specific LLM provider configuration."""
    if not current_user.role == 'admin':
        return jsonify({"success": False, "error": "Permission denied"}), 403
    
    # Check cache first
    cache_key = f"provider_details_{provider_name}"
    current_time = datetime.now().timestamp()
    
    if cache_key in PROVIDER_CACHE:
        cached_data, timestamp = PROVIDER_CACHE[cache_key]
        if current_time - timestamp < CACHE_TIMEOUT:
            return cached_data
    
    config = llm_connector.config.get_provider_config(provider_name)
    if not config:
        return jsonify({"success": False, "error": "Provider not found"}), 404
    
    response = jsonify({
        "success": True,
        "provider": {
            "name": provider_name,
            "has_api_key": bool(config.api_key),
            "base_url": config.base_url,
            "model_name": config.model_name,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature
        }
    })
    
    # Cache the response
    PROVIDER_CACHE[cache_key] = (response, current_time)
    
    return response

@app.route('/admin/ai-prompts')
@login_required
def admin_ai_prompts():
    """AI Prompts management page."""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    per_page = max(5, min(100, per_page))  # Between 5 and 100
    
    # Get search parameter
    search_query = request.args.get('search', '')
    
    # Build the query
    query = {}
    if search_query:
        query = {
            '$or': [
                {'name': {'$regex': search_query, '$options': 'i'}},
                {'value': {'$regex': search_query, '$options': 'i'}},
                {'description': {'$regex': search_query, '$options': 'i'}}
            ]
        }
    
    # Get total count for pagination
    total_prompts = mongo.db.ai_prompts.count_documents(query)
    total_pages = (total_prompts + per_page - 1) // per_page  # Ceiling division
    
    # Get prompts for current page
    ai_prompts = list(mongo.db.ai_prompts.find(query).skip((page - 1) * per_page).limit(per_page))
    
    return render_template(
        'admin/ai_prompts.html', 
        ai_prompts=ai_prompts,
        search_query=search_query,
        current_page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_prompts=total_prompts
    )

@app.route('/admin/ai-prompts/add', methods=['GET', 'POST'])
@login_required
def admin_add_ai_prompt():
    """Add a new AI prompt."""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Get form data
        prompt_data = {
            'name': request.form.get('name', ''),
            'value': request.form.get('value', ''),
            'description': request.form.get('description', ''),
            'target_field': request.form.get('target_field', 'general'),  # Added target field
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Insert the prompt
        mongo.db.ai_prompts.insert_one(prompt_data)
        flash('AI prompt added successfully!', 'success')
        return redirect(url_for('admin_ai_prompts'))
    
    return render_template('admin/add_ai_prompt.html')

@app.route('/admin/ai-prompts/edit/<prompt_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_ai_prompt(prompt_id):
    """Edit an existing AI prompt."""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    prompt = mongo.db.ai_prompts.find_one({'_id': ObjectId(prompt_id)})
    if not prompt:
        flash('Prompt not found.')
        return redirect(url_for('admin_ai_prompts'))
    
    if request.method == 'POST':
        # Get form data
        prompt_data = {
            'name': request.form.get('name', ''),
            'value': request.form.get('value', ''),
            'description': request.form.get('description', ''),
            'target_field': request.form.get('target_field', 'general'),  # Added target field
            'updated_at': datetime.now()
        }
        
        # Update the prompt
        mongo.db.ai_prompts.update_one(
            {'_id': ObjectId(prompt_id)},
            {'$set': prompt_data}
        )
        flash('AI prompt updated successfully!', 'success')
        return redirect(url_for('admin_ai_prompts'))
    
    return render_template('admin/edit_ai_prompt.html', prompt=prompt)

@app.route('/admin/ai-prompts/delete/<prompt_id>', methods=['POST'])
@login_required
def admin_delete_ai_prompt(prompt_id):
    """Delete an AI prompt."""
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.')
        return redirect(url_for('dashboard'))
    
    # Delete the prompt
    result = mongo.db.ai_prompts.delete_one({'_id': ObjectId(prompt_id)})
    
    if result.deleted_count > 0:
        flash('AI prompt deleted successfully!', 'success')
    else:
        flash('Failed to delete prompt. Prompt not found.', 'error')
    
    return redirect(url_for('admin_ai_prompts'))

@app.route('/admin/llm/health', methods=['POST'])
@login_required
def admin_llm_health():
    """Perform a health check on an LLM provider."""
    if not current_user.role == 'admin':
        return jsonify({"success": False, "error": "Permission denied"}), 403
    
    provider_name = request.form.get('provider')
    if not provider_name or provider_name not in llm_connector.config.providers:
        return jsonify({"success": False, "error": f"Provider '{provider_name}' not found"}), 404
    
    try:
        config = llm_connector.config.get_provider_config(provider_name)
        
        # Different health check logic based on provider type
        if 'ollama' in provider_name:
            import requests
            from requests.exceptions import Timeout, ConnectionError
            
            base_url = config.base_url or "http://localhost:11434"
            
            # Check API connection
            try:
                version_response = requests.get(f"{base_url}/api/version", timeout=3)
                if version_response.status_code != 200:
                    return jsonify({
                        "success": False,
                        "error": f"Ollama API not responding: {version_response.status_code}"
                    })
                    
                version_info = version_response.json()
                
                # Check if model is available
                if config.model_name:
                    models_response = requests.get(f"{base_url}/api/tags", timeout=3)
                    if models_response.status_code != 200:
                        return jsonify({
                            "success": True,
                            "status": "API available but couldn't check model",
                            "version": version_info.get("version"),
                            "warning": "Could not verify if model is available"
                        })
                    
                    models = [m.get("name") for m in models_response.json().get("models", [])]
                    if config.model_name not in models:
                        return jsonify({
                            "success": True,
                            "status": "API available but model not found",
                            "version": version_info.get("version"),
                            "warning": f"Model '{config.model_name}' not found in available models"
                        })
                
                return jsonify({
                    "success": True,
                    "status": "API and model available",
                    "version": version_info.get("version")
                })
            except (ConnectionError, Timeout) as e:
                return jsonify({
                    "success": False,
                    "error": f"Cannot connect to Ollama at {base_url}. Is Ollama running?"
                })
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"Ollama API error: {str(e)}"
                })
        else:
            # For cloud providers, check API key validity with minimal token usage
            try:
                # Use a very simple prompt to minimize token usage
                response = llm_connector.generate_text(
                    "Respond with only one word: OK", 
                    provider_name=provider_name,
                    max_tokens=5
                )
                return jsonify({
                    "success": True,
                    "status": "API connection successful",
                    "response": response.strip()
                })
            except Exception as e:
                return jsonify({
                    "success": False, 
                    "error": f"API connection failed: {str(e)}"
                })
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": f"Health check failed: {str(e)}"
        }), 500

@app.route('/admin/llm/ollama/warmup', methods=['POST'])
@login_required
def admin_ollama_warmup():
    """Warm up an Ollama model."""
    if not current_user.role == 'admin':
        return jsonify({"success": False, "error": "Permission denied"}), 403
    
    model_name = request.form.get('model_name')
    base_url = request.form.get('base_url', 'http://localhost:11434')
    
    if not model_name:
        return jsonify({"success": False, "error": "Model name is required"}), 400
    
    def warm_up_model():
        try:
            # Make a request that loads the model but doesn't wait for completion
            print(f"Starting warm-up for model: {model_name}")
            requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": "Hello world",
                    "stream": False,
                    "max_tokens": 1
                },
                timeout=300  # Long timeout for model loading
            )
            print(f"Warm-up completed for model: {model_name}")
        except Exception as e:
            print(f"Error during warm-up: {str(e)}")
    
    # Start in a separate thread
    thread = threading.Thread(target=warm_up_model)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "success": True,
        "message": f"Started warming up model: {model_name}. This happens in the background and may take a few minutes."
    })

@app.route('/company/ai_update/<company_id>', methods=['POST'])
@login_required
def company_ai_update(company_id):
    """Update company details using AI."""
    try:
        # Get request data
        data = request.get_json()
        prompt_id = data.get('prompt_id')
        provider = data.get('provider')
        target_field = data.get('target_field', 'all')
        website = data.get('website', '')
        
        # Log for debugging
        print(f"AI Update Request: company_id={company_id}, prompt={prompt_id}, provider={provider}, target={target_field}")
        
        # Validate inputs
        if not prompt_id or not provider:
            return jsonify({"success": False, "message": "Missing prompt or provider"})
        
        # Get the company data
        company = mongo.db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            return jsonify({"success": False, "message": "Company not found"})
        
        # Use website from request if provided
        company_website = website if website else company.get("website", "")
        
        # Get the AI prompt
        ai_prompt = mongo.db.ai_prompts.find_one({"_id": ObjectId(prompt_id)})
        if not ai_prompt:
            return jsonify({"success": False, "message": "AI prompt not found"})
        
        # Prepare company data
        company_data = {
            "name": company.get("name", ""),
            "website": company_website,
            "products": company.get("products", ""),
            "services": company.get("services", ""),
            "location": company.get("location", ""),
            "description": company.get("description", ""),
            "industry": company.get("industry", ""),
            "founded": company.get("founded", ""),
            "employees": company.get("employees", ""),
            "revenue": company.get("revenue", "")
        }
        
        # Identify fields to update based on target selection
        if target_field != 'all':
            # If specific field selected, only include that field if empty
            missing_fields = [target_field] if not company_data.get(target_field) else []
        else:
            # Check prompt's target field first
            if ai_prompt.get('target_field') and ai_prompt.get('target_field') != 'general':
                # If prompt is field-specific, use that field if empty
                target = ai_prompt.get('target_field')
                missing_fields = [target] if not company_data.get(target) else []
            else:
                # For general prompts, get all empty fields
                missing_fields = [field for field, value in company_data.items() 
                                 if field not in ('_id', 'website') and (
                                     (field != 'name' and not value) or  # For all fields except name, check if empty
                                     (field == 'name' and target_field == 'name')  # For name, only include if specifically requested
                                 )]
        
        if not missing_fields:
            return jsonify({
                "success": False, 
                "message": "No fields to update for the selected criteria"
            })
        
        # Format the prompt with company data
        missing_fields_str = ", ".join(missing_fields)
        prompt_text = ai_prompt["value"].format(
            company_name=company_data["name"],
            company_website=company_website,
            missing_fields=missing_fields_str
        )
        
        # Get LLM provider and generate response
        try:
            llm_connector = LLMConnector()
            llm_provider = llm_connector.get_provider(provider)
            
            # Map field names to database field names
            field_mapping = {
                "name": "name",
                "products": "products",
                "services": "services",
                "location": "location",
                "description": "description", 
                "industry": "industry",
                "founded": "founded",
                "employees": "employees",
                "revenue": "revenue",
                "keyword": "keyword"
            }
            
            # Make request to LLM
            response = llm_provider.generate_text(
                prompt=prompt_text,
                max_tokens=1000,
                temperature=0.5
            )
            
            # Parse the response to extract field:value pairs
            update_data = {}
            for line in response.strip().split("\n"):
                if ":" in line:
                    try:
                        field, value = line.split(":", 1)
                        field = field.strip().lower()
                        value = value.strip()
                        
                        # Only update fields that were marked as missing
                        db_field = field_mapping.get(field)
                        if db_field and db_field in missing_fields and value:
                            update_data[db_field] = value
                    except Exception as e:
                        print(f"Error parsing line '{line}': {str(e)}")
            
            # Update the company data if we have updates
            if update_data:
                mongo.db.companies.update_one(
                    {"_id": ObjectId(company_id)},
                    {"$set": update_data}
                )
                
                # Return success response
                fields_updated = len(update_data)
                fields_text = "fields" if fields_updated > 1 else "field"
                return jsonify({
                    "success": True, 
                    "message": f"Successfully updated {fields_updated} {fields_text} with AI",
                    "updated_fields": list(update_data.keys())
                })
            else:
                return jsonify({
                    "success": False, 
                    "message": "AI couldn't extract useful information"
                })
                
        except Exception as e:
            print(f"LLM error: {str(e)}")
            return jsonify({
                "success": False, 
                "message": f"Error calling AI service: {str(e)}"
            })
            
    except Exception as e:
        print(f"Error in AI update: {str(e)}")
        return jsonify({
            "success": False, 
            "message": "An unexpected error occurred"
        })

def extract_json_from_text(text):
    """Extract JSON from text that might contain markdown or other content."""
    # First try to extract code blocks with json
    json_pattern = r'```(?:json)?\s*({[\s\S]*?})\s*```'
    json_match = re.search(json_pattern, text)
    
    if json_match:
        return json_match.group(1)
    
    # Then try to extract any code blocks
    code_pattern = r'```\s*([\s\S]*?)\s*```'
    code_match = re.search(code_pattern, text)
    
    if code_match:
        return code_match.group(1)
    
    # Finally try to extract any JSON-like structure
    json_like_pattern = r'{[\s\S]*?}'
    json_like_match = re.search(json_like_pattern, text)
    
    if json_like_match:
        return json_like_match.group(0)
    
    return text  # Return the original text if no JSON-like structure is found

def normalize_company_data(data, missing_fields):
    """Normalize company data to ensure proper structure."""
    normalized = {}
    
    # Define array fields
    array_fields = ['products', 'services', 'location', 'keyword']
    
    # Process each requested field
    for field in missing_fields:
        # Get the value, accounting for different possible keys
        value = None
        possible_keys = [field]
        
        if field == 'name':
            possible_keys.extend(['company_name', 'company'])
        elif field == 'keyword':
            possible_keys.extend(['keywords', 'tags'])
        elif field == 'products':
            possible_keys.append('product')
        elif field == 'services':
            possible_keys.append('service')
        elif field == 'location':
            possible_keys.extend(['locations', 'address', 'addresses'])
        
        # Try all possible keys
        for key in possible_keys:
            if key in data:
                value = data[key]
                break
        
        # Skip if no value found
        if value is None:
            continue
        
        # Normalize array fields
        if field in array_fields:
            if isinstance(value, list):
                # Keep arrays as arrays, but ensure all items are strings
                normalized[field] = [str(item).strip() for item in value if item]
            elif isinstance(value, str):
                # Convert string to array, splitting by comma if present
                if ',' in value:
                    normalized[field] = [item.strip() for item in value.split(',') if item.strip()]
                else:
                    normalized[field] = [value.strip()]
            else:
                # For other types, convert to string and wrap in array
                normalized[field] = [str(value).strip()]
        else:
            # For non-array fields, ensure they're strings
            if not isinstance(value, str):
                value = str(value)
            normalized[field] = value.strip()
    
    return normalized

@app.route('/api/company/update_from_web', methods=['POST'])
@login_required
def update_company_from_web():
    """Update company details using AI from company website and LinkedIn."""
    try:
        # Get request data
        data = request.json
        company_id = data.get('company_id')
        website = data.get('website', '').strip()
        fields_to_update = data.get('fields', 'all')
        
        if not company_id or not website:
            return jsonify({
                "success": False,
                "message": "Missing company ID or website URL"
            })
        
        # Get the company from the database
        company = mongo.db.companies.find_one({"_id": ObjectId(company_id)})
        if not company:
            return jsonify({
                "success": False,
                "message": "Company not found"
            })
        
        # Determine which fields to update
        if fields_to_update == 'all':
            # Check for empty or missing fields
            missing_fields = []
            for field in ['name', 'products', 'services', 'location', 'description', 'industry', 'keyword']:
                if field not in company or not company[field]:
                    missing_fields.append(field)
            
            if not missing_fields:
                return jsonify({
                    "success": False,
                    "message": "No empty fields to update"
                })
        elif fields_to_update == 'all_override':
            # Update all fields regardless of whether they're empty or not
            missing_fields = ['name', 'products', 'services', 'location', 'description', 'industry', 'keyword']
        else:
            # Update only the specified field
            missing_fields = [fields_to_update]
        
        # Create a better prompt for foundation models - simpler approach
        company_name = company.get('name', '')
        
        # First try to extract the LinkedIn URL from the website
        linkedin_url = None
        try:
            # Use our LinkedIn extraction function
            linkedin_url = extract_linkedin_url(website, company_name)
            print(f"Found LinkedIn URL: {linkedin_url}")
        except Exception as e:
            print(f"Error finding LinkedIn URL: {str(e)}")
        
        # Build combined prompt that includes LinkedIn data if available
        prompt = f"""Visit the company website {website} """
        
        if linkedin_url:
            prompt += f"and their LinkedIn profile at {linkedin_url} "
        
        prompt += f"""and extract the following information:

Format your response with these EXACT labels (include the colon):
COMPANY NAME: [official company name]
PRODUCTS: [list of products, separated by commas]
SERVICES: [list of services, separated by commas]
LOCATION: [headquarters or office locations, separated by commas]
DESCRIPTION: [brief description of what the company does]
INDUSTRY: [main industry or sector]
KEYWORDS: [relevant business keywords, separated by commas]
LINKEDIN: [LinkedIn URL if found]

Only include fields where you can find information. Do not add any explanations.
"""
        
        if company_name:
            prompt += f"\n\nNote: The company may be known as '{company_name}' but verify this from the website and LinkedIn."
        
        if linkedin_url:
            prompt += "\n\nPrioritize LinkedIn data for company name, industry, and location as it's likely to be more accurate."
        
        print(f"Using prompt for {website}:\n{prompt}")
        
        try:
            # Get a handle to the Bedrock provider
            llm_provider = app.llm_connector.get_provider('bedrock')
            
            # Generate the response
            ai_response = llm_provider.generate_text(prompt)
            print(f"Raw response:\n\n{ai_response}")
            
            # Parse the response to extract fields
            update_data = {}
            updated_fields = []
            
            # Improved parsing logic to handle different response formats
            try:
                # First, try the structured format parsing
                lines = ai_response.strip().split('\n')
                current_field = None
                current_value = ""
                
                # Define mappings for different possible field labels
                field_mappings = {
                    'COMPANY NAME': 'name',
                    'Company Name': 'name',
                    'PRODUCTS': 'products',
                    'Products': 'products',
                    'SERVICES': 'services',
                    'Services': 'services',
                    'LOCATION': 'location',
                    'Location': 'location',
                    'DESCRIPTION': 'description',
                    'Description': 'description',
                    'INDUSTRY': 'industry',
                    'Industry': 'industry',
                    'KEYWORDS': 'keyword',
                    'Keywords': 'keyword',
                    'LINKEDIN': 'linkedin_url',
                    'LinkedIn': 'linkedin_url'
                }
                
                for line in lines:
                    line = line.strip()
                    if not line or line == '---':  # Skip empty lines or separators
                        continue
                    
                    # Check for field labels with more flexible matching
                    found_field = False
                    for label, field_name in field_mappings.items():
                        if line.startswith(f"{label}:"):
                            # Save the previous field if there was one
                            if current_field and current_value:
                                update_data[current_field] = current_value.strip()
                                updated_fields.append(current_field)
                            
                            # Start a new field
                            current_field = field_name
                            current_value = line.split(':', 1)[1].strip()
                            found_field = True
                            break
                    
                    if not found_field and current_field:
                        # Continuation of the current field
                        current_value += " " + line
                
                # Add the last field
                if current_field and current_value:
                    # Special handling for LinkedIn URL
                    if current_field == 'linkedin_url':
                        # Extract URL from markdown link format [text](url)
                        import re
                        url_match = re.search(r'\[.*?\]\((.*?)\)', current_value)
                        if url_match:
                            current_value = url_match.group(1)
                    
                    update_data[current_field] = current_value.strip()
                    updated_fields.append(current_field)
                
                # If we didn't extract any fields but found a LinkedIn URL earlier, use that
                if not update_data and linkedin_url:
                    update_data["linkedin_url"] = linkedin_url
                    updated_fields.append("linkedin_url")
                
                # Update the company in the database
                if update_data:
                    update_data["updated_at"] = datetime.now()
                    
                    result = mongo.db.companies.update_one(
                        {"_id": ObjectId(company_id)},
                        {"$set": update_data}
                    )
                    
                    if result.modified_count > 0:
                        return jsonify({
                            "success": True,
                            "message": f"Successfully updated {len(updated_fields)} fields" + (" with LinkedIn data" if linkedin_url else ""),
                            "updated_fields": updated_fields,
                            "data": update_data,
                            "used_linkedin": linkedin_url is not None
                        })
                    else:
                        return jsonify({
                            "success": False,
                            "message": "No changes made to company"
                        })
                else:
                    # If we couldn't extract any data but found a LinkedIn URL, just update that
                    if linkedin_url:
                        result = mongo.db.companies.update_one(
                            {"_id": ObjectId(company_id)},
                            {"$set": {
                                "linkedin_url": linkedin_url,
                                "updated_at": datetime.now()
                            }}
                        )
                        
                        if result.modified_count > 0:
                            return jsonify({
                                "success": True,
                                "message": "Successfully updated LinkedIn URL",
                                "updated_fields": ["linkedin_url"],
                                "data": {"linkedin_url": linkedin_url},
                                "used_linkedin": True
                            })
                    
                    return jsonify({
                        "success": False,
                        "message": "Could not extract any useful data from the website or LinkedIn"
                    })
                
            except Exception as parsing_error:
                print(f"Primary parsing failed, trying alternative approach: {str(parsing_error)}")
                
                # Fallback: Just update the LinkedIn URL if we found it
                if linkedin_url:
                    result = mongo.db.companies.update_one(
                        {"_id": ObjectId(company_id)},
                        {"$set": {
                            "linkedin_url": linkedin_url,
                            "updated_at": datetime.now()
                        }}
                    )
                    
                    if result.modified_count > 0:
                        return jsonify({
                            "success": True,
                            "message": "Successfully updated LinkedIn URL",
                            "updated_fields": ["linkedin_url"],
                            "data": {"linkedin_url": linkedin_url},
                            "used_linkedin": True
                        })
                
                return jsonify({
                    "success": False,
                    "message": f"Error parsing AI response: {str(parsing_error)}"
                })
            
        except Exception as e:
            return jsonify({
                "success": False,
                "message": f"Error: {str(e)}"
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error: {str(e)}"
        })

@app.route('/company/bulk_delete', methods=['POST'])
@login_required
def bulk_delete_companies():
    """Delete multiple companies at once."""
    try:
        data = request.json
        company_ids = data.get('company_ids', [])
        
        if not company_ids:
            return jsonify({
                "success": False,
                "message": "No company IDs provided"
            })
        
        # Convert string IDs to ObjectId
        object_ids = [ObjectId(id) for id in company_ids]
        
        # Delete the companies
        result = mongo.db.companies.delete_many({'_id': {'$in': object_ids}})
        
        if result.deleted_count > 0:
            return jsonify({
                "success": True,
                "message": f"Successfully deleted {result.deleted_count} companies"
            })
        else:
            return jsonify({
                "success": False,
                "message": "No companies were deleted"
            })
            
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"An error occurred: {str(e)}"
        })

# Make these accessible to blueprints
app.mongo = mongo
app.llm_connector = llm_connector

# Now register the blueprint
from routes.admin_routes import admin_bp
app.register_blueprint(admin_bp, url_prefix='/admin')

def extract_linkedin_url(website_url, company_name=None):
    """Extract LinkedIn URL from a company website."""
    import requests
    import re
    from urllib.parse import urljoin
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    try:
        # Try to get the website content
        response = requests.get(website_url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch website: {response.status_code}")
            return None
        
        # Extract LinkedIn URLs from the webpage
        content = response.text
        
        # Look for LinkedIn URLs in the page
        linkedin_patterns = [
            # Standard LinkedIn company URLs
            r'https?://(?:www\.)?linkedin\.com/company/[a-zA-Z0-9_-]+',
            # Alternate formats
            r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+',
            r'https?://(?:www\.)?linkedin\.com/school/[a-zA-Z0-9_-]+'
        ]
        
        for pattern in linkedin_patterns:
            matches = re.findall(pattern, content)
            if matches:
                # Return the first match
                return matches[0]
        
        # If company name is provided, try a backup approach with Google search
        if company_name:
            try:
                google_search_url = f"https://www.google.com/search?q={company_name}+linkedin+company"
                google_response = requests.get(
                    google_search_url, 
                    headers=headers, 
                    timeout=10
                )
                
                if google_response.status_code == 200:
                    # Look for LinkedIn company URLs in search results
                    for pattern in linkedin_patterns:
                        matches = re.findall(pattern, google_response.text)
                        if matches:
                            return matches[0]
            except Exception as e:
                print(f"Error in Google search fallback: {str(e)}")
                # Continue with the process even if Google search fails
        
        # No LinkedIn URL found
        return None
        
    except Exception as e:
        print(f"Error extracting LinkedIn URL: {str(e)}")
        return None

@app.route('/api/companies/download-csv', methods=['POST'])
@login_required
def download_companies_csv():
    """Download selected companies as CSV."""
    try:
        data = request.get_json()
        company_ids = data.get('company_ids', [])
        
        if not company_ids:
            return jsonify({"success": False, "message": "No companies selected"}), 400
        
        # Convert string IDs to ObjectId
        object_ids = [ObjectId(id) for id in company_ids]
        
        # Query the companies
        companies = list(mongo.db.companies.find({"_id": {"$in": object_ids}}))
        
        if not companies:
            return jsonify({"success": False, "message": "No companies found"}), 404
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header - adjust fields as needed
        fields = ['name', 'website', 'linkedin_url', 'industry', 'products', 'services', 'location', 
                 'description', 'keyword', 'email', 'phone']
        
        writer.writerow(fields)
        
        # Write company data
        for company in companies:
            row = []
            for field in fields:
                # Handle nested or missing fields
                if field in company:
                    value = company[field]
                    # Convert lists to comma-separated strings
                    if isinstance(value, list):
                        value = ', '.join(value)
                    row.append(value)
                else:
                    row.append('')
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        csv_data = output.getvalue()
        
        # Create response with proper headers
        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=companies-{datetime.now().strftime('%Y-%m-%d')}.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
        
        return response
        
    except Exception as e:
        app.logger.error(f"Error generating CSV: {str(e)}")
        return jsonify({"success": False, "message": f"Error generating CSV: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True) 