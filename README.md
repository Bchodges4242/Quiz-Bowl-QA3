Requirements

Python 3.6+
Tkinter (included in standard Python installation)
SQLite3 (included in standard Python installation)

Taking a Quiz

Launch the application
Click on "Take a Quiz"
Select a quiz category
Answer the questions presented
View your final score at the end

Admin Functions

Launch the application
Click on "Admin Login"
Enter the admin password (default: "1526")
From the admin panel, you can:

Add new quiz categories
Create new questions
View, edit, or delete existing questions

Customization
Changing the Admin Password
Edit the self.admin_password value in the QuizApp.__init__ method to set a custom password.
Database Location
By default, the database is stored in the same directory as the script with the name "quiz_database.db". You can modify the database path by changing the db_file parameter when initializing QuizDatabase.
