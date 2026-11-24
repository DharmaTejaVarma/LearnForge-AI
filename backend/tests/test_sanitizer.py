import pytest
from app.core.sanitizer import EducationalSanitizer

def test_clean_title_removes_extensions_and_noise():
    raw_name = "1nbsped-1098135504-9781098135508.pdf"
    cleaned = EducationalSanitizer.clean_title(raw_name)
    assert not cleaned.endswith(".pdf")
    assert "1nbsped" not in cleaned
    assert len(cleaned) > 0

    doc_name = "introduction_to_machine_learning_v2.docx"
    assert EducationalSanitizer.clean_title(doc_name) == "Introduction To Machine Learning V2"

    uuid_name = "550e8400-e29b-41d4-a716-446655440000.pdf"
    cleaned_uuid = EducationalSanitizer.clean_title(uuid_name)
    assert not cleaned_uuid.endswith(".pdf")
    assert "Study Guide" in cleaned_uuid or len(cleaned_uuid) > 0

def test_contains_metadata_leak():
    # Should detect raw filenames and extensions
    assert EducationalSanitizer.contains_metadata_leak("Check 1nbsped-1098135504-9781098135508.pdf for details")
    assert EducationalSanitizer.contains_metadata_leak("Uploaded file: lecture1.docx")
    assert EducationalSanitizer.contains_metadata_leak("Internal path uploads/pdfs/lecture.pdf")
    assert EducationalSanitizer.contains_metadata_leak("Chunk id: chunk_00492_doc1")
    assert EducationalSanitizer.contains_metadata_leak("UUID 550e8400-e29b-41d4-a716-446655440000")

    # Clean educational prose should NOT trigger leak
    assert not EducationalSanitizer.contains_metadata_leak("A neural network consists of layers of interconnected nodes.")
    assert not EducationalSanitizer.contains_metadata_leak("Polymorphism allows objects of different classes to be treated through a uniform interface.")

def test_sanitize_educational_text():
    dirty_text = """
    1nbsped-1098135504-9781098135508.pdf
    ISBN 978-1-098-13550-8
    Page 42 of 300
    [Chunk 12 of document 4]

    A binary search algorithm operates on a sorted array by repeatedly dividing the search interval in half.
    If the target value is less than the middle element, the search continues in the lower half.

    Downloaded from example.com/doc.pdf
    """
    clean_text = EducationalSanitizer.sanitize_educational_text(dirty_text)
    assert "binary search algorithm" in clean_text
    assert "1nbsped-1098135504-9781098135508.pdf" not in clean_text
    assert "ISBN 978-1-098-13550-8" not in clean_text
    assert "[Chunk 12" not in clean_text

def test_validate_flashcard():
    # Valid active recall flashcard
    assert EducationalSanitizer.validate_flashcard(
        "What is recursion in computer science?",
        "Recursion is a programming technique where a function calls itself to solve a smaller instance of the same problem."
    ) is True

    # Leaked filename in question
    assert EducationalSanitizer.validate_flashcard(
        "What does 1nbsped-1098135504-9781098135508.pdf discuss?",
        "It discusses programming principles."
    ) is False

    # Leaked filename in answer
    assert EducationalSanitizer.validate_flashcard(
        "What is an abstract data type?",
        "See details in lecture_notes.pdf on page 12."
    ) is False

    # Too short / trivial
    assert EducationalSanitizer.validate_flashcard("Why?", "Because.") is False

def test_validate_quiz_question():
    # Valid 4-option MCQ
    valid_q = {
        "question_text": "What is the primary purpose of an index in a relational database?",
        "options": [
            "A) To enforce foreign key cascade deletes",
            "B) To accelerate data retrieval operations without scanning every row",
            "C) To automatically compress table data on disk",
            "D) To encrypt sensitive columnar values"
        ],
        "correct_answer": "B",
        "explanation": "Indexes maintain an auxiliary data structure (typically a B-Tree) that allows the database engine to locate target records in logarithmic time."
    }
    assert EducationalSanitizer.validate_quiz_question(valid_q) is True

    # Missing option D (only 3 options)
    invalid_q1 = {
        "question_text": "What is encapsulation in object-oriented programming?",
        "options": [
            "A) Bundling data and methods",
            "B) Inheritance hierarchy",
            "C) Dynamic polymorphism"
        ],
        "correct_answer": "A",
        "explanation": "Encapsulation restricts direct access to some of an object's components."
    }
    assert EducationalSanitizer.validate_quiz_question(invalid_q1) is False

    # Metadata leak in explanation
    invalid_q2 = {
        "question_text": "Which layer handles end-to-end communication in the OSI model?",
        "options": [
            "A) Network Layer",
            "B) Transport Layer",
            "C) Session Layer",
            "D) Physical Layer"
        ],
        "correct_answer": "B",
        "explanation": "As stated in textbook_final_v1.pdf, Transport Layer manages end-to-end flow control."
    }
    assert EducationalSanitizer.validate_quiz_question(invalid_q2) is False
