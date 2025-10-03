"""
Enhanced Chatbot with PyQt5 GUI (Improved Formatting)
- Adds HTML-rich rendering for Assistant responses.
- Chat bubbles styled differently for User and Assistant.
- Auto-scrolls to latest message.
"""

import sys
import logging
import json
import re
import datetime
from collections import deque, defaultdict

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLineEdit, QStatusBar
)
from PyQt5.QtCore import Qt

try:
    from call_ollama_classify import call_ollama_classify
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False
    def call_ollama_classify(prompt, model="llama3.1:8b-instruct-q4_0"):
        logging.getLogger("enhanced_chatbot").warning("Using fallback LLM stub.")
        return "(Stub) Please install real LLM backend."

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("enhanced_chatbot")

# ---------------- Memory Manager ----------------
class MemoryManager:
    def __init__(self, max_raw_turns=12, model=None):
        self.raw_history = deque(maxlen=max_raw_turns)
        self.model = model

    def add_turn(self, role, text):
        ts = datetime.datetime.now(datetime.UTC).isoformat()
        self.raw_history.append({"role": role, "text": text, "time": ts})

    def get_prompt_history(self):
        recent = "\n".join([f"{h['role'].capitalize()}: {h['text']}" for h in self.raw_history])
        return f"Conversation so far:\n{recent if recent else '(none)'}\n"

# ---------------- Report Index ----------------
class ReportIndex:
    def __init__(self, student_reports_file="student_reports.txt", category_groups_file="category_groups.txt"):
        self.by_student = {}
        self.categories = defaultdict(list)
        self.raw_text = ""
        self._load(student_reports_file, category_groups_file)

    def _load(self, student_reports_file, category_groups_file):
        try:
            with open(student_reports_file, "r", encoding="utf-8") as f:
                self.raw_text = f.read()
        except FileNotFoundError:
            logger.warning("Student reports file not found: %s", student_reports_file)

        blocks = re.split(r"\n\s*\n", self.raw_text.strip()) if self.raw_text.strip() else []
        for b in blocks:
            m = re.search(r"(?:Name|Student)[:\s]+([A-Za-z0-9 \-']{2,40})", b)
            if m:
                self.by_student[m.group(1).strip().lower()] = b.strip()

        try:
            with open(category_groups_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    if ":" in line:
                        cat, members = line.split(":", 1)
                        for n in re.split(r",|;", members):
                            if n.strip():
                                self.categories[cat.strip()].append(n.strip())
        except FileNotFoundError:
            logger.warning("Category groups file not found: %s", category_groups_file)

    def find_student(self, query_name):
        key = query_name.strip().lower()
        if key in self.by_student:
            return self.by_student[key]
        for name, block in self.by_student.items():
            if key in name:
                return block
        return None

# ---------------- Chatbot ----------------
class EnhancedChatbot:
    def __init__(self, student_reports_file='student_reports.txt', category_groups_file='category_groups.txt', ollama_model=None):
        self.report_index = ReportIndex(student_reports_file, category_groups_file)
        self.memory = MemoryManager(model=ollama_model)
        self.ollama_model = ollama_model or 'llama3.1:8b-instruct-q4_0'

    def _compose_prompt(self, user_text, extra_context=""):
        parts = [
            "You are a helpful assistant with access to student performance reports.",
            extra_context,
            self.memory.get_prompt_history(),
            f"User question: {user_text}\nAnswer clearly and professionally."
        ]
        return "\n\n".join([p for p in parts if p.strip()])

    def handle_user_message(self, user_text):
        student_block = self.report_index.find_student(user_text)
        if student_block:
            prompt = self._compose_prompt(user_text, f"Student data for {user_text}:\n{student_block}")
            response = call_ollama_classify(prompt, model=self.ollama_model)
            self.memory.add_turn('user', user_text)
            self.memory.add_turn('assistant', response)
            return response

        if any(k in user_text.lower() for k in ["general performance", "overall", "summary"]):
            cats = "\n".join([f"{c}: {', '.join(s)}" for c, s in self.report_index.categories.items()])
            prompt = self._compose_prompt(user_text, f"Overall categories and students:\n{cats}\n")
            response = call_ollama_classify(prompt, model=self.ollama_model)
            self.memory.add_turn('user', user_text)
            self.memory.add_turn('assistant', response)
            return response

        context = self.report_index.raw_text + "\n\nCategories:\n" + str(dict(self.report_index.categories))
        prompt = self._compose_prompt(user_text, f"Here is the context from the reports:\n{context}")
        response = call_ollama_classify(prompt, model=self.ollama_model)
        self.memory.add_turn('user', user_text)
        self.memory.add_turn('assistant', response)
        return response

# ---------------- GUI ----------------
class ChatbotGUI(QWidget):
    def __init__(self, chatbot):
        super().__init__()
        self.chatbot = chatbot
        self.setWindowTitle("Student Report Chatbot")
        self.setGeometry(200, 200, 800, 600)

        self.layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("font-size:14px;")
        self.layout.addWidget(self.chat_display)

        input_layout = QHBoxLayout()
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type your question...")
        input_layout.addWidget(self.input_box)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        self.layout.addLayout(input_layout)

        self.status = QStatusBar()
        self.layout.addWidget(self.status)

        self.setLayout(self.layout)

    def append_message(self, role, message):
        if role == "user":
            bubble_color = "#e0e0e0"
            align = "right"
            prefix = "<b>You:</b>"
        else:
            bubble_color = "#f5faff"
            align = "left"
            prefix = "<b>Assistant:</b>"

        # Wrap in styled div for bubble effect
        html = f"""
        <div style='background:{bubble_color}; padding:8px; border-radius:8px; margin:6px; text-align:{align};'>
        {prefix}<br>{message.replace('\n','<br>')}
        </div>
        """
        self.chat_display.append(html)
        self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum())

    def send_message(self):
        user_text = self.input_box.text().strip()
        if not user_text:
            return
        self.append_message("user", user_text)
        self.input_box.clear()

        try:
            response = self.chatbot.handle_user_message(user_text)
            # Allow model output to be shown with HTML formatting
            formatted_response = response.replace("**", "<b>").replace("*", "<li>")
            self.append_message("assistant", formatted_response)
            self.status.showMessage("Response received", 2000)
        except Exception as e:
            self.append_message("assistant", "Sorry, there was an error.")
            self.status.showMessage(f"Error: {e}", 5000)

# ---------------- Main ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    chatbot = EnhancedChatbot()
    gui = ChatbotGUI(chatbot)
    gui.show()
    sys.exit(app.exec_())