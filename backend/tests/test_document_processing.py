import pytest
import io
from pathlib import Path
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.agents.document_agent import DocumentAgent
from app.core.exceptions import BadRequestException

def test_extract_txt(tmp_path):
    txt_file = tmp_path / "sample_lecture.txt"
    content = (
        "Chapter 1: Foundations of Algorithms\n\n"
        "An algorithm is a finite sequence of well-defined instructions to solve a problem.\n\n"
        "Chapter 2: Computational Complexity\n\n"
        "Big-O notation characterizes the upper bound of the asymptotic growth rate of a function."
    )
    txt_file.write_text(content, encoding="utf-8")

    pages = DocumentLoader.load_document(str(txt_file), "text/plain")
    assert len(pages) >= 1
    assert "Foundations of Algorithms" in pages[0]["text"]
    assert pages[0]["page_number"] == 1
    assert len(pages[0]["headings"]) >= 1

def test_extract_markdown(tmp_path):
    md_file = tmp_path / "sample_course.md"
    content = (
        "# Introduction to Quantum Computing\n\n"
        "Quantum computing utilizes quantum mechanical phenomena such as superposition and entanglement.\n\n"
        "## Quantum Bits (Qubits)\n\n"
        "Unlike classical bits which are binary, a qubit can exist in a linear combination of states.\n\n"
        "```python\n"
        "import qiskit\n"
        "circuit = qiskit.QuantumCircuit(2, 2)\n"
        "```\n\n"
        "| Gate | Description |\n"
        "| --- | --- |\n"
        "| Hadamard | Creates superposition |\n"
    )
    md_file.write_text(content, encoding="utf-8")

    pages = DocumentLoader.load_document(str(md_file), "text/markdown")
    assert len(pages) >= 1
    assert "Quantum Computing" in pages[0]["text"]
    assert "```python" in pages[0]["text"]
    assert "| Hadamard |" in pages[0]["text"]
    assert "Introduction to Quantum Computing" in pages[0]["headings"]

def test_extract_pptx(tmp_path):
    from pptx import Presentation
    prs = Presentation()
    slide_layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(slide_layout)
    title = slide.shapes.title
    title.text = "Microeconomic Theory: Supply & Demand"
    subtitle = slide.placeholders[1]
    subtitle.text = "Market equilibrium occurs at the intersection of supply and demand curves."

    pptx_file = tmp_path / "lecture.pptx"
    prs.save(str(pptx_file))

    pages = DocumentLoader.load_document(str(pptx_file), "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    assert len(pages) == 1
    assert pages[0]["page_number"] == 1
    assert "Microeconomic Theory" in pages[0]["text"]
    assert "Supply & Demand" in pages[0]["headings"][0]

def test_empty_and_corrupt_files(tmp_path):
    empty_file = tmp_path / "empty.pdf"
    empty_file.write_bytes(b"")

    with pytest.raises(BadRequestException) as exc_info:
        DocumentLoader.load_document(str(empty_file), "application/pdf")
    assert "empty or corrupted" in str(exc_info.value).lower()

    corrupt_file = tmp_path / "corrupted.docx"
    corrupt_file.write_bytes(b"This is not a zip file!")

    with pytest.raises(BadRequestException) as exc_info2:
        DocumentLoader.load_document(str(corrupt_file), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert "corrupted" in str(exc_info2.value).lower()

def test_text_cleaner_repeated_headers():
    pages = [
        {"page_number": 1, "text": "MIT OpenCourseWare 2026\nChapter 1 Introduction\nContent of page 1.\nFooter info"},
        {"page_number": 2, "text": "MIT OpenCourseWare 2026\nChapter 1 Introduction\nContent of page 2.\nFooter info"},
        {"page_number": 3, "text": "MIT OpenCourseWare 2026\nChapter 1 Introduction\nContent of page 3.\nFooter info"},
    ]
    cleaned = TextCleaner.clean_document_pages(pages)
    assert len(cleaned) == 3
    # Repeated header line should be scrubbed across pages
    for cp in cleaned:
        assert "Content of page" in cp["text"]
        assert "MIT OpenCourseWare 2026" not in cp["text"]

def test_document_agent_classification():
    # 1. Programming Document
    prog_pages = [
        {
            "page_number": 1,
            "text": "Chapter 1: Python Data Structures\nWe explore lists, dicts, tuples, and recursion. def binary_search(arr, target): return -1",
            "headings": ["Chapter 1: Python Data Structures"]
        }
    ]
    prog_analysis = DocumentAgent.analyze_document(prog_pages, "advanced_python_programming.pdf")
    assert prog_analysis["subject_domain"] == "computer_science"
    assert prog_analysis["content_type"] == "programming"
    assert prog_analysis["pedagogical_profile"]["requires_code_snippets"] is True
    assert prog_analysis["clean_title"] == "Advanced Python Programming"

    # 2. Mathematics Document
    math_pages = [
        {
            "page_number": 1,
            "text": "Chapter 1: Differential Equations & Linear Algebra\nTheorem 3.1: Given an invertible matrix A, the eigenvalue equation Ax = lambda x holds.",
            "headings": ["Chapter 1: Differential Equations"]
        }
    ]
    math_analysis = DocumentAgent.analyze_document(math_pages, "calculus_and_linear_algebra.pdf")
    assert math_analysis["subject_domain"] == "mathematics"
    assert math_analysis["content_type"] == "mathematical"
    assert math_analysis["pedagogical_profile"]["requires_formula_derivations"] is True

    # 3. Outline structure extraction
    assert len(prog_analysis["detected_outline"]) >= 1
    assert prog_analysis["detected_outline"][0]["title"] == "Chapter 1: Python Data Structures"
