#!/usr/bin/env python3
"""
Script to update all main_*.py files to use logging instead of print statements
"""

import os
import re

def update_main_file(filename):
    """Update a main_*.py file to use logging instead of print"""
    print(f"Updating {filename}...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace print statements with logging
    # Replace: print(f"HATA - Logger oluşturulamadı: {e}")
    # With: logging.error(f"HATA - Logger oluşturulamadı: {e}")
    content = re.sub(
        r'print\(f"HATA - Logger oluşturulamadı: \{e\}"\)',
        '''# Fallback logging if logger creation failed
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                logging.error(f"HATA - Logger oluşturulamadı: {e}")''',
        content
    )
    
    # Replace: print("Bot manuel olarak durduruldu")
    # With: logging.info("Bot manuel olarak durduruldu")
    content = re.sub(
        r'print\("Bot manuel olarak durduruldu"\)',
        '''# Fallback logging if logger creation failed
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                logging.info("Bot manuel olarak durduruldu")''',
        content
    )
    
    # Write back to file
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Updated {filename}")

def main():
    """Main function to update all main_*.py files"""
    # Get all main_*.py files
    main_files = [f for f in os.listdir('.') if f.startswith('main_') and f.endswith('.py')]
    
    print(f"Found {len(main_files)} main files to update:")
    for f in main_files:
        print(f"  - {f}")
    
    print("\nUpdating files...")
    for filename in main_files:
        update_main_file(filename)
    
    print("\nAll files updated successfully!")

if __name__ == "__main__":
    main() 