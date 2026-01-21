#!/usr/bin/env python3
"""
Apply Experiment Overview Template to Existing Dashboards

This script adds the standardized experiment overview section (service graph,
status panels, risk metrics) to existing chaos experiment dashboards.

Usage:
    python apply_template.py <dashboard_file> [--output <output_file>] [--dry-run]

Examples:
    # Apply template to a dashboard (overwrites original)
    python apply_template.py ../extensive_postgres_dashboard.json

    # Save to a different file
    python apply_template.py ../extensive_postgres_dashboard.json --output ../new_dashboard.json

    # Preview changes without modifying files
    python apply_template.py ../extensive_postgres_dashboard.json --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List


def load_json(file_path: str) -> Dict:
    """Load JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)


def save_json(data: Dict, file_path: str) -> None:
    """Save JSON file with proper formatting."""
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved: {file_path}")


def has_template_panels(panels: List[Dict]) -> bool:
    """Check if dashboard already has template panels."""
    template_ids = {999, 100, 101, 102, 103, 104, 105, 106}
    panel_ids = {p.get('id') for p in panels if 'id' in p}
    return bool(template_ids & panel_ids)


def calculate_template_height(template_panels: List[Dict]) -> int:
    """Calculate total height of template panels."""
    if not template_panels:
        return 0

    max_y = 0
    for panel in template_panels:
        if 'gridPos' in panel:
            grid_pos = panel['gridPos']
            panel_bottom = grid_pos.get('y', 0) + grid_pos.get('h', 0)
            max_y = max(max_y, panel_bottom)

    return max_y


def adjust_panel_positions(panels: List[Dict], y_offset: int) -> List[Dict]:
    """Adjust Y positions of all panels by offset."""
    adjusted = []
    for panel in panels:
        panel_copy = panel.copy()
        if 'gridPos' in panel_copy:
            panel_copy['gridPos'] = panel_copy['gridPos'].copy()
            panel_copy['gridPos']['y'] += y_offset
        adjusted.append(panel_copy)
    return adjusted


def get_dashboard_title(dashboard: Dict) -> str:
    """Extract dashboard title."""
    return dashboard.get('title', 'Unknown Dashboard')


def update_service_graph_title(template_panels: List[Dict], dashboard_title: str) -> None:
    """Update service graph title to include dashboard name."""
    for panel in template_panels:
        if panel.get('id') == 999 and panel.get('type') == 'nodeGraph':
            # Update title to be dashboard-specific
            base_title = f"{dashboard_title} - Service Graph"
            panel['title'] = base_title


def apply_template(
    dashboard_file: str,
    output_file: str = None,
    dry_run: bool = False
) -> None:
    """Apply experiment overview template to dashboard."""

    # Resolve paths
    script_dir = Path(__file__).parent
    template_file = script_dir / 'experiment-overview-template.json'
    dashboard_path = Path(dashboard_file).resolve()

    print(f"📂 Loading template: {template_file}")
    template = load_json(str(template_file))

    print(f"📂 Loading dashboard: {dashboard_path}")
    dashboard = load_json(str(dashboard_path))

    # Extract panels
    template_panels = template.get('panels', [])
    existing_panels = dashboard.get('panels', [])

    if not template_panels:
        print("❌ Error: Template has no panels")
        sys.exit(1)

    # Check if template already applied
    if has_template_panels(existing_panels):
        print("⚠️  Warning: Dashboard already has template panels (IDs 999-106)")
        print("   Template will be replaced with latest version")
        # Remove existing template panels
        existing_panels = [p for p in existing_panels if p.get('id', 0) not in {999, 100, 101, 102, 103, 104, 105, 106}]

    # Calculate offset needed
    template_height = calculate_template_height(template_panels)
    print(f"📏 Template height: {template_height} grid units")

    # Update service graph title
    dashboard_title = get_dashboard_title(dashboard)
    update_service_graph_title(template_panels, dashboard_title)

    # Adjust existing panel positions
    print(f"📐 Adjusting {len(existing_panels)} existing panels (y+{template_height})")
    adjusted_panels = adjust_panel_positions(existing_panels, template_height)

    # Combine panels
    dashboard['panels'] = template_panels + adjusted_panels

    print(f"✨ Combined dashboard: {len(template_panels)} template + {len(adjusted_panels)} custom panels")

    # Preview mode
    if dry_run:
        print("\n🔍 DRY RUN - No files modified")
        print("\nTemplate panels added:")
        for panel in template_panels:
            panel_id = panel.get('id', 'N/A')
            panel_title = panel.get('title', 'Untitled')
            panel_type = panel.get('type', 'unknown')
            print(f"  - [{panel_id:3}] {panel_title} ({panel_type})")

        print(f"\nExisting panels shifted down by {template_height} units")
        print(f"Output would be written to: {output_file or dashboard_path}")
        return

    # Determine output path
    if output_file:
        output_path = Path(output_file).resolve()
    else:
        output_path = dashboard_path

    # Save dashboard
    save_json(dashboard, str(output_path))
    print(f"\n✅ Template applied successfully!")
    print(f"   Dashboard: {dashboard_title}")
    print(f"   File: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Apply Experiment Overview Template to Chaos Dashboards',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Apply template to dashboard (overwrites original)
  python apply_template.py ../extensive_postgres_dashboard.json

  # Save to new file
  python apply_template.py ../extensive_postgres_dashboard.json --output ../new_dashboard.json

  # Preview without modifying
  python apply_template.py ../extensive_postgres_dashboard.json --dry-run

  # Batch apply to multiple dashboards
  for f in ../*.json; do python apply_template.py "$f"; done
        """
    )

    parser.add_argument(
        'dashboard',
        help='Path to dashboard JSON file'
    )

    parser.add_argument(
        '-o', '--output',
        help='Output file path (default: overwrite input file)'
    )

    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )

    args = parser.parse_args()

    try:
        apply_template(args.dashboard, args.output, args.dry_run)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
