import argparse
import logging
from get_classroom_service import get_classroom_service
from get_all_courses import get_all_courses
from get_all_students import get_all_students
from get_all_coursework import get_all_coursework
from call_ollama_classify import call_ollama_classify
from build_batch_prompt import build_batch_prompt
from analyse_students import analyse_students
from generate_reports import generate_reports
from save_reports_to_file import save_reports_to_file
from select_course import select_course
from select_student import select_student


# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    parser.add_argument("--ollama-model", default="gpt-oss:20b")
    args = parser.parse_args()

    logger.info("Starting learner analysis run")

    # Prompt for start and end dates
    start_date = input("Enter start date (YYYY-MM-DD, e.g., 2025-09-01): ")
    end_date = input("Enter end date (YYYY-MM-DD, e.g., 2025-09-30): ")

    service = get_classroom_service(args.credentials, args.token)
    courses = get_all_courses(service)
    # Sort courses alphabetically by name
    courses = sorted(courses, key=lambda x: x["name"])
    logger.info("Fetched %d courses", len(courses))

    if not courses:
        print("No courses found.")
        return

    print("Options:")
    print("1. Analyze all classes")
    print("2. Analyze a single class")
    print("3. Analyze a single student")
    while True:
        try:
            mode_choice = int(input("Enter choice (1/2/3): "))
            if mode_choice in [1, 2, 3]:
                break
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")

    selected_student_id = None
    additional_context = None
    if mode_choice == 1:
        target_courses = courses
    elif mode_choice == 2:
        selected_course = select_course(courses)
        target_courses = [selected_course]
    elif mode_choice == 3:
        selected_course = select_course(courses)
        target_courses = [selected_course]
        selected_student_id = select_student(service, selected_course)
        if not selected_student_id:
            return
        additional_context = input("Provide additional context about the student (e.g., attendance, behavior, external factors) for a more accurate report: ")

    categories = ["High Performer", "At Risk", "Average", "Improving", "Emerging", "Needs Review"]

    for course in target_courses:
        logger.info("Analysing course=%s (%s)", course["id"], course["name"])
        student_analysis = analyse_students(service, course, selected_student_id, additional_context, start_date, end_date)
        if not student_analysis:
            logger.warning("No students to analyse in course=%s", course["id"])
            with open("student_reports.txt", "a", encoding="utf-8") as f:
                f.write(f"No students to analyze in course {course['name']} ({course['id']})\n\n")
            continue

        reports = generate_reports(student_analysis, categories, args.ollama_model)
        save_reports_to_file(course, student_analysis, reports)
        for sid, rep in reports.items():
            logger.info("Report for student=%s: %s", sid, rep["ai_response"][:120])

    # Start chatbot after reports are generated
    #run_chatbot(ollama_model=args.ollama_model)

if __name__ == "__main__":
    main()