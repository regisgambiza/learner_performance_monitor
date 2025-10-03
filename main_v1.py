#Example usage: python main.py --start-date 2025-09-01 --end-date 2025-09-30
#Example usage: python main.py --start-date 2025-09-01

import os
import sys
import argparse
import logging
import time
import requests
import pandas as pd
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# Google Classroom scopes (fixed version)
SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.students.readonly",
    "https://www.googleapis.com/auth/classroom.student-submissions.me.readonly",
]

OLLAMA_API_URL = "http://localhost:11434/api/generate"

# ----------------- Google API Helpers -----------------

def get_classroom_service(credentials_file="credentials.json", token_file="token.json"):
    logger.info("Requesting Google Classroom service...")
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.debug("Refreshing expired Google credentials")
            creds.refresh(Request())
        else:
            logger.debug("Starting OAuth flow for Google Classroom")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    logger.info("Google Classroom service ready")
    return build("classroom", "v1", credentials=creds)


def get_all_courses(service):
    logger.debug("Fetching all courses...")
    courses = []
    page_token = None
    while True:
        response = service.courses().list(pageToken=page_token, pageSize=100, courseStates=['ACTIVE']).execute()
        courses.extend(response.get("courses", []))
        logger.debug("Fetched %d courses so far", len(courses))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return courses


def get_all_students(service, course_id):
    logger.debug("Fetching students for course_id=%s", course_id)
    students = []
    page_token = None
    while True:
        response = (
            service.courses()
            .students()
            .list(courseId=course_id, pageToken=page_token, pageSize=100)
            .execute()
        )
        students.extend(response.get("students", []))
        logger.debug("Fetched %d students so far for course_id=%s", len(students), course_id)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return students


def get_all_coursework(service, course_id, start_date=None, end_date=None):
    coursework = []
    page_token = None
    while True:
        response = service.courses().courseWork().list(
            courseId=course_id, pageToken=page_token, pageSize=100
        ).execute()
        for cw in response.get("courseWork", []):
            created = cw.get("creationTime")  # e.g. "2025-09-28T10:30:00Z"
            if start_date or end_date:
                if created:
                    created_ts = pd.to_datetime(created)
                    if start_date and created_ts < pd.to_datetime(start_date):
                        continue
                    if end_date and created_ts > pd.to_datetime(end_date):
                        continue
            coursework.append(cw)
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return coursework



# ----------------- AI Integration -----------------

def call_ollama_classify(prompt, model="gpt-oss:20b"):
    url = OLLAMA_API_URL
    payload = {"model": model, "prompt": prompt, "stream": True}
    logger.info("Calling Ollama model=%s with prompt length=%d chars", model, len(prompt))
    resp = requests.post(url, json=payload, stream=True, timeout=120)
    resp.raise_for_status()
    full_response = ""
    for line in resp.iter_lines():
        if line:
            try:
                chunk = json.loads(line)
                if "response" in chunk:
                    full_response += chunk["response"]
                if chunk.get("done", False):
                    logger.debug("Ollama stream finished")
                    break
            except json.JSONDecodeError:
                logger.warning("Failed to decode chunk: %s", line)
    logger.debug("Ollama response length=%d chars", len(full_response))
    return full_response.strip()


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


# ----------------- Analysis -----------------

def analyse_students(service, course, selected_student_id=None, additional_context=None):
    students = get_all_students(service, course["id"])
    logger.info("Fetched %d students from course=%s", len(students), course["name"])

    if selected_student_id:
        students = [s for s in students if s["userId"] == selected_student_id]
        if not students:
            logger.error("Student %s not found in course %s", selected_student_id, course["id"])
            return {}

    coursework = get_all_coursework(service, course["id"])
    logger.info("Fetched %d coursework items from course=%s", len(coursework), course["name"])

    # --- Fetch all submissions in bulk ---
    logger.info("Fetching submissions in bulk for all coursework...")
    submissions_lookup = {}  # (studentId, courseworkId) -> submission
    for j, cw in enumerate(coursework, 1):
        logger.debug("Fetching submissions for coursework %d/%d: %s",
                     j, len(coursework), cw.get("title", cw["id"]))
        try:
            subs_response = service.courses().courseWork().studentSubmissions().list(
                courseId=course["id"],
                courseWorkId=cw["id"],
                pageSize=200
            ).execute()
            subs = subs_response.get("studentSubmissions", [])
            for sub in subs:
                sid = sub.get("userId")
                if sid:
                    submissions_lookup[(sid, cw["id"])] = sub
        except Exception as e:
            logger.warning("Error fetching submissions for coursework=%s: %s",
                           cw.get("id"), str(e))

    logger.info("Finished bulk fetch: %d total submissions cached", len(submissions_lookup))

    # --- Analyse per student ---
    student_analysis = {}
    for idx, s in enumerate(students, 1):
        profile = s.get("profile", {})
        name_info = profile.get("name", {})
        full_name = " ".join(filter(None, [name_info.get("givenName", ""), name_info.get("familyName", "")])).strip() or s["userId"]

        logger.info("Processing student %d/%d: %s", idx, len(students), full_name)

        metrics = {
            "total_assignments": len(coursework),
            "missing": 0,
            "late": 0,
            "average_score": 0.0,
            "graded_count": 0,
            "additional_context": additional_context if selected_student_id else ""
        }
        total_score = 0.0

        for cw in coursework:
            sub = submissions_lookup.get((s["userId"], cw["id"]))
            if not sub:
                metrics["missing"] += 1
                continue
            state = sub.get("state", "")
            if state in ["NEW", "CREATED"]:
                metrics["missing"] += 1
            if sub.get("late", False):
                metrics["late"] += 1
            if "assignedGrade" in sub:
                total_score += sub["assignedGrade"]
                metrics["graded_count"] += 1

                if metrics["graded_count"] > 0:
                    metrics["average_score"] = total_score / metrics["graded_count"]

                # Attach student, metrics, and detailed coursework/submission info
                student_analysis[s["userId"]] = {
                    "student": s,
                    "metrics": metrics,
                    "coursework": [
                        {
                            "id": cw["id"],
                            "title": cw.get("title", ""),
                            "submission": submissions_lookup.get((s["userId"], cw["id"]))
                        }
                        for cw in coursework
                    ]
                }

                logger.info("Finished metrics for %s -> %s", full_name, metrics)


    return student_analysis



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

# ----------------- Report Saving -----------------

def save_reports_to_file(course, student_analysis, reports, output_file="student_reports.txt"):
    logger.info("Saving reports to %s", output_file)

    category_groups = {}

    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"Reports for Course: {course['name']} ({course['id']})\n")
        f.write("=" * 50 + "\n")
        for sid, rep in reports.items():
            profile = student_analysis[sid]["student"].get("profile", {}) if sid in student_analysis else {}
            name_info = profile.get("name", {})
            full_name = " ".join(filter(None, [name_info.get("givenName",""), name_info.get("familyName","")])).strip() or sid

            ai_text = rep["ai_response"]

            # Extract category
            category_line = next((line for line in ai_text.splitlines() if line.strip().startswith("Category:")), None)
            category = category_line.split(":", 1)[1].strip() if category_line else "Uncategorized"

            # Add to grouping
            category_groups.setdefault(category, []).append(full_name)

            # --- Write header + AI teacher report ---
            f.write(f"Student: {full_name}\n")
            f.write(f"Student ID: {sid}\n")
            f.write(f"Teacher Report:\n{ai_text}\n")

            metrics = student_analysis[sid]["metrics"]

            # --- Submission Summary Table ---
            f.write("\nSubmission Summary Table:\n")
            f.write("+-----------------+-----------------+\n")
            f.write("| Metric          | Value           |\n")
            f.write("+-----------------+-----------------+\n")
            f.write(f"| Total Assigned  | {metrics['total_assignments']:<15} |\n")
            f.write(f"| Missing         | {metrics['missing']:<15} |\n")
            f.write(f"| Late            | {metrics['late']:<15} |\n")
            f.write(f"| Graded Count    | {metrics['graded_count']:<15} |\n")
            f.write(f"| Average Score   | {metrics['average_score']:<15.2f} |\n")
            f.write("+-----------------+-----------------+\n\n")

            # --- Detailed Activity Table ---
            f.write("Detailed Submission Table:\n")
            f.write("==================================================\n")
            f.write("Title                           | ID              | Status    | Score     | Created\n")
            f.write("------------------------------------------------------------------------------------------\n")

            # loop all coursework items in order
            for cw in student_analysis[sid]["coursework"]:
                title = cw.get("title", cw["id"])
                id_ = cw["id"]
                created = cw.get("creationTime", "—")
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
                    score = submission.get("assignedGrade", "—")
                f.write(f"{title[:32]:<32} | {id_:<16} | {status:<10} | {score:<10} | {created}\n")

            f.write("------------------------------------------------------------------------------------------\n\n")
            f.write("-" * 50 + "\n")
        f.write("\n")

    # --- Save separate category file ---
    cat_file = "category_groups.txt"
    with open(cat_file, "a", encoding="utf-8") as cf:
        cf.write(f"Course: {course['name']} ({course['id']})\n")
        cf.write("=" * 40 + "\n")
        for cat, learners in category_groups.items():
            cf.write(f"{cat}:\n")
            for name in learners:
                cf.write(f" - {name}\n")
            cf.write("\n")
    logger.info(f"Category grouping saved to {cat_file}")


    # --- Save separate category file ---
    cat_file = "category_groups.txt"
    with open(cat_file, "a", encoding="utf-8") as cf:
        cf.write(f"Course: {course['name']} ({course['id']})\n")
        cf.write("=" * 40 + "\n")
        for cat, learners in category_groups.items():
            cf.write(f"{cat}:\n")
            for name in learners:
                cf.write(f" - {name}\n")
            cf.write("\n")
    logger.info(f"Category grouping saved to {cat_file}")


# ----------------- Interactive Selection -----------------

def select_course(courses):
    print("Available courses:")
    for i, course in enumerate(courses, 1):
        print(f"{i}. {course['name']} (ID: {course['id']})")
    while True:
        try:
            choice = int(input("Select course number: "))
            if 1 <= choice <= len(courses):
                return courses[choice - 1]
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")


def select_student(service, course):
    students = get_all_students(service, course["id"])
    if not students:
        print("No students in this course.")
        return None
    print("Available students:")
    for i, s in enumerate(students, 1):
        profile = s.get("profile", {})
        name_info = profile.get("name", {})
        full_name = " ".join(filter(None, [name_info.get("givenName",""), name_info.get("familyName","")])).strip() or s["userId"]
        print(f"{i}. {full_name} (ID: {s['userId']})")
    while True:
        try:
            choice = int(input("Select student number: "))
            if 1 <= choice <= len(students):
                return students[choice - 1]["userId"]
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Please enter a number.")

# ----------------- Main -----------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--token", default="token.json")
    parser.add_argument("--ollama-model", default="gpt-oss:20b")
    args = parser.parse_args()

    logger.info("Starting learner analysis run")

    service = get_classroom_service(args.credentials, args.token)
    courses = get_all_courses(service)
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

    categories = ["High Performer", "At Risk", "Average", "Improving"]

    for course in target_courses:
        logger.info("Analysing course=%s (%s)", course["id"], course["name"])
        student_analysis = analyse_students(service, course, selected_student_id, additional_context)
        if not student_analysis:
            logger.warning("No students to analyse in course=%s", course["id"])
            with open("student_reports.txt", "a", encoding="utf-8") as f:
                f.write(f"No students to analyze in course {course['name']} ({course['id']})\n\n")
            continue

        reports = generate_reports(student_analysis, categories, args.ollama_model)
        save_reports_to_file(course, student_analysis, reports)
        for sid, rep in reports.items():
            logger.info("Report for student=%s: %s", sid, rep["ai_response"][:120])


if __name__ == "__main__":
    main()