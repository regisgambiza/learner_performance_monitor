import logging

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

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