import json

def build_batch_prompt(batch_data, categories):
    student_blocks = []
    for name, metrics in batch_data:
        context_str = metrics.get("additional_context", "")
        block = f"Student: {name}\nMetrics: {json.dumps({k: v for k, v in metrics.items() if k != 'additional_context'})}\nAdditional Context: {context_str}"
        student_blocks.append(block)
    joined_blocks = "\n\n---\n\n".join(student_blocks)
    prompt = f"""
Classify each student below into one of the following categories: {', '.join(categories)}.

Write a detailed report for the TEACHER. 
- Analyze the student's metrics (total assignments, missing, late, average score, graded count) and additional context to determine the category.
- Treat a score of 0 out of the maximum points (e.g., 0/30) as a non-submission, equivalent to a missing assignment, and increment the 'missing' count accordingly when evaluating performance.
- Use the following guidelines for categorization:
  - **High Performer**: Average score ≥90% (out of total possible points), no missing or late assignments, and consistent high performance across assignments.
  - **Average**: Average score ≥75% but <90%, with minimal missing (≤1) or late assignments, showing consistent but not exceptional performance.
  - **Improving**: Average score ≥65% but <75%, with signs of progress (e.g., recent higher scores) or additional context indicating improvement.
  - **Emerging**: Average score ≥50% but <65%, with inconsistent performance but some potential shown in specific assignments.
  - **At Risk**: Average score <50%, multiple missing (≥2, including 0/30 scores) or late assignments, or significant issues (e.g., failing critical assessments like quizzes with no other strong performance).
  - **Needs Review**: Insufficient data (e.g., no graded assignments) or ambiguous metrics requiring manual teacher review.
- A single missing critical assessment (e.g., quiz) or a 0/30 score should not automatically place a student in 'At Risk' if their average score is ≥75% and other metrics show consistency.
- Highlight inconsistencies in performance, such as high completion rates but low scores (including 0/30 as non-submissions), and consider additional context (e.g., external factors) when relevant.
- Explain clearly why the student falls into the chosen category, referencing specific metrics and context.
- Identify risks, learning gaps, and performance patterns that require teacher attention.
- Suggest concrete teaching strategies, interventions, or follow-up actions tailored to the student's needs.
- Keep the tone professional, objective, and focused on classroom management and academic improvement.

For each student, output in this exact format:
Category: <category>
Teacher Report: <detailed multi-paragraph report for teacher use>

Separate each student's classification with ---

Students:
{joined_blocks}
""".strip()
    return prompt