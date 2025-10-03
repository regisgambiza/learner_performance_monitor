import logging
import json
from build_batch_prompt import build_batch_prompt
from call_ollama_classify import call_ollama_classify

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

def generate_reports(student_analysis, categories, ollama_model):
    results = {}
    student_items = list(student_analysis.items())
    BATCH_SIZE = 5

    for start in range(0, len(student_items), BATCH_SIZE):
        batch = student_items[start:start + BATCH_SIZE]
        batch_data = []
        for sid, data in batch:
            profile = data["student"].get("profile", {})
            name_info = profile.get("name", {})
            full_name = " ".join(filter(None, [name_info.get("givenName",""), name_info.get("familyName","")])).strip() or sid
            metrics = data["metrics"]
            # Extract detailed submissions
            detailed_submissions = []
            for cw in data["coursework"]:
                title = cw.get("title", cw["id"])
                max_points = cw.get("maxPoints", "—")
                submission = cw.get("submission")
                if not submission:
                    status = "Missing"
                    score = "—"
                else:
                    state = submission.get("state", "")
                    if state in ["NEW", "CREATED"]:
                        status = "Missing"
                    elif submission.get("late", False):
                        status = "Late"
                    else:
                        status = "Submitted"
                    assigned_grade = submission.get("assignedGrade")
                    if assigned_grade is not None:
                        if assigned_grade == 0:
                            status = "Missing"
                            score = "—"
                        else:
                            score = f"{assigned_grade}/{max_points}" if max_points != "—" else f"{assigned_grade}"
                    else:
                        score = "—"
                detailed_submissions.append({
                    "title": title,
                    "status": status,
                    "score": score
                })
            batch_data.append((full_name, metrics, detailed_submissions))

        logger.info("Building prompt for batch %d-%d learners", start + 1, start + len(batch))
        prompt = build_batch_prompt(batch_data, categories)
        logger.info("Submitting batch %d-%d learners to Ollama", start + 1, start + len(batch))
        ai_response = call_ollama_classify(prompt, model=ollama_model)

        # Split the AI response by ---
        individual_responses = [r.strip() for r in ai_response.split('---') if r.strip()]

        if len(individual_responses) != len(batch):
            logger.warning("Mismatch in responses: got %d, expected %d. Full response: %s", len(individual_responses), len(batch), ai_response)
            for sid, _ in batch:
                results[sid] = {"ai_response": "Category: Needs Review\nTeacher Report: Unable to categorize due to incomplete AI response. Please review student metrics manually."}
            continue

        # Assign individual responses
        for i, (sid, _) in enumerate(batch):
            response = individual_responses[i]
            # Check if the response contains a valid category
            category_line = next((line for line in response.splitlines() if line.strip().startswith("Category:")), None)
            if category_line:
                category = category_line.split(":", 1)[1].strip()
                if category not in categories:
                    logger.warning("Invalid category '%s' for student=%s, assigning 'Needs Review'", category, sid)
                    response = f"Category: Needs Review\nTeacher Report: AI provided an invalid category ('{category}'). Please review student metrics: {json.dumps(batch_data[i][1])}"
            else:
                logger.warning("No category found for student=%s, assigning 'Needs Review'", sid)
                response = f"Category: Needs Review\nTeacher Report: No category provided by AI. Please review student metrics: {json.dumps(batch_data[i][1])}"
            results[sid] = {"ai_response": response}
            logger.debug("Assigned AI response to student=%s", sid)

    return results