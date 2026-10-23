"""Shared report defaults, including the Android-only concept explanation format."""

from .._types.enums import ReportFormat

_REPORT_CONFIGS: dict[ReportFormat, tuple[str, str, str]] = {
    ReportFormat.BRIEFING_DOC: (
        "Briefing Doc",
        "Key insights and important quotes",
        "Create a comprehensive briefing document that includes an Executive Summary, "
        "detailed analysis of key themes, important quotes with context, and actionable "
        "insights.",
    ),
    ReportFormat.STUDY_GUIDE: (
        "Study Guide",
        "Short-answer quiz, essay questions, glossary",
        "Create a comprehensive study guide that includes key concepts, short-answer "
        "practice questions, essay prompts for deeper exploration, and a glossary of "
        "important terms.",
    ),
    ReportFormat.BLOG_POST: (
        "Blog Post",
        "Insightful takeaways in readable article format",
        "Write an engaging blog post that presents the key insights in an accessible, "
        "reader-friendly format. Include an attention-grabbing introduction, well-organized "
        "sections, and a compelling conclusion with takeaways.",
    ),
    ReportFormat.CONCEPT_EXPLANATION: (
        "Concept Explanation",
        "Clear explanations of key concepts",
        "Explain the key concepts from the provided sources clearly and comprehensively. "
        "Define important terms, connect related ideas, use examples where helpful, and "
        "address common misconceptions.",
    ),
}
