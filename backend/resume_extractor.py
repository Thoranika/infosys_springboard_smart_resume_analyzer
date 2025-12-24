import pdfplumber
import os
import sys


def extract_text_from_pdf(path: str) -> str:
    """
    Best-quality PDF text extraction using pdfplumber
    """
    text_blocks = []

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_blocks.append(page_text)

    return "\n".join(text_blocks).strip()


def extract_text_from_file(path: str) -> str:
    """Extract text from common resume files (minimal implementation).
    - .txt: native read
    - .pdf: uses PyPDF2 if installed
    - .docx: uses python-docx if installed
    Falls back to reading as text.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if ext == ".pdf":
        try:
            from PyPDF2 import PdfReader
        except Exception as e:
            raise ImportError("PyPDF2 required for PDF extraction. Install with: pip install PyPDF2") from e
        text_parts = []
        reader = PdfReader(path)
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)

    if ext in (".docx",):
        try:
            import docx
        except Exception as e:
            raise ImportError("python-docx required for .docx extraction. Install with: pip install python-docx") from e
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)

    # fallback: attempt to read as text
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


if __name__ == "__main__":
    # Change directory to the project folder
    os.chdir(r"c:\Users\THORANIKA\OneDrive\Desktop\infosysproject")

    # Run the Streamlit app
    os.system("python -m streamlit run frontend/app.py")
