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
            batch_data.append((full_name, metrics))

        logger.info("Building prompt for batch %d-%d learners", start + 1, start + len(batch))
        prompt = build_batch_prompt(batch_data, categories)
        logger.info("Submitting batch %d-%d learners to Ollama", start + 1, start + len(batch))
        ai_response = call_ollama_classify(prompt, model=ollama_model)

        # Split the AI response by ---
        individual_responses = [r.strip() for r in ai_response.split('---') if r.strip()]

        if len(individual_responses) != len(batch):
            logger.warning("Mismatch in responses: got %d, expected %d. Full response: %s", len(individual_responses), len(batch), ai_response)
            for sid, _ in batch:
                results[sid] = {"ai_response": "Error in AI response parsing"}
            continue

        # Assign individual responses
        for i, (sid, _) in enumerate(batch):
            results[sid] = {"ai_response": individual_responses[i]}
            logger.debug("Assigned AI response to student=%s", sid)

    return results