import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.nav_manager import NavManager

import argparse

def main():
    parser = argparse.ArgumentParser(description="Generate ISIN master list from NAVAll.txt")
    parser.add_argument("keywords", nargs='+', help="Keywords to filter Scheme Names (e.g. Quant HDFC)")
    parser.add_argument("-o", "--output", default="data/isin_master_list.csv", help="Output CSV file path (default: data/isin_master_list.csv)")
    
    args = parser.parse_args()

    print(f"Generating master list for keywords: {args.keywords}...")
    print(f"Output file: {args.output}")
    
    manager = NavManager()
    success = manager.generate_master_list(args.output, args.keywords)
    
    if success:
        print(f"Success! Master list saved to {args.output}")
    else:
        print("Failed to generate master list. Check logs for details.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
