import logging
import json
from call_ollama_classify import call_ollama_classify

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chatbot")

def run_chatbot(student_reports_file="student_reports.txt", category_groups_file="category_groups.txt", ollama_model="gpt-oss:20b"):
    logger.info("Starting chatbot for report queries")
    
    # Load report data
    report_context = ""
    try:
        with open(student_reports_file, "r", encoding="utf-8") as f:
            report_context += f.read()
    except FileNotFoundError:
        logger.warning("Student reports file %s not found", student_reports_file)
        report_context += "No student reports available.\n"
    
    try:
        with open(category_groups_file, "r", encoding="utf-8") as f:
            report_context += "\nCategory Groups:\n" + f.read()
    except FileNotFoundError:
        logger.warning("Category groups file %s not found", category_groups_file)
        report_context += "No category groups available.\n"

    print("\n=== Chatbot for Report Queries ===")
    print("Ask questions about the student reports or type 'exit'/'quit' to end.")
    print("Example questions: 'Why was Jacob classified as At Risk?', 'What are the categories?', 'Who is in High Performer?'")

    while True:
        user_input = input("\nYour question: ").strip()
        if user_input.lower() in ["exit", "quit"]:
            logger.info("Chatbot session ended by user")
            print("Goodbye!")
            break

        # Build prompt for Ollama
        prompt = f"""
You are a helpful assistant with access to student performance reports from a Google Classroom analysis. The reports include student metrics (total assignments, missing, late, average score, graded count), AI-generated teacher reports, submission details, and category groupings (High Performer, At Risk, Average, Improving, Emerging, Needs Review).

Here is the context from the reports:
{report_context}

Based on this context, answer the following question in a clear, concise, and professional manner. If the question is unrelated to the reports, provide a general response but note that your primary focus is the report data. If the information is not available, say so and suggest how the user might clarify or check the data.

Question: {user_input}
"""
        logger.info("Submitting chatbot query to Ollama: %s", user_input[:100])
        try:
            response = call_ollama_classify(prompt, model=ollama_model)
            print("\nChatbot Response:")
            print(response)
        except Exception as e:
            logger.error("Error processing chatbot query: %s", str(e))
            print("Sorry, there was an error processing your question. Please try again.")