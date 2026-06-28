from flask import Flask, render_template, request, redirect, session, url_for, send_file, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timezone
import os
import pandas as pd
import io
import certifi

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "admin123")

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb+srv://umiraoutlook_db_user:umira123@cluster0.x4b4h0j.mongodb.net/?appName=Cluster0",
)
DB_NAME = os.environ.get("MONGO_DB", "mcq_system")
LIVE_QUESTIONS_COLLECTION = os.environ.get("LIVE_QUESTIONS_COLLECTION", "Live questions")
SUBJECTS_COLLECTION = os.environ.get("SUBJECTS_COLLECTION", "subjects")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[DB_NAME]
live_questions = db[LIVE_QUESTIONS_COLLECTION]
subjects_collection = db[SUBJECTS_COLLECTION]

PASS_THRESHOLD = 50


def require_admin():
    if "admin" not in session:
        return redirect("/")
    return None


def parse_id(doc_id):
    try:
        return ObjectId(doc_id)
    except Exception:
        return doc_id


def normalize_student(raw):
    """Map MongoDB Atlas `students` documents to a consistent internal shape."""
    if not raw:
        return {}

    name = (raw.get("name") or "").strip()
    if raw.get("first_name"):
        first = raw.get("first_name", "")
        last = raw.get("last_name", "")
        full_name = f"{first} {last}".strip()
    elif name:
        parts = name.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
        full_name = name
    else:
        first, last, full_name = "", "", ""

    return {
        **raw,
        "name": full_name or name,
        "first_name": first,
        "last_name": last,
        "degree": raw.get("degree") or raw.get("programme", ""),
        "programme": raw.get("programme") or raw.get("degree", ""),
        "batch": raw.get("batch") or raw.get("admission_year", ""),
        "admission_year": raw.get("admission_year") or raw.get("batch", ""),
        "email": raw.get("email", ""),
        "mobile": raw.get("mobile", ""),
        "dob": raw.get("dob", ""),
        "dob_display": raw.get("dob_display", ""),
        "serial_no": raw.get("serial_no", ""),
    }


def find_student(student_id):
    parsed = parse_id(student_id)
    student = db.students.find_one({"_id": parsed})
    if student:
        return normalize_student(student)
    return None


def calc_percent(result):
    score = result.get("score", 0)
    total = result.get("total", 1) if result.get("total", 0) > 0 else 1
    return round((score / total) * 100, 1)


def build_user_maps(students):
    user_map_full = {}
    user_map = {}
    for student in students:
        reg_no = student.get("register_number", "")
        if reg_no:
            user_map_full[reg_no] = student
            user_map[reg_no] = student.get("name") or f"{student.get('first_name', '')} {student.get('last_name', '')}".strip()
    return user_map_full, user_map


def build_result_entry(result, user_map_full, user_map, rank=None):
    reg_no = result.get("register_number", "")
    user_info = user_map_full.get(reg_no, {})
    percent = calc_percent(result)
    violation = result.get("terminated_due_to_violation", False)

    if violation:
        status = "Violation"
    elif percent >= PASS_THRESHOLD:
        status = "Pass"
    else:
        status = "Fail"

    user_id = user_info.get("_id")
    display_name = (
        user_map.get(reg_no)
        or result.get("name")
        or "Unknown Student"
    )

    return {
        "rank": rank,
        "result_id": str(result.get("_id")),
        "name": display_name,
        "register_number": reg_no,
        "email": user_info.get("email", ""),
        "mobile": user_info.get("mobile", ""),
        "degree": user_info.get("degree") or result.get("programme", "") or "—",
        "batch": user_info.get("batch") or result.get("admission_year", "") or "—",
        "level": user_info.get("level", "") or "—",
        "semester": user_info.get("semester") or result.get("semester", "") or "—",
        "subject": user_info.get("subject") or result.get("subject_title", "") or "—",
        "subject_code": result.get("subject_code", ""),
        "score": result.get("score", 0),
        "total": result.get("total", 1) if result.get("total", 0) > 0 else 1,
        "correct": result.get("correct", 0),
        "wrong": result.get("wrong", 0),
        "unanswered": result.get("unanswered", 0),
        "exam_date": result.get("exam_date", ""),
        "percent": percent,
        "violation": violation,
        "status": status,
        "user_id": str(user_id) if user_id else None,
    }


def build_leaderboard(results, user_map_full, user_map, include_violations=False, limit=None):
    valid_results = results if include_violations else [
        r for r in results if not r.get("terminated_due_to_violation")
    ]
    valid_results = sorted(
        valid_results,
        key=lambda x: (calc_percent(x), x.get("score", 0)),
        reverse=True,
    )

    if limit:
        valid_results = valid_results[:limit]

    return [
        build_result_entry(result, user_map_full, user_map, rank=index)
        for index, result in enumerate(valid_results, start=1)
    ]


def get_not_attempted(students, results):
    attempted_regs = {r.get("register_number") for r in results if r.get("register_number")}
    not_attempted = []
    for student in students:
        reg_no = student.get("register_number", "")
        if reg_no and reg_no not in attempted_regs:
            not_attempted.append({
                "user_id": str(student.get("_id")),
                "name": student.get("name") or f"{student.get('first_name', '')} {student.get('last_name', '')}".strip(),
                "register_number": reg_no,
                "email": student.get("email", ""),
                "mobile": student.get("mobile", ""),
                "degree": student.get("degree", "") or "—",
                "batch": student.get("batch", "") or "—",
                "subject": student.get("subject", "") or "—",
            })
    return not_attempted


def compute_dashboard_stats(students, results):
    user_map_full, user_map = build_user_maps(students)
    passed = failed = violations = 0

    for result in results:
        entry = build_result_entry(result, user_map_full, user_map)
        if entry["violation"]:
            violations += 1
        elif entry["percent"] >= PASS_THRESHOLD:
            passed += 1
        else:
            failed += 1

    total_exams = len(results)
    pass_rate = round((passed / total_exams) * 100, 1) if total_exams else 0

    return {
        "total_users": len(students),
        "total_exams": total_exams,
        "passed": passed,
        "failed": failed,
        "violations": violations,
        "pass_rate": pass_rate,
        "not_attempted": len(get_not_attempted(students, results)),
        "avg_score": round(
            sum(calc_percent(r) for r in results) / total_exams, 1
        ) if total_exams else 0,
    }


def compute_analytics_stats(students, results):
    user_map_full, user_map = build_user_maps(students)
    passed = failed = violation_count = 0
    score_distribution = {"0-20%": 0, "21-40%": 0, "41-60%": 0, "61-80%": 0, "81-100%": 0}
    passed_students = []
    failed_students = []
    violation_students = []

    for result in results:
        entry = build_result_entry(result, user_map_full, user_map)
        percent = entry["percent"]

        if entry["violation"]:
            violation_count += 1
            violation_students.append(entry)
        if percent >= PASS_THRESHOLD and not entry["violation"]:
            passed += 1
            passed_students.append(entry)
        elif not entry["violation"]:
            failed += 1
            failed_students.append(entry)

        if percent <= 20:
            score_distribution["0-20%"] += 1
        elif percent <= 40:
            score_distribution["21-40%"] += 1
        elif percent <= 60:
            score_distribution["41-60%"] += 1
        elif percent <= 80:
            score_distribution["61-80%"] += 1
        else:
            score_distribution["81-100%"] += 1

    degree_counts = {}
    batch_counts = {}
    for student in students:
        degree = student.get("degree", "Unknown") or "Unknown"
        batch = student.get("batch", "Unknown") or "Unknown"
        degree_counts[degree] = degree_counts.get(degree, 0) + 1
        batch_counts[batch] = batch_counts.get(batch, 0) + 1

    top_performers = build_leaderboard(results, user_map_full, user_map, limit=10)
    not_attempted = get_not_attempted(students, results)

    return {
        "stats": {
            "total_users": len(students),
            "total_exams": len(results),
            "passed": passed,
            "failed": failed,
            "violation_count": violation_count,
            "not_attempted": len(not_attempted),
            "normal_completion": len(results) - violation_count,
            "score_distribution": score_distribution,
            "degree_counts": degree_counts,
            "batch_counts": batch_counts,
            "top_performers": top_performers,
            "pass_rate": round((passed / len(results)) * 100, 1) if results else 0,
            "avg_score": round(sum(calc_percent(r) for r in results) / len(results), 1) if results else 0,
        },
        "passed_students": sorted(passed_students, key=lambda x: x["percent"], reverse=True),
        "failed_students": sorted(failed_students, key=lambda x: x["percent"]),
        "violation_students": violation_students,
        "not_attempted": not_attempted,
    }


def fetch_all_data():
    students = [normalize_student(s) for s in db.students.find()]
    results = list(db.exam_results.find())
    return students, results


def student_matches_search(student, query):
    q = query.lower()
    return (
        q in (student.get("name") or "").lower()
        or q in (student.get("first_name") or "").lower()
        or q in (student.get("last_name") or "").lower()
        or q in (student.get("register_number") or "").lower()
        or q in (student.get("degree") or "").lower()
        or q in (student.get("programme") or "").lower()
        or q in (student.get("batch") or "").lower()
        or q in (student.get("admission_year") or "").lower()
    )


def result_matches_search(result, query):
    q = query.lower()
    return (
        q in (result.get("register_number") or "").lower()
        or q in (result.get("name") or "").lower()
        or q in (result.get("subject_title") or "").lower()
        or q in (result.get("subject_code") or "").lower()
    )


def utc_now():
    return datetime.now(timezone.utc)


def normalize_subject_record(doc):
    if not doc:
        return None

    name = (
        doc.get("subject_name")
        or doc.get("name")
        or doc.get("subject")
        or doc.get("title")
        or doc.get("subject_title")
        or ""
    ).strip()

    code = (
        doc.get("subject_code")
        or doc.get("code")
        or doc.get("subjectCode")
        or ""
    ).strip()

    if not name:
        return None

    return {
        "id": str(doc.get("_id")),
        "name": name,
        "code": code,
    }


def get_available_subjects():
    subjects = []
    for doc in subjects_collection.find():
        normalized = normalize_subject_record(doc)
        if normalized:
            subjects.append(normalized)

    return sorted(subjects, key=lambda item: item["name"].lower())


def find_subject(subject_name=None, subject_id=None):
    if subject_id:
        record = normalize_subject_record(
            subjects_collection.find_one({"_id": parse_id(subject_id)})
        )
        if record:
            return record

    if subject_name:
        target = subject_name.strip().lower()
        for doc in subjects_collection.find():
            record = normalize_subject_record(doc)
            if record and record["name"].lower() == target:
                return record

    return None


def serialize_live_question(doc):
    return {
        "id": str(doc.get("_id")),
        "subject": doc.get("subject", ""),
        "subject_code": doc.get("subject_code", ""),
        "question_number": doc.get("question_number", 0),
        "question_text": doc.get("question_text", ""),
        "options": doc.get("options", {}),
        "correct_answer": doc.get("correct_answer", ""),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else "",
    }


def validate_question_payload(question, index):
    errors = []
    question_text = (question.get("question_text") or "").strip()
    if not question_text:
        errors.append(f"Question {index}: text is required.")

    options = question.get("options") or {}
    for key in ("A", "B", "C", "D"):
        if not (options.get(key) or "").strip():
            errors.append(f"Question {index}: option {key} is required.")

    correct = (question.get("correct_answer") or "").strip().upper()
    if correct not in ("A", "B", "C", "D"):
        errors.append(f"Question {index}: select a valid correct answer.")

    return errors


def build_live_question_docs(subject, subject_code, subject_id, questions):
    now = utc_now()
    docs = []
    for index, question in enumerate(questions, start=1):
        options = question.get("options") or {}
        docs.append({
            "subject": subject,
            "subject_code": subject_code,
            "subject_id": subject_id,
            "question_number": index,
            "question_text": question["question_text"].strip(),
            "options": {
                "A": options["A"].strip(),
                "B": options["B"].strip(),
                "C": options["C"].strip(),
                "D": options["D"].strip(),
            },
            "correct_answer": question["correct_answer"].strip().upper(),
            "status": "live",
            "created_at": now,
            "published_at": now,
        })
    return docs


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form["username"] == ADMIN_USERNAME
            and request.form["password"] == ADMIN_PASSWORD
        ):
            session["admin"] = True
            return redirect("/dashboard")
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    auth = require_admin()
    if auth:
        return auth
        
    search_query = request.args.get("search", "").strip()
    all_students, all_results = fetch_all_data()
    user_map_full, user_map = build_user_maps(all_students)
    
    if search_query:
        students = [s for s in all_students if student_matches_search(s, search_query)]
        results = [r for r in all_results if result_matches_search(r, search_query)]
    else:
        students = all_students
        results = all_results

    enriched_results = [build_result_entry(r, user_map_full, user_map) for r in results]
    stats = compute_dashboard_stats(all_students, all_results)
    top_three = build_leaderboard(all_results, user_map_full, user_map, limit=3)
    not_attempted = get_not_attempted(all_students, all_results)[:5]

    return render_template(
        "dashboard.html",
        users=students,
        results=enriched_results,
        search_query=search_query,
        stats=stats,
        top_three=top_three,
        not_attempted=not_attempted,
        active_page="dashboard",
    )


@app.route("/leaderboard")
def leaderboard():
    auth = require_admin()
    if auth:
        return auth

    status_filter = request.args.get("status", "all")
    degree_filter = request.args.get("degree", "")
    search_query = request.args.get("search", "").strip()

    students, results = fetch_all_data()
    user_map_full, user_map = build_user_maps(students)

    include_violations = status_filter in ("all", "violation")
    entries = build_leaderboard(results, user_map_full, user_map, include_violations=include_violations)

    if status_filter == "pass":
        entries = [e for e in entries if e["status"] == "Pass"]
    elif status_filter == "fail":
        entries = [e for e in entries if e["status"] == "Fail"]
    elif status_filter == "violation":
        entries = [e for e in entries if e["status"] == "Violation"]

    if degree_filter:
        entries = [e for e in entries if e["degree"].lower() == degree_filter.lower()]

    if search_query:
        q = search_query.lower()
        entries = [
            e for e in entries
            if q in e["name"].lower()
            or q in e["register_number"].lower()
            or q in (e["subject"] or "").lower()
            or q in (e["subject_code"] or "").lower()
        ]

    for index, entry in enumerate(entries, start=1):
        entry["rank"] = index

    degrees = sorted({s.get("degree") for s in students if s.get("degree")})
    stats = compute_dashboard_stats(students, results)
    podium = entries[:3]

    return render_template(
        "leaderboard.html",
        entries=entries,
        podium=podium,
        stats=stats,
        status_filter=status_filter,
        degree_filter=degree_filter,
        search_query=search_query,
        degrees=degrees,
        active_page="leaderboard",
    )


@app.route("/edit_user/<user_id>", methods=["GET", "POST"])
def edit_user(user_id):
    auth = require_admin()
    if auth:
        return auth
        
    if request.method == "POST":
        full_name = f"{request.form.get('first_name', '')} {request.form.get('last_name', '')}".strip()
        db.students.update_one(
            {"_id": parse_id(user_id)},
            {
                "$set": {
                    "name": full_name,
                "register_number": request.form.get("register_number"),
                    "programme": request.form.get("degree"),
                    "admission_year": request.form.get("batch"),
                    "dob": request.form.get("dob"),
                }
            },
        )
        return redirect(url_for("view_user", user_id=user_id))

    user = find_student(user_id)
    if not user:
        return redirect("/dashboard")
    return render_template("edit_user.html", user=user, active_page="dashboard")
        

@app.route("/delete_user/<user_id>")
def delete_user(user_id):
    auth = require_admin()
    if auth:
        return auth
    user = find_student(user_id)
    if user and user.get("register_number"):
        db.exam_results.delete_many({"register_number": user["register_number"]})
    db.students.delete_one({"_id": parse_id(user_id)})
    return redirect("/dashboard")


@app.route("/delete_result/<result_id>")
def delete_result(result_id):
    auth = require_admin()
    if auth:
        return auth
    db.exam_results.delete_one({"_id": parse_id(result_id)})
    return redirect("/dashboard")


@app.route("/clear_all_data", methods=["POST"])
def clear_all_data():
    auth = require_admin()
    if auth:
        return auth
    db.students.delete_many({})
    db.exam_results.delete_many({})
    return redirect("/dashboard")


@app.route("/view_user/<user_id>")
def view_user(user_id):
    auth = require_admin()
    if auth:
        return auth
        
    user = find_student(user_id)
    if not user:
        return redirect("/dashboard")
        
    reg_no = user.get("register_number")
    raw_results = list(db.exam_results.find({"register_number": reg_no}))
    user_map_full, user_map = build_user_maps([user])
    user_results = sorted(
        [build_result_entry(r, user_map_full, user_map) for r in raw_results],
        key=lambda x: x["percent"],
        reverse=True,
    )

    return render_template(
        "view_user.html",
        user=user,
        results=user_results,
        active_page="dashboard",
    )


@app.route("/export")
def export_data():
    auth = require_admin()
    if auth:
        return auth

    students, results = fetch_all_data()
    user_map_full, user_map = build_user_maps(students)
    leaderboard = build_leaderboard(results, user_map_full, user_map, include_violations=True)

    df_students = pd.DataFrame(list(db.students.find({}, {"_id": 0})))
    df_results = pd.DataFrame(list(db.exam_results.find({}, {"_id": 0})))
    df_leaderboard = pd.DataFrame([
        {
            "Rank": e["rank"],
            "Name": e["name"],
            "Register Number": e["register_number"],
            "Programme": e["degree"],
            "Batch": e["batch"],
            "Subject": e["subject"],
            "Subject Code": e["subject_code"],
            "Score": e["score"],
            "Total": e["total"],
            "Correct": e["correct"],
            "Wrong": e["wrong"],
            "Unanswered": e["unanswered"],
            "Percentage": e["percent"],
            "Exam Date": e["exam_date"],
            "Status": e["status"],
        }
        for e in leaderboard
    ])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheets = [
            ("Students", df_students),
            ("Exam Results", df_results),
            ("Leaderboard", df_leaderboard),
        ]
        for name, df in sheets:
            if not df.empty:
                df.to_excel(writer, sheet_name=name, index=False)
        else:
                pd.DataFrame({"Message": ["No data"]}).to_excel(writer, sheet_name=name, index=False)
            
    output.seek(0)
    return send_file(output, download_name="mcq_portal_data.xlsx", as_attachment=True)


@app.route("/analytics")
def analytics():
    auth = require_admin()
    if auth:
        return auth

    students, results = fetch_all_data()
    data = compute_analytics_stats(students, results)

    return render_template(
        "analytics.html",
        stats=data["stats"],
        passed_students=data["passed_students"],
        failed_students=data["failed_students"],
        violation_students=data["violation_students"],
        not_attempted=data["not_attempted"],
        active_page="analytics",
    )


@app.route("/publish-questions")
def publish_questions_page():
    auth = require_admin()
    if auth:
        return auth

    subjects = get_available_subjects()
    live_subject_stats = list(live_questions.aggregate([
        {"$group": {"_id": "$subject", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]))

    return render_template(
        "publish_questions.html",
        subjects=subjects,
        live_subject_stats=live_subject_stats,
        active_page="publish_questions",
    )


@app.route("/api/live-questions")
def api_list_live_questions():
    auth = require_admin()
    if auth:
        return jsonify({"error": "Unauthorized"}), 401

    subject = request.args.get("subject", "").strip()
    query = {"subject": subject} if subject else {}
    questions = [
        serialize_live_question(doc)
        for doc in live_questions.find(query).sort("question_number", 1)
    ]

    return jsonify({
        "subject": subject,
        "count": len(questions),
        "questions": questions,
    })


@app.route("/api/live-questions/publish", methods=["POST"])
def api_publish_live_questions():
    auth = require_admin()
    if auth:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    subject_name = (payload.get("subject") or "").strip()
    subject_id = (payload.get("subject_id") or "").strip()
    questions = payload.get("questions") or []

    subject_record = find_subject(subject_name=subject_name, subject_id=subject_id)
    if not subject_record:
        return jsonify({"error": "Please select a valid subject from the Subject collection."}), 400

    subject = subject_record["name"]
    subject_code = subject_record["code"]
    subject_id = subject_record["id"]

    if not questions:
        return jsonify({"error": "Add at least one question before submitting."}), 400

    errors = []
    normalized = []
    for index, question in enumerate(questions, start=1):
        question_errors = validate_question_payload(question, index)
        errors.extend(question_errors)
        normalized.append({
            "question_text": question.get("question_text", ""),
            "options": question.get("options", {}),
            "correct_answer": question.get("correct_answer", ""),
        })

    if errors:
        return jsonify({"error": errors[0], "errors": errors}), 400

    docs = build_live_question_docs(subject, subject_code, subject_id, normalized)
    deleted = live_questions.delete_many({"subject": subject}).deleted_count
    live_questions.insert_many(docs)

    return jsonify({
        "success": True,
        "message": f"Published {len(docs)} question(s) for {subject}.",
        "subject": subject,
        "published_count": len(docs),
        "replaced_count": deleted,
    })


@app.route("/api/live-questions/clear", methods=["POST"])
def api_clear_live_questions():
    auth = require_admin()
    if auth:
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or "").strip()
    clear_all = payload.get("clear_all", False)

    if clear_all:
        deleted = live_questions.delete_many({}).deleted_count
        return jsonify({
            "success": True,
            "message": f"Cleared all {deleted} live question(s).",
            "deleted_count": deleted,
        })

    if not subject:
        return jsonify({"error": "Select a subject or choose clear all."}), 400

    deleted = live_questions.delete_many({"subject": subject}).deleted_count
    return jsonify({
        "success": True,
        "message": f"Cleared {deleted} question(s) for {subject}.",
        "subject": subject,
        "deleted_count": deleted,
    })


@app.route("/api/live_stats")
def live_stats():
    if "admin" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    students, results = fetch_all_data()
    stats = compute_dashboard_stats(students, results)
    data = compute_analytics_stats(students, results)

    return jsonify({
        **stats,
        "score_distribution": data["stats"]["score_distribution"],
    })


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
