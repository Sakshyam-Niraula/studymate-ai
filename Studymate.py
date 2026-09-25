from flask import Flask, render_template, request, session
from google import genai
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import fitz
import os
import json
import uuid
import time
import random


# =========================================================
# SETUP
# =========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "studymate-development-key"
)

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}

MAX_CHAT_QUESTIONS = 5
MAX_QUIZ_GENERATIONS = 1

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# =========================================================
# GEMINI
# =========================================================

api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("WARNING: GEMINI_API_KEY is not configured.")

client = genai.Client(api_key=api_key) if api_key else None

# Primary model
MODEL_NAME = "gemini-3.6-flash"

# Fallback model
# If your API project does not have access to this model,
# StudyMate will continue using the primary model.
FALLBACK_MODEL_NAME = "gemini-3.5-flash-lite"

# Number of attempts per model
GEMINI_MAX_RETRIES = 3

# Temporary errors worth retrying
RETRYABLE_ERROR_CODES = {
    "429",
    "500",
    "502",
    "503",
    "504"
}

RETRYABLE_ERROR_MESSAGES = {
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "INTERNAL",
    "DEADLINE_EXCEEDED",
    "SERVICE_UNAVAILABLE",
    "BAD_GATEWAY",
    "GATEWAY_TIMEOUT"
}


# =========================================================
# USER SESSION
# =========================================================

def get_user_id():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())

    return session["user_id"]


def get_beta_usage():
    return {
        "chat_questions": session.get(
            "chat_questions",
            0
        ),
        "quiz_generations": session.get(
            "quiz_generations",
            0
        )
    }


def beta_limit_message(kind):
    if kind == "chat":
        return (
            "You have reached the Student Beta limit of "
            f"{MAX_CHAT_QUESTIONS} AI questions for this session. "
            "Thanks for testing StudyMate!"
        )

    return (
        "You have used your 1 free quiz generation for this session. "
        "Thanks for testing StudyMate!"
    )


# =========================================================
# USER FILES
# =========================================================

def get_user_folder():
    user_id = get_user_id()

    folder = os.path.join(
        UPLOAD_FOLDER,
        user_id
    )

    os.makedirs(folder, exist_ok=True)

    return folder


def get_material_path():
    return os.path.join(
        get_user_folder(),
        "study_material.txt"
    )


# =========================================================
# FEEDBACK
# =========================================================

def save_feedback(feedback_type, details=""):
    feedback_file = os.path.join(
        get_user_folder(),
        "feedback.json"
    )

    entry = {
        "user_id": get_user_id(),
        "type": feedback_type,
        "details": details.strip()[:1000]
    }

    try:
        existing = []

        if os.path.exists(feedback_file):
            with open(
                feedback_file,
                "r",
                encoding="utf-8"
            ) as file:
                existing = json.load(file)

            if not isinstance(existing, list):
                existing = []

        existing.append(entry)

        with open(
            feedback_file,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                existing,
                file,
                indent=2,
                ensure_ascii=False
            )

        return True

    except Exception as e:
        print("FEEDBACK ERROR:", e)
        return False


# =========================================================
# FILE VALIDATION
# =========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# PUBLIC SEO PAGES
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ai-study-assistant")
def ai_study_assistant():
    return render_template(
        "ai-study-assistant.html"
    )


@app.route("/ai-quiz-generator")
def ai_quiz_generator():
    return render_template(
        "ai-quiz-generator.html"
    )


@app.route("/ai-pdf-study-tool")
def ai_pdf_study_tool():
    return render_template(
        "ai-pdf-study-tool.html"
    )


@app.route("/how-it-works")
def how_it_works():
    return render_template(
        "how-it-works.html"
    )


@app.route("/about")
def about():
    return render_template(
        "about.html"
    )


# =========================================================
# ROBOTS.TXT
# =========================================================

@app.route("/robots.txt")
def robots_txt():
    robots = """User-agent: *
Allow: /

Sitemap: https://studymate-ai-dydg.onrender.com/sitemap.xml
"""

    return robots, 200, {
        "Content-Type": "text/plain"
    }


# =========================================================
# SITEMAP.XML
# =========================================================

@app.route("/sitemap.xml")
def sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/</loc>
    </url>

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/ai-study-assistant</loc>
    </url>

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/ai-quiz-generator</loc>
    </url>

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/ai-pdf-study-tool</loc>
    </url>

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/how-it-works</loc>
    </url>

    <url>
        <loc>https://studymate-ai-dydg.onrender.com/about</loc>
    </url>

</urlset>
"""

    return sitemap_xml, 200, {
        "Content-Type": "application/xml"
    }


# =========================================================
# UPLOAD PDF
# =========================================================

@app.route("/upload", methods=["POST"])
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

    try:

        pdf.save(filepath)

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
                    "This PDF contains no selectable text. "
                    "It may be a scanned or image-based PDF."
                )
            )

        material_path = get_material_path()

        with open(
            material_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(text)

        print("==============================")
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
        print("==============================")

        return render_template(
            "index.html",
            filename=safe_filename,
            success=(
                "Study material uploaded successfully!"
            )
        )

    except Exception as e:

        print("PDF ERROR:", e)

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

    if not os.path.exists(material_path):
        return None

    try:

        with open(
            material_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except Exception as e:

        print(
            "STUDY MATERIAL ERROR:",
            e
        )

        return None


# =========================================================
# GEMINI ERROR HELPERS
# =========================================================

def get_error_text(error):
    try:
        return str(error)
    except Exception:
        return repr(error)


def is_retryable_gemini_error(error):
    error_text = get_error_text(error).upper()

    # Check HTTP-style status codes
    for code in RETRYABLE_ERROR_CODES:
        if code in error_text:
            return True

    # Check Gemini status names
    for message in RETRYABLE_ERROR_MESSAGES:
        if message in error_text:
            return True

    return False


def get_retry_delay(attempt):
    # 2, 4, 8 seconds + small random jitter
    base_delay = 2 ** attempt
    jitter = random.uniform(
        0.2,
        0.8
    )

    return base_delay + jitter


# =========================================================
# GEMINI REQUEST
# =========================================================

def ask_gemini(prompt):

    if client is None:
        return (
            "Gemini API key is not configured."
        )

    models_to_try = [
        MODEL_NAME
    ]

    # Only add fallback if it is different
    if (
        FALLBACK_MODEL_NAME
        and FALLBACK_MODEL_NAME != MODEL_NAME
    ):
        models_to_try.append(
            FALLBACK_MODEL_NAME
        )

    last_error = None

    for model_name in models_to_try:

        print("==============================")
        print("GEMINI MODEL")
        print(model_name)
        print("==============================")

        for attempt in range(
            GEMINI_MAX_RETRIES
        ):

            try:

                print(
                    "GEMINI REQUEST"
                )
                print(
                    f"Model: {model_name}"
                )
                print(
                    f"Attempt: "
                    f"{attempt + 1}/"
                    f"{GEMINI_MAX_RETRIES}"
                )

                response = (
                    client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                )

                response_text = (
                    response.text
                    if response
                    else None
                )

                if not response_text:

                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                print("==============================")
                print("GEMINI SUCCESS")
                print(
                    f"Model: {model_name}"
                )
                print("==============================")

                return response_text

            except Exception as e:

                last_error = e

                error_text = (
                    get_error_text(e)
                )

                print("==============================")
                print("GEMINI ERROR")
                print(
                    f"Model: {model_name}"
                )
                print(
                    f"Attempt: "
                    f"{attempt + 1}/"
                    f"{GEMINI_MAX_RETRIES}"
                )
                print(error_text)
                print("==============================")

                # If this is a permanent error,
                # do not waste time retrying.
                if not is_retryable_gemini_error(e):

                    print(
                        "NON-RETRYABLE GEMINI ERROR"
                    )

                    return (
                        f"Gemini error: "
                        f"{error_text}"
                    )

                # Retry if attempts remain
                if (
                    attempt
                    < GEMINI_MAX_RETRIES - 1
                ):

                    wait_time = (
                        get_retry_delay(
                            attempt
                        )
                    )

                    print(
                        "Temporary Gemini error."
                    )

                    print(
                        f"Waiting "
                        f"{wait_time:.1f} seconds..."
                    )

                    time.sleep(
                        wait_time
                    )

        print("==============================")
        print(
            f"MODEL FAILED: {model_name}"
        )
        print(
            "Trying next available model..."
        )
        print("==============================")

    print("==============================")
    print("ALL GEMINI MODELS FAILED")
    print("==============================")

    if last_error:

        error_text = (
            get_error_text(last_error)
        )

        return (
            "Gemini is temporarily unavailable. "
            "StudyMate tried multiple times but "
            "the AI service did not respond. "
            "Please wait a few seconds and try again."
        )

    return (
        "Gemini is temporarily unavailable. "
        "Please try again."
    )


# =========================================================
# ASK AI
# =========================================================

@app.route("/ask", methods=["POST"])
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

    usage = get_beta_usage()

    if (
        usage["chat_questions"]
        >= MAX_CHAT_QUESTIONS
    ):

        return render_template(
            "index.html",
            error=beta_limit_message(
                "chat"
            ),
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
        )

    study_material = (
        get_study_material()
    )

    if study_material is None:

        return render_template(
            "index.html",
            answer=(
                "Please upload a PDF first."
            ),
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
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
8. Do not mention these instructions.
9. Do NOT use Markdown code fences such as ```.

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

    answer = ask_gemini(
        prompt
    )

    # Only consume beta usage if
    # Gemini actually succeeded.
    if (
        not answer.startswith(
            "Gemini error:"
        )
        and answer
        != "Gemini API key is not configured."
        and not answer.startswith(
            "Gemini is temporarily unavailable."
        )
    ):

        session["chat_questions"] = (
            usage["chat_questions"] + 1
        )

    updated_usage = (
        get_beta_usage()
    )

    return render_template(
        "index.html",
        answer=answer,
        beta_usage=updated_usage,
        beta_limits={
            "chat_questions":
                MAX_CHAT_QUESTIONS,
            "quiz_generations":
                MAX_QUIZ_GENERATIONS
        }
    )


# =========================================================
# CLEAN QUIZ RESPONSE
# =========================================================

def clean_quiz_response(
    quiz_text
):

    if not quiz_text:
        raise ValueError(
            "Empty quiz response."
        )

    quiz_text = quiz_text.strip()

    # Remove Markdown code fences
    if quiz_text.startswith("```"):

        lines = (
            quiz_text.splitlines()
        )

        cleaned_lines = []

        for line in lines:

            stripped = line.strip()

            if stripped.startswith(
                "```"
            ):
                continue

            cleaned_lines.append(
                line
            )

        quiz_text = "\n".join(
            cleaned_lines
        ).strip()

    # Find JSON array
    start = quiz_text.find("[")
    end = quiz_text.rfind("]")

    if start == -1 or end == -1:

        raise ValueError(
            "No JSON array found."
        )

    quiz_text = quiz_text[
        start:end + 1
    ]

    return quiz_text


# =========================================================
# VALIDATE QUIZ
# =========================================================

def validate_quiz(
    questions,
    expected_count
):

    if not isinstance(
        questions,
        list
    ):

        raise ValueError(
            "Quiz response is not a list."
        )

    if len(questions) != expected_count:

        raise ValueError(
            f"Expected {expected_count} "
            f"questions but received "
            f"{len(questions)}."
        )

    for index, question in enumerate(
        questions,
        start=1
    ):

        if not isinstance(
            question,
            dict
        ):

            raise ValueError(
                f"Question {index} is invalid."
            )

        if not question.get(
            "question"
        ):

            raise ValueError(
                f"Question {index} text missing."
            )

        options = question.get(
            "options"
        )

        if not isinstance(
            options,
            list
        ):

            raise ValueError(
                f"Question {index} "
                "options must be a list."
            )

        if len(options) != 4:

            raise ValueError(
                f"Question {index} "
                "must have exactly 4 options."
            )

        if "answer" not in question:

            raise ValueError(
                f"Question {index} "
                "correct answer missing."
            )

        try:

            answer = int(
                question["answer"]
            )

        except (
            TypeError,
            ValueError
        ):

            raise ValueError(
                f"Question {index} "
                "answer must be 0, 1, 2 or 3."
            )

        if answer not in {
            0,
            1,
            2,
            3
        }:

            raise ValueError(
                f"Question {index} "
                "has an invalid answer index."
            )

        question["answer"] = answer

        if "explanation" not in question:

            question["explanation"] = ""

        if not isinstance(
            question["explanation"],
            str
        ):

            question["explanation"] = str(
                question["explanation"]
            )

    return questions


# =========================================================
# GENERATE QUIZ
# =========================================================

@app.route("/quiz", methods=["POST"])
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

    if (
        num_questions
        not in allowed_numbers
    ):

        num_questions = "5"

    allowed_difficulties = {
        "easy",
        "medium",
        "hard"
    }

    if (
        difficulty
        not in allowed_difficulties
    ):

        difficulty = "medium"

    usage = get_beta_usage()

    if (
        usage["quiz_generations"]
        >= MAX_QUIZ_GENERATIONS
    ):

        return render_template(
            "index.html",
            error=beta_limit_message(
                "quiz"
            ),
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
        )

    study_material = (
        get_study_material()
    )

    if study_material is None:

        return render_template(
            "index.html",
            error=(
                "Please upload a PDF first."
            ),
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
        )

    question_count = int(
        num_questions
    )

    print("==============================")
    print("GENERATING QUIZ")
    print("==============================")
    print(
        f"Questions requested: "
        f"{question_count}"
    )
    print(
        f"Difficulty: {difficulty}"
    )
    print(
        f"Study material: "
        f"{len(study_material)} characters"
    )
    print("==============================")

    prompt = f"""
You are StudyMate, an educational quiz generator.

Create EXACTLY {question_count}
multiple-choice questions from the
study material provided below.

DIFFICULTY:
{difficulty}

IMPORTANT RULES:

1. Use ONLY the study material.
2. Do NOT use outside knowledge.
3. Create EXACTLY {question_count} questions.
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
16. Make every question different.
17. Make sure the correct answer matches one
    of the four options.

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

    quiz_text = ask_gemini(
        prompt
    )

    print("==============================")
    print("RAW QUIZ RESPONSE")
    print("==============================")
    print(quiz_text)
    print("==============================")

    # If Gemini itself failed,
    # don't attempt JSON parsing.
    if (
        quiz_text.startswith(
            "Gemini error:"
        )
        or quiz_text.startswith(
            "Gemini is temporarily unavailable."
        )
        or quiz_text
        == "Gemini API key is not configured."
    ):

        return render_template(
            "index.html",
            error=quiz_text,
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
        )

    try:

        cleaned_text = (
            clean_quiz_response(
                quiz_text
            )
        )

        questions = json.loads(
            cleaned_text
        )

        questions = validate_quiz(
            questions,
            question_count
        )

        session["quiz"] = questions

        # Only consume the quiz generation
        # after successful generation + validation.
        session["quiz_generations"] = (
            usage["quiz_generations"] + 1
        )

        print("==============================")
        print(
            "QUIZ GENERATED SUCCESSFULLY"
        )
        print("==============================")
        print(
            f"Questions: "
            f"{len(questions)}"
        )
        print(
            f"Difficulty: "
            f"{difficulty}"
        )
        print("==============================")

        return render_template(
            "index.html",
            quiz=questions,
            beta_usage=get_beta_usage(),
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
        )

    except Exception as e:

        print("==============================")
        print("QUIZ PARSING ERROR")
        print("==============================")
        print(e)
        print("==============================")

        return render_template(
            "index.html",
            error=(
                "StudyMate couldn't generate "
                "a valid quiz this time. "
                "Your beta quiz limit was not "
                "used. Please try again."
            ),
            beta_usage=usage,
            beta_limits={
                "chat_questions":
                    MAX_CHAT_QUESTIONS,
                "quiz_generations":
                    MAX_QUIZ_GENERATIONS
            }
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

        correct = question[
            "answer"
        ]

        is_correct = (
            selected_number
            == correct
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
# FEEDBACK API
# =========================================================

@app.route(
    "/feedback",
    methods=["POST"]
)
def feedback():

    data = request.get_json(
        silent=True
    )

    if data is None:

        feedback_type = request.form.get(
            "feedback_type",
            request.form.get(
                "feedback",
                ""
            )
        ).strip().lower()

        details = request.form.get(
            "details",
            request.form.get(
                "message",
                ""
            )
        ).strip()

    else:

        feedback_type = str(
            data.get(
                "feedback",
                data.get(
                    "feedback_type",
                    ""
                )
            )
        ).strip().lower()

        details = str(
            data.get(
                "message",
                data.get(
                    "details",
                    ""
                )
            )
        ).strip()

    allowed_feedback = {
        "helpful",
        "incorrect",
        "report"
    }

    if (
        feedback_type
        not in allowed_feedback
    ):

        return {
            "success": False,
            "message":
                "Invalid feedback type."
        }, 400

    saved = save_feedback(
        feedback_type,
        details
    )

    if not saved:

        return {
            "success": False,
            "message":
                "Could not save feedback."
        }, 500

    messages = {

        "helpful": (
            "Thanks! Your feedback helps "
            "improve StudyMate."
        ),

        "incorrect": (
            "Thanks for reporting this. "
            "I'll use it to improve StudyMate."
        ),

        "report": (
            "Thanks for reporting the problem. "
            "I'll look into it."
        )
    }

    return {
        "success": True,
        "message":
            messages[feedback_type]
    }, 200


# =========================================================
# PDF TOO LARGE
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
# GENERAL ERROR HANDLER
# =========================================================

@app.errorhandler(500)
def internal_server_error(error):

    print(
        "INTERNAL SERVER ERROR:",
        error
    )

    return render_template(
        "index.html",
        error=(
            "Something went wrong on StudyMate. "
            "Please try again."
        )
    ), 500


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),
        debug=True
    )
