import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import base64

def main():
    st.set_page_config(page_title="Hotel Transaction Reconciler", layout="wide")
    
    # Add custom CSS
    st.markdown("""
        <style>
        .main {
            padding: 2rem;
        }
        .stButton>button {
            width: 100%;
            background-color: #4CAF50;
            color: white;
        }
        .success-text {
            color: #4CAF50;
        }
        .error-text {
            color: #ff0000;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("ABC Hosp Ltd - Transaction Reconciliation")
    st.write("Upload your Opera PMS report and POS report to reconcile transactions")
    
    # File upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload Opera PMS Report")
        opera_file = st.file_uploader("Choose Opera PMS file (Excel or CSV)", 
                                    type=['xlsx', 'csv'])
        
    with col2:
        st.subheader("Upload POS Report")
        pos_file = st.file_uploader("Choose POS report file (Excel or CSV)", 
                                  type=['xlsx', 'csv'])

    if opera_file and pos_file:
        try:
            # Load Opera data
            if opera_file.name.endswith('.xlsx'):
                opera_df = pd.read_excel(opera_file)
            else:
                opera_df = pd.read_csv(opera_file)
                
            # Load POS data
            if pos_file.name.endswith('.xlsx'):
                pos_df = pd.read_excel(pos_file)
            else:
                pos_df = pd.read_csv(pos_file)
            
            # Button to start reconciliation
            if st.button("Reconcile Transactions"):
                results = reconcile_transactions(opera_df, pos_df)
                display_results(results)
                
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")

def reconcile_transactions(opera_df, pos_df):
    """Reconcile transactions between Opera PMS and POS data"""
    
    # Standardize column names (adjust these based on your actual column names)
    opera_df.columns = opera_df.columns.str.lower().str.strip()
    pos_df.columns = pos_df.columns.str.lower().str.strip()
    
    # Ensure amount columns are numeric
    opera_df['amount'] = pd.to_numeric(opera_df['amount'].astype(str).str.replace('[^\d.-]', '', regex=True), errors='coerce')
    pos_df['amount'] = pd.to_numeric(pos_df['amount'].astype(str).str.replace('[^\d.-]', '', regex=True), errors='coerce')
    
    # Initialize results dictionary
    results = {
        'matched': [],
        'unmatched_opera': [],
        'unmatched_pos': [],
        'amount_mismatch': []
    }
    
    # Create copy of dataframes for processing
    opera_unmatched = opera_df.copy()
    pos_unmatched = pos_df.copy()
    
    # Find exact matches
    for _, opera_row in opera_df.iterrows():
        match_found = False
        
        for _, pos_row in pos_df.iterrows():
            if abs(opera_row['amount'] - pos_row['amount']) < 0.01:  # Account for floating point
                results['matched'].append({
                    'opera': opera_row.to_dict(),
                    'pos': pos_row.to_dict(),
                    'amount': opera_row['amount']
                })
                
                # Remove matched transactions from unmatched sets
                opera_unmatched = opera_unmatched[opera_unmatched['amount'] != opera_row['amount']]
                pos_unmatched = pos_unmatched[pos_unmatched['amount'] != pos_row['amount']]
                
                match_found = True
                break
        
        if not match_found:
            # Look for similar amounts (within 5% difference)
            for _, pos_row in pos_df.iterrows():
                difference = abs(opera_row['amount'] - pos_row['amount'])
                if difference > 0 and difference/opera_row['amount'] < 0.05:
                    results['amount_mismatch'].append({
                        'opera': opera_row.to_dict(),
                        'pos': pos_row.to_dict(),
                        'difference': difference
                    })
    
    # Add remaining unmatched transactions
    results['unmatched_opera'] = opera_unmatched.to_dict('records')
    results['unmatched_pos'] = pos_unmatched.to_dict('records')
    
    return results

def display_results(results):
    """Display reconciliation results in a user-friendly format"""
    
    st.header("Reconciliation Results")
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Matched Transactions", len(results['matched']))
    with col2:
        st.metric("Amount Mismatches", len(results['amount_mismatch']))
    with col3:
        st.metric("Unmatched Opera", len(results['unmatched_opera']))
    with col4:
        st.metric("Unmatched POS", len(results['unmatched_pos']))
    
    # Matched Transactions
    st.subheader("Matched Transactions")
    if results['matched']:
        matched_df = pd.DataFrame([{
            'Amount': m['amount'],
            'Opera Transaction ID': m['opera'].get('transaction_id', 'N/A'),
            'POS Transaction ID': m['pos'].get('transaction_id', 'N/A'),
            'Date': m['opera'].get('date', 'N/A')
        } for m in results['matched']])
        st.dataframe(matched_df)
    else:
        st.write("No matched transactions found")
    
    # Amount Mismatches
    st.subheader("Amount Mismatches")
    if results['amount_mismatch']:
        mismatch_df = pd.DataFrame([{
            'Opera Amount': m['opera']['amount'],
            'POS Amount': m['pos']['amount'],
            'Difference': m['difference'],
            'Opera Transaction ID': m['opera'].get('transaction_id', 'N/A'),
            'POS Transaction ID': m['pos'].get('transaction_id', 'N/A')
        } for m in results['amount_mismatch']])
        st.dataframe(mismatch_df)
    else:
        st.write("No amount mismatches found")
    
    # Unmatched Transactions
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Unmatched Opera Transactions")
        if results['unmatched_opera']:
            st.dataframe(pd.DataFrame(results['unmatched_opera']))
        else:
            st.write("No unmatched Opera transactions")
    
    with col2:
        st.subheader("Unmatched POS Transactions")
        if results['unmatched_pos']:
            st.dataframe(pd.DataFrame(results['unmatched_pos']))
        else:
            st.write("No unmatched POS transactions")
    
    # Download results button
    if st.button("Download Reconciliation Report"):
        generate_report(results)

def generate_report(results):
    """Generate and download Excel report"""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Matched transactions
        matched_df = pd.DataFrame([{
            'Amount': m['amount'],
            'Opera Transaction ID': m['opera'].get('transaction_id', 'N/A'),
            'POS Transaction ID': m['pos'].get('transaction_id', 'N/A'),
            'Date': m['opera'].get('date', 'N/A')
        } for m in results['matched']])
        matched_df.to_excel(writer, sheet_name='Matched', index=False)
        
        # Amount mismatches
        mismatch_df = pd.DataFrame([{
            'Opera Amount': m['opera']['amount'],
            'POS Amount': m['pos']['amount'],
            'Difference': m['difference'],
            'Opera Transaction ID': m['opera'].get('transaction_id', 'N/A'),
            'POS Transaction ID': m['pos'].get('transaction_id', 'N/A')
        } for m in results['amount_mismatch']])
        mismatch_df.to_excel(writer, sheet_name='Mismatches', index=False)
        
        # Unmatched transactions
        pd.DataFrame(results['unmatched_opera']).to_excel(writer, sheet_name='Unmatched Opera', index=False)
        pd.DataFrame(results['unmatched_pos']).to_excel(writer, sheet_name='Unmatched POS', index=False)
    
    # Download link
    st.download_button(
        label="Download Excel Report",
        data=buffer,
        file_name=f"reconciliation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.ms-excel"
    )

if __name__ == "__main__":
    main()
