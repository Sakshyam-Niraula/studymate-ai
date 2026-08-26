from flask import Flask, render_template, request, session
from google import genai
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import fitz
import os
import json
import uuid


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "studymate-development-key"
)


# =========================================================
# CONFIGURATION
# =========================================================

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum PDF size: 20 MB
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("WARNING: GEMINI_API_KEY is not configured.")

client = (
    genai.Client(api_key=api_key)
    if api_key
    else None
)

MODEL_NAME = "models/gemini-3.6-flash"


# =========================================================
# USER SESSION
# =========================================================

def get_user_id():

    if "user_id" not in session:

        session["user_id"] = str(
            uuid.uuid4()
        )

    return session["user_id"]


# =========================================================
# USER-SPECIFIC FOLDER
# =========================================================

def get_user_folder():

    user_id = get_user_id()

    folder = os.path.join(
        UPLOAD_FOLDER,
        user_id
    )

    os.makedirs(
        folder,
        exist_ok=True
    )

    return folder


# =========================================================
# STUDY MATERIAL PATH
# =========================================================

def get_material_path():

    return os.path.join(
        get_user_folder(),
        "study_material.txt"
    )


# =========================================================
# CHECK FILE
# =========================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# ROBOTS.TXT
# =========================================================

@app.route("/robots.txt")
def robots_txt():

    return (
        "User-agent: *\n"
        "Allow: /\n\n"
        "Sitemap: https://studymate-ai-dydg.onrender.com/sitemap.xml\n"
    ), 200, {
        "Content-Type": "text/plain"
    }


# =========================================================
# SITEMAP.XML
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    return """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://studymate-ai-dydg.onrender.com/</loc>
    </url>
</urlset>""", 200, {
        "Content-Type": "application/xml"
    }


# =========================================================
# UPLOAD PDF
# =========================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    pdf = request.files.get("pdf")

    if not pdf or pdf.filename == "":

        return render_template(
            "index.html",
            error="Please choose a PDF."
        )

    if not allowed_file(pdf.filename):

        return render_template(
            "index.html",
            error="Only PDF files are allowed."
        )

    safe_filename = secure_filename(
        pdf.filename
    )

    if not safe_filename:

        return render_template(
            "index.html",
            error="Invalid filename."
        )

    user_folder = get_user_folder()

    filepath = os.path.join(
        user_folder,
        safe_filename
    )

    pdf.save(filepath)

    try:

        document = fitz.open(filepath)

        text = ""

        for page_number, page in enumerate(
            document,
            start=1
        ):

            page_text = page.get_text()

            print(
                f"User {get_user_id()[:8]} | "
                f"Page {page_number}: "
                f"{len(page_text)} characters"
            )

            text += page_text + "\n"

        document.close()

        if not text.strip():

            if os.path.exists(filepath):
                os.remove(filepath)

            return render_template(
                "index.html",
                error=(
                    "This PDF contains no selectable "
                    "text. It may be a scanned or "
                    "image-based PDF."
                )
            )

        material_path = get_material_path()

        with open(
            material_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(text)

        print("\n==============================")
        print("PDF UPLOAD SUCCESS")
        print("==============================")
        print(
            f"User: {get_user_id()[:8]}"
        )
        print(
            f"File: {safe_filename}"
        )
        print(
            f"Characters: {len(text)}"
        )
        print("==============================\n")

        return render_template(
            "index.html",
            filename=safe_filename,
            success=(
                "Study material uploaded successfully!"
            )
        )

    except Exception as e:

        print(
            "PDF ERROR:",
            e
        )

        if os.path.exists(filepath):
            os.remove(filepath)

        return render_template(
            "index.html",
            error=(
                f"Could not read PDF: {str(e)}"
            )
        )


# =========================================================
# GET STUDY MATERIAL
# =========================================================

def get_study_material():

    material_path = get_material_path()

    if not os.path.exists(
        material_path
    ):

        return None

    with open(
        material_path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


# =========================================================
# GEMINI FUNCTION
# =========================================================

def ask_gemini(prompt):

    if client is None:

        return (
            "Gemini API key is not configured."
        )

    try:

        response = client.models.generate_content(

            model=MODEL_NAME,

            contents=prompt

        )

        if not response.text:

            return (
                "Gemini returned an empty response."
            )

        return response.text

    except Exception as e:

        print(
            "GEMINI ERROR:",
            e
        )

        return (
            f"Gemini error: {str(e)}"
        )


# =========================================================
# ASK STUDYMATE
# =========================================================

@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    question = request.form.get(
        "question",
        ""
    ).strip()

    if not question:

        return render_template(
            "index.html",
            error="Please enter a question."
        )

    study_material = get_study_material()

    if study_material is None:

        return render_template(
            "index.html",
            answer="Please upload a PDF first."
        )

    prompt = f"""
You are StudyMate, an AI tutor.

Your job is to help the student understand
their uploaded study material.

IMPORTANT RULES:

1. Use ONLY the study material.
2. Do NOT use outside knowledge.
3. Do NOT invent information.
4. If the answer cannot be found in the material,
say exactly:

"I couldn't find that information in your study material."

5. Keep explanations clear and appropriate for students.
6. Make difficult concepts easier to understand.
7. Be concise but useful.

When appropriate, structure the answer as:

📚 Explanation

💡 In simple words

🎯 Exam tip

🧠 Quick check


STUDY MATERIAL:
==============================

{study_material}

==============================

STUDENT QUESTION:

{question}
"""

    answer = ask_gemini(prompt)

    return render_template(
        "index.html",
        answer=answer
    )


# =========================================================
# GENERATE QUIZ
# =========================================================

@app.route(
    "/quiz",
    methods=["POST"]
)
def quiz():

    num_questions = request.form.get(
        "num_questions",
        "5"
    )

    difficulty = request.form.get(
        "difficulty",
        "medium"
    )

    allowed_numbers = {
        "5",
        "10",
        "15",
        "20"
    }

    if num_questions not in allowed_numbers:

        num_questions = "5"

    allowed_difficulties = {
        "easy",
        "medium",
        "hard"
    }

    if difficulty not in allowed_difficulties:

        difficulty = "medium"

    study_material = get_study_material()

    if study_material is None:

        return render_template(
            "index.html",
            error="Please upload a PDF first."
        )

    print("\n==============================")
    print("GENERATING QUIZ")
    print("==============================")
    print(
        f"Questions requested: {num_questions}"
    )
    print(
        f"Difficulty: {difficulty}"
    )
    print(
        f"Study material: {len(study_material)} characters"
    )
    print("==============================\n")

    prompt = f"""
You are StudyMate, an educational quiz generator.

Create EXACTLY {num_questions} multiple-choice questions
from the study material provided below.

DIFFICULTY:
{difficulty}

IMPORTANT RULES:

1. Use ONLY the study material.
2. Do NOT use outside knowledge.
3. Create EXACTLY {num_questions} questions.
4. Every question must have exactly 4 options.
5. There must be exactly ONE correct answer.
6. The correct answer must be represented by an integer.
7. Use 0 for option A.
8. Use 1 for option B.
9. Use 2 for option C.
10. Use 3 for option D.
11. Include a short explanation.
12. Return ONLY valid JSON.
13. Do NOT use Markdown.
14. Do NOT write ```json.
15. Do NOT write anything before or after the JSON.

Return exactly this format:

[
  {{
    "question": "Question text",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer": 0,
    "explanation": "Short explanation"
  }}
]

STUDY MATERIAL:
==============================

{study_material}

==============================
"""

    quiz_text = ask_gemini(prompt)

    print("\n==============================")
    print("RAW QUIZ RESPONSE")
    print("==============================")
    print(quiz_text)
    print("==============================\n")

    try:

        quiz_text = quiz_text.strip()

        if quiz_text.startswith("```"):

            lines = quiz_text.splitlines()

            cleaned_lines = []

            for line in lines:

                if line.strip().startswith("```"):
                    continue

                cleaned_lines.append(line)

            quiz_text = "\n".join(
                cleaned_lines
            ).strip()

        start = quiz_text.find("[")

        end = quiz_text.rfind("]")

        if start == -1 or end == -1:

            raise ValueError(
                "No JSON array found."
            )

        quiz_text = quiz_text[
            start:end + 1
        ]

        questions = json.loads(
            quiz_text
        )

        if not isinstance(
            questions,
            list
        ):

            raise ValueError(
                "Quiz response is not a list."
            )

        if len(questions) != int(
            num_questions
        ):

            raise ValueError(
                f"Expected {num_questions} "
                f"questions but received "
                f"{len(questions)}."
            )

        for question in questions:

            if not isinstance(
                question,
                dict
            ):

                raise ValueError(
                    "Invalid question object."
                )

            if "question" not in question:

                raise ValueError(
                    "Question text missing."
                )

            if "options" not in question:

                raise ValueError(
                    "Question options missing."
                )

            if not isinstance(
                question["options"],
                list
            ):

                raise ValueError(
                    "Options must be a list."
                )

            if len(
                question["options"]
            ) != 4:

                raise ValueError(
                    "Every question must have "
                    "exactly 4 options."
                )

            if "answer" not in question:

                raise ValueError(
                    "Correct answer missing."
                )

            try:

                question["answer"] = int(
                    question["answer"]
                )

            except (
                TypeError,
                ValueError
            ):

                raise ValueError(
                    "Answer must be 0, 1, 2 or 3."
                )

            if question["answer"] not in {
                0,
                1,
                2,
                3
            }:

                raise ValueError(
                    "Invalid answer index."
                )

            if "explanation" not in question:

                question["explanation"] = ""

        session["quiz"] = questions

        print("\n==============================")
        print("QUIZ GENERATED SUCCESSFULLY")
        print("==============================")
        print(
            f"Questions: {len(questions)}"
        )
        print(
            f"Difficulty: {difficulty}"
        )
        print("==============================\n")

        return render_template(
            "index.html",
            quiz=questions
        )

    except Exception as e:

        print("\n==============================")
        print("QUIZ PARSING ERROR")
        print("==============================")
        print(e)
        print("==============================\n")

        return render_template(
            "index.html",
            error=(
                "StudyMate couldn't generate "
                "a valid quiz this time. "
                "Please try again."
            )
        )


# =========================================================
# SUBMIT QUIZ
# =========================================================

@app.route(
    "/submit_quiz",
    methods=["POST"]
)
def submit_quiz():

    questions = session.get(
        "quiz"
    )

    if not questions:

        return render_template(
            "index.html",
            error=(
                "Please generate a quiz first."
            )
        )

    score = 0

    results = []

    for index, question in enumerate(
        questions
    ):

        selected = request.form.get(
            f"question_{index}"
        )

        try:

            selected_number = int(
                selected
            )

        except (
            TypeError,
            ValueError
        ):

            selected_number = -1

        correct = question["answer"]

        is_correct = (
            selected_number == correct
        )

        if is_correct:

            score += 1

        results.append({

            "question":
                question["question"],

            "options":
                question["options"],

            "selected":
                selected_number,

            "correct":
                correct,

            "is_correct":
                is_correct,

            "explanation":
                question.get(
                    "explanation",
                    ""
                )

        })

    total = len(
        questions
    )

    percentage = int(
        (score / total) * 100
    )

    return render_template(

        "index.html",

        results=results,

        score=score,

        total=total,

        percentage=percentage

    )


# =========================================================
# FILE TOO LARGE
# =========================================================

@app.errorhandler(413)
def file_too_large(error):

    return render_template(

        "index.html",

        error=(
            "That PDF is too large. "
            "Please upload a PDF smaller than 20 MB."
        )

    ), 413


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
