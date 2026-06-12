import pypdf

pdf_path = r"c:\Users\Admin\Desktop\projects\learning-repo\mongodb-mastery\MongoDB_ The Definitive Guide_ Powerful and Scalable Data -- Shannon Bradshaw; Eoin Brazil; Kristina Chodorow -- 3rd.pdf"

def inspect():
    reader = pypdf.PdfReader(pdf_path)
    print("Total Pages:", len(reader.pages))
    
    # Try to extract document outline/bookmarks
    outline = reader.outline
    if outline:
        print("Outline found! Printing first 30 outline items:")
        def print_outline(items, depth=0):
            for item in items[:30]:
                if isinstance(item, list):
                    print_outline(item, depth + 1)
                else:
                    print("  " * depth + str(item.title))
        print_outline(outline)
    else:
        print("No outline found in PDF. Let's extract headers from the first few pages (pages 5-15) to identify chapters.")
        for page_num in range(5, min(25, len(reader.pages))):
            text = reader.pages[page_num].extract_text()
            first_lines = [line.strip() for line in text.split('\n') if line.strip()][:5]
            print(f"--- Page {page_num} ---")
            for line in first_lines:
                print("  ", line)

if __name__ == "__main__":
    inspect()
