#!/usr/bin/env python3
"""
Update README.md with daily statistics.
This script reads the generated statistics and updates the README file
while preserving its existing style and content.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class ReadmeUpdater:
    """Update README with statistics."""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.readme_file = self.repo_path / "README.md"
        self.stats_file = self.repo_path / "stats" / "daily_stats.json"
        self.chart_file = self.repo_path / "stats" / "trend.png"
        
    def load_stats(self) -> Optional[Dict]:
        """Load statistics from JSON file."""
        if not self.stats_file.exists():
            print(f"Error: Statistics file not found: {self.stats_file}")
            return None
        
        with open(self.stats_file, 'r') as f:
            return json.load(f)
    
    def format_number(self, num: int) -> str:
        """Format number with thousands separator."""
        return f"{num:,}"
    
    def format_change(self, count: int, percentage: float) -> str:
        """Format change with sign and percentage."""
        sign = "+" if count >= 0 else ""
        emoji = "📈" if count > 0 else "📉" if count < 0 else "➡️"
        return f"{emoji} {sign}{self.format_number(count)} ({sign}{percentage:.2f}%)"
    
    def generate_stats_section(self, stats: Dict) -> str:
        """Generate the statistics section for README."""
        updated_at = datetime.fromisoformat(stats['generated_at']).strftime('%Y-%m-%d %H:%M UTC')
        
        # Check if chart exists
        chart_line = ""
        if self.chart_file.exists():
            chart_line = f"\n![Trend Chart](stats/trend.png)\n"
        
        section = f"""<!-- STATS_START -->
## 📊 Daily Statistics

**Last Updated**: {updated_at}

| Metric | Value |
|--------|-------|
| 🎯 **Total Domains** | **{self.format_number(stats['total_domains'])}** |
| ✅ **Whitelisted** | {self.format_number(stats['whitelisted_domains'])} |
| 📚 **Sources** | {stats['blacklist_sources']} |
| 📅 **Daily Change** | {self.format_change(stats['changes']['daily']['count'], stats['changes']['daily']['percentage'])} |
| 📅 **Weekly Change** | {self.format_change(stats['changes']['weekly']['count'], stats['changes']['weekly']['percentage'])} |
| 📅 **Monthly Change** | {self.format_change(stats['changes']['monthly']['count'], stats['changes']['monthly']['percentage'])} |
{chart_line}
> 🤖 *Statistics are automatically updated daily at midnight UTC*

<!-- STATS_END -->"""
        
        return section
    
    def update_badges(self, content: str, stats: Dict) -> str:
        """Update badge values in README."""
        # Update blacklisted badge
        content = re.sub(
            r'blacklisted-\d+',
            f"blacklisted-{stats['total_domains']}",
            content
        )
        
        # Update whitelisted badge
        content = re.sub(
            r'whitelisted-\d+',
            f"whitelisted-{stats['whitelisted_domains']}",
            content
        )
        
        # Update blacklists count badge
        content = re.sub(
            r'blacklists-\d+',
            f"blacklists-{stats['blacklist_sources']}",
            content
        )
        
        return content
    
    def update_readme(self, dry_run: bool = False) -> bool:
        """Update README with statistics."""
        # Load stats
        stats = self.load_stats()
        if not stats:
            return False
        
        # Read current README
        if not self.readme_file.exists():
            print(f"Error: README not found: {self.readme_file}")
            return False
        
        with open(self.readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Generate new stats section
        new_stats = self.generate_stats_section(stats)
        
        # Check if stats section exists
        if '<!-- STATS_START -->' in content and '<!-- STATS_END -->' in content:
            # Replace existing stats section
            pattern = r'<!-- STATS_START -->.*?<!-- STATS_END -->'
            updated_content = re.sub(pattern, new_stats, content, flags=re.DOTALL)
            print("✓ Updated existing statistics section")
        else:
            # Insert stats section after badges (line 18)
            # Find the badges line
            lines = content.split('\n')
            insert_index = None
            
            for i, line in enumerate(lines):
                if 'Static Badge' in line and 'blacklisted' in line:
                    insert_index = i + 1
                    break
            
            if insert_index is None:
                print("Warning: Could not find badges line, appending stats at the end of header")
                # Insert after first header
                for i, line in enumerate(lines):
                    if line.startswith('## '):
                        insert_index = i
                        break
            
            if insert_index is not None:
                lines.insert(insert_index, new_stats)
                updated_content = '\n'.join(lines)
                print("✓ Inserted new statistics section")
            else:
                print("Error: Could not find suitable location for stats")
                return False
        
        # Update badges
        updated_content = self.update_badges(updated_content, stats)
        print("✓ Updated badges")
        
        if dry_run:
            print("\n" + "=" * 60)
            print("DRY RUN - Would update README with:")
            print("=" * 60)
            print(new_stats)
            print("=" * 60)
            return True
        
        # Write updated README
        with open(self.readme_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
        
        print(f"✓ README updated: {self.readme_file}")
        return True
    
    def update_hourly_to_daily(self) -> bool:
        """Update 'Hourly' references to 'Daily' in README."""
        if not self.readme_file.exists():
            return False
        
        with open(self.readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace hourly with daily
        updated = content.replace('Hourly updated', 'Daily updated')
        updated = updated.replace('Hourly Updates', 'Daily Updates')
        updated = updated.replace('**Hourly Updates**', '**Daily Updates**')
        
        if updated != content:
            with open(self.readme_file, 'w', encoding='utf-8') as f:
                f.write(updated)
            print("✓ Updated 'Hourly' to 'Daily' references")
            return True
        
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update README with statistics')
    parser.add_argument('--repo-path', default='.', help='Path to repository')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (do not write)')
    parser.add_argument('--update-schedule', action='store_true', 
                       help='Update hourly to daily references')
    
    args = parser.parse_args()
    
    updater = ReadmeUpdater(args.repo_path)
    
    print("=" * 60)
    print("README Statistics Updater")
    print("=" * 60)
    
    if args.update_schedule:
        updater.update_hourly_to_daily()
    
    success = updater.update_readme(dry_run=args.dry_run)
    
    print("=" * 60)
    if success:
        print("✓ README update complete!")
    else:
        print("✗ README update failed!")
        sys.exit(1)
    print("=" * 60)


if __name__ == '__main__':
    main()
