import pytest
from pathlib import Path
from app.ai.rag.document_loader import DocumentLoader
from app.ai.rag.text_cleaner import TextCleaner
from app.ai.agents.document_agent import DocumentAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.lesson_agent import LessonAgent
from app.core.course_validator import CourseValidator

@pytest.mark.asyncio
async def test_adaptive_course_outline_synthesis():
    # Synthetic blueprint for a Computer Science document
    doc_blueprint = {
        "clean_title": "Distributed Systems Architecture",
        "subject_domain": "computer_science",
        "content_type": "programming",
        "detected_outline": [
            {
                "title": "RPC and Communication Protocols",
                "start_page": 1,
                "topics": [{"title": "Remote Procedure Calls", "page": 1}, {"title": "gRPC & Protocol Buffers", "page": 4}]
            },
            {
                "title": "Consensus and Fault Tolerance",
                "start_page": 8,
                "topics": [{"title": "Paxos and Raft Consensus", "page": 8}, {"title": "Byzantine Fault Tolerance", "page": 12}]
            }
        ],
        "pedagogical_profile": DocumentAgent._build_pedagogical_profile("computer_science", "programming"),
        "total_pages": 15,
        "sample_overview_text": "Distributed systems consist of autonomous computing nodes communicating over a network. Topics include RPC, Raft consensus, and replication."
    }

    outline = await ContentAgent.synthesize_course_outline(
        doc_blueprint=doc_blueprint,
        target_chapters_count=2,
        difficulty="advanced"
    )

    valid, reason = CourseValidator.validate_course_outline(outline, "Distributed Systems Architecture")
    assert valid is True, f"Validation failed: {reason}"
    assert len(outline["chapters"]) >= 1
    assert "title" in outline
    assert "learning_objectives" in outline
    assert len(outline["learning_objectives"]) >= 2

@pytest.mark.asyncio
async def test_domain_adapted_lesson_generation():
    from unittest.mock import patch

    mock_cs_content = (
        "# Binary Search Trees\n\n"
        "## 1. Lesson Overview & Learning Objectives\n"
        "- Master binary search tree invariants and time complexities\n"
        "- Implement insertion, deletion, and search algorithms\n\n"
        "## 2. Intuitive Introduction & Real-World Analogy\n"
        "A binary search tree acts like a sorted dictionary where searching takes logarithmic time.\n\n"
        "## 3. Core Definitions & Formal Theory\n"
        "A binary search tree maintains sorted order where each left child is smaller and right child is greater.\n\n"
        "## 4. Detailed Technical Analysis\n"
        "Search complexity is O(h) where h is the tree height. Balancing ensures optimal performance across operations.\n\n"
        "## 5. Code Implementation & Practical Walkthrough\n"
        "```python\n"
        "class Node:\n"
        "    def __init__(self, key):\n"
        "        self.key = key\n"
        "        self.left = None\n"
        "        self.right = None\n"
        "```\n\n"
        "## 6. Common Misconceptions & Pitfalls\n"
        "Failing to account for unbalanced tree degradation into a linked list when inputs are pre-sorted.\n\n"
        "## 7. Step-by-Step Implementation Guidelines\n"
        "Always compare input key to current node and recurse down left or right subtree accordingly.\n\n"
        "## 8. Key Takeaways\n"
        "- Left subtree contains smaller keys; right subtree contains greater keys.\n"
        "- Search and insertion operate in O(log n) average time when balanced.\n\n"
        "## 9. Practice Review Questions\n"
        "1. What is the worst-case search complexity? Answer: O(n).\n\n"
        "## 10. Source References\n"
        "Verified learning materials: Page 3."
    )

    mock_math_content = (
        "# Gradient Vectors and Directional Derivatives\n\n"
        "## 1. Lesson Overview & Learning Objectives\n"
        "- Understand the gradient vector as the direction of maximum increase\n"
        "- Calculate directional derivatives using the dot product formula\n\n"
        "## 2. Intuitive Introduction & Real-World Analogy\n"
        "Imagine standing on a hillside; the gradient points directly up the steepest incline.\n\n"
        "## 3. Core Definitions & Formal Theory\n"
        "The gradient vector nabla f points in the direction of greatest rate of increase of a scalar field f.\n\n"
        "## 4. Detailed Technical Analysis\n"
        "For a function f(x, y), the gradient is the vector of partial derivatives with respect to each coordinate.\n\n"
        "## 5. Mathematical Formulations & Worked Derivations\n"
        "$$\\nabla f(x, y) = \\left( \\frac{\\partial f}{\\partial x}, \\frac{\\partial f}{\\partial y} \\right)$$\n\n"
        "The directional derivative along unit vector u is computed as:\n"
        "$$D_u f = \\nabla f \\cdot \\mathbf{u}$$\n\n"
        "## 6. Common Misconceptions & Pitfalls\n"
        "Forgetting to normalize the direction vector into a unit vector before computing the dot product.\n\n"
        "## 7. Step-by-Step Implementation Guidelines\n"
        "Calculate all first-order partial derivatives and evaluate at the given coordinates systematically.\n\n"
        "## 8. Key Takeaways\n"
        "- The gradient vector is orthogonal to level curves.\n"
        "- The magnitude of the gradient represents the maximum rate of change.\n\n"
        "## 9. Practice Review Questions\n"
        "1. What is the directional derivative in a direction perpendicular to the gradient? Answer: Zero.\n\n"
        "## 10. Source References\n"
        "Verified learning materials: Page 7."
    )

    # 1. Computer Science Lesson
    cs_blueprint = {
        "clean_title": "Python Data Structures",
        "subject_domain": "computer_science",
        "content_type": "programming",
        "pedagogical_profile": DocumentAgent._build_pedagogical_profile("computer_science", "programming"),
    }
    cs_passages = [
        {"text": "A binary search tree maintains sorted order where each left child is smaller and right child is greater than the parent node.", "page_number": 3}
    ]

    with patch("app.ai.agents.lesson_agent.model_router.generate", return_value={"content": mock_cs_content}):
        cs_lesson = await LessonAgent.generate_lesson(
            topic_title="Binary Search Trees",
            chapter_title="Tree Structures",
            course_title="Python Data Structures",
            passages=cs_passages,
            source_pages=[3],
            doc_blueprint=cs_blueprint,
            difficulty="intermediate"
        )

    valid, reason = CourseValidator.validate_lesson_content(cs_lesson, "Binary Search Trees")
    assert valid is True, f"Lesson validation failed: {reason}"
    assert "def " in cs_lesson["content"] or "class " in cs_lesson["content"] or "```" in cs_lesson["content"]
    assert "## 1. Lesson Overview" in cs_lesson["content"]
    assert "## 8. Key Takeaways" in cs_lesson["content"]
    assert "## 9. Practice Review Questions" in cs_lesson["content"]
    assert "## 10. Source References" in cs_lesson["content"]

    # 2. Mathematics Lesson
    math_blueprint = {
        "clean_title": "Multivariable Calculus",
        "subject_domain": "mathematics",
        "content_type": "mathematical",
        "pedagogical_profile": DocumentAgent._build_pedagogical_profile("mathematics", "mathematical"),
    }
    math_passages = [
        {"text": "The gradient vector nabla f points in the direction of greatest rate of increase of a scalar field f.", "page_number": 7}
    ]

    with patch("app.ai.agents.lesson_agent.model_router.generate", return_value={"content": mock_math_content}):
        math_lesson = await LessonAgent.generate_lesson(
            topic_title="Gradient Vectors and Directional Derivatives",
            chapter_title="Differential Vector Calculus",
            course_title="Multivariable Calculus",
            passages=math_passages,
            source_pages=[7],
            doc_blueprint=math_blueprint,
            difficulty="advanced"
        )

    valid_math, reason_math = CourseValidator.validate_lesson_content(math_lesson, "Gradient Vectors")
    assert valid_math is True, f"Math lesson validation failed: {reason_math}"
    assert "$$" in math_lesson["content"] or "Formulations" in math_lesson["content"]

def test_course_validator_edge_cases():
    # Missing chapters
    bad_outline_1 = {"title": "Valid Course", "chapters": []}
    assert CourseValidator.validate_course_outline(bad_outline_1)[0] is False

    # Leaked filename in title
    bad_outline_2 = {
        "title": "Course based on lecture_notes_v1.pdf",
        "chapters": [{"title": "Chapter 1", "topics": ["Topic 1"]}]
    }
    assert CourseValidator.validate_course_outline(bad_outline_2)[0] is False

    # Duplicate topics across chapters
    bad_outline_3 = {
        "title": "Valid Algorithms Course",
        "chapters": [
            {"title": "Chapter 1", "topics": ["Introduction to Trees"]},
            {"title": "Chapter 2", "topics": ["Introduction to Trees"]}
        ]
    }
    assert CourseValidator.validate_course_outline(bad_outline_3)[0] is False

    # Shallow lesson (< 200 words)
    shallow_lesson = {
        "title": "Recursion",
        "content": "Recursion is when a function calls itself. It needs a base case. That is all."
    }
    assert CourseValidator.validate_lesson_content(shallow_lesson, "Recursion")[0] is False
