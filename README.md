# Dynamic File Downloader

A Python script for dynamically downloading files from URLs listed in a `files.txt` file. The script supports parallel downloads using multiple threads, each with its own Tor instance to ensure anonymity and prevent IP blocking.

## Features

- **Dynamic Monitoring**: Continuously monitors `files.txt` for new URLs and downloads them on the fly.
- **Parallel Downloads**: Utilizes multithreading to download multiple files simultaneously.
- **Tor Integration**: Automatically starts multiple Tor instances, assigning each thread its own proxy for enhanced privacy.
- **Robustness**: Implements retry mechanisms with customizable backoff strategies.
- **Logging**: Detailed logging to both console and file for monitoring progress and troubleshooting.
- **Progress Bars**: Visual feedback for each file being downloaded using `tqdm`.

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Command-Line Arguments](#command-line-arguments)
- [Examples](#examples)
- [Notes](#notes)
- [License](#license)

## Requirements

- **Python**: 3.6 or higher
- **Libraries**:
  - `requests`
  - `urllib3`
  - `tqdm`
  - `stem`
- **Tor**: The Tor executable must be installed and accessible in your system's PATH.

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/FilipPwn/python_tor_downloader.git
   cd dynamic-file-downloader
   ```

2. **Install Python Dependencies**:

   You can install the required Python libraries using `pip`:

   ```bash
   pip install -r requirements.txt
   ```

   **Contents of `requirements.txt`**:

   ```txt
   requests
   urllib3
   tqdm
   stem
   ```

3. **Install Tor**:

   - **Debian/Ubuntu**:

     ```bash
     sudo apt-get update
     sudo apt-get install tor
     ```

   - **macOS (using Homebrew)**:

     ```bash
     brew install tor
     ```

   - **Windows**:

     Download and install the Tor Expert Bundle from the [official website](https://www.torproject.org/download/tor/).

   Ensure that the Tor executable is in your system's PATH. You can verify by running:

   ```bash
   tor --version
   ```

## Usage

1. **Prepare `files.txt`**:

   Create a `files.txt` file in the script directory or specify a custom path using the `--input` argument. List the URLs you wish to download, one per line.

   ```txt
   https://example.com/file1.jpg
   https://example.com/file2.mp4
   ```

2. **Run the Script**:

   ```bash
   python dynamic_file_downloader.py
   ```

3. **Monitor Downloads**:

   The script will display progress bars for each file and log details to both the console and a log file (`dynamic_file_downloader.log` by default).

4. **Add More URLs on the Fly**:

   You can append new URLs to `files.txt` while the script is running. The script will detect new URLs and start downloading them immediately.

## Command-Line Arguments

You can customize the script's behavior using the following command-line arguments:

```bash
python dynamic_file_downloader.py --help
```

```txt
usage: dynamic_file_downloader.py [-h] [--input INPUT] [--output_dir OUTPUT_DIR]
                                  [--log_file LOG_FILE] [--retries RETRIES]
                                  [--backoff_factor BACKOFF_FACTOR]
                                  [--max_workers MAX_WORKERS]
                                  [--poll_interval POLL_INTERVAL]
                                  [--base_socks_port BASE_SOCKS_PORT]
                                  [--base_control_port BASE_CONTROL_PORT]

Dynamic File Downloader Script

optional arguments:
  -h, --help            show this help message and exit
  --input INPUT         Path to the input files.txt (default: files.txt)
  --output_dir OUTPUT_DIR
                        Directory to save downloaded files (default: downloaded_files)
  --log_file LOG_FILE   Log file name (default: dynamic_file_downloader.log)
  --retries RETRIES     Number of retries for requests (default: 10)
  --backoff_factor BACKOFF_FACTOR
                        Backoff factor for retries (default: 1)
  --max_workers MAX_WORKERS
                        Maximum number of parallel downloads (default: 10)
  --poll_interval POLL_INTERVAL
                        Polling interval in seconds for files.txt (default: 1.0)
  --base_socks_port BASE_SOCKS_PORT
                        Starting port number for Tor SocksPorts (default: 9500)
  --base_control_port BASE_CONTROL_PORT
                        Starting port number for Tor ControlPorts (default: 9600)
```

## Examples

### Basic Usage

Download files listed in `files.txt` to the `downloaded_files` directory:

```bash
python dynamic_file_downloader.py
```

### Custom Input and Output Directories

Specify custom paths for the input file and output directory:

```bash
python dynamic_file_downloader.py --input /path/to/my_files.txt --output_dir /path/to/downloads
```

### Increase Parallel Downloads

Increase the number of parallel downloads to 20:

```bash
python dynamic_file_downloader.py --max_workers 20
```

### Adjust Retry Mechanism

Customize the retry behavior:

```bash
python dynamic_file_downloader.py --retries 5 --backoff_factor 0.5
```

### Change Tor Ports

If the default ports conflict with existing services, you can specify different base ports:

```bash
python dynamic_file_downloader.py --base_socks_port 9700 --base_control_port 9800
```

## Notes

- **System Resources**: Starting multiple Tor instances can be resource-intensive. Ensure your system has enough resources (CPU, memory) to handle the number of instances specified by `--max_workers`.
- **Tor Executable Path**: If the Tor executable is not in your system's PATH, you can specify the path by modifying the `launch_tor_with_config` function in the script:

  ```python
  tor_process = launch_tor_with_config(
      tor_cmd='/path/to/tor',
      config={...},
      init_msg_handler=print_bootstrap_lines,
  )
  ```

- **Security Considerations**: Running multiple Tor instances may have security implications. Be aware of Tor's usage policies and ensure compliance.
- **Logging**: Detailed logs are saved in `dynamic_file_downloader.log`. You can adjust the logging levels in the script if needed.

## License

This project is licensed under the [MIT License](LICENSE).

---

**Disclaimer**: This script is intended for educational and lawful purposes only. The use of this script to download copyrighted material or for any illegal activities is strictly prohibited.
