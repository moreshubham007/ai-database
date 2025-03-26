from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from bson.objectid import ObjectId
import os
from datetime import datetime
from functools import wraps
from llm import LLMConnector
from llm.config import ProviderConfig
from werkzeug.security import generate_password_hash

# Create Blueprint
admin_bp = Blueprint('admin_bp', __name__)

# Define admin_required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not hasattr(current_user, 'role') or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def admin_home():
    """Redirect to admin dashboard."""
    return redirect(url_for('admin_bp.admin_dashboard'))

@admin_bp.route('/bedrock', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_bedrock():
    """AWS Bedrock AI configuration page."""
    # Add debug logs
    print("==== ACCESSING BEDROCK CONFIG PAGE ====")
    print(f"Current user: {current_user.username if current_user else 'Not logged in'}")
    print(f"Current user role: {current_user.role if hasattr(current_user, 'role') else 'No role'}")
    
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    llm_connector = current_app.llm_connector
    
    if request.method == 'POST':
        # Get form data
        aws_access_key = request.form.get('aws_access_key')
        aws_secret_key = request.form.get('aws_secret_key')
        aws_region = request.form.get('aws_region', 'us-east-1')
        model_id = request.form.get('model_id', 'amazon.titan-text-express-v1')
        
        # Store configuration in database for persistence
        mongo.db.settings.update_one(
            {'setting_type': 'bedrock_config'},
            {'$set': {
                'setting_type': 'bedrock_config',
                'aws_access_key': aws_access_key,
                'aws_secret_key': aws_secret_key,
                'aws_region': aws_region,
                'model_id': model_id,
                'updated_at': datetime.now()
            }},
            upsert=True
        )
        
        # Create a new provider config for Bedrock
        try:
            from llm.providers.bedrock_connector import BedrockConnector
            provider_config = ProviderConfig(
                api_key=f"{aws_access_key}:{aws_secret_key}",
                base_url=aws_region,
                model_name=model_id,
                max_tokens=1000,
                temperature=0.7
            )
            
            # Update the global LLM connector configuration
            llm_connector.config.providers['bedrock'] = provider_config
            
            # Clear any existing instance
            if 'bedrock' in llm_connector.provider_instances:
                del llm_connector.provider_instances['bedrock']
                
            flash('AWS Bedrock configuration saved successfully!', 'success')
            flash('Note: Some models require inference profiles to be set up in AWS Bedrock before they can be used.', 'info')
        except Exception as e:
            flash(f'Error configuring Bedrock: {str(e)}', 'error')
        
        return redirect(url_for('admin_bp.admin_bedrock'))
    
    # Get existing configuration
    bedrock_config = mongo.db.settings.find_one({'setting_type': 'bedrock_config'})
    
    # Mark reliable models that don't need inference profiles
    reliable_models = [
        {'id': 'anthropic.claude-instant-v1', 'name': 'Anthropic Claude Instant (MCP Compatible)'},
        {'id': 'amazon.titan-text-express-v1', 'name': 'Amazon Titan Text Express (MCP Compatible)'},
        {'id': 'anthropic.claude-v2', 'name': 'Anthropic Claude v2 (MCP Compatible)'},
    ]
    
    # Available models for Bedrock, including Llama 3.2 and 3.3 models
    available_models = [
        # Reliable models first
        *reliable_models,
        
        # Then other models that might need inference profiles
        {'id': 'anthropic.claude-3-sonnet-20240229-v1:0', 'name': 'Anthropic Claude 3 Sonnet (Excellent MCP support, may need inference profile)'},
        {'id': 'anthropic.claude-3-haiku-20240307-v1:0', 'name': 'Anthropic Claude 3 Haiku (Good MCP support, balanced speed/quality)'},
        {'id': 'amazon.titan-text-lite-v1', 'name': 'Amazon Titan Text Lite (Basic MCP support)'},
        
        # Llama models
        {'id': 'meta.llama2-13b-chat-v1', 'name': 'Meta Llama 2 13B Chat (Limited MCP support)'},
        {'id': 'meta.llama3-1-405b-instruct-v1:0', 'name': 'Llama 3.1 405B Instruct (Good MCP support)'},
        {'id': 'meta.llama2-70b-chat-v1', 'name': 'Meta Llama 2 70B Chat (Moderate MCP support)'},
        {'id': 'meta.llama3-2-8b-instruct-v1', 'name': 'Meta Llama 3.2 8B Instruct (Likely needs inference profile)'},
        {'id': 'meta.llama3-2-3b-instruct-v1:0', 'name': 'Llama 3.2 3B Instruct (Needs inference profile)'},
        {'id': 'meta.llama3-2-70b-instruct-v1', 'name': 'Meta Llama 3.2 70B Instruct (Likely needs inference profile)'},
        {'id': 'meta.llama3-2-405b-instruct-v1', 'name': 'Meta Llama 3.2 405B Instruct (Likely needs inference profile)'},
        {'id': 'meta.llama3-3-70b-instruct-v1:0', 'name': 'Meta Llama 3.3 70B Instruct (Likely needs inference profile)'},
        {'id': 'meta.llama3-3-8b-instruct-v1', 'name': 'Meta Llama 3.3 8B Instruct (Likely needs inference profile)'},
        {'id': 'meta.llama3-8b-instruct-v1:0', 'name': 'Meta Llama 3 8B Instruct'},
        {'id': 'meta.llama3-1-70b-instruct-v1:0', 'name': 'Meta Llama 3 1B Instruct'},
       
        
        # Mistral models
        {'id': 'mistral.mistral-7b-instruct-v0:2', 'name': 'Mistral 7B Instruct (May need inference profile)'},
        {'id': 'mistral.mistral-large-2407-v1:0', 'name': 'Mistral Large 2 (24.07)'},
        {'id': 'mistral.mixtral-8x7b-instruct-v0:1', 'name': 'Mistral Mixtral 8x7B Instruct (May need inference profile)'}
    ]
    
    # Available AWS regions where Bedrock is supported
    available_regions = [
        {'id': 'us-east-1', 'name': 'US East (N. Virginia)'},
        {'id': 'us-east-2', 'name': 'US East (Ohio)'},
        {'id': 'us-west-1', 'name': 'US West (N. California)'},
        {'id': 'us-west-2', 'name': 'US West (Oregon)'},
        {'id': 'ap-south-1', 'name': 'Asia Pacific (Mumbai)'},
        {'id': 'ap-northeast-1', 'name': 'Asia Pacific (Tokyo)'},
        {'id': 'eu-central-1', 'name': 'EU (Frankfurt)'},
        {'id': 'eu-west-1', 'name': 'EU (Ireland)'}
    ]
    
    return render_template(
        'admin/bedrock.html',
        bedrock_config=bedrock_config,
        available_models=available_models,
        reliable_models=reliable_models,
        available_regions=available_regions
    )

@admin_bp.route('/bedrock/test', methods=['POST'])
@login_required
@admin_required
def test_bedrock():
    """Test AWS Bedrock configuration."""
    try:
        # Get the llm_connector from the current app
        llm_connector = current_app.llm_connector
        
        # Get the bedrock provider from the connector
        provider = llm_connector.get_provider('bedrock')
        
        # Test with a simple prompt
        prompt = "Hello, this is a test message from AWS Bedrock. Please respond with a brief greeting."
        response = provider.generate_text(prompt)
        
        return jsonify({
            'success': True,
            'message': 'AWS Bedrock is configured correctly!',
            'response': response
        })
    except Exception as e:
        # Log the full error
        current_app.logger.error(f"Bedrock test error: {str(e)}")
        
        # Return a user-friendly message
        return jsonify({
            'success': False,
            'message': f'Error testing AWS Bedrock: {str(e)}'
        })

@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard with links to all admin functions."""
    return render_template('admin/dashboard.html')

@admin_bp.route('/test')
def admin_test():
    """Simple test route to verify the admin blueprint is working."""
    return "Admin blueprint is working correctly!"

@admin_bp.route('/users')
@login_required
@admin_required
def admin_users():
    """Admin user management page."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    # Get all users
    users = list(mongo.db.users.find())
    
    return render_template('admin/users.html', users=users, current_user=current_user)

@admin_bp.route('/users/add', methods=['POST'])
@login_required
@admin_required
def add_user():
    """Add a new user."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role', 'user')
        
        # Simple validation
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Check if username or email already exists
        if mongo.db.users.find_one({'$or': [{'username': username}, {'email': email}]}):
            flash('Username or email already exists', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Generate password hash
        password_hash = generate_password_hash(password)
        
        # Create new user
        new_user = {
            'username': username,
            'email': email,
            'password': password_hash,
            'role': role,
            'created_at': datetime.now(),
            'last_login': None
        }
        
        # Insert new user
        result = mongo.db.users.insert_one(new_user)
        
        if result.inserted_id:
            flash(f'User {username} created successfully', 'success')
        else:
            flash('Failed to create user', 'error')
            
    return redirect(url_for('admin_bp.admin_users'))

@admin_bp.route('/users/update', methods=['POST'])
@login_required
@admin_required
def update_user():
    """Update user details."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role', 'user')
        
        # Simple validation
        if not user_id or not username or not email:
            flash('All fields are required', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Check if username or email already exists for other users
        existing_user = mongo.db.users.find_one({
            '$and': [
                {'_id': {'$ne': ObjectId(user_id)}},
                {'$or': [{'username': username}, {'email': email}]}
            ]
        })
        
        if existing_user:
            flash('Username or email already exists for another user', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Update user
        result = mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'username': username,
                'email': email,
                'role': role
            }}
        )
        
        if result.modified_count > 0:
            flash(f'User {username} updated successfully', 'success')
        else:
            flash('No changes made to user', 'info')
            
    return redirect(url_for('admin_bp.admin_users'))

@admin_bp.route('/users/reset-password', methods=['POST'])
@login_required
@admin_required
def reset_user_password():
    """Reset a user's password."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Simple validation
        if not user_id or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Generate password hash
        password_hash = generate_password_hash(password)
        
        # Update user password
        result = mongo.db.users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'password': password_hash}}
        )
        
        if result.modified_count > 0:
            flash('Password reset successfully', 'success')
        else:
            flash('Failed to reset password', 'error')
            
    return redirect(url_for('admin_bp.admin_users'))

@admin_bp.route('/users/delete', methods=['POST'])
@login_required
@admin_required
def delete_user():
    """Delete a user."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        
        # Don't allow deleting your own account
        if str(ObjectId(user_id)) == str(current_user.get_id()):
            flash('You cannot delete your own account', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Get the user to be deleted (for the username)
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('admin_bp.admin_users'))
            
        # Delete the user
        result = mongo.db.users.delete_one({'_id': ObjectId(user_id)})
        
        if result.deleted_count > 0:
            flash(f'User {user["username"]} deleted successfully', 'success')
        else:
            flash('Failed to delete user', 'error')
            
    return redirect(url_for('admin_bp.admin_users'))

@admin_bp.route('/companies')
@login_required
@admin_required
def admin_companies():
    """Admin company management page."""
    # Get the mongo instance from the current app
    mongo = current_app.mongo
    
    # Get all companies
    companies = list(mongo.db.companies.find())
    
    return render_template('admin/companies.html', companies=companies)

@admin_bp.route('/check-admin')
@login_required
def check_admin():
    """Check if current user has admin role."""
    is_admin = hasattr(current_user, 'role') and current_user.role == 'admin'
    return f"""
    <h1>Admin Role Check</h1>
    <p>User: {current_user.username if current_user else 'Not logged in'}</p>
    <p>Is Admin: {is_admin}</p>
    <p>Role: {current_user.role if hasattr(current_user, 'role') else 'No role'}</p>
    <p><a href="{url_for('admin_bp.admin_bedrock')}">Go to Bedrock Config</a></p>
    """ 