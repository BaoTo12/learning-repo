import pypdf

pdf_path = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\MongoDB_ The Definitive Guide_ Powerful and Scalable Data -- Shannon Bradshaw; Eoin Brazil; Kristina Chodorow -- 3rd.pdf"
excerpts_path = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\scratch\book_excerpts.txt"

# Map of section names to PDF page ranges (0-indexed, start inclusive, end exclusive)
page_ranges = {
    "NUMA_THP_Readahead_Scheduler": (475, 482),  # Book pages 454-461
    "Friends_Followers_Cardinality": (236, 240), # Book pages 215-219
    "Capped_Collections": (171, 177),            # Book pages 150-156
    "GridFS": (177, 182),                        # Book pages 156-161
    "Syncing_Elections_Rollbacks": (269, 282),   # Book pages 248-261
    "Jumbo_Chunks": (384, 390),                  # Book pages 363-369
    "Causal_Consistency": (221, 226)             # Book pages 200-205
}

def extract_excerpts():
    reader = pypdf.PdfReader(pdf_path)
    
    with open(excerpts_path, "w", encoding="utf-8") as f:
        f.write("=== MongoDB: The Definitive Guide Book Excerpts ===\n\n")
        
        for name, (start, end) in page_ranges.items():
            f.write(f"============================================================\n")
            f.write(f"SECTION: {name} (PDF pages {start}-{end-1})\n")
            f.write(f"============================================================\n\n")
            
            for page_num in range(start, end):
                if page_num < len(reader.pages):
                    f.write(f"--- [PDF PAGE {page_num}] (Book Page {page_num - 21}) ---\n")
                    text = reader.pages[page_num].extract_text()
                    f.write(text.strip())
                    f.write("\n\n")
                    
    print(f"Excerpts successfully extracted to {excerpts_path}")

if __name__ == "__main__":
    extract_excerpts()
