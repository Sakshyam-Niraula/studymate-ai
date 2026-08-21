from flask import Flask, render_template, request, session
from google import genai
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import fitz
import os
import json
import uuid


# ==========================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "studymate-development-key"
)


# ==========================================
# CONFIGURATION
# ==========================================

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Maximum upload size: 20 MB
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024

ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


# ==========================================
# GEMINI
# ==========================================

api_key = os.environ.get(
    "GEMINI_API_KEY"
)

if not api_key:

    print(
        "WARNING: GEMINI_API_KEY is not configured."
    )

client = (
    genai.Client(api_key=api_key)
    if api_key
    else None
)

MODEL_NAME = "models/gemini-3.6-flash"


# ==========================================
# USER SESSION
# ==========================================

def get_user_id():

    if "user_id" not in session:

        session["user_id"] = str(
            uuid.uuid4()
        )

    return session["user_id"]


# ==========================================
# USER FOLDER
# ==========================================

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


# ==========================================
# STUDY MATERIAL PATH
# ==========================================

def get_material_path():

    return os.path.join(
        get_user_folder(),
        "study_material.txt"
    )


# ==========================================
# CHECK FILE
# ==========================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower() in ALLOWED_EXTENSIONS
    )


# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==========================================
# UPLOAD PDF
# ==========================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    pdf = request.files.get(
        "pdf"
    )

    if not pdf or pdf.filename == "":

        return render_template(
            "index.html",
            error="Please choose a PDF."
        )


    if not allowed_file(
        pdf.filename
    ):

        return render_template(
            "index.html",
            error="Only PDF files are allowed."
        )


    # Secure the original filename

    safe_filename = secure_filename(
        pdf.filename
    )


    if not safe_filename:

        return render_template(
            "index.html",
            error="Invalid filename."
        )


    # User-specific folder

    user_folder = get_user_folder()


    filepath = os.path.join(
        user_folder,
        safe_filename
    )


    pdf.save(
        filepath
    )


    try:

        document = fitz.open(
            filepath
        )

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


        # Empty/scanned PDF

        if not text.strip():

            os.remove(
                filepath
            )

            return render_template(
                "index.html",
                error=(
                    "This PDF contains no selectable "
                    "text. It may be a scanned or "
                    "image-based PDF."
                )
            )


        # Save material for THIS USER ONLY

        material_path = get_material_path()


        with open(
            material_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(text)


        print(
            "\n=============================="
        )

        print(
            "PDF UPLOAD SUCCESS"
        )

        print(
            "=============================="
        )

        print(
            f"User: {get_user_id()[:8]}"
        )

        print(
            f"File: {safe_filename}"
        )

        print(
            f"Characters: {len(text)}"
        )

        print(
            "==============================\n"
        )


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

            os.remove(
                filepath
            )


        return render_template(
            "index.html",

            error=(
                f"Could not read PDF: {str(e)}"
            )
        )


# ==========================================
# GET STUDY MATERIAL
# ==========================================

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


# ==========================================
# GEMINI FUNCTION
# ==========================================

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

        return response.text


    except Exception as e:

        print(
            "GEMINI ERROR:",
            e
        )

        return (
            f"Gemini error: {str(e)}"
        )


# ==========================================
# ASK STUDYMATE
# ==========================================

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
            answer=(
                "Please upload a PDF first."
            )
        )


    prompt = f"""

You are StudyMate, an AI tutor designed
to help students understand their own
study material.

IMPORTANT RULES:

1. Use ONLY the study material provided below.

2. Do NOT use outside knowledge.

3. Do NOT invent information.

4. If the answer cannot be found in the
study material, say exactly:

"I couldn't find that information in your study material."

5. Keep explanations appropriate for students.

6. Make difficult concepts easier to understand.

7. Be concise but useful.

The student asked:

{question}


When the answer IS found in the material,
structure your response like this when useful:


📚 Explanation

Give a clear explanation based ONLY
on the study material.


💡 In simple words

Explain the concept in simpler language.


🎯 Exam tip

Give one useful exam-focused point
supported by the material.


🧠 Quick check

Ask one short question that tests
whether the student understood the concept.


Do not force every section if it doesn't
make sense for the question.


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


    return render_template(
        "index.html",
        answer=answer
    )


# ==========================================
# GENERATE QUIZ
# ==========================================

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


    # Validate number

    allowed_numbers = {
        "5",
        "10",
        "15",
        "20"
    }


    if num_questions not in allowed_numbers:

        num_questions = "5"


    # Validate difficulty

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
            error=(
                "Please upload a PDF first."
            )
        )


    prompt = f"""

You are StudyMate, an educational
quiz generator.

Create EXACTLY {num_questions}
multiple-choice questions.

Use ONLY the study material provided.

Difficulty level:

{difficulty}


IMPORTANT RULES:

1. Use ONLY the study material.

2. Do not use outside knowledge.

3. Create exactly {num_questions} questions.

4. Every question must have exactly
4 options.

5. There must be exactly ONE correct answer.

6. Questions should test understanding,
not just memorization.

7. Include a short explanation.

8. Return ONLY valid JSON.

9. Do NOT use markdown.

10. Do NOT include ```json.


Return EXACTLY this structure:

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


Answer indexes:

0 = A
1 = B
2 = C
3 = D


STUDY MATERIAL:
==============================

{study_material}

==============================

"""


    quiz_text = ask_gemini(
        prompt
    )


    try:

        quiz_text = quiz_text.strip()


        if quiz_text.startswith(
            "```"
        ):

            quiz_text = (
                quiz_text
                .replace(
                    "```json",
                    ""
                )
                .replace(
                    "```",
                    ""
                )
                .strip()
            )


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
                "AI did not generate the "
                "requested number of questions."
            )


        for question in questions:

            if "question" not in question:

                raise ValueError(
                    "Question text missing."
                )


            if "options" not in question:

                raise ValueError(
                    "Question options missing."
                )


            if len(
                question["options"]
            ) != 4:

                raise ValueError(
                    "Every question must "
                    "have exactly 4 options."
                )


            if "answer" not in question:

                raise ValueError(
                    "Correct answer missing."
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


        # Store quiz for this session

        session["quiz"] = questions


        print(
            "\n=============================="
        )

        print(
            "QUIZ GENERATED"
        )

        print(
            "=============================="
        )

        print(
            f"User: {get_user_id()[:8]}"
        )

        print(
            f"Questions: {len(questions)}"
        )

        print(
            f"Difficulty: {difficulty}"
        )

        print(
            "==============================\n"
        )


        return render_template(
            "index.html",
            quiz=questions
        )


    except Exception as e:

        print(
            "QUIZ PARSING ERROR:",
            e
        )

        print(
            "\nRAW AI RESPONSE:"
        )

        print(
            quiz_text
        )


        return render_template(
            "index.html",
            error=(
                "StudyMate generated an "
                "invalid quiz. Please try again."
            )
        )


# ==========================================
# SUBMIT QUIZ
# ==========================================

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


# ==========================================
# FILE TOO LARGE
# ==========================================

@app.errorhandler(413)
def file_too_large(error):

    return render_template(
        "index.html",
        error=(
            "That PDF is too large. "
            "Please upload a PDF smaller than 20 MB."
        )
    ), 413


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(
        debug=True
    )