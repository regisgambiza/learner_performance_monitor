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
            category = category_line.split(":", 1)[1].strip() if category_line else "Needs Review"

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
            average_score = metrics['average_score']
            total_possible_points = sum(cw.get("maxPoints", 0) for cw in student_analysis[sid]["coursework"] if cw.get("submission") and cw.get("submission").get("assignedGrade") is not None)
            average_max_points = total_possible_points / metrics['graded_count'] if metrics['graded_count'] > 0 else 0
            f.write(f"| Average Score   | {average_score:.2f}/{average_max_points:.2f} |\n")
            f.write("+-----------------+-----------------+\n\n")

            # --- Detailed Activity Table ---
            f.write("Detailed Submission Table:\n")
            f.write("==================================================\n")
            f.write("Title                           | ID              | Status    | Score     | Created\n")
            f.write("------------------------------------------------------------------------------------------\n")

            scores = []
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
                        score = f"{assigned_grade}/{max_points}"
                        scores.append(assigned_grade)
                        total_possible_points += max_points
                    else:
                        score = "—"
                f.write(f"{title[:32]:<32} | {id_:<16} | {status:<10} | {score:<10} | {created}\n")

            f.write("------------------------------------------------------------------------------------------\n\n")

            # --- Average Score Calculation ---
            f.write("Average Score Calculation:\n")
            if scores:
                f.write("Scores used: " + ", ".join(map(str, scores)) + "\n")
                total = sum(scores)
                count = len(scores)
                average = total / count
                f.write(f"Total Score: {total}\n")
                f.write(f"Count: {count}\n")
                f.write(f"Raw Average: {average:.2f}\n")
                if total_possible_points > 0:
                    percentage = (total / total_possible_points) * 100
                    average_max_points = total_possible_points / count
                    f.write(f"Total Possible Points: {total_possible_points}\n")
                    f.write(f"Average Score as Fraction: {average:.2f}/{average_max_points:.2f}\n")
                    f.write(f"Percentage: {percentage:.2f}%\n\n")
                else:
                    f.write("Total Possible Points: Not available\n")
                    f.write("Average Score as Fraction: Not calculable\n")
                    f.write("Percentage: Not calculable\n\n")
            else:
                f.write("No graded assignments.\n\n")

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