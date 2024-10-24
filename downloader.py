import os
import sys
import time
import requests
import logging
from urllib.parse import urlparse, unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import deque
import urllib3
import warnings
import argparse
import tempfile
import shutil
from itertools import cycle
from stem.process import launch_tor_with_config

# Suppress only the insecure request warnings from urllib3
warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)


def setup_logging(log_file='dynamic_file_downloader.log'):
    """
    Configures the logging settings.
    Logs are written to both the console and a file.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Capture all levels of logs

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # File handler for detailed logs
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # Console handler for general information
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)  # Adjust as needed (DEBUG, INFO, WARNING, etc.)
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def create_session(retries=100, backoff_factor=1, status_forcelist=(500, 502, 503, 504), proxy=None):
    """
    Creates a requests Session with a retry strategy, custom headers, and optional proxy.

    :param retries: Total number of retry attempts.
    :param backoff_factor: A backoff factor to apply between attempts.
    :param status_forcelist: A set of HTTP status codes that we should force a retry on.
    :param proxy: SOCKS proxy URL (e.g., 'socks5h://localhost:9050').
    :return: Configured requests Session object.
    """
    session = requests.Session()
    session.verify = False

    # Define custom headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/129.0.0.0 Safari/537.36"
    }
    session.headers.update(headers)

    # Define retry strategy
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS"]  # 'method_whitelist' is deprecated
    )

    # Mount the HTTPAdapter with the retry strategy
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    # Set up proxies if provided
    if proxy:
        session.proxies.update({
            'http': proxy,
            'https': proxy
        })

    return session


def sanitize_filename(file_path):
    """
    Sanitizes the filename by removing or replacing invalid characters.
    Only the file name is sanitized; directory separators are preserved.

    :param file_path: The original file path.
    :return: Sanitized file path.
    """
    # Separate directory and filename
    directory, filename = os.path.split(file_path)

    # Remove query parameters or fragments from the filename
    filename = filename.split('?')[0].split('#')[0]

    # Replace invalid characters in the filename
    # Here, we replace '/' and '\\' with '_', but since we've split the path,
    # these characters shouldn't appear in the filename. You can extend this as needed.
    filename = filename.replace('/', '_').replace('\\', '_')

    # Optionally, add more replacements or use a more robust sanitization method
    return os.path.join(directory, filename)


def get_local_path(base_download_dir, file_url):
    """
    Determines the local file path based on the file URL and base download directory.

    :param base_download_dir: The root directory where files will be downloaded.
    :param file_url: The URL of the file to be downloaded.
    :return: Full local path where the file will be saved.
    """
    parsed_url = urlparse(file_url)
    path = unquote(parsed_url.path)  # Decode URL-encoded characters

    # Remove the '/files/' part from the path if present
    if '/files/' in path:
        relative_path = path.split('/files/', 1)[1]
    else:
        relative_path = path.lstrip('/')

    # Construct the full local path
    local_path = os.path.join(base_download_dir, relative_path)

    # Sanitize the filename to prevent issues
    sanitized_path = sanitize_filename(local_path)

    return sanitized_path


def download_file(session, file_url, local_path, chunk_size=1024):
    """
    Downloads a single file from the given URL to the specified local path.

    :param session: The requests Session object with retry strategy and custom headers.
    :param file_url: The URL of the file to be downloaded.
    :param local_path: The local filesystem path where the file will be saved.
    :param chunk_size: The size of each chunk to read from the response (in bytes).
    """
    try:
        # Check if the file already exists
        if os.path.exists(local_path):
            logging.info(f"SKIPPED: File already exists: {local_path}")
            return

        # Make the GET request with streaming
        with session.get(file_url, stream=True, timeout=180) as response:
            response.raise_for_status()  # Raise HTTPError for bad responses

            # Get the total file size for the progress bar
            total_size_in_bytes = int(response.headers.get('content-length', 0))
            block_size = chunk_size  # 1 Kilobyte

            # Ensure the directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Initialize progress bar
            progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True,
                                desc=os.path.basename(local_path), leave=False)

            with open(local_path, 'wb') as file:
                for data in response.iter_content(block_size):
                    file.write(data)
                    progress_bar.update(len(data))
            progress_bar.close()

            if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
                logging.warning(f"WARNING: Downloaded size mismatch for {file_url}")
            else:
                logging.info(f"SUCCESS: Downloaded {file_url} to {local_path}")

    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred while downloading {file_url}: {http_err}")
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error occurred while downloading {file_url}: {conn_err}")
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error occurred while downloading {file_url}: {timeout_err}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Request exception occurred while downloading {file_url}: {req_err}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while downloading {file_url}: {e}")


def monitor_files_txt(files_txt, stop_event, new_urls_queue):
    """
    Monitors the 'files.txt' file for new URLs appended during script execution.

    :param files_txt: Path to the 'files.txt' file.
    :param stop_event: threading.Event object to signal stopping the monitoring.
    :param new_urls_queue: Thread-safe queue to store new URLs.
    """
    try:
        with open(files_txt, 'r', encoding='utf-8') as f:
            # Move to the end of the file
            f.seek(0, os.SEEK_END)

            while not stop_event.is_set():
                line = f.readline()
                if not line:
                    time.sleep(1)  # Wait before trying again
                    continue
                url = line.strip()
                if url:
                    new_urls_queue.append(url)
                    logging.debug(f"New URL detected: {url}")

    except Exception as e:
        logging.error(f"Error while monitoring {files_txt}: {e}")


def print_bootstrap_lines(line):
    if "Bootstrapped " in line:
        logging.debug(line)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Dynamic File Downloader Script")
    parser.add_argument('--input', type=str, default='files.txt', help='Path to the input files.txt')
    parser.add_argument('--output_dir', type=str, default='downloaded_files', help='Directory to save downloaded files')
    parser.add_argument('--log_file', type=str, default='dynamic_file_downloader.log', help='Log file name')
    parser.add_argument('--retries', type=int, default=30, help='Number of retries for requests')
    parser.add_argument('--backoff_factor', type=float, default=1, help='Backoff factor for retries')
    parser.add_argument('--max_workers', type=int, default=10, help='Maximum number of parallel downloads')
    parser.add_argument('--poll_interval', type=float, default=1.0, help='Polling interval in seconds for files.txt')
    parser.add_argument('--base_socks_port', type=int, default=29500, help='Starting port number for Tor SocksPorts')
    parser.add_argument('--base_control_port', type=int, default=39500, help='Starting port number for Tor ControlPorts')
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_file)

    # Initialize Tor instances
    tor_instances = []
    temp_dir = tempfile.mkdtemp()

    try:
        for i in range(args.max_workers):
            socks_port = args.base_socks_port + i
            control_port = args.base_control_port + i
            data_directory = os.path.join(temp_dir, f'tor_data_{i}')
            os.makedirs(data_directory, exist_ok=True)
            logging.info(f"Starting Tor instance {i} on SocksPort {socks_port} and ControlPort {control_port}")
            tor_process = launch_tor_with_config(
                config={
                    'SocksPort': str(socks_port),
                    'ControlPort': str(control_port),
                    'DataDirectory': data_directory,
                },
                init_msg_handler=print_bootstrap_lines,
            )
            tor_instances.append({'process': tor_process, 'socks_port': socks_port, 'control_port': control_port})
    except Exception as e:
        logging.error(f"Failed to start Tor instances: {e}")
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        sys.exit(1)

    # Create proxies
    proxies = [f'socks5h://localhost:{tor_instance["socks_port"]}' for tor_instance in tor_instances]
    proxy_cycle = cycle(proxies)

    # Define the path to files.txt
    files_txt = args.input

    # Define the base directory where files will be downloaded
    base_download_dir = args.output_dir

    # Create a set to keep track of downloaded URLs
    downloaded_urls = set()

    # Read all existing URLs from files.txt
    with open(files_txt, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url:
                downloaded_urls.add(url)

    logging.info(f"Initial load: Found {len(downloaded_urls)} files to download.")

    # Initialize a thread-safe queue for new URLs
    new_urls_queue = deque()

    # Start a separate thread to monitor files.txt for new URLs
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=monitor_files_txt, args=(files_txt, stop_event, new_urls_queue))
    monitor_thread.daemon = True  # Daemonize thread to exit with the main program
    monitor_thread.start()

    # Initialize ThreadPoolExecutor for parallel downloads
    try:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = {}
            try:
                while True:
                    # Submit initial download tasks
                    for url in downloaded_urls.copy():
                        if url not in futures:
                            proxy = next(proxy_cycle)
                            session = create_session(retries=args.retries, backoff_factor=args.backoff_factor,
                                                     status_forcelist=(500, 502, 503, 504), proxy=proxy)
                            future = executor.submit(download_file, session, url, get_local_path(base_download_dir, url))
                            futures[url] = future

                    # Process new URLs from the queue
                    while new_urls_queue:
                        new_url = new_urls_queue.popleft()
                        if new_url not in downloaded_urls:
                            downloaded_urls.add(new_url)
                            proxy = next(proxy_cycle)
                            session = create_session(retries=args.retries, backoff_factor=args.backoff_factor,
                                                     status_forcelist=(500, 502, 503, 504), proxy=proxy)
                            future = executor.submit(download_file, session, new_url, get_local_path(base_download_dir, new_url))
                            futures[new_url] = future

                    # Clean up completed futures
                    done_urls = [url for url, future in futures.items() if future.done()]
                    for url in done_urls:
                        futures.pop(url)

                    time.sleep(args.poll_interval)  # Polling interval

            except KeyboardInterrupt:
                logging.info("INFO: KeyboardInterrupt received. Shutting down gracefully...")
                stop_event.set()
                monitor_thread.join(timeout=5)
                executor.shutdown(wait=False)
                logging.info("INFO: Shutdown complete.")
                sys.exit(0)

            except Exception as e:
                logging.error(f"ERROR: An unexpected error occurred: {e}")
                stop_event.set()
                monitor_thread.join(timeout=5)
                executor.shutdown(wait=False)
                sys.exit(1)

    finally:
        # Shutdown Tor instances
        for i, tor_instance in enumerate(tor_instances):
            tor_process = tor_instance['process']
            logging.info(f"Terminating Tor instance {i}")
            tor_process.terminate()
            tor_process.wait()
            data_directory = os.path.join(temp_dir, f'tor_data_{i}')
            shutil.rmtree(data_directory, ignore_errors=True)
        shutil.rmtree(temp_dir, ignore_errors=True)
        logging.info("All Tor instances terminated.")

    logging.info("All downloads completed.")


if __name__ == "__main__":
    main()
