from flask import Flask, jsonify, render_template, g
import imaplib
import email
from email.header import decode_header
import time
import threading
import smtplib
from email.mime.text import MIMEText
import openai
import pickle
import sqlite3
import random

# Initialize Flask App
app = Flask(__name__)

# Database Connection
DATABASE = "emails_analysis.db"

def get_db():
    """ Ensure a single database connection per request """
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, check_same_thread=False)
    return db

@app.teardown_appcontext
def close_connection(exception):
    """ Close database connection after each request """
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()

# Setup Database Schema
with sqlite3.connect(DATABASE) as conn:
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            subject TEXT,
            body TEXT,
            tag TEXT,
            sentiment TEXT,
            summary TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    


# Load Credentials
with open(r"C:\Users\joice\OneDrive\Documentos\Ironhack\ML course\secrets\googlepass.txt", "r") as file:
    password = file.read().strip()

with open(r"C:\Users\joice\OneDrive\Documentos\Ironhack\ML course\secrets\openai-api.txt", "r") as file:
    openai_api_key = file.read().strip()

openai_client = openai.OpenAI(api_key=openai_api_key)

# Email Credentials
myemail = "joaomailclassifier@gmail.com"

# IMAP & SMTP Setup
imap_url = "imap.gmail.com"
smtp_server = "smtp.gmail.com"
smtp_port = 587

# Load Classification Dataset
with open("complaints dict.pkl", "rb") as file:
    dataset = pickle.load(file)

# Define Classification Labels
label_list = [
    "Credit reporting or other personal consumer reports",
    "Debt collection",
    "Payday loan",
    "Checking or savings account",
    "Mortgage",
    "Credit card",
    "Money transfer, virtual currency, or money service",
    "Student loan",
    "Prepaid card",
    "Payday loan, title loan, personal loan, or advance loan",
    "Vehicle loan or lease",
    "Debt or credit management",
    "Credit reporting, credit repair services, or other personal consumer reports",
    "Bank account or service",
    "Credit card or prepaid card",
    "Consumer Loan",
    "Credit reporting",
    "Payday loan, title loan, or personal loan",
    "Money transfers",
    "Other financial service",
    "Virtual currency",
    "Compliance, data protection"
]

def detect_and_translate(text):
    """ Detects and translates text if it's not in English """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Detect and translate."}, {"role": "user", "content": text}]
        )
        result = response.choices[0].message.content.strip()

        if "|||" in result:
            detected_lang, translated_text = result.split(" ||| ", 1)
        else:
            detected_lang, translated_text = "English", text

        return detected_lang, translated_text
    except Exception as e:
        print(f"❌ Error in translation: {e}")
        return "Unknown", text

def classify_complaint(text, dataset, label_list):
    """
    Classifies a complaint strictly into one of the predefined categories.
    Uses few-shot examples from dataset to improve accuracy.
    """
    try:
        # Select up to 5 random examples from dataset
        examples = random.sample(dataset, min(5, len(dataset)))

        # Format the examples as few-shot demonstrations
        examples_prompt = "\n".join([f'"{ex["text"]}" -> {ex["label"]}' for ex in examples])
        labels_str = "\n".join([f"- {label}" for label in label_list])

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": 
                    f"You are a financial complaint classifier. Your task is to strictly classify complaints "
                    f"into one of the following categories:\n\n"
                    f"{labels_str}\n\n"
                    f"Here are some labeled examples to guide you:\n\n"
                    f"{examples_prompt}\n\n"
                    f"Now, classify the following consumer complaint into one of the categories above:\n\n"
                    f"Complaint: '{text}'\n\n"
                    f"Provide only the category name from the list, without any explanation."
                }
            ]
        )

        predicted_label = response.choices[0].message.content.strip()

        # Ensure the model provides a valid label from label_list
        if predicted_label in label_list:
            return predicted_label
        else:
            print(f"⚠️ Warning: Model generated unexpected label: {predicted_label}")
            return "Unknown Label"

    except Exception as e:
        print(f"❌ Error in classification: {e}")
        return "Unknown Label"
    
    
def send_email(original_sender, subject, body, tag):
    msg_content = f"""
    ORIGINAL EMAIL:
    -----------------
    From: {original_sender}
    Subject: {subject}

    {body}

    -----------------
    TAGGED AS:
    Tag: {tag}
    """
    msg = MIMEText(msg_content)
    msg["Subject"] = f"Tagged Email - {subject}"
    msg["From"] = myemail
    msg["To"] = "joaotaggedemails@gmail.com"

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(myemail, password)
        server.send_message(msg)
        server.quit()
        print(f"📨 Email sent to joaotaggedemails@gmail.com with tag: {tag}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


def sentiment_analysis(text):
    """ Performs sentiment analysis """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Analyze the sentiment as Positive, Neutral, or Negative."}, 
                      {"role": "user", "content": text}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error in sentiment analysis: {e}")
        return "Unknown"

def summarize_text(text):
    """ Summarizes the translated English text to ensure consistent language output. """
    if len(text.split()) < 5:
        return "Text too short to summarize."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "Summarize the following email content in English."}, 
                      {"role": "user", "content": text}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"❌ Error in summarization: {e}")
        return "Failed to generate summary."


def store_analysis(sender, subject, body, tag, sentiment, summary):
    """ Stores processed email data in SQLite, preventing duplicate entries. """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()

        # ✅ Check if the email already exists before inserting
        cursor.execute("SELECT COUNT(*) FROM email_analysis WHERE sender = ? AND subject = ? AND body = ?",
                       (sender, subject, body))
        exists = cursor.fetchone()[0]

        if exists == 0:  # ✅ Insert only if no duplicate exists
            cursor.execute("""
                INSERT INTO email_analysis (sender, subject, body, tag, sentiment, summary)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (sender, subject, body, tag, sentiment, summary)
            )
            db.commit()




def process_emails():
    """ Fetches and processes unread emails, ensuring they are marked as read. """
    while True:
        try:
            mail = imaplib.IMAP4_SSL(imap_url)
            mail.login(myemail, password)
            mail.select("inbox")

            # Search for unread (UNSEEN) emails
            _, data = mail.search(None, "UNSEEN")
            mail_ids = data[0].split()

            print(f"📩 Found {len(mail_ids)} new emails to process.")

            for i, num in enumerate(mail_ids):
                print(f"Processing email {i+1} of {len(mail_ids)}")

                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])

                # ✅ Decode sender
                from_header = msg.get("From")
                decoded_sender, encoding = decode_header(from_header)[0]
                sender = decoded_sender.decode(encoding or "utf-8") if isinstance(decoded_sender, bytes) else decoded_sender

                # ✅ Decode subject
                subject, encoding = decode_header(msg["Subject"])[0]
                subject = subject.decode(encoding or "utf-8") if isinstance(subject, bytes) else subject

                # ✅ Extract email body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                # ✅ Mark email as read immediately
                mail.store(num, '+FLAGS', '\\Seen')

                # ✅ Email Processing Steps
                detected_lang, translated_body = detect_and_translate(body)
                tag = classify_complaint(translated_body, dataset, label_list)
                sentiment = sentiment_analysis(translated_body)
                summary = summarize_text(translated_body)

                # ✅ Store results and send email
                store_analysis(sender, subject, body, tag, sentiment, summary)
                send_email(sender, subject, body, tag)

            mail.logout()

        except Exception as e:
            print(f"❌ Error in email processing: {e}")

        time.sleep(30)  # Check for new emails every 30 seconds




# process_emails()
# threading.Thread(target=process_emails, daemon=True).start()


@app.route("/api/emails", methods=["GET"])
def get_emails():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT sender, subject, tag, sentiment, summary FROM email_analysis ORDER BY timestamp DESC LIMIT 100")
    emails = cursor.fetchall()
    return jsonify([
        {"sender": row[0], "subject": row[1], "tag": row[2], "sentiment": row[3], "summary": row[4]}
        for row in emails
    ])

@app.route("/api/sentiment", methods=["GET"])
def get_sentiment():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT sentiment, COUNT(*) FROM email_analysis GROUP BY sentiment")
    data = cursor.fetchall()
    return jsonify({row[0]: row[1] for row in data}) if data else jsonify({"error": "No sentiment data found"}), 404

@app.route("/api/tags", methods=["GET"])
def get_tags():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT tag, COUNT(*) FROM email_analysis GROUP BY tag")
    data = cursor.fetchall()
    return jsonify({row[0]: row[1] for row in data}) if data else jsonify({"error": "No tag data found"}), 404


@app.route("/")
def dashboard():
    return render_template("dashboard.html")

# Start email processing in a background thread
email_thread = None
thread_lock = threading.Lock()

def start_email_thread():
    global email_thread
    with thread_lock:
        if email_thread is None or not email_thread.is_alive():
            email_thread = threading.Thread(target=process_emails, daemon=True)
            email_thread.start()
            print("📩 Email thread started.")

# Start Flask and email processing together
if __name__ == "__main__":
    start_email_thread()  # Only start once
    app.run(debug=True, use_reloader=False)


