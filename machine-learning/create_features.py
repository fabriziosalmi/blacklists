import requests
import re
import math
import tldextract
import pandas as pd
import whois
import ipinfo
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from sklearn.metrics import classification_report, roc_auc_score, accuracy_score, f1_score, precision_score, recall_score, confusion_matrix
from sklearn.utils import resample
import logging
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed
import joblib
import socket
import os
import numpy as np

# Configure logging for console output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Replace with your actual IPinfo access token
ACCESS_TOKEN = "your_ipinfo_access_token"  
handler = ipinfo.getHandler(ACCESS_TOKEN)

# Constants
BLACKLIST_URL = "https://github.com/fabriziosalmi/blacklists/releases/download/latest/blacklist.txt"
OUTPUT_FILE = 'enhanced_features.csv'
MODEL_FILE = 'best_model_enhanced.pkl'
BATCH_SIZE = 1000
TEST_SIZE = 0.3
RANDOM_STATE = 42
N_ITER = 10
CHUNK_SIZE = 10000

# --- Utility Functions ---
def download_blacklist(url):
    """Downloads a blacklist from a URL.

    Args:
        url (str): The URL of the blacklist.

    Returns:
        list: A list of strings, where each string is a line from the blacklist, or an empty list on failure.
    """
    logging.info(f"Downloading blacklist from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        return [line.decode('utf-8').strip() for line in response.iter_lines()]  # Decode bytes to string and strip whitespace
    except requests.RequestException as e:
        logging.error(f"Error downloading blacklist: {e}")
        return []

def calculate_entropy(domain):
    """Calculates the entropy of a string.

    Args:
        domain (str): The string to calculate the entropy of.

    Returns:
        float: The entropy of the string.
    """
    if not domain:
        return 0  # Handle empty domain case
    probabilities = [float(domain.count(c)) / len(domain) for c in set(domain)]
    return -sum(p * math.log2(p) for p in probabilities)  # Use log2 for entropy in bits

# --- Feature Extraction ---
def extract_features(domain):
    """Extracts features from a domain name.

    Args:
        domain (str): The domain name to extract features from.

    Returns:
        list: A list of extracted features.
    """
    try:
        tld = tldextract.extract(domain)
    except Exception as e:
        logging.warning(f"TLD extraction failed for {domain}: {e}")
        tld = tldextract.ExtractResult('', '', '')  # Provide default values

    try:
        whois_info = whois.whois(domain)
        creation_date = whois_info.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]  # Take the first creation date if multiple exist
        domain_age = (datetime.now() - creation_date).days if creation_date else 0
    except Exception as e:
        logging.warning(f"WHOIS lookup failed for {domain}: {e}")
        domain_age = 0

    try:
        ip = socket.gethostbyname(domain)
        details = handler.getDetails(ip)
        hosting_provider = details.org if details and details.org else "Unknown"
    except socket.gaierror:
        logging.warning(f"Could not resolve IP for {domain}")
        hosting_provider = "Unknown"
        ip = None  # Set ip to None
    except Exception as e:
        logging.warning(f"IP lookup or IPinfo failed for {domain}: {e}")
        hosting_provider = "Unknown"
        ip = None  # Set ip to None

    features = {
        'length': len(domain),
        'subdomains': domain.count('.') - 1,
        'special_chars': int(bool(re.search(r'[-_0-9]', domain))),
        'entropy': calculate_entropy(domain),
        'suspicious_words': int(any(word in domain.lower() for word in ["login", "secure", "bank", "verify", "official"])),
        'tld': tld.suffix,
        'domain_age': domain_age,
        'hosting_provider': hosting_provider,
        'has_ip': int(ip is not None)  # Add a feature indicating if the domain has a resolved IP address
    }
    return features

# --- Data Processing ---
def process_batch(batch, output_file):
    """Processes a batch of domain features and writes them to a CSV file.

    Args:
        batch (list): A list of dictionaries, where each dictionary represents the features of a domain.
        output_file (str): The path to the output CSV file.
    """
    df = pd.DataFrame(batch)
    df = pd.get_dummies(df, columns=['tld', 'hosting_provider'], drop_first=True)  # One-hot encode categorical features
    df.to_csv(output_file, mode='a', index=False, header=not os.path.exists(output_file))

def process_domains_in_stream(url, output_file, batch_size=BATCH_SIZE):
    """Processes domains from a URL in streaming mode, extracting features and writing them to a file.

    Args:
        url (str): The URL of the blacklist.
        output_file (str): The path to the output file.
        batch_size (int): The number of domains to process in each batch.
    """
    logging.info("Starting domain processing in streaming mode...")
    domains = download_blacklist(url)
    if not domains:
        logging.warning("No domains to process.  Exiting.")
        return

    batch = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = []
        for domain in domains:
            try:
                features = extract_features(domain)
                batch.append(features)
            except Exception as e:
                logging.error(f"Error extracting features for {domain}: {e}")

            if len(batch) >= batch_size:
                futures.append(executor.submit(process_batch, batch, output_file))
                batch = []

        if batch:
            futures.append(executor.submit(process_batch, batch, output_file))

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing batches", mininterval=1):
            try:
                future.result()  # Check for exceptions in the completed future
            except Exception as e:
                logging.error(f"Error in batch processing: {e}")

def generate_summary_statistics(file_path, chunk_size=CHUNK_SIZE):
    """Generates summary statistics for a CSV file.

    Args:
        file_path (str): The path to the CSV file.
        chunk_size (int): The number of rows to read in each chunk.

    Returns:
        pandas.DataFrame: A DataFrame containing the summary statistics.
    """
    logging.info("Generating summary statistics...")
    summary = None
    try:
        for chunk in pd.read_csv(file_path, chunksize=chunk_size, on_bad_lines='skip', low_memory=False):
            chunk_summary = chunk.describe(include='all')
            if summary is None:
                summary = chunk_summary
            else:
                summary = pd.concat([summary, chunk_summary], axis=1)

        # Combine and average the summary statistics
        if summary is not None:
            if summary.shape[1] > 1:  # Check if there are multiple chunks
                summary = summary.groupby(level=0, axis=1).mean()
            else:
                summary = summary.iloc[:, 0] # If only one chunk, select the first series

        print(summary)
        return summary

    except Exception as e:
        logging.error(f"Error generating statistics: {e}")
        return None

# --- Model Training and Evaluation ---
def train_model(X_train, y_train):
    """Trains a Gradient Boosting Classifier model.

    Args:
        X_train (pandas.DataFrame): The training features.
        y_train (pandas.Series): The training labels.

    Returns:
        sklearn.ensemble.GradientBoostingClassifier: The trained model.
    """
    logging.info("Starting model training...")
    model = GradientBoostingClassifier(random_state=RANDOM_STATE)
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 7], # Reduced max_depth range
        'learning_rate': [0.01, 0.1] # Reduced learning_rate range
    }
    randomized_search = RandomizedSearchCV(
        model, 
        param_distributions=param_grid, 
        n_iter=N_ITER, 
        cv=3, # Reduced cv for faster training
        verbose=1,  # Add verbose for logging during training
        n_jobs=-1, 
        scoring='f1', 
        random_state=RANDOM_STATE
    )
    randomized_search.fit(X_train, y_train)
    logging.info(f"Best parameters found: {randomized_search.best_params_}")
    logging.info("Model training complete.")
    return randomized_search.best_estimator_

def evaluate_model(model, X_test, y_test):
    """Evaluates a model.

    Args:
        model (sklearn.ensemble.GradientBoostingClassifier): The trained model.
        X_test (pandas.DataFrame): The test features.
        y_test (pandas.Series): The test labels.

    Returns:
        dict: A dictionary containing the evaluation metrics.
    """
    logging.info("Starting model evaluation...")
    try:
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'f1': f1_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred),
            'recall': recall_score(y_test, y_pred),
            'roc_auc': roc_auc_score(y_test, y_proba),
            'confusion_matrix': confusion_matrix(y_test, y_pred).tolist()
        }

        logging.info(f"Evaluation metrics: {metrics}")
        return metrics
    except Exception as e:
        logging.error(f"Error during model evaluation: {e}")
        return {}

# --- Main Execution ---
def main():
    """Main function to execute the script."""
    logging.info("Starting main execution...")

    # 1. Feature Extraction
    process_domains_in_stream(BLACKLIST_URL, OUTPUT_FILE)
    logging.info(f"Feature extraction complete. Data saved to: {OUTPUT_FILE}")

    # 2. Generate Summary Statistics
    summary_stats = generate_summary_statistics(OUTPUT_FILE)
    if summary_stats is None:
        logging.warning("Summary statistics generation failed.")

    # 3. Data Loading and Preprocessing
    try:
        df = pd.read_csv(OUTPUT_FILE, on_bad_lines='skip', low_memory=False)
        # Check if the DataFrame is empty
        if df.empty:
            raise ValueError("DataFrame is empty after reading the CSV file. Check the file content and format.")
        # Try to automatically detect a 'Malicious' column.  If it doesn't exist, create it.
        if 'Malicious' in df.columns:
            y = df['Malicious']
            X = df.drop('Malicious', axis=1)
        else:
            logging.warning("No 'Malicious' column found.  Creating placeholder labels.")
            y = np.random.choice([0, 1], size=len(df), p=[0.5, 0.5])  # Placeholder labels
            X = df # Use all columns as features

        # Ensure that X contains only numeric columns: One-Hot Encode again just in case
        X = pd.get_dummies(X)

        # Align columns: Add missing columns to each other and fill with 0
        train_cols = X.columns
        #X = X.reindex(columns=train_cols, fill_value=0)
        logging.info(f"Number of features: {len(X.columns)}")

    except FileNotFoundError:
        logging.error(f"File not found: {OUTPUT_FILE}")
        return
    except Exception as e:
        logging.error(f"Error loading and preprocessing data: {e}")
        return

    # 4. Handle Class Imbalance
    try:
        X_resampled, y_resampled = resample(X, y, replace=True, n_samples=len(y), random_state=RANDOM_STATE)
    except Exception as e:
        logging.error(f"Error during resampling: {e}")
        return

    # 5. Train-Test Split
    try:
        X_train, X_test, y_train, y_test = train_test_split(X_resampled, y_resampled, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    except Exception as e:
        logging.error(f"Error during train-test split: {e}")
        return

    # 6. Model Training
    try:
        best_model = train_model(X_train, y_train)
    except Exception as e:
        logging.error(f"Error during model training: {e}")
        return

    # 7. Model Evaluation
    try:
        metrics = evaluate_model(best_model, X_test, y_test)
    except Exception as e:
        logging.error(f"Error during model evaluation: {e}")
        return

    # 8. Save Model
    try:
        joblib.dump(best_model, MODEL_FILE)
        logging.info(f"Best model saved to: {MODEL_FILE}")
    except Exception as e:
        logging.error(f"Error saving model: {e}")

    logging.info("Main execution complete.")

if __name__ == "__main__":
    main()
