import pypdf
import re

pdf_path = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\MongoDB_ The Definitive Guide_ Powerful and Scalable Data -- Shannon Bradshaw; Eoin Brazil; Kristina Chodorow -- 3rd.pdf"
notes_path = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\scratch\pdf_notes.txt"

keywords = [
    r"NUMA",
    r"Transparent Huge Pages",
    r"readahead",
    r"GridFS",
    r"rollback",
    r"causal consistency",
    r"jumbo chunk",
    r"initial sync",
    r"friends"
]

def search_pdf():
    reader = pypdf.PdfReader(pdf_path)
    print(f"Total pages: {len(reader.pages)}")
    
    results = []
    
    for page_num in range(len(reader.pages)):
        text = reader.pages[page_num].extract_text()
        for kw in keywords:
            if re.search(kw, text, re.IGNORECASE):
                # Save the page number and a snippet
                results.append((kw, page_num, text))
                
    # Group results by keyword and write the text of the first few occurrences to pdf_notes.txt
    with open(notes_path, "w", encoding="utf-8") as f:
        f.write("=== MongoDB: The Definitive Guide Search Notes ===\n\n")
        
        for kw in keywords:
            f.write(f"=========================================\n")
            f.write(f"KEYWORD: {kw}\n")
            f.write(f"=========================================\n\n")
            
            kw_results = [r for r in results if r[0] == kw]
            f.write(f"Found in {len(kw_results)} pages.\n\n")
            
            # Print text of first 3 unique pages for each keyword
            printed_pages = set()
            for r_kw, page, text in kw_results:
                if page not in printed_pages:
                    f.write(f"--- Page {page} ---\n")
                    f.write(text.strip())
                    f.write("\n\n")
                    printed_pages.add(page)
                if len(printed_pages) >= 2: # Limit to 2 pages per keyword to keep file readable
                    break
                    
    print(f"Search completed. Notes saved to {notes_path}")

if __name__ == "__main__":
    search_pdf()
