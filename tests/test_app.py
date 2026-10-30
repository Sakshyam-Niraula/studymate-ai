import io
import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

import fitz

import Studymate as study_app


class StudyMateAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_upload_folder = study_app.UPLOAD_FOLDER
        study_app.UPLOAD_FOLDER = self.temp_dir.name
        study_app.app.config.update(TESTING=True)
        self.client = study_app.app.test_client()

        with self.client.session_transaction() as session:
            session["user_id"] = str(uuid.uuid4())

    def tearDown(self):
        study_app.UPLOAD_FOLDER = self.original_upload_folder
        self.temp_dir.cleanup()

    @staticmethod
    def make_pdf():
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Photosynthesis converts light energy into chemical energy.")
        content = document.tobytes()
        document.close()
        return content

    def test_dashboard_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"StudyMate", response.data)
        self.assertIn(b"Session limits", response.data)

    def test_pdf_upload_and_tutor_question(self):
        response = self.client.post(
            "/upload",
            data={"pdf": (io.BytesIO(self.make_pdf()), "biology.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Study material uploaded successfully", response.data)

        with patch.object(study_app, "ask_gemini", return_value="Photosynthesis stores energy in chemical bonds."):
            response = self.client.post("/ask", data={"question": "What is photosynthesis?"})

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Photosynthesis stores energy", response.data)

        with self.client.session_transaction() as session:
            self.assertEqual(session.get("chat_questions"), 1)

    def test_chat_beta_limit_is_preserved(self):
        with self.client.session_transaction() as session:
            session["chat_questions"] = study_app.MAX_CHAT_QUESTIONS

        response = self.client.post("/ask", data={"question": "Explain this"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Beta limit", response.data)

    def test_quiz_generation_and_submission(self):
        questions = [
            {
                "question": f"Photosynthesis practice question {index + 1}: what does it convert?",
                "options": [
                    "Light energy into chemical energy",
                    "Chemical energy into sound",
                    "Water into oxygen only",
                    "Heat into matter",
                ],
                "answer": 0,
                "explanation": "The material states that photosynthesis converts light energy into chemical energy.",
            }
            for index in range(5)
        ]

        with patch.object(study_app, "get_study_material", return_value="Photosynthesis converts light energy into chemical energy."), patch.object(
            study_app, "ask_gemini", return_value=json.dumps(questions)
        ):
            response = self.client.post(
                "/quiz",
                data={"num_questions": "5", "difficulty": "medium"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your generated quiz", response.data)

        with self.client.session_transaction() as session:
            self.assertEqual(session.get("quiz_generations"), 1)

        response = self.client.post("/submit_quiz", data={"question_0": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your quiz result", response.data)
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir.name, user_id, "quiz.json")))

    def test_feedback_endpoint(self):
        response = self.client.post(
            "/feedback",
            json={"feedback_type": "helpful", "details": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_rejects_non_pdf_upload(self):
        response = self.client.post(
            "/upload",
            data={"pdf": (io.BytesIO(b"not a PDF"), "notes.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Only PDF files are allowed", response.data)


if __name__ == "__main__":
    unittest.main()
