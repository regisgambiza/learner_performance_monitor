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
- Explain clearly why the student falls into the category based on metrics and context. 
- Highlight risks, learning gaps, and performance patterns that require teacher attention. 
- Suggest concrete teaching strategies, interventions, or follow-up actions the teacher can take. 
- Keep the tone professional, objective, and focused on classroom management and academic improvement.

For each student, output in this exact format:
Category: <category>
Teacher Report: <detailed multi-paragraph report for teacher use>

Separate each student's classification with ---

Students:
{joined_blocks}
""".strip()
    return prompt