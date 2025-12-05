import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import os
import logging
import datetime

from get_classroom_service import get_classroom_service
from get_all_courses import get_all_courses
from get_all_students import get_all_students
import main

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-5s | %(name)s | %(message)s")
logger = logging.getLogger("gui")


class DateSelector(ttk.Frame):
    """A small date selector widget. Uses tkcalendar.DateEntry when installed, otherwise
    falls back to year/month/day comboboxes."""
    def __init__(self, parent, initial_date: str = None):
        super().__init__(parent)
        try:
            from tkcalendar import DateEntry
        except Exception:
            DateEntry = None
        self._has_dateentry = DateEntry is not None
        if self._has_dateentry:
            # Use DateEntry (provides a calendar popup)
            self._widget = DateEntry(self, date_pattern='yyyy-mm-dd')
            if initial_date:
                try:
                    y, m, d = [int(x) for x in initial_date.split('-')]
                    self._widget.set_date(datetime.date(y, m, d))
                except Exception:
                    pass
            self._widget.pack()
        else:
            # Fallback: comboboxes for year/month/day
            today = datetime.date.today()
            years = [str(y) for y in range(today.year - 5, today.year + 6)]
            months = [f"{m:02d}" for m in range(1, 13)]
            days = [f"{d:02d}" for d in range(1, 32)]

            self.year_var = tk.StringVar(value=str(today.year))
            self.month_var = tk.StringVar(value=f"{today.month:02d}")
            self.day_var = tk.StringVar(value=f"{today.day:02d}")

            self.year_cb = ttk.Combobox(self, values=years, width=6, textvariable=self.year_var, state='readonly')
            self.month_cb = ttk.Combobox(self, values=months, width=4, textvariable=self.month_var, state='readonly')
            self.day_cb = ttk.Combobox(self, values=days, width=4, textvariable=self.day_var, state='readonly')

            if initial_date:
                try:
                    y, m, d = [int(x) for x in initial_date.split('-')]
                    self.year_var.set(str(y))
                    self.month_var.set(f"{m:02d}")
                    self.day_var.set(f"{d:02d}")
                except Exception:
                    pass

            self.year_cb.pack(side=tk.LEFT)
            self.month_cb.pack(side=tk.LEFT, padx=(4, 0))
            self.day_cb.pack(side=tk.LEFT, padx=(4, 0))

    def get(self) -> str:
        """Return date as ISO string YYYY-MM-DD, or empty string if not set."""
        if self._has_dateentry:
            try:
                d = self._widget.get_date()
                return d.isoformat()
            except Exception:
                return ""
        else:
            y = self.year_var.get()
            m = self.month_var.get()
            d = self.day_var.get()
            if not (y and m and d):
                return ""
            return f"{y}-{m}-{d}"


class AnalyzerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Learner Performance Monitor")
        self.geometry("800x600")

        # Credentials / token
        frm = ttk.Frame(self)
        frm.pack(fill=tk.X, padx=8, pady=6)

        ttk.Label(frm, text="Credentials file:").grid(row=0, column=0, sticky=tk.W)
        self.credentials_var = tk.StringVar(value="credentials.json")
        ttk.Entry(frm, textvariable=self.credentials_var, width=40).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(frm, text="Browse", command=self.browse_credentials).grid(row=0, column=2)

        ttk.Label(frm, text="Token file:").grid(row=1, column=0, sticky=tk.W)
        self.token_var = tk.StringVar(value="token.json")
        ttk.Entry(frm, textvariable=self.token_var, width=40).grid(row=1, column=1, sticky=tk.W)
        ttk.Button(frm, text="Browse", command=self.browse_token).grid(row=1, column=2)

        # Model and env
        ttk.Label(frm, text="Ollama model:").grid(row=2, column=0, sticky=tk.W)
        self.model_var = tk.StringVar(value="gpt-oss:20b")
        ttk.Entry(frm, textvariable=self.model_var, width=40).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(frm, text="Reports dir:").grid(row=3, column=0, sticky=tk.W)
        self.reports_dir_var = tk.StringVar(value="reports")
        ttk.Entry(frm, textvariable=self.reports_dir_var, width=40).grid(row=3, column=1, sticky=tk.W)

        ttk.Label(frm, text="AI max retries:").grid(row=4, column=0, sticky=tk.W)
        self.ai_retries_var = tk.StringVar(value="5")
        ttk.Entry(frm, textvariable=self.ai_retries_var, width=10).grid(row=4, column=1, sticky=tk.W)

        # Dates and mode
        # Date selectors: prefer tkcalendar.DateEntry if available, otherwise fallback to combobox selectors
        ttk.Label(frm, text="Start date:").grid(row=5, column=0, sticky=tk.W)
        self.start_selector = DateSelector(frm)
        self.start_selector.grid(row=5, column=1, sticky=tk.W)

        ttk.Label(frm, text="End date:").grid(row=6, column=0, sticky=tk.W)
        self.end_selector = DateSelector(frm)
        self.end_selector.grid(row=6, column=1, sticky=tk.W)

        # Mode radio
        self.mode_var = tk.IntVar(value=1)
        modes = [(1, "Analyze all classes"), (2, "Analyze single class"), (3, "Analyze single student")]
        for idx, (val, txt) in enumerate(modes):
            ttk.Radiobutton(frm, text=txt, variable=self.mode_var, value=val, command=self.on_mode_change).grid(row=7+idx, column=0, columnspan=2, sticky=tk.W)

        # Course selection
        ttk.Label(frm, text="Selected course:").grid(row=10, column=0, sticky=tk.W)
        self.course_cb = ttk.Combobox(frm, state="readonly", width=50)
        self.course_cb.grid(row=10, column=1, sticky=tk.W)
        ttk.Button(frm, text="Load Courses", command=self.load_courses).grid(row=10, column=2)

        ttk.Label(frm, text="Selected student:").grid(row=11, column=0, sticky=tk.W)
        self.student_cb = ttk.Combobox(frm, state="readonly", width=50)
        self.student_cb.grid(row=11, column=1, sticky=tk.W)
        ttk.Button(frm, text="Load Students", command=self.load_students).grid(row=11, column=2)

        # Additional context
        ttk.Label(frm, text="Additional context:").grid(row=12, column=0, sticky=tk.NW)
        self.context_txt = scrolledtext.ScrolledText(frm, width=50, height=4)
        self.context_txt.grid(row=12, column=1, columnspan=2, sticky=tk.W)

        # Controls
        ctrl = ttk.Frame(self)
        ctrl.pack(fill=tk.X, padx=8, pady=6)
        self.run_btn = ttk.Button(ctrl, text="Run Analysis", command=self.on_run)
        self.run_btn.pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Quit", command=self.quit).pack(side=tk.RIGHT)

        # Log output
        self.log_out = scrolledtext.ScrolledText(self, state="disabled")
        self.log_out.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

        self.courses = []
        self.students = []

    def browse_credentials(self):
        p = filedialog.askopenfilename(title="Select credentials.json", filetypes=[("JSON files","*.json"), ("All files","*")])
        if p:
            self.credentials_var.set(p)

    def browse_token(self):
        p = filedialog.askopenfilename(title="Select token.json", filetypes=[("JSON files","*.json"), ("All files","*")])
        if p:
            self.token_var.set(p)

    def log(self, msg):
        self.log_out.configure(state="normal")
        self.log_out.insert(tk.END, msg + "\n")
        self.log_out.see(tk.END)
        self.log_out.configure(state="disabled")

    def on_mode_change(self):
        mode = self.mode_var.get()
        if mode == 1:
            self.course_cb.set("")
            self.student_cb.set("")
        # else user can load selections

    def load_courses(self):
        self.log("Loading courses...")
        try:
            service = get_classroom_service(self.credentials_var.get(), self.token_var.get())
            courses = get_all_courses(service)
            if not courses:
                messagebox.showwarning("No courses", "No courses found with provided credentials/token")
                return
            self.courses = sorted(courses, key=lambda x: x["name"]) if courses else []
            names = [f"{c['name']} ({c['id']})" for c in self.courses]
            self.course_cb['values'] = names
            if names:
                self.course_cb.current(0)
            self.log(f"Loaded {len(self.courses)} courses")
        except Exception as e:
            logger.exception("Error loading courses: %s", e)
            messagebox.showerror("Error", str(e))

    def load_students(self):
        sel = self.course_cb.get()
        if not sel:
            messagebox.showinfo("Select course", "Please select a course first")
            return
        # extract id from selection
        course_id = sel.split('(')[-1].strip(')')
        self.log(f"Loading students for course {course_id}...")
        try:
            service = get_classroom_service(self.credentials_var.get(), self.token_var.get())
            students = get_all_students(service, course_id)
            if not students:
                messagebox.showwarning("No students", "No students found for selected course")
                return
            self.students = students
            names = [f"{s.get('profile', {}).get('name', {}).get('givenName','') } {s.get('profile', {}).get('name', {}).get('familyName','')} ({s['userId']})" for s in students]
            self.student_cb['values'] = names
            if names:
                self.student_cb.current(0)
            self.log(f"Loaded {len(students)} students")
        except Exception as e:
            logger.exception("Error loading students: %s", e)
            messagebox.showerror("Error", str(e))

    def on_run(self):
        # gather params
        creds = self.credentials_var.get()
        token = self.token_var.get()
        model = self.model_var.get()
        reports_dir = self.reports_dir_var.get()
        ai_retries = self.ai_retries_var.get()
        # Use date selectors
        start_date = self.start_selector.get() or None
        end_date = self.end_selector.get() or None
        mode = self.mode_var.get()
        course_sel = self.course_cb.get()
        course_id = None
        if course_sel:
            course_id = course_sel.split('(')[-1].strip(')')
        student_sel = self.student_cb.get()
        student_id = None
        if student_sel:
            student_id = student_sel.split('(')[-1].strip(')')
        additional_context = self.context_txt.get('1.0', tk.END).strip() or None

        # run in background thread
        def target():
            try:
                self.run_btn.configure(state="disabled")
                self.log("Starting analysis...")
                main.run_with_params(credentials=creds,
                                      token=token,
                                      ollama_model=model,
                                      start_date=start_date,
                                      end_date=end_date,
                                      mode_choice=mode,
                                      course_id=course_id,
                                      student_id=student_id,
                                      additional_context=additional_context,
                                      reports_dir=reports_dir,
                                      ai_max_retries=ai_retries)
                self.log("Analysis complete. Check reports directory.")
                messagebox.showinfo("Done", "Analysis complete. Check reports directory.")
            except Exception as e:
                logger.exception("Error during analysis: %s", e)
                messagebox.showerror("Error", str(e))
            finally:
                self.run_btn.configure(state="normal")

        threading.Thread(target=target, daemon=True).start()


if __name__ == '__main__':
    app = AnalyzerGUI()
    app.mainloop()
