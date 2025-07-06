
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography.fernet import Fernet
import json
import time

# Generate encryption key
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

def cleanup_database(db_path='db/database.db'):
    """Clean up database file on startup."""
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            st.info("🗑️ Previous database cleaned up")
    except Exception as e:
        st.warning(f"Could not clean up database: {str(e)}")

def show_temporary_message(message, message_type="success", duration=5):
    """Show a temporary message that disappears after specified duration."""
    # Create a unique key for this message
    message_key = f"temp_msg_{int(time.time() * 1000)}"
    
    # Store message in session state
    if 'temp_messages' not in st.session_state:
        st.session_state.temp_messages = {}
    
    st.session_state.temp_messages[message_key] = {
        'message': message,
        'type': message_type,
        'created_at': time.time(),
        'duration': duration
    }
    
    # Display the message
    placeholder = st.empty()
    with placeholder:
        if message_type == "success":
            st.success(message)
        elif message_type == "info":
            st.info(message)
        elif message_type == "warning":
            st.warning(message)
        elif message_type == "error":
            st.error(message)
    
    # Store placeholder for cleanup
    if 'temp_placeholders' not in st.session_state:
        st.session_state.temp_placeholders = {}
    st.session_state.temp_placeholders[message_key] = placeholder

def load_raw_data():
    """Load raw customer data from CSV file."""
    try:
        df = pd.read_csv('data/raw_customer_churn.csv')
        st.session_state.pipeline_status['data_loaded'] = True
        st.success("✅ 1. Loaded the raw data successfully.")
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None

def add_synthetic_fields(df):
    """Add synthetic fields to the dataset."""
    try:
        # Generate synthetic email addresses
        df['email'] = [f"customer{i}@example.com" for i in range(len(df))]
        
        # Generate synthetic phone numbers
        df['phone_number'] = [f"+1-555-{str(i).zfill(3)}-{str(i*2).zfill(4)}" for i in range(len(df))]
        
        # Generate synthetic join dates
        base_date = datetime(2020, 1, 1)
        df['join_date'] = [base_date + timedelta(days=i*30) for i in range(len(df))]
        
        # Generate synthetic last login dates
        df['last_login'] = [base_date + timedelta(days=i*30 + np.random.randint(1, 365)) for i in range(len(df))]
        
        # Generate synthetic monthly transaction amounts
        df['avg_monthly_txn'] = np.random.uniform(100, 5000, len(df))
        
        # Generate synthetic credit card types
        card_types = ['Visa', 'MasterCard', 'American Express', 'Discover']
        df['credit_card_type'] = np.random.choice(card_types, len(df))
        
        st.session_state.pipeline_status['synthetic_fields_added'] = True
        st.success("✅ 2. Added synthetic data.")
        return df
    except Exception as e:
        st.error(f"Error adding synthetic fields: {str(e)}")
        return None

def encrypt_sensitive_data(df):
    """Encrypt sensitive data fields."""
    try:
        df_encrypted = df.copy()
        
        # Fields to encrypt
        sensitive_fields = ['email', 'phone_number', 'credit_card_type']
        
        for field in sensitive_fields:
            if field in df_encrypted.columns:
                # Encrypt the field
                encrypted_values = []
                for value in df_encrypted[field]:
                    encrypted_value = cipher_suite.encrypt(str(value).encode())
                    encrypted_values.append(base64.b64encode(encrypted_value).decode())
                
                # Rename column to indicate encryption
                new_field_name = f"{field}_encrypted"
                df_encrypted[new_field_name] = encrypted_values
                df_encrypted.drop(columns=[field], inplace=True)
        
        st.session_state.pipeline_status['data_encrypted'] = True
        st.success("✅ 3. Encrypted the data.")
        return df_encrypted
    except Exception as e:
        st.error(f"Error encrypting data: {str(e)}")
        return None

def decrypt_data(df_encrypted):
    """Decrypt sensitive data fields."""
    try:
        df_decrypted = df_encrypted.copy()
        
        # Find encrypted fields
        encrypted_fields = [col for col in df_encrypted.columns if 'encrypted' in col]
        
        for field in encrypted_fields:
            # Get original field name
            original_field = field.replace('_encrypted', '')
            
            # Decrypt the field
            decrypted_values = []
            for value in df_encrypted[field]:
                try:
                    encrypted_bytes = base64.b64decode(value.encode())
                    decrypted_value = cipher_suite.decrypt(encrypted_bytes).decode()
                    decrypted_values.append(decrypted_value)
                except:
                    decrypted_values.append("Decryption failed")
            
            df_decrypted[original_field] = decrypted_values
            df_decrypted.drop(columns=[field], inplace=True)
        
        return df_decrypted
    except Exception as e:
        st.error(f"Error decrypting data: {str(e)}")
        return None

def store_in_database(df, db_path='db/database.db'):
    """Store encrypted data in SQLite database."""
    try:
        # Create database directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Store the data
        df.to_sql('customer_data', conn, if_exists='replace', index=False)
        
        conn.close()
        st.session_state.pipeline_status['database_stored'] = True
        st.success("✅ 4. Stored in database.")
        return True
    except Exception as e:
        st.error(f"Error storing in database: {str(e)}")
        return False

def run_complete_pipeline():
    """Run the complete data processing pipeline."""
    # Step 1: Load raw data
    df = load_raw_data()
    if df is None:
        return False, None, None
    
    # Step 2: Add synthetic fields
    df_with_synthetic = add_synthetic_fields(df)
    if df_with_synthetic is None:
        return False, None, None
    
    # Step 3: Encrypt sensitive data
    df_encrypted = encrypt_sensitive_data(df_with_synthetic)
    if df_encrypted is None:
        return False, None, None
    
    # Step 4: Store in database
    db_success = store_in_database(df_encrypted)
    if not db_success:
        return False, None, None
    
    return True, df_encrypted, df_with_synthetic

def get_database_data(db_path='db/database.db'):
    """Get data from database."""
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            df_db = pd.read_sql_query("SELECT * FROM customer_data LIMIT 10", conn)
            conn.close()
            return df_db
        else:
            return None
    except Exception as e:
        st.error(f"Error loading from database: {str(e)}")
        return None

def get_database_schema(db_path='db/database.db'):
    """Get database schema information."""
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(customer_data)")
            columns = cursor.fetchall()
            conn.close()
            return columns
        else:
            return None
    except Exception as e:
        st.error(f"Error getting schema: {str(e)}")
        return None

def download_dataframe_as_csv(df, filename, label):
    """Create a download button for a DataFrame as CSV."""
    if df is not None:
        csv_data = df.to_csv(index=False)
        st.download_button(
            label=label,
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.error("No data available for download")

def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'data_processed' not in st.session_state:
        st.session_state.data_processed = False
    if 'df_encrypted' not in st.session_state:
        st.session_state.df_encrypted = None
    if 'df_decrypted' not in st.session_state:
        st.session_state.df_decrypted = None
    if 'pipeline_status' not in st.session_state:
        st.session_state.pipeline_status = {
            'data_loaded': False,
            'synthetic_fields_added': False,
            'data_encrypted': False,
            'database_stored': False
        }

def cleanup_expired_messages():
    """Clean up expired temporary messages."""
    if 'temp_messages' not in st.session_state or 'temp_placeholders' not in st.session_state:
        return
    
    current_time = time.time()
    expired_keys = []
    
    for message_key, message_data in st.session_state.temp_messages.items():
        if current_time - message_data['created_at'] > message_data['duration']:
            expired_keys.append(message_key)
    
    # Remove expired messages
    for key in expired_keys:
        if key in st.session_state.temp_placeholders:
            # Clear the placeholder
            placeholder = st.session_state.temp_placeholders[key]
            placeholder.empty()
            del st.session_state.temp_placeholders[key]
        
        if key in st.session_state.temp_messages:
            del st.session_state.temp_messages[key] 