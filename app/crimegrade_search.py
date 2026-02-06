import json
import logging
import os
import random
import time
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from urllib.parse import quote
from pathlib import Path
from dotenv import load_dotenv
import urllib3

# Suppress SSL warnings for Bright Data proxy
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# --- Constants ---
# Bright Data Web Unlocker configuration
BRIGHTDATA_HOST = os.getenv('BRIGHTDATA_HOST', 'brd.superproxy.io')
BRIGHTDATA_PORT = int(os.getenv('BRIGHTDATA_PORT', '33335'))
BRIGHTDATA_USERNAME = os.getenv('BRIGHTDATA_USERNAME')
BRIGHTDATA_PASSWORD = os.getenv('BRIGHTDATA_PASSWORD')

REQUEST_TIMEOUT = 60 # Request timeout in seconds
MAX_RETRIES = 3 # Max retries for rate limiting or other transient errors

# --- Logging Setup ---
# Configure logging more centrally
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# --- Helper Function for Bright Data Requests ---
def _make_brightdata_request(target_url: str, retry_count=0) -> Optional[requests.Response]:
    """Makes a request to the target URL via Bright Data Web Unlocker with retries."""
    if not BRIGHTDATA_USERNAME or not BRIGHTDATA_PASSWORD:
        logger.error("Bright Data credentials not configured")
        return None

    # Encode password in case it contains special characters
    encoded_password = quote(BRIGHTDATA_PASSWORD, safe='')
    proxy_url = f"http://{BRIGHTDATA_USERNAME}:{encoded_password}@{BRIGHTDATA_HOST}:{BRIGHTDATA_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

    logger.info(f"Attempt {retry_count + 1}/{MAX_RETRIES}: Requesting {target_url} via Bright Data")

    try:
        response = requests.get(
            target_url,
            proxies=proxies,
            verify=False,
            timeout=REQUEST_TIMEOUT
        )

        # Check response status code
        if response.status_code == 429:
            # Rate limited
            logger.warning(f"Rate limited (429) for {target_url}. Attempt {retry_count + 1}/{MAX_RETRIES}.")
            if retry_count < MAX_RETRIES:
                wait_time = (2 ** retry_count) + random.uniform(0.5, 1.5) # Exponential backoff
                logger.warning(f"Retrying {target_url} in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                return _make_brightdata_request(target_url, retry_count + 1)
            else:
                logger.error(f"Failed {target_url} after {MAX_RETRIES} retries due to rate limit (429).")
                return None
        elif response.status_code == 403:
             logger.error(f"Received 403 Forbidden for {target_url}. Check Bright Data credentials or zone settings.")
             return None
        elif response.status_code >= 500:
            # Server error
             logger.warning(f"Server error ({response.status_code}) for {target_url}. Attempt {retry_count + 1}/{MAX_RETRIES}.")
             if retry_count < MAX_RETRIES:
                 wait_time = (2 ** retry_count) + random.uniform(0.5, 1.5)
                 logger.warning(f"Retrying {target_url} in {wait_time:.2f} seconds...")
                 time.sleep(wait_time)
                 return _make_brightdata_request(target_url, retry_count + 1)
             else:
                 logger.error(f"Failed {target_url} after {MAX_RETRIES} retries due to server error ({response.status_code}).")
                 return None

        response.raise_for_status()

        logger.info(f"Successfully received response via Bright Data for {target_url} (status: {response.status_code})")
        return response

    except requests.exceptions.Timeout:
        logger.warning(f"Request timed out for {target_url}. Attempt {retry_count + 1}/{MAX_RETRIES}.")
        if retry_count < MAX_RETRIES:
            time.sleep(1)
            return _make_brightdata_request(target_url, retry_count + 1)
        else:
             logger.error(f"Failed {target_url} after {MAX_RETRIES} retries due to timeout.")
             return None
    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else 'N/A'
        logger.error(f"Request failed for {target_url}. Status: {status_code}. Error: {e}")
        return None


# --- Main Scraping Function ---
def search_crime_grade(zipcode: str) -> Optional[Dict[str, str]]:
    """Fetches and parses crime grade data for a zipcode using Bright Data."""
    target_url = f'https://crimegrade.org/safest-places-in-{zipcode}/'
    logger.info(f"Processing zipcode: {zipcode}")

    response = _make_brightdata_request(target_url) # Use the helper

    if response is None or response.status_code != 200:
         # If helper returned None or reported an issue that wasn't retried
         logger.error(f"Failed to get successful response for zipcode {zipcode} via Bright Data.")
         return None

    # If we get here, Bright Data returned a 200, indicating it successfully fetched *something*
    # Now we parse the content it returned.
    try:
        # Parse the HTML from the response content
        soup = BeautifulSoup(response.content, 'html.parser') # Use response.content for bytes

        # Find the crime grade container
        # Using the same selectors as before
        crime_section = soup.select_one('div.one_half:nth-child(1)')

        if not crime_section:
            # It's possible ScraperAPI got a CAPTCHA page or different layout
            logger.warning(f"Could not find crime section in response for zipcode {zipcode}. URL: {target_url}")
            # Log a snippet of the response for debugging
            logger.debug(f"Response snippet for {zipcode}: {response.text[:500]}")
            return None

        # Extract overall grade
        overall_grade_element = crime_section.select_one('p.overallGradeLetter')
        overall_grade = overall_grade_element.text.strip() if overall_grade_element else "N/A"
        if overall_grade == "N/A":
             logger.warning(f"Could not find overall grade element for zipcode {zipcode}")

        logger.info(f"Found overall grade for {zipcode}: {overall_grade}")

        # Initialize result dictionary
        results = {"overall": overall_grade}

        # Extract specific crime grades from the table
        grade_rows = crime_section.select('table.gradeComponents tr')

        for row in grade_rows:
            # Extract crime type and grade
            crime_type_element = row.select_one('td:nth-child(1) div.mtr-cell-content')
            grade_element = row.select_one('td:nth-child(2) div.mtr-cell-content span')

            if crime_type_element and grade_element:
                crime_type = crime_type_element.text.strip().replace(' Grade', '').lower()
                grade = grade_element.text.strip()
                results[crime_type] = grade
                # logger.info(f"Found {crime_type} grade: {grade}") # Reduce log verbosity
            else:
                 logger.warning(f"Could not extract crime type/grade from row in {zipcode}")


        if len(results) <= 1 and overall_grade == "N/A": # Check if we actually found any data
             logger.warning(f"Found no specific crime grades for zipcode {zipcode}")
             # Return None if no useful data was extracted
             return None

        return results

    except Exception as e:
        # Catch errors during parsing
        logger.error(f"Error parsing crime data for {zipcode}: {e}")
        logger.debug(f"Response content causing parsing error for {zipcode}: {response.text[:500]}")
        return None


# --- Processing Function (Modified for Concurrency) ---
def process_zipcodes(zipcodes: List[str], max_workers: int = 10, save_batch_size: int = 50) -> Dict[str, Optional[Dict[str, str]]]:
    """
    Process zipcodes concurrently using ScraperAPI, load existing data,
    and save results periodically.
    """
    results = {}
    failed_zipcodes_log = 'data/failed_zipcodes_crime.txt'
    output_json_file = 'data/crime_grades.json'
    # Lock for thread-safe access to results dictionary and file writing
    lock = threading.Lock()
    processed_in_batch = 0 # Counter for periodic saving

    # Load existing results (outside the lock initially)
    if os.path.exists(output_json_file):
        try:
            with open(output_json_file, 'r') as file:
                results = json.load(file)
            logger.info(f"Loaded {len(results)} existing crime grade results from {output_json_file}")
        except (json.JSONDecodeError, IOError) as e:
             logger.error(f"Error loading existing results from {output_json_file}: {e}. Starting fresh.")
             results = {}
    else:
        logger.info(f"No existing results file found at {output_json_file}, starting fresh.")

    # Prepare list of zipcodes to process
    zipcodes_to_process = []
    processed_count = 0
    for zipcode_raw in zipcodes:
         zipcode = str(zipcode_raw).strip()
         if not zipcode:
             continue
         # Check existing results (read-only access, no lock needed here)
         if zipcode in results and results[zipcode] is not None:
             processed_count += 1
             continue
         zipcodes_to_process.append(zipcode)

    logger.info(f"Total zipcodes: {len(zipcodes)}. Already processed: {processed_count}. To process: {len(zipcodes_to_process)}")

    if not zipcodes_to_process:
        logger.info("No new zipcodes to process.")
        return results

    total_failed = 0 # Track failures within this run

    # Use ThreadPoolExecutor for concurrent scraping
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Map future back to zipcode
        future_to_zipcode = {
            executor.submit(search_crime_grade, zipcode): zipcode
            for zipcode in zipcodes_to_process
        }

        # Process futures as they complete
        progress_bar = tqdm(as_completed(future_to_zipcode), total=len(zipcodes_to_process), desc="Fetching Crime Grades")
        for future in progress_bar:
            zipcode = future_to_zipcode[future]
            current_batch_size = 0 # Local variable to track batch size inside loop

            try:
                # Get the result from the future (the crime grade dict or None)
                crime_data = future.result()

                # --- Critical Section Start ---
                with lock:
                    if crime_data:
                        results[zipcode] = crime_data
                    else:
                        # Store None to indicate failure and avoid reprocessing
                        results[zipcode] = None
                        total_failed += 1
                        # Log failed zipcode to the separate file
                        try:
                            with open(failed_zipcodes_log, 'a') as f:
                                f.write(f"{zipcode}\n")
                        except IOError as e:
                            logger.error(f"Could not write to failed zipcodes log {failed_zipcodes_log}: {e}")

                    processed_in_batch += 1
                    current_batch_size = processed_in_batch # Capture size for logging

                    # Save progress periodically inside the lock
                    if processed_in_batch >= save_batch_size:
                        logger.info(f"Saving batch of {processed_in_batch} results...")
                        try:
                            with open(output_json_file, 'w') as f:
                                json.dump(results, f, indent=2)
                            processed_in_batch = 0 # Reset batch counter after successful save
                        except IOError as e:
                             logger.error(f"Error writing batch data to {output_json_file}: {e}")
                             # Keep batch counter as is, will try saving again next time or at the end
                # --- Critical Section End ---

            except Exception as exc:
                # Catch exceptions from future.result() itself (should be rare if search_crime_grade handles its own errors)
                logger.error(f"[ERROR] Processing zipcode {zipcode} generated an exception: {exc}")
                # --- Critical Section Start ---
                with lock:
                    results[zipcode] = None # Mark as failed
                    total_failed += 1
                    try:
                        with open(failed_zipcodes_log, 'a') as f:
                            f.write(f"{zipcode} (exception)\n")
                    except IOError as e:
                        logger.error(f"Could not write to failed zipcodes log {failed_zipcodes_log}: {e}")
                # --- Critical Section End ---

            # Update tqdm description (optional)
            # progress_bar.set_postfix_str(f"Last: {zipcode}, Batch: {current_batch_size}/{save_batch_size}")


    # --- Final Save ---
    # Acquire lock one last time to save any remaining results and get final counts
    with lock:
        final_success_count = sum(1 for res in results.values() if res is not None)
        logger.info(f"Scraping complete. Success: {final_success_count}, Failed this run: {total_failed}. Total entries in file: {len(results)}")
        logger.info(f"Saving final data to {output_json_file}...")
        try:
            with open(output_json_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info("Final data saved successfully.")
        except IOError as e:
            logger.error(f"Error writing final data to {output_json_file}: {e}")

    return results


# --- Main Execution Block ---
if __name__ == "__main__":
    # Ensure data directory exists
    if not os.path.exists('data'):
        os.makedirs('data')

    zipcode_file = 'data/ca_zipcodes.txt' # Make sure this file exists
    if not os.path.exists(zipcode_file):
         logger.error(f"Zipcode file not found: {zipcode_file}")
         # Create a dummy file for testing if needed
         # with open(zipcode_file, 'w') as f:
         #     f.write("30301\n30302\n30329\n99999\n") # Add a likely invalid one too
         # exit() # Or exit if file is mandatory

    try:
        with open(zipcode_file, 'r') as file:
            zipcodes_from_file = file.readlines()
        logger.info(f"Read {len(zipcodes_from_file)} lines from {zipcode_file}")
    except IOError as e:
        logger.error(f"Error reading zipcode file {zipcode_file}: {e}")
        zipcodes_from_file = [] # Ensure it's a list

    if zipcodes_from_file:
        # Set desired number of worker threads
        num_workers = 5 # Adjust as needed based on ScraperAPI plan and system resources
        batch_size = 5 # Adjust how often to save

        final_results = process_zipcodes(zipcodes_from_file, max_workers=num_workers, save_batch_size=batch_size)
        logger.info(f"Processing complete. Final dictionary size: {len(final_results)}")
    else:
        logger.warning("No zipcodes found to process.")

    # Final save is handled within process_zipcodes now

    # # Example test for a single zipcode
    # logger.info("Testing single zipcode...")
    # single_result = search_crime_grade("30329")
    # logger.info(f"Test result for 30329: {single_result}")
