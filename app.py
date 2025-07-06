
import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib
import base64
from cryptography.fernet import Fernet
import json
from llm_agent_pipeline import run_llm_data_flow, get_llm
import sqlite3

# Generate encryption key
ENCRYPTION_KEY = Fernet.generate_key()
cipher_suite = Fernet(ENCRYPTION_KEY)

# Import helper functions
from utils.helper import (
    run_complete_pipeline,
    decrypt_data,
    get_database_data,
    get_database_schema,
    download_dataframe_as_csv,
    initialize_session_state,
    cleanup_database,
    cleanup_expired_messages
)

# Page config
st.set_page_config(
    page_title="Financial Copilot",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
initialize_session_state()

# Don't clean up database on startup - this was causing the database to be deleted every time!
# cleanup_database()

def render_header():
    """Render the application header."""
    # No tabs needed - only chat functionality
    return None

def render_chat_interface():
    """Render the chat interface without tabs."""
    # Title moved to sidebar

    # Init session state
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "input_key" not in st.session_state:
        st.session_state.input_key = 0

    # --- Show info message if data not imported or API key missing ---
    provider = st.session_state.get("llm_provider", "groq")  # or however you store provider
    if provider == "groq":
        api_key = st.session_state.get("groq_api_key", "")
    else:
        api_key = st.session_state.get("openai_api_key", "")

    data_imported = st.session_state.get("data_processed", False)

    # Only show info if data is NOT imported or API key is missing
    if not data_imported or not api_key:
        st.info('First add API key and import the data then use the chat feature .')

    # Scrollable chat container
    chat_placeholder = st.container()

    with chat_placeholder:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.write(msg.get("text", ""))
                    if "plot_figure" in msg and msg["plot_figure"] is not None:
                        st.pyplot(msg["plot_figure"])
                    if "table_df" in msg and msg["table_df"] is not None:
                        st.dataframe(msg["table_df"])
            #     st.chat_message("assistant").write(msg["content"])
            # if "graph" in msg:
            #     st.plotly_chart(msg["graph"], use_container_width=True)
            # if "table" in msg:
            #     st.dataframe(msg["table"], use_container_width=True)

    # Add a placeholder to help scroll to bottom
    scroll_to_bottom = st.empty()
    scroll_to_bottom.markdown("<div id='bottom'></div>", unsafe_allow_html=True)

    # JS trick to scroll to bottom on rerun
    st.markdown("""
    <script>
    const bottom = document.getElementById("bottom");
    if (bottom) {
        bottom.scrollIntoView({ behavior: "smooth" });
    }
    </script>
    """, unsafe_allow_html=True)

    # Chat input
    with st.container():
        col1, col2, col3 = st.columns([6, 1, 1])
        with col1:
            prompt = st.text_input(
                "Ask a question about your financial data...",
                key=f"chat_input_{st.session_state.input_key}",
                label_visibility="collapsed",
                placeholder='Ask me anything... eg. "what is the given data about?"'
            )
        with col2:
            if st.button("Send", type="primary", use_container_width=True):
                if prompt:
                    st.session_state.messages.append({"role": "user", "content": prompt})

                    # Generate AI response with potential graphs/tables
                    ai_response = generate_ai_response_with_visuals(prompt)
                    st.session_state.messages.append(ai_response)

                    st.session_state.input_key += 1
                    st.rerun()
        with col3:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.messages = []
                st.session_state.input_key += 1
                st.rerun()

def get_database_connection(db_path='db/database.db'):
    """Create and return a database connection."""
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            return conn
        else:
            st.error(f"Database file not found at: {db_path}")
            st.info(f"Current working directory: {os.getcwd()}")
            st.info(f"db directory contents: {os.listdir('db') if os.path.exists('db') else 'db directory does not exist'}")
            return None
    except Exception as e:
        st.error(f"Error connecting to database: {str(e)}")
        return None

def generate_ai_response_with_visuals(prompt):
    # Get database connection
    conn = get_database_connection()
    if not conn:
        return {"role": "assistant", "content": "Database not connected. Please import data first."}

    try:
        # Get the current provider and API key with better debugging
        provider = st.session_state.get("llm_provider", "groq")
        
        # Debug: Print session state
        print(f"Debug - Provider: {provider}")
        print(f"Debug - Session state keys: {list(st.session_state.keys())}")
        
        if provider == "groq":
            api_key = st.session_state.get("groq_api_key", "")
            print(f"Debug - Groq API key length: {len(api_key) if api_key else 0}")
        else:
            api_key = st.session_state.get("openai_api_key", "")
            print(f"Debug - OpenAI API key length: {len(api_key) if api_key else 0}")
        
        if not api_key:
            return {"role": "assistant", "content": f"API key not configured for {provider}. Please add your API key in the sidebar."}

        llm = get_llm(provider, api_key)
        result, response = run_llm_data_flow(conn, prompt, llm)
        message = {"role": "assistant", "content": ""}
        message = {
            "role": "assistant",
            "text": response.get("text", "No answer provided.")
        }
        if "plot_figure" in response:
            message["plot_figure"]=response["plot_figure"]

        if "table_df" in response:
            message["table_df"]=response["table_df"]
        
        return message
    finally:
        # Always close the connection
        if conn:
            conn.close()

def render_sidebar_controls():
    """Render sidebar controls and return user selections."""
    with st.sidebar:
        # Title at the very top
        st.title("🔐 Financial Copilot")
        
        # LLM Provider selection
        provider = st.selectbox(
            "LLM Service",
            options=["openai","groq"],
            format_func=lambda x: "Groq" if x == "groq" else "OpenAI",
            key="llm_provider"
        )

        # Dynamic label and placeholder
        if provider == "groq":
            api_label = "Groq API Key"
            api_placeholder = "gsk-..."
            api_help = "Enter your Groq API key to enable AI features"
            api_key = st.text_input(
                api_label,
                value=st.session_state.get("groq_api_key", ""),
                type="password",
                help=api_help,
                placeholder=api_placeholder,
                key="groq_api_input"
            )
            # Store in session state
            st.session_state.groq_api_key = api_key
        else:
            api_label = "OpenAI API Key"
            api_placeholder = "sk-..."
            api_help = "Enter your OpenAI API key to enable AI features"
            api_key = st.text_input(
                api_label,
                value=st.session_state.get("openai_api_key", ""),
                type="password",
                help=api_help,
                placeholder=api_placeholder,
                key="openai_api_input"
            )
            # Store in session state
            st.session_state.openai_api_key = api_key

        if api_key:
            st.success(f"✅ {api_label} configured")
        else:
            st.warning(f"⚠️ {api_label} required for AI features")
        
        st.markdown("---")
        
        # Import Data button
        st.subheader("📥 Data Import")
        
        # Use a form to ensure the button click is properly captured
        with st.form("import_form"):
            import_clicked = st.form_submit_button("📥 Import Data", use_container_width=True, type="primary")
        
        if import_clicked:
            st.write("🔄 Starting import process...")
            
            # Initialize pipeline status
            if 'pipeline_status' not in st.session_state:
                st.session_state.pipeline_status = {
                    'data_loaded': False,
                    'synthetic_fields_added': False,
                    'data_encrypted': False,
                    'database_stored': False
                }
            
            # Step 1: Load data
            st.write("Step 1: Loading data...")
            try:
                df = pd.read_csv('data/raw_customer_churn.csv')
                st.session_state.pipeline_status['data_loaded'] = True
                st.success(f"✅ Loaded {len(df)} rows of data")
            except Exception as e:
                st.error(f"❌ Failed to load data: {e}")
                st.stop()
            
            # Step 2: Add synthetic fields
            st.write("Step 2: Adding synthetic fields...")
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
                st.success("✅ Added synthetic fields")
            except Exception as e:
                st.error(f"❌ Failed to add synthetic fields: {e}")
                st.stop()
            
            # Step 3: Encrypt data
            st.write("Step 3: Encrypting data...")
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
                st.success("✅ Encrypted sensitive data")
            except Exception as e:
                st.error(f"❌ Failed to encrypt data: {e}")
                st.stop()
            
            # Step 4: Store in database
            st.write("Step 4: Storing in database...")
            try:
                # Create database directory if it doesn't exist
                os.makedirs('db', exist_ok=True)
                
                # Connect to database
                conn = sqlite3.connect('db/database.db')
                
                # Store the data
                df_encrypted.to_sql('customer_data', conn, if_exists='replace', index=False)
                
                # Verify storage
                result = pd.read_sql_query("SELECT COUNT(*) as count FROM customer_data", conn)
                conn.close()
                
                st.session_state.pipeline_status['database_stored'] = True
                st.session_state.data_processed = True
                st.session_state.df_encrypted = df_encrypted
                
                st.success(f"✅ Stored {result['count'].iloc[0]} rows in database")
                # st.balloons()
                
            except Exception as e:
                st.error(f"❌ Failed to store in database: {e}")
                st.stop()
        
        # Check if all pipeline steps are completed for button styling
        pipeline_completed = False
        if 'pipeline_status' in st.session_state:
            pipeline_completed = all(st.session_state.pipeline_status.values())
        
        # Add custom CSS for button color based on pipeline status
        if pipeline_completed:
            # Light green when pipeline is completed
            button_color = "#90EE90"  # Light Green
            button_hover_color = "#98FB98"  # Pale Green
            button_border_color = "#228B22"  # Forest Green
        else:
            # Light blue when pipeline is not completed
            button_color = "#87CEEB"  # Sky Blue
            button_hover_color = "#B0E0E6"  # Powder Blue
            button_border_color = "#4682B4"  # Steel Blue
        
        st.markdown(f"""
            <style>
            .stButton > button {{
                background-color: {button_color} !important;
                color: #000000 !important;
                border: 1px solid {button_border_color} !important;
            }}
            .stButton > button:hover {{
                background-color: {button_hover_color} !important;
                border-color: {button_border_color} !important;
            }}
            </style>
        """, unsafe_allow_html=True)
        # Check if data has been processed
        data_available = st.session_state.get('data_processed', False)
        st.markdown("---")
        
        # Database options
        st.subheader("🗄️ Database")
        preview_database = st.checkbox("Preview Database", value=False, disabled=not data_available)
        
        # Download options
        st.subheader("📁 Download")
        
        
        if not data_available:
            st.caption("📥 Import the data to download the files")
        
        download_encrypted = st.button("Download Encrypted Data", use_container_width=True, disabled=not data_available)
        download_decrypted = st.button("Download Decrypted Data", use_container_width=True, disabled=not data_available)
        
        return {
            'preview_database': preview_database,
            'download_encrypted': download_encrypted,
            'download_decrypted': download_decrypted
        }

def render_database_preview(show_preview=False):
    """Render the database preview section."""
    if show_preview:
        st.header("Database Preview")
        
        # Get data from database using helper function
        df_db = get_database_data()
        
        if df_db is not None:
            st.dataframe(
                df_db, 
                use_container_width=True,
                hide_index=True
            )
            
            # Show database info
            with st.expander("Database Schema"):
                schema = get_database_schema()
                if schema:
                    st.write("Database Schema:")
                    for col in schema:
                        st.write(f"• {col[1]} ({col[2]})")
        else:
            st.info("Database not created yet. Run the pipeline first.")

def render_pipeline_logs(pipeline_status):
    """Render the pipeline logs section."""
    with st.expander("Pipeline Logs"):
        if any(pipeline_status.values()):
            st.success("Data pipeline completed successfully!")
            st.write("Steps completed:")
            
            step_names = {
                'data_loaded': '1. Loaded the raw data successfully',
                'synthetic_fields_added': '2. Added synthetic data',
                'data_encrypted': '3. Encrypted the data',
                'database_stored': '4. Stored in database'
            }
            
            for step, completed in pipeline_status.items():
                status_icon = "✅" if completed else "⏳"
                step_name = step_names.get(step, step.replace('_', ' ').title())
                st.write(f"{status_icon} {step_name}")
        else:
            st.info("Pipeline not run yet")

def render_footer():
    """Render the application footer."""
    st.markdown("---")
    st.markdown("*Built with Streamlit • Data encrypted with AES-256 • Database: SQLite*")

# Main application logic
def main():
    """Main function to run the Financial Copilot application."""
    try:
        # Clean up expired temporary messages
        cleanup_expired_messages()

        # --- SHOW PIPELINE LOGS AT THE TOP, ONLY IF DATA IS PROCESSED ---
        if st.session_state.get('data_processed', False):
            render_pipeline_logs(st.session_state.pipeline_status)

        # Render header (no tabs needed)
        render_header()
        
        # Render chat functionality directly (no tabs)
        render_chat_interface()
        
        # Render sidebar controls and get user selections
        user_selections = render_sidebar_controls()
        
        # Handle download requests
        if user_selections['download_encrypted']:
            download_dataframe_as_csv(
                st.session_state.df_encrypted, 
                "encrypted_customer_data.csv",
                "Download Encrypted Data"
            )
        if user_selections['download_decrypted']:
            download_dataframe_as_csv(
                st.session_state.df_decrypted, 
                "decrypted_customer_data.csv",
                "Download Decrypted Data"
            )
        
        # # Render data view
        # render_data_view(
        #     df_encrypted=st.session_state.df_encrypted,
        #     df_decrypted=st.session_state.df_decrypted,
        #     show_decrypted=False,
        #     rows_to_display=10
        # )
        
        # Render database preview if requested
        if user_selections['preview_database']:
            render_database_preview(show_preview=user_selections['preview_database'])
        
        # Render footer
        render_footer()
        
    except Exception as e:
        # Handle any unexpected errors
        st.error(f"Application Error: {str(e)}")
        
        # Show helpful information
        st.info("""
        **Troubleshooting Tips:**
        - Make sure all dependencies are installed: `pip install -r requirements.txt`
        - Check that the data file exists: `data/raw_customer_churn.csv`
        - Ensure you have write permissions for the `db/` directory
        - Try refreshing the page if the error persists
        """)

if __name__ == "__main__":
    main() 