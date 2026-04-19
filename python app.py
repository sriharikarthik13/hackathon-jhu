import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Drop tables to reset state every time the app starts
    c.execute('DROP TABLE IF EXISTS users')
    c.execute('DROP TABLE IF EXISTS debts')
    
    c.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            balance REAL,
            owed_to_you REAL,
            you_owe REAL
        )
    ''')
    
    # New table for debts
    c.execute('''
        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debtor_name TEXT,
            amount REAL,
            reason TEXT
        )
    ''')
    
    # Check if Priya exists, if not insert
    c.execute('SELECT * FROM users WHERE name = ?', ('Priya',))
    if c.fetchone() is None:
        c.execute('''
            INSERT INTO users (name, balance, owed_to_you, you_owe)
            VALUES (?, ?, ?, ?)
        ''', ('Priya', 1200.00, 0, 450.00))
        conn.commit()
    
    conn.close()

# Initialize DB on startup
init_db()

def get_user_data(name):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE name = ?', (name,))
    user = c.fetchone()
    conn.close()
    return user

@app.route('/')
def hello():
    user = get_user_data('Priya')
    
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT debtor_name, sum(amount) as total FROM debts WHERE amount > 0 GROUP BY debtor_name')
    dept_rows = c.fetchall()
    
    c.execute('SELECT reason, amount FROM debts WHERE amount > 0')
    reason_rows = c.fetchall()
    conn.close()

    debtors = [row['debtor_name'] for row in dept_rows]
    
    # Calculate for Debt Bar Chart
    chart_debts = {row['debtor_name']: row['total'] for row in dept_rows}
    
    # Calculate for Reasons Pie Chart (NLP aggregated)
    chart_reasons = {}
    for r in reason_rows:
        amount = r['amount']
        # Simple NLP normalization: Title case & removing leading/trailing spaces
        raw = r['reason'].strip()
        reason = raw.title() if raw else "Other"
        
        if reason in chart_reasons:
            chart_reasons[reason] += amount
        else:
            chart_reasons[reason] = amount
            
    return render_template('index.html', user=user, debtors=debtors, chart_debts=chart_debts, chart_reasons=chart_reasons)

@app.route('/payment')
def payment():
    user = get_user_data('Priya')
    return render_template('payment.html', user=user)

exchange_rates = {
    'US': 1.0,
    'UK': 1.27,
    'EU': 1.08,
    'IN': 0.012,
    'JP': 0.0065,
    'AU': 0.66,
    'CA': 0.73,
    'CH': 1.10
}

@app.route('/send_payment', methods=['GET', 'POST'])
def send_payment():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            country = request.form.get('country', 'US')
            if amount > 0:
                rate = exchange_rates.get(country, 1.0)
                usd_amount = amount * rate
                
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                # Deduct equivalent USD from balance
                c.execute('UPDATE users SET balance = balance - ?, you_owe = MAX(0, you_owe - ?) WHERE name = ?', (usd_amount, usd_amount, 'Priya'))
                conn.commit()
                conn.close()
            return redirect(url_for('hello'))
        except ValueError:
            return redirect(url_for('send_payment'))
    return render_template('send_payment.html')

@app.route('/add_balance', methods=['GET', 'POST'])
def add_balance():
    if request.method == 'POST':
        try:
            amount = float(request.form.get('amount', 0))
            if amount > 0:
                conn = sqlite3.connect('database.db')
                c = conn.cursor()
                # Add to balance
                c.execute('UPDATE users SET balance = balance + ? WHERE name = ?', (amount, 'Priya'))
                conn.commit()
                conn.close()
            return redirect(url_for('hello'))
        except ValueError:
            return redirect(url_for('add_balance'))
    return render_template('add_balance.html')

@app.route('/debt/<name>')
def debt_details(name):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM debts WHERE debtor_name = ?', (name,))
    user_debts = c.fetchall()
    conn.close()
    
    total_owed = sum(d['amount'] for d in user_debts)
    return render_template('debt_details.html', debtor_name=name, debts=user_debts, total_owed=total_owed)

@app.route('/api/generate_reminder/<name>')
def generate_reminder(name):
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM debts WHERE debtor_name = ?', (name,))
    user_debts = c.fetchall()
    conn.close()
    
    total_owed = sum(d['amount'] for d in user_debts)
    if total_owed <= 0:
        return {"text": f"Hey {name}, looks like we're all clear! No money owed."}
    
    reasons = [d['reason'] for d in user_debts]
    if len(reasons) > 2:
        reason_str = ", ".join(reasons[:-1]) + ", and " + reasons[-1]
    elif len(reasons) == 2:
        reason_str = reasons[0] + " and " + reasons[1]
    elif len(reasons) == 1:
        reason_str = reasons[0]
    else:
        reason_str = "our recent splits"
        
    text = f"Hey {name}! Hope you're having a great week 😊. Just sending a gentle reminder about the ${total_owed:.2f} for {reason_str}. No rush at all, just let me know whenever you have a chance to settle up. Thanks! ✨"
    
    time.sleep(1.5)  # Simulate AI 'thinking' time
    return {"text": text}

@app.route('/request_money', methods=['GET', 'POST'])
def request_money():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT DISTINCT debtor_name FROM debts WHERE amount > 0')
    debtors = [row['debtor_name'] for row in c.fetchall()]
    conn.close()
    
    if request.method == 'POST':
        selected_debtor = request.form.get('debtor_name')
        if selected_debtor:
            return redirect(url_for('debt_details', name=selected_debtor))
            
    return render_template('request_money.html', debtors=debtors)

@app.route('/split', methods=['GET', 'POST'])
def split_bill():
    if request.method == 'POST':
        try:
            total_amount = float(request.form.get('amount', 0))
            reason = request.form.get('reason', '')
            
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            
            total_owed = 0
            for person in ['Harry', 'Ron', 'Emma']:
                pct = float(request.form.get(f'pct_{person}', 0))
                if pct > 0:
                    owed_amount = total_amount * (pct / 100.0)
                    total_owed += owed_amount
                    c.execute('INSERT INTO debts (debtor_name, amount, reason) VALUES (?, ?, ?)', (person, owed_amount, reason))
            
            if total_owed > 0:
                c.execute('UPDATE users SET owed_to_you = owed_to_you + ? WHERE name = ?', (total_owed, 'Priya'))
            
            conn.commit()
            conn.close()
            return redirect(url_for('hello'))
        except ValueError:
            return redirect(url_for('split_bill'))
            
    return render_template('split_bill.html', user=get_user_data('Priya'))

@app.route('/voice_split', methods=['POST'])
def voice_split():
    try:
        debtor_name = request.form.get('debtor_name')
        amount = float(request.form.get('amount', 0))
        reason = request.form.get('reason', '')
        
        if amount > 0 and debtor_name:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute('INSERT INTO debts (debtor_name, amount, reason) VALUES (?, ?, ?)', (debtor_name, amount, reason))
            c.execute('UPDATE users SET owed_to_you = owed_to_you + ? WHERE name = ?', (amount, 'Priya'))
            conn.commit()
            conn.close()
            
        return redirect(url_for('hello'))
    except ValueError:
        return redirect(url_for('split_bill'))

@app.route('/api/record_python', methods=['POST'])
def record_python():
    import speech_recognition as sr
    import re
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=3, phrase_time_limit=5)
        
        transcript = r.recognize_google(audio)
        
        # Improved NLP Parsing
        transcript_lower = transcript.lower()
        
        name = 'Harry'
        for n in ['Ron', 'Emma', 'Harry']:
            if n.lower() in transcript_lower:
                name = n
        
        amount = ''
        amount_match = re.search(r'(\d+(?:\.\d{1,2})?)', transcript)
        if amount_match:
            amount = amount_match.group(1)
        else:
            word_to_num = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
                'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
                'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50,
                'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90
            }
            words = transcript_lower.split()
            current = 0
            for w in words:
                if w in word_to_num: current += word_to_num[w]
            if current > 0: amount = str(current)
            
        reason = 'Voice split'
        clean = re.sub(rf'(?i)\b{name}\b', '', transcript)
        for_match = re.search(r'for\s+(.*)', clean, re.IGNORECASE)
        if for_match:
            r = for_match.group(1).replace('dollars', '').strip()
            r = re.sub(r'^(the|a|for|with)\s+', '', r, flags=re.IGNORECASE).strip()
            if r: reason = r.capitalize()
                
        return {"success": True, "transcript": transcript, "name": name, "amount": amount, "reason": reason}
    except sr.WaitTimeoutError:
        return {"success": False, "error": "Listening timed out. No speech detected."}
    except sr.UnknownValueError:
        return {"success": False, "error": "Speech was unintelligible."}
    except Exception as e:
        return {"success": False, "error": f"Audio error: {str(e)}"}

if __name__ == '__main__':
    app.run(debug=True)