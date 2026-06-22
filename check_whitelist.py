#!/usr/bin/env python3

import csv
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, MofNCompleteColumn
from rich.table import Table

# Configurazione
INPUT_FILE = "whitelist.txt"
OUTPUT_FILE = "whitelist_report.csv"
MAX_WORKERS = 20  # Aumenta per maggiore velocità
TIMEOUT = 5

console = Console()

def check_domain(domain):
    domain = domain.strip()
    if not domain or domain.startswith("#"):
        return None

    existence = "DOWN"
    http_status = "N/A"

    # 1. Verifica esistenza (DNS)
    try:
        socket.gethostbyname(domain)
        existence = "UP"
    except (socket.gaierror, socket.timeout):
        existence = "DOWN"

    # 2. Verifica risposta HTTP (se DNS è UP)
    if existence == "UP":
        try:
            # Proviamo prima HTTPS, poi HTTP
            for proto in ["https://", "http://"]:
                try:
                    response = requests.get(f"{proto}{domain}", timeout=TIMEOUT, allow_redirects=True)
                    http_status = str(response.status_code)
                    break
                except requests.exceptions.RequestException:
                    continue
            if http_status == "N/A":
                http_status = "ERROR"
        except Exception:
            http_status = "ERROR"
    
    return {
        "domain": domain,
        "existence": existence,
        "http_status": http_status
    }

def main():
    if not socket.getdefaulttimeout():
        socket.setdefaulttimeout(TIMEOUT)

    try:
        with open(INPUT_FILE, "r") as f:
            domains = []
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    domains.append(stripped)
    except FileNotFoundError:
        console.print(f"[red]Errore: {INPUT_FILE} non trovato.[/red]")
        return

    results = []
    
    console.print(f"[bold blue]Inizio verifica di {len(domains)} domini in whitelist...[/bold blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Verifica...", total=len(domains))
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_domain = {executor.submit(check_domain, d): d for d in domains}
            for future in future_to_domain:
                res = future.result()
                if res:
                    results.append(res)
                progress.update(task, advance=1)

    # Scrittura report CSV
    with open(OUTPUT_FILE, "w", newline="") as csvfile:
        fieldnames = ["domain", "existence", "http_status"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    console.print(f"\n[bold green]Verifica completata![/bold green]")
    console.print(f"Report salvato in: [bold cyan]{OUTPUT_FILE}[/bold cyan]")

    # Mostra un piccolo riassunto
    table = Table(title="Riassunto Verifiche (Top 10)")
    table.add_column("Dominio", style="cyan")
    table.add_column("DNS", style="magenta")
    table.add_column("HTTP Status", style="green")

    for res in results[:10]:
        table.add_row(res["domain"], res["existence"], res["http_status"])
    
    console.print(table)

if __name__ == "__main__":
    main()
