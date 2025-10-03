"""
Enhanced Chatbot with PyQt5 GUI (Modernized like Grok)
- Modern dark theme inspired by Grok/xAI.
- Chat bubbles with sleek styling.
- Removed send button; use Enter to send messages.
- Auto-scrolls to latest message.
- Minimalistic and responsive design.
- Positions: User bubbles on right, Assistant on left.
- Added timestamps, shadows, and modern bubble styles.
- Added clear labels ("You:" and "Assistant:") to distinguish messages.
- Enhanced color contrast for better readability and distinction.
"""

import sys
import logging
import json
import re
import datetime
from collections import deque, defaultdict

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QLineEdit, QStatusBar, QLabel
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

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
        self.setWindowTitle("Student Report Chatbot - Powered by Grok")
        self.setGeometry(200, 200, 800, 600)

        # Modern dark theme like Grok
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(18, 18, 18))  # Dark background
        palette.setColor(QPalette.WindowText, QColor(240, 240, 240))  # Light text
        palette.setColor(QPalette.Base, QColor(30, 30, 30))
        palette.setColor(QPalette.AlternateBase, QColor(40, 40, 40))
        palette.setColor(QPalette.Text, QColor(240, 240, 240))
        palette.setColor(QPalette.Button, QColor(50, 50, 50))
        palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
        palette.setColor(QPalette.Highlight, QColor(0, 122, 255))  # Blue accent
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        self.setPalette(palette)

        self.setFont(QFont("Arial", 11))  # Modern sans-serif font

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Header label for modern look
        header = QLabel("Chat with Student Report Assistant")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #f0f0f0; padding: 10px;")
        header.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(header)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                border: none;
                color: #f0f0f0;
                font-size: 14px;
                padding: 15px;
                border-radius: 10px;
            }
        """)
        self.layout.addWidget(self.chat_display, stretch=1)

        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Ask about a student or report...")
        self.input_box.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 25px;
                color: #f0f0f0;
                padding: 12px 25px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #007aff;
                box-shadow: 0 0 5px rgba(0, 122, 255, 0.5);
            }
        """)
        self.input_box.returnPressed.connect(self.send_message)  # Send on Enter
        self.layout.addWidget(self.input_box)

        self.status = QStatusBar()
        self.status.setStyleSheet("color: #a0a0a0; background: transparent; font-size: 12px;")
        self.layout.addWidget(self.status)

        self.setLayout(self.layout)

        # Set window icon for modern touch (assuming you have an icon file, otherwise comment out)
        # self.setWindowIcon(QIcon("path_to_grok_icon.png"))

    def append_message(self, role, message):
        current_time = datetime.datetime.now().strftime("%H:%M")
        if role == "user":
            bubble_color = "#333333"  # Slightly lighter dark gray for user to increase contrast
            text_color = "#e0e0e0"  # Softer light text for user
            align_style = "margin-left: auto;"  # Right align
            prefix = '<span style="font-weight: bold; color: #ffffff;">You:</span><br>'
        else:
            bubble_color = "#005fd7"  # Darker blue for assistant for better distinction
            text_color = "#ffffff"
            align_style = "margin-right: auto;"  # Left align
            prefix = '<span style="font-weight: bold; color: #ffffff;">Assistant:</span><br>'

        # Modern bubble styling with shadow and timestamp
        html = f"""
        <div style='background: {bubble_color}; color: {text_color}; padding: 15px; border-radius: 20px; margin: 10px 0; max-width: 70%; {align_style} box-shadow: 0 2px 5px rgba(0,0,0,0.3); width: fit-content;'>
        {prefix}{message.replace('\n', '<br>')}
        <div style='font-size: 10px; color: #b0b0b0; margin-top: 5px; text-align: right;'>{current_time}</div>
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
            # Support basic markdown in responses
            formatted_response = response.replace("**", "<b>").replace("*", "<i>").replace("\n", "<br>")
            self.append_message("assistant", formatted_response)
            self.status.showMessage("Response received", 2000)
        except Exception as e:
            self.append_message("assistant", "Sorry, there was an error.")
            self.status.showMessage(f"Error: {str(e)}", 5000)

# ---------------- Main ----------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    chatbot = EnhancedChatbot()
    gui = ChatbotGUI(chatbot)
    gui.show()
    sys.exit(app.exec_())