from main import app, check_late_tasks

if __name__ == "__main__":
    print("Starting background late task checker...")
    with app.app_context():
        check_late_tasks()  # this loops forever, sending overdue emails