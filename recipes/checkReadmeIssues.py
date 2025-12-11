#!/usr/bin/env python3
"""
Check README.md files for issues that could cause PDF rendering problems.
"""

import os
import sys
import re
import unicodedata
from pathlib import Path


def check_for_problematic_characters(content, filepath):
    """Check for invisible Unicode characters and other problematic chars."""
    issues = []
    
    # Check for zero-width characters
    zero_width_chars = {
        '\u200B': 'ZERO WIDTH SPACE',
        '\u200C': 'ZERO WIDTH NON-JOINER',
        '\u200D': 'ZERO WIDTH JOINER',
        '\u2060': 'WORD JOINER',
        '\uFEFF': 'ZERO WIDTH NO-BREAK SPACE (BOM)',
    }
    
    for line_num, line in enumerate(content.split('\n'), 1):
        for char, name in zero_width_chars.items():
            if char in line:
                col = line.index(char) + 1
                issues.append(
                    f"  Line {line_num}, col {col}: Found {name} (U+{ord(char):04X})"
                )
        
        # Check for other invisible or problematic characters
        for col, char in enumerate(line, 1):
            if unicodedata.category(char) in ['Cc', 'Cf'] and char not in ['\t', '\r', '\n']:
                issues.append(
                    f"  Line {line_num}, col {col}: Found control character {unicodedata.name(char, 'UNKNOWN')} (U+{ord(char):04X})"
                )
    
    if issues:
        print(f"❌ Found problematic Unicode characters in {filepath}:")
        for issue in issues:
            print(issue)
        return False
    
    return True


def check_line_length(content, filepath, max_length=500):
    """Check for excessively long lines that can break PDF rendering."""
    issues = []
    
    for line_num, line in enumerate(content.split('\n'), 1):
        # Skip code blocks and URLs
        stripped = line.strip()
        if stripped.startswith('```') or stripped.startswith('http'):
            continue
            
        if len(line) > max_length:
            issues.append(
                f"  Line {line_num}: {len(line)} characters (exceeds {max_length})"
            )
    
    if issues:
        print(f"❌ Found excessively long lines in {filepath}:")
        for issue in issues:
            print(issue)
        print("  Tip: Break long lines into multiple lines for better PDF compatibility.")
        return False
    
    return True


def check_mixed_line_endings(content, filepath):
    """Check for mixed line endings."""
    has_crlf = '\r\n' in content
    has_lf = '\n' in content.replace('\r\n', '')
    
    if has_crlf and has_lf:
        print(f"❌ Found mixed line endings (CRLF and LF) in {filepath}")
        print("  Tip: Use consistent line endings (LF recommended).")
        return False
    
    return True


def check_smart_quotes(content, filepath):
    """Check for smart quotes and other typographic characters."""
    issues = []
    problematic_chars = {
        '\u2018': 'LEFT SINGLE QUOTATION MARK',
        '\u2019': 'RIGHT SINGLE QUOTATION MARK',
        '\u201C': 'LEFT DOUBLE QUOTATION MARK',
        '\u201D': 'RIGHT DOUBLE QUOTATION MARK',
        '\u2013': 'EN DASH',
        '\u2014': 'EM DASH',
    }
    
    for line_num, line in enumerate(content.split('\n'), 1):
        for char, name in problematic_chars.items():
            if char in line:
                col = line.index(char) + 1
                issues.append(
                    f"  Line {line_num}, col {col}: Found {name}"
                )
    
    if issues:
        print(f"⚠️  Found typographic characters in {filepath}:")
        for issue in issues:
            print(issue)
        print("  Note: These may cause issues with some PDF converters.")
        print("  Consider replacing with ASCII equivalents (', \", -, --).")
        return True  # Warning only, not an error
    
    return True


def check_readme_file(filepath):
    """Check a single README file for PDF rendering issues."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        print(f"❌ Error: {filepath} is not valid UTF-8")
        return False
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return False
    
    all_checks_passed = True
    
    # Run all checks
    all_checks_passed &= check_for_problematic_characters(content, filepath)
    all_checks_passed &= check_line_length(content, filepath)
    all_checks_passed &= check_mixed_line_endings(content, filepath)
    check_smart_quotes(content, filepath)  # Warning only
    
    return all_checks_passed


def main():
    """Check all README.md files in recipe directories."""
    print("### Checking README.md files for PDF rendering issues...\n")
    
    # Get the recipes directory
    script_dir = Path(__file__).parent
    recipes_dir = script_dir
    
    # Find all README.md files in subdirectories
    readme_files = list(recipes_dir.glob("*/README.md"))
    
    if not readme_files:
        print("ℹ️  No README.md files found in recipe subdirectories.")
        return 0
    
    print(f"Found {len(readme_files)} README.md file(s) to check.\n")
    
    all_passed = True
    checked_count = 0
    
    for readme_path in sorted(readme_files):
        print(f"Checking {readme_path.parent.name}/README.md...")
        passed = check_readme_file(readme_path)
        
        if passed:
            print(f"✅ {readme_path.parent.name}/README.md passed all checks.\n")
        else:
            all_passed = False
            print(f"❌ {readme_path.parent.name}/README.md has issues.\n")
        
        checked_count += 1
    
    print("=" * 80)
    if all_passed:
        print(f"✅ All {checked_count} README files passed validation!")
        return 0
    else:
        print(f"❌ Some README files have issues that need to be fixed.")
        print("   These issues can cause blank PDFs or rendering problems.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
