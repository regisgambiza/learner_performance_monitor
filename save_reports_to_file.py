import logging
import os
import re

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

def save_reports_to_file(course, student_analysis, reports, output_file="student_reports.txt"):
    # Ensure reports directory exists and create a per-course file so classes aren't mixed
    reports_dir = os.getenv("REPORTS_DIR", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # Create a safe filename from the course name
    safe_course = re.sub(r'[^A-Za-z0-9 _-]', '', course.get('name', 'course')).strip()
    safe_course = safe_course.replace(' ', '_')[:100]
    file_base = f"{safe_course}_{course.get('id') }"

    # If caller passed the default output file name, override it to go into reports dir per-course
    if output_file == "student_reports.txt":
        output_path = os.path.join(reports_dir, f"{file_base}.txt")
    else:
        output_path = output_file

    logger.info("Saving reports to %s", output_path)

    category_groups = {}

    # Open per-course report file (overwrite so repeated runs don't mix old data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Reports for Course: {course['name']} ({course['id']})\n")
        f.write("=" * 50 + "\n")
        for sid, rep in reports.items():
            profile = student_analysis[sid]["student"].get("profile", {}) if sid in student_analysis else {}
            name_info = profile.get("name", {})
            full_name = " ".join(filter(None, [name_info.get("givenName",""), name_info.get("familyName","")])).strip() or sid

            ai_text = rep["ai_response"]

            # Extract category
            category_line = next((line for line in ai_text.splitlines() if line.strip().startswith("Category:")), None)
            category = category_line.split(":", 1)[1].strip() if category_line else "Needs Review"

            # Add to grouping
            category_groups.setdefault(category, []).append(full_name)

            # --- Write header + AI teacher report ---
            f.write(f"Student: {full_name}\n")
            f.write(f"Student ID: {sid}\n")
            f.write(f"Teacher Report:\n{ai_text}\n")

            metrics = student_analysis[sid]["metrics"]

            # --- Submission Summary Table ---
            scores = []
            total_possible_points = 0
            for cw in student_analysis[sid]["coursework"]:
                submission = cw.get("submission")
                if submission and "assignedGrade" in submission and cw.get("maxPoints"):
                    assigned = submission["assignedGrade"]
                    if assigned > 0:  # New: Explicitly exclude 0s (consistent with metrics)
                        scores.append(assigned)
                        total_possible_points += cw["maxPoints"]

            f.write("\nSubmission Summary Table:\n")
            f.write("+-----------------+-----------------+\n")
            f.write("| Metric          | Value           |\n")
            f.write("+-----------------+-----------------+\n")
            f.write(f"| Total Assigned  | {metrics['total_assignments']:<15} |\n")
            f.write(f"| Missing         | {metrics['missing']:<15} |\n")
            f.write(f"| Late            | {metrics['late']:<15} |\n")
            f.write(f"| Graded Count    | {metrics['graded_count']:<15} |\n")
            # Average for submitted activities (percentage) and earned/possible
            f.write(f"| Average (submitted) | {metrics['average_submitted']:<7.2f}% ({sum(scores):.2f}/{total_possible_points:.2f}) |\n")
            # Average including all activities (missing treated as 0)
            f.write(f"| Average (all)       | {metrics['average_all']:<7.2f}%{'':<13} |\n")
            f.write("+-----------------+-----------------+\n\n")

            # --- Detailed Activity Table ---
            f.write("Detailed Submission Table:\n")
            f.write("==================================================\n")
            f.write("Title                           | ID              | Status    | Score     | Created\n")
            f.write("------------------------------------------------------------------------------------------\n")

            scores = []  # Reset for this table (though not used after writing)
            total_possible_points = 0

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
                    assigned_grade = submission.get("assignedGrade")
                    max_points = cw.get("maxPoints")
                    if assigned_grade is not None and max_points is not None:
                        if assigned_grade == 0:
                            status = "Missing"
                            score = "—"
                        else:
                            score = f"{assigned_grade}/{max_points}"
                            scores.append(assigned_grade)
                            total_possible_points += max_points
                    else:
                        score = "—"
                f.write(f"{title[:32]:<32} | {id_:<16} | {status:<10} | {score:<10} | {created}\n")

            f.write("------------------------------------------------------------------------------------------\n\n")

            f.write("-" * 50 + "\n")
        f.write("\n")

    # --- Save separate category file per course inside reports dir (overwrite) ---
    cat_file = os.path.join(reports_dir, f"{file_base}_categories.txt")
    with open(cat_file, "w", encoding="utf-8") as cf:
        cf.write(f"Course: {course['name']} ({course['id']})\n")
        cf.write("=" * 40 + "\n")
        for cat, learners in category_groups.items():
            cf.write(f"{cat}:\n")
            for name in learners:
                cf.write(f" - {name}\n")
            cf.write("\n")
    logger.info("Category grouping saved to %s", cat_file)