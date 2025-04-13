import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import random
import json

class QuizDatabase:
    def __init__(self, db_file="quiz_database.db"):
        self.db_file = db_file
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )''')
        
        # Modified questions table to support multiple answers and feedback
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answers TEXT NOT NULL,
            is_multiple_choice BOOLEAN NOT NULL DEFAULT 0,
            feedback TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )''')
        
        # Check if we need to add the feedback column
        cursor.execute("PRAGMA table_info(questions)")
        columns = [info[1] for info in cursor.fetchall()]
        
        # If the feedback column doesn't exist, add it
        if "feedback" not in columns:
            cursor.execute("ALTER TABLE questions ADD COLUMN feedback TEXT")
        
        # Check if we need to migrate old data
        if "correct_answer" in columns and "correct_answers" not in columns:
            self._migrate_database(conn, cursor)
        
        conn.commit()
        conn.close()
    
    def _migrate_database(self, conn, cursor):
        # Add new columns
        cursor.execute("ALTER TABLE questions ADD COLUMN correct_answers TEXT")
        cursor.execute("ALTER TABLE questions ADD COLUMN is_multiple_choice BOOLEAN NOT NULL DEFAULT 0")
        
        # Update existing records to use the new structure
        cursor.execute("UPDATE questions SET correct_answers = correct_answer, is_multiple_choice = 0")
        
        # Remove old column (SQLite doesn't support DROP COLUMN directly)
        cursor.execute("CREATE TABLE questions_new AS SELECT id, category_id, question_text, option_a, option_b, option_c, option_d, correct_answers, is_multiple_choice, feedback FROM questions")
        cursor.execute("DROP TABLE questions")
        cursor.execute("ALTER TABLE questions_new RENAME TO questions")
        
        conn.commit()
    
    def get_categories(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM categories")
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return categories
    
    def add_category(self, category_name):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
            conn.commit()
            success = True
        except sqlite3.IntegrityError:
            success = False
        conn.close()
        return success
    
    def get_category_id(self, category_name):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def add_question(self, category_name, question_text, options, correct_answers, is_multiple_choice, feedback=""):
        category_id = self.get_category_id(category_name)
        if not category_id:
            self.add_category(category_name)
            category_id = self.get_category_id(category_name)
        
        # Convert correct answers list to JSON string
        correct_answers_json = json.dumps(correct_answers)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO questions (category_id, question_text, option_a, option_b, option_c, option_d, correct_answers, is_multiple_choice, feedback)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (category_id, question_text, options[0], options[1], options[2], options[3], correct_answers_json, is_multiple_choice, feedback))
        conn.commit()
        conn.close()
    
    def get_questions_by_category(self, category_name):
        category_id = self.get_category_id(category_name)
        if not category_id:
            return []
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT question_text, option_a, option_b, option_c, option_d, correct_answers, is_multiple_choice, feedback
        FROM questions WHERE category_id = ?
        ''', (category_id,))
        
        questions = []
        for row in cursor.fetchall():
            correct_answers = json.loads(row[5]) if row[5].startswith('[') else [row[5]]
            questions.append({
                "question": row[0],
                "options": [row[1], row[2], row[3], row[4]],
                "answers": correct_answers,
                "is_multiple_choice": bool(row[6]),
                "feedback": row[7] or ""
            })
        
        conn.close()
        return questions
    
    def get_all_questions(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        SELECT c.name, q.id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answers, q.is_multiple_choice, q.feedback
        FROM questions q JOIN categories c ON q.category_id = c.id
        ''')
        
        questions = []
        for row in cursor.fetchall():
            correct_answers = json.loads(row[7]) if row[7].startswith('[') else [row[7]]
            questions.append({
                "category": row[0],
                "id": row[1],
                "question": row[2],
                "options": [row[3], row[4], row[5], row[6]],
                "answers": correct_answers,
                "is_multiple_choice": bool(row[8]),
                "feedback": row[9] or ""
            })
        
        conn.close()
        return questions
    
    def update_question(self, question_id, question_text, options, correct_answers, is_multiple_choice, feedback=""):
        # Convert correct answers list to JSON string
        correct_answers_json = json.dumps(correct_answers)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
        UPDATE questions 
        SET question_text = ?, option_a = ?, option_b = ?, option_c = ?, option_d = ?, correct_answers = ?, is_multiple_choice = ?, feedback = ?
        WHERE id = ?
        ''', (question_text, options[0], options[1], options[2], options[3], correct_answers_json, is_multiple_choice, feedback, question_id))
        conn.commit()
        conn.close()
    
    def delete_question(self, question_id):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        conn.close()

class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Quiz Application")
        self.root.geometry("800x600")
        
        # Initialize database and UI
        self.db = QuizDatabase()
        self.admin_password = "1526"
        self.current_frame = None
        self.show_welcome_screen()
    
    def clear_current_frame(self):
        if self.current_frame:
            self.current_frame.destroy()
        self.current_frame = tk.Frame(self.root, padx=20, pady=20)
        self.current_frame.pack(fill=tk.BOTH, expand=True)
        return self.current_frame
    
    def show_welcome_screen(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Welcome to Quiz App", font=("Arial", 24, "bold")).pack(pady=20)
        
        tk.Button(frame, text="Take a Quiz", font=("Arial", 16), 
                  command=self.show_category_selection, padx=20, pady=10).pack(pady=10)
        
        tk.Button(frame, text="Admin Login", font=("Arial", 16), 
                  command=self.admin_login, padx=20, pady=10).pack(pady=10)
    
    def admin_login(self):
        password = simpledialog.askstring("Admin Login", "Enter admin password:", show='*')
        if password == self.admin_password:
            self.show_admin_panel()
        else:
            messagebox.showerror("Access Denied", "Incorrect password")
    
    def show_category_selection(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Select Quiz Category", font=("Arial", 20, "bold")).pack(pady=20)
        
        categories = self.db.get_categories()
        
        if not categories:
            tk.Label(frame, text="No quiz categories available.", font=("Arial", 14)).pack(pady=20)
        else:
            for category in categories:
                tk.Button(frame, text=category, font=("Arial", 14),
                          command=lambda c=category: self.start_quiz(c),
                          padx=20, pady=10, width=20).pack(pady=5)
        
        tk.Button(frame, text="Back", command=self.show_welcome_screen).pack(pady=20)
    
    def start_quiz(self, category):
        questions = self.db.get_questions_by_category(category)
        
        if not questions:
            messagebox.showinfo("No Questions", f"No questions available for {category}.")
            self.show_category_selection()
            return
        
        random.shuffle(questions)
        
        self.quiz_data = questions
        self.current_question = 0
        self.score = 0
        self.selected_answers = []
        
        self.show_quiz_question()
    
    def show_quiz_question(self):
        frame = self.clear_current_frame()
        
        progress_text = f"Question {self.current_question + 1} of {len(self.quiz_data)} | Score: {self.score}"
        tk.Label(frame, text=progress_text, font=("Arial", 12)).pack(pady=10)
        
        question = self.quiz_data[self.current_question]
        tk.Label(frame, text=question["question"], font=("Arial", 16), wraplength=700).pack(pady=20)
        
        # Show whether single or multiple choice
        choice_type = "Multiple answers allowed" if question["is_multiple_choice"] else "Select one answer"
        tk.Label(frame, text=choice_type, font=("Arial", 12, "italic")).pack(pady=5)
        
        options_frame = tk.Frame(frame)
        options_frame.pack(pady=10, fill=tk.X)
        
        self.selected_answers = []
        self.option_vars = []
        
        # Use checkboxes for multiple choice, radio buttons for single choice
        if question["is_multiple_choice"]:
            for option in question["options"]:
                var = tk.BooleanVar()
                self.option_vars.append((var, option))
                tk.Checkbutton(options_frame, text=option, font=("Arial", 14),
                              variable=var, padx=10, pady=5).pack(anchor=tk.W)
        else:
            answer_var = tk.StringVar()
            self.option_vars = answer_var
            for option in question["options"]:
                tk.Radiobutton(options_frame, text=option, font=("Arial", 14),
                              variable=answer_var, value=option, padx=10, pady=5).pack(anchor=tk.W)
        
        tk.Button(frame, text="Submit Answer", font=("Arial", 14),
                  command=self.check_answer, padx=10, pady=5).pack(pady=20)
    
    def check_answer(self):
        question = self.quiz_data[self.current_question]
        user_answers = []
        
        # Collect the user's answer(s)
        if question["is_multiple_choice"]:
            for var, option in self.option_vars:
                if var.get():
                    user_answers.append(option)
            
            if not user_answers:
                messagebox.showinfo("Selection Required", "Please select at least one answer.")
                return
        else:
            if not self.option_vars.get():
                messagebox.showinfo("Selection Required", "Please select an answer.")
                return
            user_answers = [self.option_vars.get()]
        
        # Check if the answer is correct
        correct_answers = question["answers"]
        
        # For multiple choice, all selections must match exactly
        if question["is_multiple_choice"]:
            is_correct = set(user_answers) == set(correct_answers)
        else:
            is_correct = user_answers[0] in correct_answers
        
        if is_correct:
            self.score += 1
            messagebox.showinfo("Correct!", "Your answer is correct!")
        else:
            formatted_answers = "\n".join(correct_answers)
            feedback_message = f"The correct answer(s):\n{formatted_answers}"
            
            # Add feedback if available
            if question["feedback"]:
                feedback_message += f"\n\nExplanation:\n{question['feedback']}"
                
            messagebox.showinfo("Incorrect", feedback_message)
        
        self.current_question += 1
        if self.current_question < len(self.quiz_data):
            self.show_quiz_question()
        else:
            self.show_quiz_results()
    
    def show_quiz_results(self):
        frame = self.clear_current_frame()
        
        result_text = f"Quiz Completed!\nYour Score: {self.score}/{len(self.quiz_data)}"
        tk.Label(frame, text=result_text, font=("Arial", 20)).pack(pady=30)
        
        percentage = (self.score / len(self.quiz_data)) * 100
        tk.Label(frame, text=f"{percentage:.1f}%", font=("Arial", 24, "bold")).pack(pady=10)
        
        tk.Button(frame, text="Try Another Quiz", font=("Arial", 14),
                  command=self.show_category_selection, padx=10, pady=5).pack(pady=10)
        
        tk.Button(frame, text="Main Menu", font=("Arial", 14),
                  command=self.show_welcome_screen, padx=10, pady=5).pack(pady=10)
    
    def show_admin_panel(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Admin Panel", font=("Arial", 20, "bold")).pack(pady=20)
        
        tk.Button(frame, text="Add New Question", font=("Arial", 14),
                  command=self.show_add_question_form, padx=10, pady=5, width=20).pack(pady=10)
        
        tk.Button(frame, text="View/Edit Questions", font=("Arial", 14),
                  command=self.show_view_questions, padx=10, pady=5, width=20).pack(pady=10)
        
        tk.Button(frame, text="Add Category", font=("Arial", 14),
                  command=self.show_add_category_form, padx=10, pady=5, width=20).pack(pady=10)
        
        tk.Button(frame, text="Logout", font=("Arial", 14),
                  command=self.show_welcome_screen, padx=10, pady=5).pack(pady=20)
    
    def show_add_category_form(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Add New Category", font=("Arial", 18, "bold")).pack(pady=20)
        
        form_frame = tk.Frame(frame)
        form_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(form_frame, text="Category Name:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, pady=10)
        category_entry = tk.Entry(form_frame, font=("Arial", 14), width=30)
        category_entry.grid(row=0, column=1, pady=10, padx=5)
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=20)
        
        def add_category():
            category_name = category_entry.get().strip()
            if not category_name:
                messagebox.showerror("Error", "Category name cannot be empty.")
                return
            
            success = self.db.add_category(category_name)
            if success:
                messagebox.showinfo("Success", f"Category '{category_name}' added successfully.")
                category_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Error", f"Category '{category_name}' already exists.")
        
        tk.Button(button_frame, text="Add Category", font=("Arial", 14),
                  command=add_category, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Back to Admin Panel", font=("Arial", 14),
                  command=self.show_admin_panel, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
    
    def show_add_question_form(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Add New Question", font=("Arial", 18, "bold")).pack(pady=20)
        
        form_frame = tk.Frame(frame)
        form_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(form_frame, text="Category:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, pady=10)
        
        categories = self.db.get_categories()
        category_var = tk.StringVar()
        
        if categories:
            category_var.set(categories[0])
        
        category_combo = ttk.Combobox(form_frame, textvariable=category_var, font=("Arial", 14), state="readonly")
        category_combo['values'] = categories
        category_combo.grid(row=0, column=1, pady=10, padx=5, sticky=tk.W+tk.E)
        
        tk.Label(form_frame, text="Question:", font=("Arial", 14)).grid(row=1, column=0, sticky=tk.W, pady=10)
        question_entry = tk.Entry(form_frame, font=("Arial", 14), width=40)
        question_entry.grid(row=1, column=1, pady=10, padx=5, sticky=tk.W+tk.E)
        
        # Multiple choice checkbox
        multiple_choice_var = tk.BooleanVar()
        tk.Checkbutton(form_frame, text="Multiple Correct Answers", font=("Arial", 14),
                      variable=multiple_choice_var).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        option_entries = []
        option_vars = []
        
        for i in range(4):
            tk.Label(form_frame, text=f"Option {chr(65+i)}:", font=("Arial", 14)).grid(row=3+i, column=0, sticky=tk.W, pady=5)
            option_entry = tk.Entry(form_frame, font=("Arial", 14), width=40)
            option_entry.grid(row=3+i, column=1, pady=5, padx=5, sticky=tk.W+tk.E)
            option_entries.append(option_entry)
            
            # Checkbox for marking correct answers
            var = tk.BooleanVar()
            option_vars.append(var)
            tk.Checkbutton(form_frame, text="Correct", variable=var).grid(row=3+i, column=2, padx=5)
        
        # Add feedback field for incorrect answers
        tk.Label(form_frame, text="Feedback:", font=("Arial", 14)).grid(row=7, column=0, sticky=tk.W, pady=10)
        feedback_text = tk.Text(form_frame, font=("Arial", 12), width=40, height=5)
        feedback_text.grid(row=7, column=1, pady=10, padx=5, sticky=tk.W+tk.E)
        tk.Label(form_frame, text="(Shown when answer is incorrect)", font=("Arial", 10, "italic")).grid(row=8, column=1, sticky=tk.W, pady=0)
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=20)
        
        def add_question():
            category = category_var.get()
            question_text = question_entry.get().strip()
            options = [entry.get().strip() for entry in option_entries]
            is_multiple_choice = multiple_choice_var.get()
            feedback = feedback_text.get("1.0", tk.END).strip()
            
            if not category or not question_text or "" in options:
                messagebox.showerror("Error", "All fields must be filled.")
                return
            
            # Collect correct answers
            correct_answers = []
            for i, var in enumerate(option_vars):
                if var.get():
                    correct_answers.append(options[i])
            
            if not correct_answers:
                messagebox.showerror("Error", "Please select at least one correct answer.")
                return
            
            # For single choice questions, ensure only one answer is selected
            if not is_multiple_choice and len(correct_answers) > 1:
                messagebox.showerror("Error", "Single choice questions can only have one correct answer.")
                return
            
            self.db.add_question(category, question_text, options, correct_answers, is_multiple_choice, feedback)
            messagebox.showinfo("Success", "Question added successfully!")
            
            question_entry.delete(0, tk.END)
            multiple_choice_var.set(False)
            for entry in option_entries:
                entry.delete(0, tk.END)
            for var in option_vars:
                var.set(False)
            feedback_text.delete("1.0", tk.END)
        
        tk.Button(button_frame, text="Add Question", font=("Arial", 14),
                 command=add_question, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Back to Admin Panel", font=("Arial", 14),
                 command=self.show_admin_panel, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
    
    def show_view_questions(self):
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="View/Edit Questions", font=("Arial", 18, "bold")).pack(pady=10)
        
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        columns = ("ID", "Category", "Question", "Type", "Correct Answers", "Has Feedback")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=scrollbar.set)
        
        for col in columns:
            tree.heading(col, text=col)
        
        tree.column("ID", width=50)
        tree.column("Category", width=100)
        tree.column("Question", width=300)
        tree.column("Type", width=100)
        tree.column("Correct Answers", width=150)
        tree.column("Has Feedback", width=100)
        
        tree.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=tree.yview)
        
        questions = self.db.get_all_questions()
        
        for q in questions:
            question_type = "Multiple Choice" if q["is_multiple_choice"] else "Single Choice"
            answers_text = ", ".join(q["answers"])
            has_feedback = "Yes" if q["feedback"] else "No"
            tree.insert("", tk.END, values=(q["id"], q["category"], q["question"], question_type, answers_text, has_feedback))
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=10, fill=tk.X)
        
        def edit_question():
            selected_item = tree.selection()
            if not selected_item:
                messagebox.showinfo("Selection Required", "Please select a question to edit.")
                return
            
            item_id = tree.item(selected_item, "values")[0]
            self.show_edit_question_form(item_id)
        
        tk.Button(button_frame, text="Edit Selected", font=("Arial", 12),
                  command=edit_question, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        def delete_question():
            selected_item = tree.selection()
            if not selected_item:
                messagebox.showinfo("Selection Required", "Please select a question to delete.")
                return
            
            item_id = tree.item(selected_item, "values")[0]
            if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this question?"):
                self.db.delete_question(item_id)
                tree.delete(selected_item)
                messagebox.showinfo("Success", "Question deleted successfully!")
        
        tk.Button(button_frame, text="Delete Selected", font=("Arial", 12),
                  command=delete_question, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Back to Admin Panel", font=("Arial", 12),
                  command=self.show_admin_panel, padx=10, pady=5).pack(side=tk.RIGHT, padx=5)
    
    def show_edit_question_form(self, question_id):
        questions = self.db.get_all_questions()
        question_data = next((q for q in questions if str(q["id"]) == str(question_id)), None)
        
        if not question_data:
            messagebox.showerror("Error", "Question not found.")
            return
        
        frame = self.clear_current_frame()
        
        tk.Label(frame, text="Edit Question", font=("Arial", 18, "bold")).pack(pady=20)
        
        form_frame = tk.Frame(frame)
        form_frame.pack(pady=10, fill=tk.X)
        
        tk.Label(form_frame, text="Category:", font=("Arial", 14)).grid(row=0, column=0, sticky=tk.W, pady=10)
        tk.Label(form_frame, text=question_data["category"], font=("Arial", 14)).grid(row=0, column=1, pady=10, padx=5, sticky=tk.W)
        
        tk.Label(form_frame, text="Question:", font=("Arial", 14)).grid(row=1, column=0, sticky=tk.W, pady=10)
        question_entry = tk.Entry(form_frame, font=("Arial", 14), width=40)
        question_entry.insert(0, question_data["question"])
        question_entry.grid(row=1, column=1, pady=10, padx=5, sticky=tk.W+tk.E)
        
        # Multiple choice checkbox
        multiple_choice_var = tk.BooleanVar(value=question_data["is_multiple_choice"])
        tk.Checkbutton(form_frame, text="Multiple Correct Answers", font=("Arial", 14),
                      variable=multiple_choice_var).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        option_entries = []
        option_vars = []
        
        for i in range(4):
            tk.Label(form_frame, text=f"Option {chr(65+i)}:", font=("Arial", 14)).grid(row=3+i, column=0, sticky=tk.W, pady=5)
            option_entry = tk.Entry(form_frame, font=("Arial", 14), width=40)
            
            if i < len(question_data["options"]):
                option_entry.insert(0, question_data["options"][i])
                
            option_entry.grid(row=3+i, column=1, pady=5, padx=5, sticky=tk.W+tk.E)
            option_entries.append(option_entry)
            
            # Checkbox for marking correct answers
            var = tk.BooleanVar()
            if question_data["options"][i] in question_data["answers"]:
                var.set(True)
            option_vars.append(var)
            tk.Checkbutton(form_frame, text="Correct", variable=var).grid(row=3+i, column=2, padx=5)
        
        # Add feedback field
        tk.Label(form_frame, text="Feedback:", font=("Arial", 14)).grid(row=7, column=0, sticky=tk.W, pady=10)
        feedback_text = tk.Text(form_frame, font=("Arial", 12), width=40, height=5)
        feedback_text.insert("1.0", question_data["feedback"])
        feedback_text.grid(row=7, column=1, pady=10, padx=5, sticky=tk.W+tk.E)
        tk.Label(form_frame, text="(Shown when answer is incorrect)", font=("Arial", 10, "italic")).grid(row=8, column=1, sticky=tk.W, pady=0)
        
        button_frame = tk.Frame(frame)
        button_frame.pack(pady=20)
        
        def save_question():
            question_text = question_entry.get().strip()
            options = [entry.get().strip() for entry in option_entries]
            is_multiple_choice = multiple_choice_var.get()
            feedback = feedback_text.get("1.0", tk.END).strip()
            
            if not question_text or "" in options:
                messagebox.showerror("Error if not question_text or "" in options:")
                messagebox.showerror("Error", "All fields must be filled.")
                return
            
            # Collect correct answers
            correct_answers = []
            for i, var in enumerate(option_vars):
                if var.get():
                    correct_answers.append(options[i])
            
            if not correct_answers:
                messagebox.showerror("Error", "Please select at least one correct answer.")
                return
            
            # For single choice questions, ensure only one answer is selected
            if not is_multiple_choice and len(correct_answers) > 1:
                messagebox.showerror("Error", "Single choice questions can only have one correct answer.")
                return
            
            self.db.update_question(question_id, question_text, options, correct_answers, is_multiple_choice, feedback)
            messagebox.showinfo("Success", "Question updated successfully!")
            self.show_view_questions()
        
        tk.Button(button_frame, text="Save Changes", font=("Arial", 14),
                  command=save_question, padx=10, pady=5).pack(side=tk.LEFT, padx=5)
        
        tk.Button(button_frame, text="Cancel", font=("Arial", 14),
                  command=self.show_view_questions, padx=10, pady=5).pack(side=tk.LEFT, padx=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = QuizApp(root)
    root.mainloop()