#!/usr/bin/env python3

import os
import platform
import subprocess
import uuid
import shutil
import logging
import sys
import urllib.request
from urllib.error import URLError
import socket
import time
import tqdm  # Rich-compatible progress bar
from rich import print  # Rich's print function
from rich.console import Console
from rich.table import Column, Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.panel import Panel  # Rich panel for framing messages
from rich.tree import Tree  # Rich Tree for hierarchical displays
from rich.logging import RichHandler  # Rich Handler for colorful logging

# Configuration (same as before)
LOGFILE = "setup_script.log"
BLACKLISTS_FILE = "blacklists.fqdn.urls"
AGGREGATED_FILE = "aggregated.fqdn.list"
FINAL_BLACKLIST_FILE = "all.fqdn.blacklist"
INPUT_FILE = "input.txt"
OUTPUT_FILE = "output.txt"
BLACKLIST_TXT = "blacklist.txt"
FILTERED_BLACKLIST_TXT = "filtered_blacklist.txt"


# Initialize Rich Console
console = Console()  # Enable Rich for interactive output

# Logging setup with RichHandler for colorful console output
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, markup=True)]  # Use RichHandler for color & styling
)

log = logging.getLogger("rich") #Use rich for the logger name.

# Define a custom log function to use Rich's print
def rich_log(message, level="info", **kwargs):
    """Logs a message to both the log file and the console using Rich's print."""
    if level == "info":
        log.info(message, extra=kwargs) #RichHandler uses the "extra" kwarg to display rich output
    elif level == "warning":
        log.warning(message, extra=kwargs)
    elif level == "error":
        log.error(message, extra=kwargs)
    elif level == "debug":
        log.debug(message, extra=kwargs)

# Example Usage
# rich_log("[blue]This is blue[/blue] and [bold red]important![/bold red]")
# rich_log("Something [italic]important[/italic] happened.")



def detect_package_manager():
    """Detects the package manager and configures commands."""
    global PACKAGE_MANAGER, UPDATE_CMD, INSTALL_CMD

    if shutil.which("apt-get"):
        PACKAGE_MANAGER = "apt-get"
        UPDATE_CMD = ["sudo", "apt-get", "update"]
        INSTALL_CMD = ["sudo", "apt-get", "install", "-y"]
    elif shutil.which("apk"):
        PACKAGE_MANAGER = "apk"
        UPDATE_CMD = ["sudo", "apk", "update"]
        INSTALL_CMD = ["sudo", "apk", "add", "--no-cache"]
    elif platform.system() == "Darwin":  # macOS check
        PACKAGE_MANAGER = "brew"
        UPDATE_CMD = ["brew", "update"]
        INSTALL_CMD = ["brew", "install"]
    else:
        rich_log("[bold red]Unsupported package manager. Exiting.[/bold red]", level="error")
        sys.exit(1)

    rich_log(f"Detected package manager: [bold green]{PACKAGE_MANAGER}[/bold green]")


def run_command(cmd, check=True):
    """Runs a command and logs the output, using Rich for formatting."""
    cmd_str = " ".join(cmd)
    rich_log(f"Running command: [cyan]{cmd_str}[/cyan]")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check)
        rich_log(f"[green]Stdout:[/green] {result.stdout.strip()}")
        if result.stderr:
            rich_log(f"[yellow]Stderr:[/yellow] {result.stderr.strip()}", level="warning")
        return result
    except subprocess.CalledProcessError as e:
        rich_log(f"[bold red]Command failed with error:[/bold red] {e}", level="error")
        if e.stdout:
            rich_log(f"[red]Stdout:[/red] {e.stdout}", level="error")
        if e.stderr:
            rich_log(f"[red]Stderr:[/red] {e.stderr}", level="error")
        raise  # Re-raise
    except FileNotFoundError as e:
        rich_log(f"[bold red]Command not found:[/bold red] {e}", level="error")
        raise
    except Exception as e:
        rich_log(f"[bold red]An unexpected error occurred:[/bold red] {e}", level="error")
        raise


def update_and_install():
    """Updates the system and installs Python 3 and pip."""
    rich_log("[bold blue]Updating system and installing Python 3...[/bold blue]")
    try:
        run_command(UPDATE_CMD)
    except Exception:
        rich_log("[bold red]Failed to update system. Exiting.[/bold red]", level="error")
        sys.exit(1)

    try:
        run_command(INSTALL_CMD + ["python3"])

        if PACKAGE_MANAGER == "apt-get":
            try:
                run_command(["sudo", "ln", "-sf", "/usr/bin/python3", "/usr/bin/python"])
            except Exception:
                rich_log("[yellow]Failed to create symbolic link for python3. This may not be an issue.[/yellow]", level="warning")

        if not shutil.which("pip3"):
            rich_log("[bold yellow]pip3 not found, installing...[/bold yellow]")
            if PACKAGE_MANAGER == "apt-get":
                run_command(INSTALL_CMD + ["python3-pip"])
            else:
                rich_log("[bold red]No pip package found for your package manager. Please install pip manually. Exiting.[/bold red]", level="error")
                sys.exit(1)

        rich_log("[bold blue]Ensuring pip and setuptools are up to date...[/bold blue]")
        run_command(["python3", "-m", "ensurepip", "--upgrade"])
        run_command(["pip3", "install", "--no-cache-dir", "--upgrade", "pip", "setuptools", "tldextract", "tqdm"])
    except Exception:
        rich_log("[bold red]Failed to install Python 3 or pip. Exiting.[/bold red]", level="error")
        sys.exit(1)


def install_additional_packages():
    """Installs additional required packages."""
    packages = ["pv", "ncftp"]

    if PACKAGE_MANAGER == "brew":
        packages = ["coreutils", "wget"]
        try:
            run_command(INSTALL_CMD + ["ncftp"])
            ncftp_installed = True
        except Exception:
            rich_log("[yellow]ncftp not found on brew. Proceeding without it (Optional Package).[/yellow]", level="warning")
            ncftp_installed = False

    try:
        for package in packages:
            rich_log(f"Installing package: [bold magenta]{package}[/bold magenta]")
            run_command(INSTALL_CMD + [package])
    except Exception:
        rich_log("[bold red]Failed to install package(s). Exiting.[/bold red]", level="error")
        sys.exit(1)


def download_url(url, progress):
    """Downloads a URL and saves it to a randomly named file."""
    random_filename = str(uuid.uuid4())
    output_filename = f"{random_filename}.fqdn.list"
    task_id = progress.add_task(f"[cyan]Downloading:[/cyan] {url.split('//')[-1][:40]}...", total=100)  # Add task to progress bar

    try:
        if shutil.which("wget"):
            download_cmd = ["wget", "-q", "--progress=bar:force", "-O", output_filename, url]
        elif shutil.which("curl"):
            download_cmd = ["curl", "-s", "-o", output_filename, url]
        else:
            rich_log("[bold red]wget or curl not found. Exiting.[/bold red]", level="error")
            sys.exit(1)

        rich_log(f"Downloading blacklist: {url} -> {output_filename}")
        #Use a progress bar for the download.  Note this implementation works best with wget.
        #Curl will just show 100% at the end
        with subprocess.Popen(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            while True:
                output = process.stderr.readline().decode('utf-8').strip()
                if output == '' and process.poll() is not None:
                    break
                if "ETA" in output and "%" in output:  # Crude, but works for wget's output
                    try:
                        percent_complete = int(output.split("%")[0])
                        progress.update(task_id, advance=percent_complete - progress.tasks[task_id].completed)  # Update progress
                    except ValueError:
                        pass

        process.wait() #Make sure it exits.

        if process.returncode != 0:
            rich_log(f"[bold red]Download failed for: {url}[/bold red]", level="error")
            progress.update(task_id, completed=100) #Make sure it hits 100% even if it failed.
            return False

    except Exception as e:
        rich_log(f"[bold red]Failed to download:[/bold red] {url} - {e}", level="error")
        progress.update(task_id, completed=100) #Make sure it hits 100% even if it failed.
        return False

    progress.update(task_id, completed=100)  # Mark as complete
    return True

def manage_downloads():
    """Downloads all URLs from the list and aggregates the files, using Rich."""
    if not os.path.isfile(BLACKLISTS_FILE):
        rich_log(f"[bold red]File {BLACKLISTS_FILE} not found. Exiting.[/bold red]", level="error")
        sys.exit(1)

    rich_log("[bold blue]Starting downloads...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console  #Use the Rich console
    ) as progress: #Use Rich progress bar
        with open(BLACKLISTS_FILE, 'r') as f:
            urls = [line.strip() for line in f]

        download_results = []
        for url in urls:
            download_results.append(download_url(url, progress))

    if not any(download_results):
        rich_log("[bold red]No downloads were successful. Check network connectivity and URL list. Exiting.[/bold red]", level="error")
        sys.exit(1)

    rich_log("[bold blue]Aggregating blacklists...[/bold blue]")

    try:
        with open(AGGREGATED_FILE, "w") as outfile:
            pass

        rich_log("Files in current directory:")
        run_command(["ls", "-l"])

        files_to_aggregate = [f for f in os.listdir(".") if f.endswith(".fqdn.list") and f != AGGREGATED_FILE]

        if not files_to_aggregate:
            rich_log("[bold red]No *.fqdn.list files found. Check your download URLs and file permissions. Exiting.[/bold red]", level="error")
            sys.exit(1)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console #Use Rich Console
        ) as progress:
            aggregate_task = progress.add_task("[green]Aggregating files...[/green]", total=len(files_to_aggregate)) # Add Task

            for file in files_to_aggregate:
                try:
                    with open(file, "r") as infile, open(AGGREGATED_FILE, "a") as outfile:
                        rich_log(f"Processing file: {file}")
                        shutil.copyfileobj(infile, outfile)
                except FileNotFoundError:
                    rich_log(f"[yellow]File not found: {file}. Skipping.[/yellow]", level="warning")
                except Exception as e:
                    rich_log(f"[bold red]Error processing file {file}: {e}[/bold red]", level="error")

                progress.update(aggregate_task, advance=1)  #Update progress

        run_command(["sort", "-u", AGGREGATED_FILE, "-o", FINAL_BLACKLIST_FILE])

        if os.stat(FINAL_BLACKLIST_FILE).st_size == 0:
            rich_log("[bold red]all.fqdn.blacklist is empty after sort. Check input data and sort command. Exiting.[/bold red]", level="error")
            sys.exit(1)

        rich_log("[bold blue]Cleanup: removing source files...[/bold blue]")
        for file in os.listdir("."):
            if file.endswith(".fqdn.list"):
                try:
                    os.remove(file)
                except OSError as e:
                    rich_log(f"[yellow]Error deleting file {file}: {e}[/yellow]", level="warning")

        try:
            os.remove(AGGREGATED_FILE)
        except OSError as e:
            rich_log(f"[yellow]Error deleting file {AGGREGATED_FILE}: {e}[/yellow]", level="warning")

    except Exception as e:
        rich_log(f"[bold red]An error occurred during aggregation: {e}[/bold red]", level="error")
        sys.exit(1)


def sanitize_and_whitelist():
    """Sanitizes and whitelists the downloaded blacklists."""
    rich_log("[bold blue]Sanitizing blacklists...[/bold blue]")

    try:
        os.rename(FINAL_BLACKLIST_FILE, INPUT_FILE)
    except FileNotFoundError:
        rich_log(f"[bold red]Could not find {FINAL_BLACKLIST_FILE} to rename to {INPUT_FILE}[/bold red]", level="error")
        sys.exit(1)

    if os.path.isfile("sanitize.py"):
        rich_log("[bold green]Running sanitize.py...[/bold green]")
        try:
            run_command(["python", "sanitize.py"])
        except Exception:
            rich_log("[bold red]Sanitization script failed. Exiting.[/bold red]", level="error")
            sys.exit(1)
        try:
            os.rename(OUTPUT_FILE, FINAL_BLACKLIST_FILE)
        except FileNotFoundError:
            rich_log(f"[bold red]Could not find {OUTPUT_FILE} to rename to {FINAL_BLACKLIST_FILE}[/bold red]", level="error")
            sys.exit(1)

    else:
        rich_log("[yellow]sanitize.py not found. Skipping sanitation.[/yellow]", level="warning")

    rich_log("[bold blue]Removing whitelisted domains...[/bold blue]")
    try:
        os.rename(FINAL_BLACKLIST_FILE, BLACKLIST_TXT)
    except FileNotFoundError:
        rich_log(f"[bold red]Could not find {FINAL_BLACKLIST_FILE} to rename to {BLACKLIST_TXT}[/bold red]", level="error")
        sys.exit(1)

    if os.path.isfile("whitelist.py"):
        rich_log("[bold green]Running whitelist.py...[/bold green]")
        try:
            run_command(["python", "whitelist.py"])
        except Exception:
            rich_log("[bold red]Whitelist script failed. Exiting.[/bold red]", level="error")
            sys.exit(1)

        try:
            os.rename(FILTERED_BLACKLIST_TXT, FINAL_BLACKLIST_FILE)
        except FileNotFoundError:
            rich_log(f"[bold red]Could not find {FILTERED_BLACKLIST_TXT} to rename to {FINAL_BLACKLIST_FILE}[/bold red]", level="error")
            sys.exit(1)
    else:
        rich_log("[yellow]whitelist.py not found. Skipping whitelist filtering.[/yellow]", level="warning")

    try:
        os.remove(BLACKLIST_TXT)
        os.remove(INPUT_FILE)
    except FileNotFoundError as e:
        rich_log(f"[yellow]File not found during cleanup: {e}[/yellow]", level="warning")
    except OSError as e:
        rich_log(f"[yellow]Error deleting file during cleanup: {e}[/yellow]", level="warning")

def main():
    """Main routine."""
    console.rule("[bold blue]Starting Setup Script[/bold blue]")  # Rich rule for visual separation
    detect_package_manager()
    update_and_install()
    install_additional_packages()
    manage_downloads()
    sanitize_and_whitelist()
    try:
        with open(FINAL_BLACKLIST_FILE, 'r') as f:
            total_lines_new = sum(1 for _ in f)
    except FileNotFoundError:
        total_lines_new = 0

    rich_log(f"[bold green]Total domains:[/bold green] [bold cyan]{total_lines_new}[/bold cyan] 🌍.")
    console.rule("[bold blue]Setup Script Complete[/bold blue]")

if __name__ == "__main__":
    main()