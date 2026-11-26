from typing import List, Dict, Any, Optional
from app.core.sanitizer import EducationalSanitizer


class ResourceAgent:
    """
    Finds supplementary study references and clearly distinguishes between
    uploaded-document material (with page citations) and general educational study guidance.
    Never fabricates external URLs or fake references.
    """

    @staticmethod
    def recommend_resources(
        query: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        course_title: Optional[str] = None,
        lesson_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        resources: List[Dict[str, Any]] = []
        seen = set()

        # 1. Grounded Uploaded Document References
        for c in citations or []:
            doc_title = EducationalSanitizer.clean_title(c.get("filename") or course_title or "Study Material")
            page_num = c.get("page_number", 1)
            key = (doc_title, page_num)
            if key in seen:
                continue
            seen.add(key)
            resources.append({
                "title": f"{doc_title} — Page {page_num}",
                "source_type": "uploaded_document",
                "page_number": page_num,
                "document_id": c.get("document_id"),
                "description": "Primary source excerpt in your uploaded course materials.",
            })

        # 2. General Educational Study Strategy (clearly labeled as non-document)
        topic_focus = (lesson_title or course_title or query or "this topic").strip()
        if len(topic_focus) > 80:
            topic_focus = topic_focus[:77] + "..."

        resources.append({
            "title": f"Active Recall & Concept Check: {topic_focus}",
            "source_type": "general_guidance",
            "page_number": None,
            "document_id": None,
            "description": (
                "General study recommendation (not from the uploaded document): generate flashcards or a "
                "targeted practice quiz on this concept to reinforce long-term retention."
            ),
        })

        return resources[:4]
