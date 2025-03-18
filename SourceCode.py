import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
import json
from datetime import datetime
import re
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

class DatabaseManager:
    def __init__(self, is_local=True, email=None):
        self.is_local = is_local
        self.email = email
        self.local_db_file = "expenses.db"
        self.email_db_file = f"expenses_{self.sanitize_email(email)}.db" if email else None
        self.current_db_file = self.local_db_file if is_local else self.email_db_file
        self.create_table()
    
    def sanitize_email(self, email):
        if not email:
            return ""
        return re.sub(r'[^a-zA-Z0-9]', '_', email)
    
    def create_table(self):
        """Create the expenses table if it doesn't exist."""
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    description TEXT,
                    amount REAL,
                    category TEXT,
                    date TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                )
            ''')
            conn.commit()
    
    def add_expense(self, description, amount, category, date):
        """Add a new expense to the database."""
        try:
            with sqlite3.connect(self.current_db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (category,))
                cursor.execute('''
                    INSERT INTO expenses (description, amount, category, date)
                    VALUES (?, ?, ?, ?)
                ''', (description, amount, category, date))
                conn.commit()
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def load_expenses(self):
        """Load expenses from the database."""
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM expenses ORDER BY date DESC')
            return cursor.fetchall()
    
    def get_categories(self):
        """Get all categories from the database."""
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT name FROM categories ORDER BY name')
            return [category[0] for category in cursor.fetchall()]

    def delete_expense(self, expense_id):
        """Delete an expense from the database."""
        try:
            with sqlite3.connect(self.current_db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
                conn.commit()
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def update_expense(self, expense_id, description, amount, category, date):
        """Update an existing expense."""
        try:
            with sqlite3.connect(self.current_db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO categories (name) VALUES (?)', (category,))
                cursor.execute('''
                    UPDATE expenses 
                    SET description = ?, amount = ?, category = ?, date = ?
                    WHERE id = ?
                ''', (description, amount, category, date, expense_id))
                conn.commit()
            return True
        except Exception as e:
            print(f"An error occurred: {e}")
            return False

    def total_expenses(self):
        """Calculate total expenses from the database."""
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT SUM(amount) FROM expenses')
            total = cursor.fetchone()[0]
            return total if total is not None else 0
    
    def expenses_by_category(self):
        """Get expenses grouped by category."""
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT category, SUM(amount) as total
                FROM expenses
                GROUP BY category
                ORDER BY total DESC
            ''')
            return cursor.fetchall()
    
    def expenses_by_month(self, year=None):
        """Get expenses grouped by month for the specified year."""
        current_year = datetime.now().year
        year = year or current_year
        
        with sqlite3.connect(self.current_db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT strftime('%m', date) as month, SUM(amount) as total
                FROM expenses
                WHERE strftime('%Y', date) = ?
                GROUP BY month
                ORDER BY month
            ''', (str(year),))
            return cursor.fetchall()
    
    def export_to_json(self, filename):
        """Export expenses to JSON file."""
        try:
            expenses = self.load_expenses()
            expense_list = []
            for expense in expenses:
                expense_list.append({
                    "id": expense[0],
                    "description": expense[1],
                    "amount": expense[2],
                    "category": expense[3],
                    "date": expense[4]
                })
            
            with open(filename, 'w') as f:
                json.dump(expense_list, f, indent=4)
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False
    
    def email_backup(self, user_email, password, recipient_email=None):
        """Email database backup file."""
        try:
            if not recipient_email:
                recipient_email = user_email
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"expense_backup_{timestamp}.json"
            self.export_to_json(backup_file)
            
            msg = MIMEMultipart()
            msg['From'] = user_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Expense Tracker Backup - {timestamp}"
            
            body = "Attached is your expense tracker database backup."
            msg.attach(MIMEText(body, 'plain'))
            
            with open(backup_file, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="json")
                attachment.add_header('Content-Disposition', 'attachment', filename=backup_file)
                msg.attach(attachment)
            
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(user_email, password)
                server.sendmail(user_email, recipient_email, msg.as_string())
            
            os.remove(backup_file)
            return True
        except Exception as e:
            print(f"Email error: {e}")
            return False

    def switch_database(self, is_local, email=None):
        """Switch between local and email-linked database."""
        self.is_local = is_local
        self.email = email
        if is_local:
            self.current_db_file = self.local_db_file
        else:
            self.email_db_file = f"expenses_{self.sanitize_email(email)}.db"
            self.current_db_file = self.email_db_file
        
        self.create_table()
        return True

class EmailBackupDialog:
    """Dialog for getting email backup credentials."""
    def __init__(self, parent):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Backup")
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + parent.winfo_width() // 2 - 200,
            parent.winfo_rooty() + parent.winfo_height() // 2 - 100
        ))
        
        frame = ttk.Frame(self.dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Your Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_email = ttk.Entry(frame, width=30)
        self.user_email.grid(row=0, column=1, pady=5, padx=5)
        
        ttk.Label(frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.password = ttk.Entry(frame, width=30, show="*")
        self.password.grid(row=1, column=1, pady=5, padx=5)
        
        ttk.Label(frame, text="Recipient Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.recipient_email = ttk.Entry(frame, width=30)
        self.recipient_email.grid(row=2, column=1, pady=5, padx=5)
        ttk.Label(frame, text="(Leave blank to send to yourself)").grid(row=3, column=1, sticky=tk.W)
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="Send", command=self.on_send).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)
        
        parent.wait_window(self.dialog)
    
    def on_send(self):
        user_email = self.user_email.get().strip()
        password = self.password.get()
        recipient_email = self.recipient_email.get().strip()
        
        if not user_email or not re.match(r"[^@]+@[^@]+\.[^@]+", user_email):
            messagebox.showerror("Invalid Email", "Please enter a valid email address")
            return
            
        if not password:
            messagebox.showerror("Invalid Password", "Please enter your password")
            return
            
        if recipient_email and not re.match(r"[^@]+@[^@]+\.[^@]+", recipient_email):
            messagebox.showerror("Invalid Recipient", "Please enter a valid recipient email address")
            return
            
        self.result = (user_email, password, recipient_email)
        self.dialog.destroy()
    
    def on_cancel(self):
        self.dialog.destroy()

class ExpenseTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Expense Tracker")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        self.root.configure(bg="#f0f0f0")
        
        try:
            self.root.iconbitmap("expense_icon.ico")
        except:
            pass
        
        self.db_manager = DatabaseManager(is_local=True)
        self.selected_expense = None
        
        self.create_widgets()
        self.load_expenses()
        self.update_stats()
    
    def create_widgets(self):
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TButton", padding=6, relief="flat", background="#4CAF50")
        style.configure("TLabel", background="#f0f0f0", font=('Segoe UI', 10))
        style.configure("Header.TLabel", font=('Segoe UI', 12, 'bold'))
        style.configure("Stats.TLabel", font=('Segoe UI', 11))
        
        menu_bar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Export to JSON", command=self.export_data)
        file_menu.add_command(label="Email Backup", command=self.email_backup)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        
        db_menu = tk.Menu(menu_bar, tearoff=0)
        db_menu.add_command(label="Use Local Database", command=lambda: self.switch_database(True))
        db_menu.add_command(label="Use Email-linked Database", command=lambda: self.switch_database(False))
        menu_bar.add_cascade(label="Database", menu=db_menu)
        
        self.root.config(menu=menu_bar)
        
        main_container = ttk.Frame(self.root, padding="10")
        main_container.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_container)
        top_frame.pack(fill=tk.X, pady=10)
        
        form_frame = ttk.Frame(top_frame)
        form_frame.pack(fill=tk.X)
        
        row1 = ttk.Frame(form_frame)
        row1.pack(fill=tk.X, pady=5)
        ttk.Label(row1, text="Description:").pack(side=tk.LEFT, padx=5)
        self.description_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.description_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(row1, text="Amount:").pack(side=tk.LEFT, padx=5)
        self.amount_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.amount_var, width=10).pack(side=tk.LEFT, padx=5)
        
        row2 = ttk.Frame(form_frame)
        row2.pack(fill=tk.X, pady=5)
        ttk.Label(row2, text="Category:").pack(side=tk.LEFT, padx=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(row2, textvariable=self.category_var, width=15)
        self.category_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(row2, text="Date:").pack(side=tk.LEFT, padx=5)
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(row2, textvariable=self.date_var, width=10).pack(side=tk.LEFT, padx=5)
        
        buttons_frame = ttk.Frame(form_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        self.add_button = ttk.Button(buttons_frame, text="Add Expense", command=self.add_expense)
        self.add_button.pack(side=tk.LEFT, padx=5)
        self.update_button = ttk.Button(buttons_frame, text="Update", command=self.update_expense, state=tk.DISABLED)
        self.update_button.pack(side=tk.LEFT, padx=5)
        self.cancel_button = ttk.Button(buttons_frame, text="Cancel", command=self.cancel_selection, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        middle_frame = ttk.Frame(main_container)
        middle_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        notebook = ttk.Notebook(middle_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        expenses_frame = ttk.Frame(notebook)
        notebook.add(expenses_frame, text="Expenses")
        tree_frame = ttk.Frame(expenses_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll = ttk.Scrollbar(tree_frame)
        self.tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        columns = ("id", "date", "description", "amount", "category")
        self.expense_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", 
                                       yscrollcommand=self.tree_scroll.set)

        self.expense_tree.column("id", width=50, anchor="center")
        self.expense_tree.heading("id", text="ID")

        self.expense_tree.column("date", width=100, anchor="center")
        self.expense_tree.heading("date", text="Date ")

        self.expense_tree.column("description", width=200, anchor="center")
        self.expense_tree.heading("description", text="Description")

        self.expense_tree.column("amount", width=100, anchor="center")
        self.expense_tree.heading("amount", text="Amount")
        
        self.expense_tree.column("category", width=150, anchor="center")
        self.expense_tree.heading("category", text="Category")

        self.expense_tree.pack(fill=tk.BOTH, expand=True)
        self.tree_scroll.config(command=self.expense_tree.yview)
        self.expense_tree.bind("<<TreeviewSelect>>", self.item_selected)
        
        delete_frame = ttk.Frame(expenses_frame)
        delete_frame.pack(fill=tk.X, pady=5)
        self.delete_button = ttk.Button(delete_frame, text="Delete Selected", command=self.delete_expense, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)
        
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        stats_container = ttk.Frame(stats_frame)
        stats_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        summary_frame = ttk.LabelFrame(stats_container, text="Summary")
        summary_frame.pack(fill=tk.X, padx=10, pady=5)
        self.summary_label = ttk.Label(summary_frame, text="", style="Stats.TLabel")
        self.summary_label.pack(padx=10, pady=10)
        
        category_frame = ttk.LabelFrame(stats_container, text="Expenses by Category")
        category_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        cat_tree_frame = ttk.Frame(category_frame)
        cat_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        cat_scroll = ttk.Scrollbar(cat_tree_frame)
        cat_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        cat_columns = ("Category", "Amount", "Percentage")
        self.category_tree = ttk.Treeview(cat_tree_frame, columns=cat_columns, show="headings", 
                                        yscrollcommand=cat_scroll.set)
        self.category_tree.column("Category", width=150)
        self.category_tree.column("Amount", width=100)
        self.category_tree.column("Percentage", width=100)
        for col in cat_columns:
            self.category_tree.heading(col, text=col)
        self.category_tree.pack(fill=tk.BOTH, expand=True)
        cat_scroll.config(command=self.category_tree.yview)
        
        monthly_frame = ttk.LabelFrame(stats_container, text="Monthly Expenses")
        monthly_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        month_tree_frame = ttk.Frame(monthly_frame)
        month_tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        month_scroll = ttk.Scrollbar(month_tree_frame)
        month_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        month_columns = ("Month", "Amount")
        self.monthly_tree = ttk.Treeview(month_tree_frame, columns=month_columns, show="headings", 
                                       yscrollcommand=month_scroll.set)
        self.monthly_tree.column("Month", width=150)
        self.monthly_tree.column("Amount", width=100)
        for col in month_columns:
            self.monthly_tree.heading(col, text=col)
        self.monthly_tree.pack(fill=tk.BOTH, expand=True)
        month_scroll.config(command=self.monthly_tree.yview)
        
        year_frame = ttk.Frame(monthly_frame)
        year_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(year_frame, text="Year:").pack(side=tk.LEFT, padx=5)
        current_year = datetime.now().year
        years = [str(year) for year in range(current_year-5, current_year+1)]
        self.year_var = tk.StringVar(value=str(current_year))
        year_combo = ttk.Combobox(year_frame, textvariable=self.year_var, values=years, width=6)
        year_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(year_frame, text="Update", command=self.update_monthly_stats).pack(side=tk.LEFT, padx=5)
        
        status_frame = ttk.Frame(main_container)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_var = tk.StringVar()
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(side=tk.LEFT, fill=tk.X)
        self.update_status("Ready")
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()
    
    def update_category_combo(self):
        categories = self.db_manager.get_categories()
        self.category_combo['values'] = categories
    
    def add_expense(self):
        try:
            description = self.description_var.get().strip()
            amount_str = self.amount_var.get().strip()
            category = self.category_var.get().strip()
            date = self.date_var.get().strip()
            
            if not description:
                messagebox.showerror("Error", "Please enter a description")
                return
            
            if not amount_str:
                messagebox.showerror("Error", "Please enter an amount")
                return
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be positive")
                    return
            except ValueError:
                messagebox.showerror("Error", "Amount must be a number")
                return
            
            if not category:
                messagebox.showerror("Error", "Please enter a category")
                return
            
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Date must be in YYYY-MM-DD format")
                return
            
            if self.db_manager.add_expense(description, amount, category, date):
                self.update_status(f"Added expense: {description}, ₹{amount:.2f}")
                self.description_var.set("")
                self.amount_var.set("")
                self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
                self.load_expenses()
                self.update_stats()
                self.update_category_combo()
            else:
                messagebox.showerror("Error", "Failed to add expense")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
    
    def update_expense(self):
        if not self.selected_expense:
            return
        
        try:
            expense_id = self.selected_expense[0]
            description = self.description_var.get().strip()
            amount_str = self.amount_var.get().strip()
            category = self.category_var.get().strip()
            date = self.date_var.get().strip()
            
            if not description:
                messagebox.showerror("Error", "Please enter a description")
                return
            
            if not amount_str:
                messagebox.showerror("Error", "Please enter an amount")
                return
            
            try:
                amount = float(amount_str)
                if amount <= 0:
                    messagebox.showerror("Error", "Amount must be positive")
                    return
            except ValueError:
                messagebox.showerror("Error", "Amount must be a number")
                return
            
            if not category:
                messagebox.showerror("Error", "Please enter a category")
                return
            
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Date must be in YYYY-MM-DD format")
                return
            
            if self.db_manager.update_expense(expense_id, description, amount, category, date):
                self.update_status(f"Updated expense: {description}, ₹{amount:.2f}")
                self.description_var.set("")
                self.amount_var.set("")
                self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
                self.update_button.config(state=tk.DISABLED)
                self.cancel_button.config(state=tk.DISABLED)
                self.add_button.config(state=tk.NORMAL)
                self.load_expenses()
                self.update_stats()
                self.update_category_combo()
                self.selected_expense = None
            else:
                messagebox.showerror("Error", "Failed to update expense")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
    
    def delete_expense(self):
        if not self.selected_expense:
            return
        
        expense_id = self.selected_expense[0]
        description = self.selected_expense[1]
        
        confirm = messagebox.askyesno("Confirm Delete", f"Delete expense: {description}?")
        if not confirm:
            return
        
        if self.db_manager.delete_expense(expense_id):
            self.update_status(f"Deleted expense: {description}")
            self.description_var.set("")
            self.amount_var.set("")
            self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
            self.update_button.config(state=tk.DISABLED)
            self.cancel_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
            self.add_button.config(state=tk.NORMAL)
            self.load_expenses()
            self.update_stats()
            self.selected_expense = None
        else:
            messagebox.showerror("Error", "Failed to delete expense")
    
    def item_selected(self, event):
        selected_items = self.expense_tree.selection()
        if not selected_items:
            return
        
        item = selected_items[0]
        values = self.expense_tree.item(item, "values")
        self.selected_expense = values
        self.description_var.set(values[2])
        self.amount_var.set(values[3])
        self.category_var.set(values[4])
        self.date_var.set(values[1])
        self.update_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.NORMAL)
        self.delete_button.config(state=tk.NORMAL)
    
    def cancel_selection(self):
        self.description_var.set("")
        self.amount_var.set("")
        self.date_var.set(datetime.now().strftime("%Y-%m-%d"))
        self.update_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.add_button.config(state=tk.NORMAL)
        self.selected_expense = None
        self.expense_tree.selection_remove(self.expense_tree.selection())
    
    def load_expenses(self):
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)
        expenses = self.db_manager.load_expenses()
        for expense in expenses:
            expense_id, description, amount, category, date = expense
            self.expense_tree.insert("", "end", values=(expense_id, date, description, f"₹{amount:.2f}", category))
    
    def update_stats(self):
        total = self.db_manager.total_expenses()
        expenses = self.db_manager.load_expenses()
        summary_text = f"Total Expenses: ₹{total:.2f}\n"
        summary_text += f"Number of Expenses: {len(expenses)}\n"
        if expenses:
            avg = total / len(expenses)
            summary_text += f"Average Expense: ₹{avg:.2f}"
        self.summary_label.config(text=summary_text)
        self.update_category_stats()
        self.update_monthly_stats()
    
    def update_category_stats(self):
        for item in self.category_tree.get_children():
            self.category_tree.delete(item)
        category_stats = self.db_manager.expenses_by_category()
        total = self.db_manager.total_expenses()
        if not total:
            return
        for category, amount in category_stats:
            percentage = (amount / total) * 100
            self.category_tree.insert("", "end", values=(category, f"₹{amount:.2f}", f"{percentage:.1f}%"))
    
    def update_monthly_stats(self):
        for item in self.monthly_tree.get_children():
            self.monthly_tree.delete(item)
        try:
            year = int(self.year_var.get())
        except:
            year = datetime.now().year
        monthly_stats = self.db_manager.expenses_by_month(year)
        month_names = ["January", "February", "March", "April", "May", "June", 
                      "July", "August", "September", "October", "November", "December"]
        for month, amount in monthly_stats:
            month_idx = int(month) - 1
            month_name = month_names[month_idx]
            self.monthly_tree.insert("", "end", values=(month_name, f"₹{amount:.2f}"))
    
    def export_data(self):
        try:
            filename = simpledialog.askstring("Export Data", "Enter filename:", initialvalue="expenses_export.json")
            if not filename:
                return
            if not filename.endswith('.json'):
                filename += '.json'
            if self.db_manager.export_to_json(filename):
                self.update_status(f"Data exported to {filename}")
                messagebox.showinfo("Export Successful", f"Data exported to {filename}")
            else:
                messagebox.showerror("Export Failed", "Failed to export data")
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred: {e}")
    
    def email_backup(self):
        try:
            email_dialog = EmailBackupDialog(self.root)
            if not email_dialog.result:
                return
            user_email, password, recipient_email = email_dialog.result
            if self.db_manager.email_backup(user_email, password, recipient_email):
                self.update_status("Backup email sent successfully")
                messagebox.showinfo("Email Sent", "Backup email sent successfully")
            else:
                messagebox.showerror("Email Failed", "Failed to send backup email")
        except Exception as e:
            messagebox.showerror("Email Error", f"An error occurred: {e}")
    
    def switch_database(self, is_local):
        try:
            if not is_local:
                email = simpledialog.askstring("Email Database", "Enter your email:")
                if not email:
                    return
                if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    messagebox.showerror("Invalid Email", "Please enter a valid email address")
                    return
            else:
                email = None
            if self.db_manager.switch_database(is_local, email):
                db_type = "local" if is_local else f"email-linked ({email})"
                self.update_status(f"Switched to {db_type} database")
                self.load_expenses()
                self.update_stats()
                self.update_category_combo()
            else:
                messagebox.showerror("Switch Failed", "Failed to switch database")
        except Exception as e:
            messagebox.showerror("Database Error", f"An error occurred: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ExpenseTrackerApp(root)
    root.mainloop()