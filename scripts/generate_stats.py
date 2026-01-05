#!/usr/bin/env python3
"""
Generate daily statistics for the blacklists repository.
This script analyzes the current blacklist, compares with historical data,
and generates statistics for the README.

The script fetches the domain count from the latest GitHub release since
the all.fqdn.blacklist file is not committed to the repository (excluded in .gitignore).
It uses the GitHub API or downloads the release asset as a fallback.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not available, charts will not be generated")


class StatsGenerator:
    """Generate statistics for the blacklists repository."""
    
    # GitHub repository information
    DEFAULT_GITHUB_OWNER = "fabriziosalmi"
    DEFAULT_GITHUB_REPO = "blacklists"
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.stats_dir = self.repo_path / "stats"
        self.stats_file = self.stats_dir / "daily_stats.json"
        self.history_file = self.stats_dir / "history.csv"
        self.chart_file = self.stats_dir / "trend.png"
        
        # Ensure stats directory exists
        self.stats_dir.mkdir(exist_ok=True)
        
        # Detect GitHub repository
        self.github_owner, self.github_repo = self._detect_github_repo()
        
    def _detect_github_repo(self) -> tuple:
        """Detect GitHub owner and repo from git remote."""
        try:
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0 and result.stdout.strip():
                remote_url = result.stdout.strip()
                # Parse owner/repo from GitHub URL
                # Handles both https://github.com/owner/repo and git@github.com:owner/repo
                # Stops at .git suffix or end of string, handles repos with dots in name
                match = re.search(r'github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$', remote_url)
                if match:
                    return match.groups()
        except Exception:
            pass
        
        # Return defaults
        return self.DEFAULT_GITHUB_OWNER, self.DEFAULT_GITHUB_REPO
    
    def count_lines(self, filepath: Path) -> int:
        """Count lines in a file."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0
    
    def count_blacklist_sources(self) -> int:
        """Count number of blacklist sources."""
        sources_file = self.repo_path / "blacklists.fqdn.urls"
        if not sources_file.exists():
            return 0
        
        with open(sources_file, 'r') as f:
            # Count non-empty, non-comment lines
            return sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
    
    def get_domain_count_from_release_asset(self) -> Optional[int]:
        """Download and count lines from the release asset."""
        try:
            # Use detected repository info
            asset_url = f"https://github.com/{self.github_owner}/{self.github_repo}/releases/download/latest/blacklist.txt"
            
            print(f"Downloading blacklist from release to count domains...")
            
            req = urllib.request.Request(asset_url)
            req.add_header('User-Agent', 'blacklists-stats-generator')
            
            count = 0
            with urllib.request.urlopen(req, timeout=30) as response:
                # Read line by line to avoid loading entire file
                for line in response:
                    count += 1
                    # Show progress every 100k lines
                    if count % 100000 == 0:
                        print(f"  Counted {count:,} lines...")
            
            print(f"✓ Counted {count:,} domains from release asset")
            return count
                    
        except Exception as e:
            print(f"Warning: Could not count domains from release asset: {e}")
            return None
    
    def get_domain_count_from_release(self) -> Optional[int]:
        """Get domain count from the latest GitHub release."""
        try:
            # Use detected repository info
            repo_url = f"https://api.github.com/repos/{self.github_owner}/{self.github_repo}/releases/latest"
            
            # Fetch release info
            req = urllib.request.Request(repo_url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'blacklists-stats-generator')
            
            # Add GitHub token if available (from environment)
            github_token = os.environ.get('GITHUB_TOKEN')
            if github_token:
                req.add_header('Authorization', f'Bearer {github_token}')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                release_data = json.loads(response.read().decode('utf-8'))
                
                # Extract domain count from release body
                # Expected format: "Domains: 1234567" (case-insensitive, flexible)
                body = release_data.get('body', '')
                match = re.search(r'Domains?\s*:?\s*(\d+)', body, re.IGNORECASE)
                if match:
                    count = int(match.group(1))
                    print(f"✓ Fetched domain count from GitHub release: {count:,}")
                    return count
                else:
                    print(f"Warning: Could not parse domain count from release body (body length: {len(body)} chars)")
                    # Try downloading the asset as fallback
                    return self.get_domain_count_from_release_asset()
                    
        except Exception as e:
            print(f"Warning: Could not fetch domain count from release API: {e}")
            # Try downloading the asset as fallback
            return self.get_domain_count_from_release_asset()
    
    def get_git_history_count(self, days_ago: int) -> Optional[int]:
        """Get domain count from git history N days ago."""
        try:
            # First try to get from history file
            history = self.load_history()
            target_date = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            # Find the closest date in history
            for entry in reversed(history):
                if entry['date'] <= target_date and entry['total_domains'] > 0:
                    print(f"✓ Found historical count for {days_ago} days ago from history: {entry['total_domains']:,}")
                    return entry['total_domains']
            
            # Fallback to git history
            # Get commit from N days ago
            date_str = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
            
            # Try to get the file content from that date
            result = subprocess.run(
                ['git', 'log', '--before', date_str, '--max-count=1', '--format=%H'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                return None
            
            commit_hash = result.stdout.strip()
            
            # Try to get stats file from that commit
            result = subprocess.run(
                ['git', 'show', f'{commit_hash}:stats/daily_stats.json'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode == 0:
                try:
                    stats = json.loads(result.stdout)
                    if stats.get('total_domains', 0) > 0:
                        return stats['total_domains']
                except:
                    pass
            
            # Try to get blacklist.txt from that commit
            # First check in root, then in blacklist_output
            for path in ['blacklist.txt', 'blacklist_output/blacklist.txt', 'all.fqdn.blacklist']:
                result = subprocess.run(
                    ['git', 'show', f'{commit_hash}:{path}'],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if result.returncode == 0:
                    return len(result.stdout.strip().split('\n'))
            
            return None
            
        except Exception as e:
            print(f"Warning: Could not get git history for {days_ago} days ago: {e}")
            return None
    
    def load_history(self) -> List[Dict]:
        """Load historical statistics."""
        if not self.history_file.exists():
            return []
        
        history = []
        with open(self.history_file, 'r') as f:
            lines = f.readlines()
            if len(lines) > 1:  # Skip header
                for line in lines[1:]:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        try:
                            history.append({
                                'date': parts[0],
                                'total_domains': int(parts[1]),
                                'whitelisted': int(parts[2]) if len(parts) > 2 else 0,
                                'sources': int(parts[3]) if len(parts) > 3 else 0
                            })
                        except ValueError:
                            continue
        return history
    
    def save_history(self, stats: Dict):
        """Append current stats to history."""
        # Load existing history
        history = self.load_history()
        
        # Add current stats
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Remove today's entry if it exists (update)
        history = [h for h in history if h['date'] != today]
        
        # Add new entry
        history.append({
            'date': today,
            'total_domains': stats['total_domains'],
            'whitelisted': stats['whitelisted_domains'],
            'sources': stats['blacklist_sources']
        })
        
        # Keep only last 90 days
        history = history[-90:]
        
        # Write to file
        with open(self.history_file, 'w') as f:
            f.write('date,total_domains,whitelisted,sources\n')
            for entry in history:
                f.write(f"{entry['date']},{entry['total_domains']},{entry['whitelisted']},{entry['sources']}\n")
    
    def generate_chart(self, history: List[Dict]):
        """Generate trend chart."""
        if not HAS_MATPLOTLIB or len(history) < 2:
            return
        
        try:
            dates = [datetime.strptime(h['date'], '%Y-%m-%d') for h in history]
            totals = [h['total_domains'] for h in history]
            
            plt.figure(figsize=(12, 6))
            plt.plot(dates, totals, marker='o', linewidth=2, markersize=4, color='#cc0000')
            plt.title('Blacklist Growth Trend (Last 90 Days)', fontsize=16, fontweight='bold')
            plt.xlabel('Date', fontsize=12)
            plt.ylabel('Total Domains', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            # Format x-axis
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=7))
            plt.xticks(rotation=45, ha='right')
            
            # Format y-axis with thousands separator
            ax = plt.gca()
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
            
            plt.tight_layout()
            plt.savefig(self.chart_file, dpi=150, bbox_inches='tight')
            plt.close()
            
            print(f"✓ Chart generated: {self.chart_file}")
            
        except Exception as e:
            print(f"Warning: Could not generate chart: {e}")
    
    def generate_stats(self) -> Dict:
        """Generate current statistics."""
        print("Generating statistics...")
        
        # Try to get domain count from GitHub release first
        total_domains = self.get_domain_count_from_release()
        
        # Fallback to counting from file if release method fails
        if total_domains is None:
            blacklist_file = self.repo_path / "all.fqdn.blacklist"
            if not blacklist_file.exists():
                # Try alternative locations
                for alt_path in ["blacklist.txt", "blacklist_output/blacklist.txt"]:
                    alt_file = self.repo_path / alt_path
                    if alt_file.exists():
                        blacklist_file = alt_file
                        break
            
            total_domains = self.count_lines(blacklist_file)
            if total_domains == 0:
                print("Warning: Could not determine domain count from any source")
        
        whitelisted = self.count_lines(self.repo_path / "whitelist.txt")
        sources = self.count_blacklist_sources()
        
        # Get historical data
        count_1d = self.get_git_history_count(1)
        count_7d = self.get_git_history_count(7)
        count_30d = self.get_git_history_count(30)
        
        # Calculate changes
        change_1d = total_domains - count_1d if count_1d else 0
        change_7d = total_domains - count_7d if count_7d else 0
        change_30d = total_domains - count_30d if count_30d else 0
        
        # Calculate growth percentages
        growth_1d = (change_1d / count_1d * 100) if count_1d and count_1d > 0 else 0
        growth_7d = (change_7d / count_7d * 100) if count_7d and count_7d > 0 else 0
        growth_30d = (change_30d / count_30d * 100) if count_30d and count_30d > 0 else 0
        
        stats = {
            'generated_at': datetime.now().isoformat(),
            'total_domains': total_domains,
            'whitelisted_domains': whitelisted,
            'blacklist_sources': sources,
            'changes': {
                'daily': {
                    'count': change_1d,
                    'percentage': round(growth_1d, 2)
                },
                'weekly': {
                    'count': change_7d,
                    'percentage': round(growth_7d, 2)
                },
                'monthly': {
                    'count': change_30d,
                    'percentage': round(growth_30d, 2)
                }
            }
        }
        
        print(f"✓ Total domains: {total_domains:,}")
        print(f"✓ Whitelisted: {whitelisted:,}")
        print(f"✓ Sources: {sources}")
        print(f"✓ Daily change: {change_1d:+,} ({growth_1d:+.2f}%)")
        print(f"✓ Weekly change: {change_7d:+,} ({growth_7d:+.2f}%)")
        print(f"✓ Monthly change: {change_30d:+,} ({growth_30d:+.2f}%)")
        
        return stats
    
    def save_stats(self, stats: Dict):
        """Save statistics to JSON file."""
        with open(self.stats_file, 'w') as f:
            json.dump(stats, indent=2, fp=f)
        print(f"✓ Statistics saved to {self.stats_file}")
    
    def run(self):
        """Run the statistics generation."""
        print("=" * 60)
        print("Blacklist Statistics Generator")
        print("=" * 60)
        
        # Generate stats
        stats = self.generate_stats()
        
        # Save stats
        self.save_stats(stats)
        
        # Save to history
        self.save_history(stats)
        
        # Load history and generate chart
        history = self.load_history()
        if len(history) >= 2:
            self.generate_chart(history)
        else:
            print("⚠ Not enough historical data for chart (need at least 2 days)")
        
        print("=" * 60)
        print("✓ Statistics generation complete!")
        print("=" * 60)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate blacklist statistics')
    parser.add_argument('--repo-path', default='.', help='Path to repository')
    parser.add_argument('--test', action='store_true', help='Test mode (dry run)')
    
    args = parser.parse_args()
    
    generator = StatsGenerator(args.repo_path)
    
    if args.test:
        print("Running in test mode...")
        stats = generator.generate_stats()
        print("\nGenerated stats:")
        print(json.dumps(stats, indent=2))
    else:
        generator.run()


if __name__ == '__main__':
    main()
