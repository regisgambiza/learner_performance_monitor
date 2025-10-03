import logging
import pandas as pd
from get_all_students import get_all_students
from get_all_coursework import get_all_coursework

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

def analyse_students(service, course, selected_student_id=None, additional_context=None, start_date=None, end_date=None):
    students = get_all_students(service, course["id"])
    logger.info("Fetched %d students from course=%s", len(students), course["name"])

    if selected_student_id:
        students = [s for s in students if s["userId"] == selected_student_id]
        if not students:
            logger.error("Student %s not found in course %s", selected_student_id, course["id"])
            return {}

    coursework = get_all_coursework(service, course["id"], start_date, end_date)
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