import os
import sqlite3
import click
from flask import Flask, render_template, request, redirect, url_for, g, flash, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta



# --- App Initialization and Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key'
app.config['DATABASE'] = os.path.join(app.root_path, 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- Constants for Insurance Companies ---
INSURANCE_COMPANIES = sorted([
    "Agriculture Insurance Company of India Ltd", "ECGC Ltd (Export Credit Guarantee Corporation)",
    "National Insurance Company Ltd", "New India Assurance Company Ltd", "Oriental Insurance Company Ltd",
    "United India Insurance Company Ltd", "Acko General Insurance Ltd", "Bajaj Allianz General Insurance Co Ltd",
    "Bharti AXA / Zurich Kotak General Insurance Co Ltd", "Cholamandalam MS General Insurance Co Ltd",
    "Edelweiss / Zuno General Insurance Ltd", "Future Generali India Insurance Co Ltd",
    "Go Digit General Insurance Ltd", "HDFC ERGO General Insurance Co Ltd", "ICICI Lombard General Insurance Co Ltd",
    "IFFCO-Tokio General Insurance Co Ltd", "Kotak Mahindra General Insurance Co Ltd", "Liberty General Insurance Ltd",
    "Magma HDI / Magma General Insurance Co Ltd", "Navi General Insurance Ltd", "Raheja QBE General Insurance Co Ltd",
    "Reliance General Insurance Co Ltd", "Royal Sundaram General Insurance Co Ltd", "SBI General Insurance Co Ltd",
    "Shriram General Insurance Co Ltd", "Tata AIG General Insurance Co Ltd", "Universal Sompo General Insurance Co Ltd"
])

# --- Database ---
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('init-db')
def init_db_command():
    init_db()
    click.echo('Initialized the database.')

# --- Main Routes ---
@app.route('/')
def dashboard():
    db = get_db()
    client_count = db.execute('SELECT COUNT(id) FROM Clients').fetchone()[0]
    today = datetime.now().date()
    thirty_days_from_now = today + timedelta(days=30)
    upcoming_policy_count = db.execute(
        'SELECT COUNT(id) FROM Policies WHERE date(policy_end_date) BETWEEN ? AND ?',
        (today.strftime('%Y-%m-%d'), thirty_days_from_now.strftime('%Y-%m-%d'))
    ).fetchone()[0]
    return render_template('dashboard.html', client_count=client_count, upcoming_policy_count=upcoming_policy_count)

# --- Client Management Routes ---
@app.route('/clients')
def list_clients():
    db = get_db()
    search_query = request.args.get('search', '')
    if search_query:
        clients = db.execute('SELECT * FROM Clients WHERE name LIKE ? ORDER BY name', (f'%{search_query}%',)).fetchall()
    else:
        clients = db.execute('SELECT * FROM Clients ORDER BY name').fetchall()
    return render_template('clients.html', clients=clients, search_query=search_query)

@app.route('/client/<int:client_id>')
def client_detail(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM Clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('Client not found.', 'danger')
        return redirect(url_for('list_clients'))
    policies = db.execute('SELECT * FROM Policies WHERE client_id = ? ORDER BY policy_end_date', (client_id,)).fetchall()
    documents = db.execute('SELECT * FROM Documents WHERE client_id = ? ORDER BY filename', (client_id,)).fetchall()
    return render_template('client_detail.html', client=client, policies=policies, documents=documents)

@app.route('/client/<int:client_id>/upload_document', methods=['GET', 'POST'])
def upload_document(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM Clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('Client not found.', 'danger')
        return redirect(url_for('list_clients'))

    if request.method == 'POST':
        file = request.files['document']
        if file and file.filename:
            filename = secure_filename(file.filename)
            client_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(client_id))
            os.makedirs(client_folder, exist_ok=True)
            filepath = os.path.join(client_folder, filename)
            file.save(filepath)

            db.execute('INSERT INTO Documents (client_id, filename) VALUES (?, ?)', (client_id, filename))
            db.commit()
            flash('Document uploaded successfully.', 'success')
            return redirect(url_for('client_detail', client_id=client_id))
        else:
            flash('No file selected.', 'danger')

    return render_template('upload_document.html', client=client)

@app.route('/uploads/<int:client_id>/<filename>')
def view_document(client_id, filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], str(client_id)), filename)

@app.route('/documents/<int:doc_id>/edit', methods=['GET', 'POST'])
def edit_document(doc_id):
    db = get_db()
    document = db.execute('SELECT * FROM Documents WHERE id = ?', (doc_id,)).fetchone()
    if document is None:
        abort(404)

    if request.method == 'POST':
        new_filename = request.form['filename'].strip()
        if new_filename:
            db.execute('UPDATE Documents SET filename = ? WHERE id = ?', (new_filename, doc_id))
            db.commit()
            flash('Document updated.')
            return redirect(url_for('client_detail', client_id=document['client_id']))
        else:
            flash('Filename cannot be empty.')

    return render_template('edit_document.html', doc=document)

@app.route('/documents/<int:doc_id>/delete', methods=['POST'])
def delete_document(doc_id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Get document first
    cursor.execute("SELECT * FROM Documents WHERE id = ?", (doc_id,))
    document = cursor.fetchone()
    
    if document:
        cursor.execute("DELETE FROM Documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        flash('Document deleted.')
        return redirect(url_for('client_detail', client_id=document[1]))  # Assuming client_id is second column
    else:
        conn.close()
        abort(404)



@app.route('/add_client', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        db = get_db()
        raw_dob = request.form['dob']
        dob = datetime.strptime(raw_dob, '%Y-%m-%d').strftime('%d/%m/%Y')
        if request.form.get('has_nominee') == 'yes':
            nominee_name = request.form.get('nominee_name')
            raw_nominee_dob = request.form.get('nominee_dob')
            nominee_dob = datetime.strptime(raw_nominee_dob, '%Y-%m-%d').strftime('%d/%m/%Y') if raw_nominee_dob else None
        else:
            nominee_name = None
            nominee_dob = None
        db.execute(
            'INSERT INTO Clients (name, phone, email, address, dob, nominee_name, nominee_dob) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (request.form['name'], request.form['phone'], request.form['email'], request.form['address'], request.form['dob'], nominee_name, nominee_dob)
        )
        db.commit()
        flash(f'Client "{request.form["name"]}" was successfully added!', 'success')
        return redirect(url_for('list_clients'))
    return render_template('add_client.html')

@app.route('/client/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    db = get_db()
    client = db.execute('SELECT * FROM Clients WHERE id = ?', (client_id,)).fetchone()
    if not client:
        flash('Client not found.', 'danger')
        return redirect(url_for('list_clients'))
    if request.method == 'POST':
        raw_dob = request.form['dob']
        dob = datetime.strptime(raw_dob, '%Y-%m-%d').strftime('%d/%m/%Y')
        if request.form.get('has_nominee') == 'yes':
            nominee_name = request.form.get('nominee_name')
            raw_nominee_dob = request.form.get('nominee_dob')
            nominee_dob = datetime.strptime(raw_nominee_dob, '%Y-%m-%d').strftime('%d/%m/%Y') if raw_nominee_dob else None
        else:
            nominee_name = None
            nominee_dob = None
        db.execute(
            'UPDATE Clients SET name = ?, phone = ?, email = ?, address = ?, dob = ?, nominee_name = ?, nominee_dob = ? WHERE id = ?',
            (request.form['name'], request.form['phone'], request.form['email'], request.form['address'], request.form['dob'], nominee_name, nominee_dob, client_id)
        )
        db.commit()
        flash(f'Client "{request.form["name"]}" has been updated.', 'success')
        return redirect(url_for('list_clients'))
        try:
            client = dict(client)  # convert to dict so we can modify fields
            client['dob'] = datetime.strptime(client['dob'], '%d/%m/%Y').strftime('%Y-%m-%d')
            if client['nominee_dob']:
                client['nominee_dob'] = datetime.strptime(client['nominee_dob'], '%d/%m/%Y').strftime('%Y-%m-%d')
        except Exception:
            pass  # In case format is already correct or empty

    return render_template('edit_client.html', client=client)

@app.route('/client/<int:client_id>/delete', methods=['POST'])
def delete_client(client_id):
    db = get_db()
    db.execute('DELETE FROM Clients WHERE id = ?', (client_id,))
    db.commit()
    flash('Client has been deleted.', 'success')
    return redirect(url_for('list_clients'))

# --- Policy Management Routes ---
@app.route('/policies')
def track_policies():
    db = get_db()
    search_query = request.args.get('search', '')
    base_query = 'SELECT p.*, c.name as client_name FROM Policies p JOIN Clients c ON p.client_id = c.id'
    params = []
    if search_query:
        base_query += ' WHERE p.policy_number LIKE ?'
        params.append(f'%{search_query}%')
    base_query += ' ORDER BY p.policy_end_date'
    policies = db.execute(base_query, params).fetchall()
    return render_template('policies.html', policies=policies, search_query=search_query)

def process_policy_form(client_id):
    def format_date(date_str):
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d/%m/%Y') if date_str else None

    return {
        'client_id': client_id, 'policy_number': request.form.get('policy_number'), 'vehicle_number': request.form.get('vehicle_number'),
        'vehicle_type': request.form.get('vehicle_type'), 'agency': request.form.get('agency'), 'policy_type': request.form.get('policy_type'),
        'insurance_company': request.form.get('insurance_company'), 'premium': request.form.get('premium') or 0.0,
        'policy_start_date': request.form.get('policy_start_date') or None, 'policy_end_date': request.form.get('policy_end_date') or None,
        'account_details': request.form.get('account_details')
    }

@app.route('/client/<int:client_id>/add_policy', methods=['GET', 'POST'])
def add_policy(client_id):
    db = get_db()
    agencies = db.execute('SELECT * FROM Agencies ORDER BY name').fetchall()
    if request.method == 'POST':
        policy_data = process_policy_form(client_id)
        db.execute('INSERT INTO Policies (client_id, policy_number, vehicle_number, vehicle_type, agency, policy_type, insurance_company, premium, policy_start_date, policy_end_date, account_details) VALUES (:client_id, :policy_number, :vehicle_number, :vehicle_type, :agency, :policy_type, :insurance_company, :premium, :policy_start_date, :policy_end_date, :account_details)', policy_data)
        db.commit()
        flash(f'Policy "{policy_data["policy_number"]}" was successfully added.', 'success')
        return redirect(url_for('client_detail', client_id=client_id))
    client = db.execute('SELECT * FROM Clients WHERE id = ?', (client_id,)).fetchone()
    return render_template('add_policy.html', client=client, agencies=agencies, insurance_companies=INSURANCE_COMPANIES)

@app.route('/policy/<int:policy_id>/edit', methods=['GET', 'POST'])
def edit_policy(policy_id):
    db = get_db()
    policy = db.execute('SELECT * FROM Policies WHERE id = ?', (policy_id,)).fetchone()
    agencies = db.execute('SELECT * FROM Agencies ORDER BY name').fetchall()
    if request.method == 'POST':
        policy_data = process_policy_form(policy['client_id'])
        policy_data['policy_id'] = policy_id
        db.execute('UPDATE Policies SET policy_number = :policy_number, vehicle_number = :vehicle_number, vehicle_type = :vehicle_type, agency = :agency, policy_type = :policy_type, insurance_company = :insurance_company, premium = :premium, policy_start_date = :policy_start_date, policy_end_date = :policy_end_date, account_details = :account_details WHERE id = :policy_id', policy_data)
        db.commit()
        flash(f'Policy "{policy_data["policy_number"]}" has been updated.', 'success')
        return redirect(url_for('client_detail', client_id=policy['client_id']))
    policy = dict(policy)  # make mutable
    try:
        policy['policy_start_date'] = datetime.strptime(policy['policy_start_date'], '%d/%m/%Y').strftime('%Y-%m-%d')
        policy['policy_end_date'] = datetime.strptime(policy['policy_end_date'], '%d/%m/%Y').strftime('%Y-%m-%d')
    except Exception:
        pass  # in case dates are null or already in correct format
    return render_template('edit_policy.html', policy=policy, agencies=agencies, insurance_companies=INSURANCE_COMPANIES)

@app.route('/policy/<int:policy_id>/delete', methods=['POST'])
def delete_policy(policy_id):
    db = get_db()
    policy = db.execute('SELECT client_id FROM Policies WHERE id = ?', (policy_id,)).fetchone()
    if policy:
        db.execute('DELETE FROM Policies WHERE id = ?', (policy_id,))
        db.commit()
        flash('Policy has been deleted.', 'success')
        return redirect(url_for('client_detail', client_id=policy['client_id']))
    return redirect(url_for('track_policies'))

# --- Document Management ---
# (No changes needed here, code is correct)

# --- Agency Routes ---
@app.route('/agencies')
def list_agencies():
    agencies = get_db().execute('SELECT * FROM Agencies ORDER BY name').fetchall()
    return render_template('agencies.html', agencies=agencies)

@app.route('/add_agency', methods=['GET', 'POST'])
def add_agency():
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            try:
                get_db().execute('INSERT INTO Agencies (name) VALUES (?)', (name,))
                get_db().commit()
                flash(f'Agency "{name}" added.', 'success')
            except sqlite3.IntegrityError:
                flash(f'Agency "{name}" already exists.', 'danger')
        return redirect(url_for('list_agencies'))
    return render_template('add_agency.html')

@app.route('/agency/<int:agency_id>/edit', methods=['GET', 'POST'])
def edit_agency(agency_id):
    db = get_db()
    agency = db.execute('SELECT * FROM Agencies WHERE id = ?', (agency_id,)).fetchone()
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            try:
                db.execute('UPDATE Agencies SET name = ? WHERE id = ?', (name, agency_id))
                db.commit()
                flash('Agency updated.', 'success')
            except sqlite3.IntegrityError:
                flash(f'Agency "{name}" already exists.', 'danger')
        return redirect(url_for('list_agencies'))
    return render_template('edit_agency.html', agency=agency)

@app.route('/agency/<int:agency_id>/delete', methods=['POST'])
def delete_agency(agency_id):
    get_db().execute('DELETE FROM Agencies WHERE id = ?', (agency_id,))
    get_db().commit()
    flash('Agency deleted.', 'success')
    return redirect(url_for('list_agencies'))

# --- Birthday Route ---
@app.route('/birthdays')
def birthdays():
    clients = get_db().execute('SELECT id, name, dob, email FROM Clients WHERE dob IS NOT NULL AND dob != ""').fetchall()
    today, todays_birthdays, upcoming_birthdays = datetime.now(), [], []
    for client in clients:
        try:
            dob = datetime.strptime(client['dob'], '%Y-%m-%d')
            this_year_bday = dob.replace(year=today.year)
            if this_year_bday.strftime('%m-%d') == today.strftime('%m-%d'):
                todays_birthdays.append(client)
            elif today.date() < this_year_bday.date() <= (today + timedelta(days=7)).date():
                upcoming_birthdays.append({'date': this_year_bday, 'client': client})
        except (ValueError, TypeError):
            continue
    upcoming_birthdays.sort(key=lambda x: x['date'])
    return render_template('birthdays.html', todays_birthdays=todays_birthdays, upcoming_birthdays=upcoming_birthdays)

# --- Reporting ---
@app.route('/reports')
def generate_reports():
    total_premium_result = get_db().execute('SELECT SUM(premium) as total_premium FROM Policies').fetchone()
    total_premium = total_premium_result['total_premium'] if total_premium_result['total_premium'] else 0
    return render_template('reports.html', total_premium=total_premium)

if __name__ == '__main__':
    app.run(debug=True)