import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField, SelectField, TextAreaField, DecimalField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, NumberRange
from sqlalchemy import or_, func

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'CHANGE-THIS-SECRET-BEFORE-DEPLOYMENT')
database_url = os.environ.get('DATABASE_URL', 'sqlite:///benjor_inventory.db')
# Render PostgreSQL URLs may use postgres:// or postgresql://. This project
# installs psycopg 3, so explicitly select its SQLAlchemy dialect/driver.
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect(app)

ROLES = [('admin', 'Administrator'), ('it_support', 'IT Support'), ('officer', 'Officer / Client')]
ITEM_STATUSES = [('Available', 'Available'), ('Borrowed', 'Borrowed'), ('Under Repair', 'Under Repair'), ('Unserviceable', 'Unserviceable'), ('Disposed', 'Disposed')]
REQUEST_TYPES = [('Borrowing', 'Borrowing'), ('Repair', 'Repair')]
REQUEST_STATUSES = ['Pending', 'Approved', 'Rejected', 'In Progress', 'Ready for Pickup', 'Borrowed', 'Completed', 'Cancelled']

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=True)
    department = db.Column(db.String(120), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='officer')
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    requests = db.relationship('ServiceRequest', backref='requester', lazy=True, foreign_keys='ServiceRequest.requester_id')
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ctrl_no = db.Column(db.String(40), unique=True, nullable=False, index=True)
    serial_no = db.Column(db.String(120), default='')
    item = db.Column(db.String(160), nullable=False)
    brand = db.Column(db.String(120), default='')
    details = db.Column(db.Text, default='')
    date_purchased = db.Column(db.Date, nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(40), nullable=False, default='Available')
    assigned_to = db.Column(db.String(160), default='')
    location = db.Column(db.String(160), default='')
    remarks = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ServiceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(30), unique=True, nullable=False, index=True)
    request_type = db.Column(db.String(20), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True)
    item_description = db.Column(db.String(180), default='')
    description = db.Column(db.Text, nullable=False)
    needed_from = db.Column(db.Date, nullable=True)
    needed_until = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(40), nullable=False, default='Pending')
    staff_notes = db.Column(db.Text, default='')
    decision_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    item = db.relationship('InventoryItem', backref='service_requests')
    decision_maker = db.relationship('User', foreign_keys=[decision_by])

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')

def log_action(action, details=''):
    try:
        db.session.add(AuditLog(user_id=current_user.id if current_user.is_authenticated else None, action=action, details=details))
        db.session.commit()
    except Exception:
        db.session.rollback()

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.context_processor
def inject_globals():
    return {'now': datetime.utcnow, 'role_label': dict(ROLES).get}

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign in')

class UserForm(FlaskForm):
    full_name = StringField('Full name', validators=[DataRequired(), Length(max=120)])
    username = StringField('Username', validators=[DataRequired(), Length(max=80)])
    email = StringField('Email', validators=[Optional(), Length(max=160)])
    department = StringField('Department / Office', validators=[Optional(), Length(max=120)])
    role = SelectField('Role', choices=ROLES, validators=[DataRequired()])
    password = PasswordField('Temporary password', validators=[Optional(), Length(min=8, max=128)])
    submit = SubmitField('Save user')

class ItemForm(FlaskForm):
    ctrl_no = StringField('Control number', validators=[DataRequired(), Length(max=40)])
    serial_no = StringField('Serial number', validators=[Optional(), Length(max=120)])
    item = StringField('Item', validators=[DataRequired(), Length(max=160)])
    brand = StringField('Brand', validators=[Optional(), Length(max=120)])
    details = TextAreaField('Details', validators=[Optional()])
    date_purchased = DateField('Date purchased', validators=[Optional()], format='%Y-%m-%d')
    amount = DecimalField('Amount', validators=[DataRequired(), NumberRange(min=0)], places=2, default=0)
    status = SelectField('Status', choices=ITEM_STATUSES, validators=[DataRequired()])
    assigned_to = StringField('Assigned to', validators=[Optional(), Length(max=160)])
    location = StringField('Location', validators=[Optional(), Length(max=160)])
    remarks = TextAreaField('Remarks', validators=[Optional()])
    submit = SubmitField('Save item')

class RequestForm(FlaskForm):
    request_type = SelectField('Request type', choices=REQUEST_TYPES, validators=[DataRequired()])
    item_id = SelectField('Inventory item (optional)', choices=[], validators=[Optional()])
    item_description = StringField('Item / equipment description', validators=[Optional(), Length(max=180)])
    description = TextAreaField('Request details', validators=[DataRequired(), Length(min=8, max=4000)])
    needed_from = DateField('Start / requested date', validators=[Optional()], format='%Y-%m-%d')
    needed_until = DateField('Return date (borrowing)', validators=[Optional()], format='%Y-%m-%d')
    submit = SubmitField('Submit request')

class UpdateRequestForm(FlaskForm):
    status = SelectField('Status', choices=[(s, s) for s in REQUEST_STATUSES], validators=[DataRequired()])
    staff_notes = TextAreaField('IT Support notes / decision reason', validators=[Optional(), Length(max=4000)])
    submit = SubmitField('Update request')

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(func.lower(User.username) == form.username.data.strip().lower()).first()
        if user and user.active and user.check_password(form.password.data):
            login_user(user)
            log_action('LOGIN', f'{user.username} signed in')
            return redirect(url_for('dashboard'))
        flash('Invalid username or password, or the account is disabled.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    log_action('LOGOUT', f'{current_user.username} signed out')
    logout_user()
    flash('You have signed out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role in ('admin', 'it_support'):
        counts = {
            'items': InventoryItem.query.count(),
            'available': InventoryItem.query.filter_by(status='Available').count(),
            'pending': ServiceRequest.query.filter_by(status='Pending').count(),
            'repairs': ServiceRequest.query.filter(ServiceRequest.request_type == 'Repair', ServiceRequest.status.in_(['Pending','Approved','In Progress'])).count(),
            'borrowing': ServiceRequest.query.filter(ServiceRequest.request_type == 'Borrowing', ServiceRequest.status.in_(['Pending','Approved','Borrowed'])).count(),
        }
        recent = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).limit(8).all()
        return render_template('dashboard_staff.html', counts=counts, recent=recent)
    mine = ServiceRequest.query.filter_by(requester_id=current_user.id).order_by(ServiceRequest.created_at.desc()).limit(8).all()
    available = InventoryItem.query.filter_by(status='Available').order_by(InventoryItem.item.asc()).limit(8).all()
    return render_template('dashboard_officer.html', mine=mine, available=available)

@app.route('/inventory')
@roles_required('admin', 'it_support')
def inventory():
    q = request.args.get('q', '').strip()
    query = InventoryItem.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(InventoryItem.ctrl_no.ilike(like), InventoryItem.serial_no.ilike(like), InventoryItem.item.ilike(like), InventoryItem.brand.ilike(like), InventoryItem.assigned_to.ilike(like), InventoryItem.location.ilike(like)))
    items = query.order_by(InventoryItem.ctrl_no.asc()).all()
    return render_template('inventory.html', items=items, q=q)

@app.route('/inventory/new', methods=['GET', 'POST'])
@roles_required('admin', 'it_support')
def inventory_new():
    form = ItemForm()
    if form.validate_on_submit():
        if InventoryItem.query.filter_by(ctrl_no=form.ctrl_no.data.strip()).first():
            flash('That control number already exists.', 'danger')
        else:
            item = InventoryItem()
            assign_item_form(item, form)
            db.session.add(item); db.session.commit()
            log_action('ITEM_CREATED', f'{item.ctrl_no}: {item.item}')
            flash('Inventory item created.', 'success')
            return redirect(url_for('inventory'))
    return render_template('item_form.html', form=form, title='Add inventory item')

def assign_item_form(item, form):
    for field, attr in [('ctrl_no','ctrl_no'),('serial_no','serial_no'),('item','item'),('brand','brand'),('details','details'),('date_purchased','date_purchased'),('amount','amount'),('status','status'),('assigned_to','assigned_to'),('location','location'),('remarks','remarks')]:
        value = getattr(form, field).data
        setattr(item, attr, value.strip() if isinstance(value, str) else value)

@app.route('/inventory/<int:item_id>/edit', methods=['GET', 'POST'])
@roles_required('admin', 'it_support')
def inventory_edit(item_id):
    item = db.get_or_404(InventoryItem, item_id)
    form = ItemForm(obj=item)
    if form.validate_on_submit():
        old_ctrl = item.ctrl_no
        if item.ctrl_no != form.ctrl_no.data.strip() and InventoryItem.query.filter_by(ctrl_no=form.ctrl_no.data.strip()).first():
            flash('That control number already exists.', 'danger')
        else:
            assign_item_form(item, form); db.session.commit()
            log_action('ITEM_UPDATED', f'{old_ctrl}: {item.item}')
            flash('Inventory item updated.', 'success')
            return redirect(url_for('inventory'))
    return render_template('item_form.html', form=form, title=f'Edit {item.ctrl_no}')

@app.route('/inventory/<int:item_id>/delete', methods=['POST'])
@roles_required('admin')
def inventory_delete(item_id):
    item = db.get_or_404(InventoryItem, item_id)
    if item.service_requests:
        flash('Cannot delete an item with request history. Mark it Disposed instead.', 'warning')
    else:
        log_action('ITEM_DELETED', f'{item.ctrl_no}: {item.item}')
        db.session.delete(item); db.session.commit(); flash('Inventory item deleted.', 'success')
    return redirect(url_for('inventory'))

@app.route('/requests')
@login_required
def requests_list():
    q = request.args.get('q', '').strip()
    if current_user.role == 'officer':
        query = ServiceRequest.query.filter_by(requester_id=current_user.id)
    else:
        query = ServiceRequest.query
    if q:
        like = f'%{q}%'
        query = query.filter(or_(ServiceRequest.request_no.ilike(like), ServiceRequest.description.ilike(like), ServiceRequest.item_description.ilike(like), ServiceRequest.status.ilike(like)))
    requests_list = query.order_by(ServiceRequest.created_at.desc()).all()
    return render_template('requests.html', requests=requests_list, q=q)

@app.route('/requests/new', methods=['GET', 'POST'])
@roles_required('officer')
def request_new():
    form = RequestForm()
    items = InventoryItem.query.filter_by(status='Available').order_by(InventoryItem.item.asc()).all()
    form.item_id.choices = [('', '— Choose an available item (optional) —')] + [(str(i.id), f'{i.ctrl_no} · {i.item} ({i.location or "No location"})') for i in items]
    if form.validate_on_submit():
        item = db.session.get(InventoryItem, int(form.item_id.data)) if form.item_id.data else None
        if item and item.status != 'Available':
            flash('That item is no longer available. Please choose another.', 'danger')
        elif not item and not form.item_description.data.strip():
            flash('Choose an inventory item or enter an item/equipment description.', 'danger')
        elif form.needed_from.data and form.needed_until.data and form.needed_until.data < form.needed_from.data:
            flash('Return date cannot be earlier than the start date.', 'danger')
        else:
            request_no = f'BJR-{datetime.utcnow():%y%m%d}-{os.urandom(3).hex().upper()}'
            rec = ServiceRequest(request_no=request_no, request_type=form.request_type.data, requester_id=current_user.id,
                item_id=item.id if item else None, item_description=(form.item_description.data or (item.item if item else '')).strip(),
                description=form.description.data.strip(), needed_from=form.needed_from.data, needed_until=form.needed_until.data, status='Pending')
            db.session.add(rec); db.session.commit(); log_action('REQUEST_SUBMITTED', f'{request_no} by {current_user.username}')
            flash(f'Request submitted. Reference: {request_no}', 'success')
            return redirect(url_for('requests_list'))
    return render_template('request_form.html', form=form)

@app.route('/requests/<int:request_id>')
@login_required
def request_detail(request_id):
    rec = db.get_or_404(ServiceRequest, request_id)
    if current_user.role == 'officer' and rec.requester_id != current_user.id: abort(403)
    form = UpdateRequestForm()
    form.status.data = rec.status
    form.staff_notes.data = rec.staff_notes
    return render_template('request_detail.html', rec=rec, form=form)

@app.route('/requests/<int:request_id>/update', methods=['POST'])
@roles_required('admin', 'it_support')
def request_update(request_id):
    rec = db.get_or_404(ServiceRequest, request_id)
    form = UpdateRequestForm()
    if form.validate_on_submit():
        new_status = form.status.data
        if rec.request_type == 'Borrowing' and new_status == 'Borrowed' and rec.item and rec.item.status not in ('Available', 'Borrowed'):
            flash('This item is not available to borrow.', 'danger')
            return redirect(url_for('request_detail', request_id=rec.id))
        rec.status = new_status
        rec.staff_notes = form.staff_notes.data.strip()
        rec.decision_by = current_user.id
        if rec.item:
            if rec.request_type == 'Borrowing':
                if new_status == 'Borrowed': rec.item.status = 'Borrowed'; rec.item.assigned_to = rec.requester.full_name
                elif new_status in ('Completed', 'Cancelled', 'Rejected') and rec.item.status == 'Borrowed': rec.item.status = 'Available'; rec.item.assigned_to = ''
            elif rec.request_type == 'Repair':
                if new_status in ('Approved', 'In Progress'): rec.item.status = 'Under Repair'
                elif new_status == 'Ready for Pickup': rec.item.status = 'Available'
                elif new_status == 'Completed' and rec.item.status == 'Under Repair': rec.item.status = 'Available'
                elif new_status == 'Rejected' and rec.item.status == 'Under Repair': rec.item.status = 'Available'
        db.session.commit(); log_action('REQUEST_UPDATED', f'{rec.request_no} → {new_status}')
        flash('Request updated.', 'success')
    else:
        flash('Please check the submitted values.', 'danger')
    return redirect(url_for('request_detail', request_id=rec.id))

@app.route('/users')
@roles_required('admin')
def users():
    return render_template('users.html', users=User.query.order_by(User.created_at.desc()).all())

@app.route('/users/new', methods=['GET', 'POST'])
@roles_required('admin')
def user_new():
    form = UserForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = (form.email.data or '').strip() or None
        if User.query.filter(func.lower(User.username) == username.lower()).first():
            flash('Username already exists.', 'danger')
        elif email and User.query.filter(func.lower(User.email) == email.lower()).first():
            flash('Email already exists.', 'danger')
        elif not form.password.data:
            flash('Set a temporary password of at least 8 characters.', 'danger')
        else:
            user = User(full_name=form.full_name.data.strip(), username=username, email=email, department=(form.department.data or '').strip(), role=form.role.data)
            user.set_password(form.password.data)
            db.session.add(user); db.session.commit(); log_action('USER_CREATED', f'{username} ({user.role})')
            flash('User created. Share credentials securely and ask the user to change their password.', 'success')
            return redirect(url_for('users'))
    return render_template('user_form.html', form=form, title='Create user')

@app.route('/users/<int:user_id>/toggle', methods=['POST'])
@roles_required('admin')
def user_toggle(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('You cannot disable your own account.', 'warning')
    elif user.role == 'admin' and User.query.filter_by(role='admin', active=True).count() <= 1 and user.active:
        flash('At least one active administrator must remain.', 'warning')
    else:
        user.active = not user.active; db.session.commit(); log_action('USER_STATUS', f'{user.username}: active={user.active}')
        flash('Account status updated.', 'success')
    return redirect(url_for('users'))

@app.route('/reports')
@roles_required('admin', 'it_support')
def reports():
    by_status = db.session.query(InventoryItem.status, func.count(InventoryItem.id)).group_by(InventoryItem.status).all()
    by_type = db.session.query(ServiceRequest.request_type, func.count(ServiceRequest.id)).group_by(ServiceRequest.request_type).all()
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(30).all()
    return render_template('reports.html', by_status=by_status, by_type=by_type, logs=logs)

@app.errorhandler(403)
def forbidden(_): return render_template('error.html', code=403, message='You do not have permission to access this page.'), 403
@app.errorhandler(404)
def not_found(_): return render_template('error.html', code=404, message='The requested page or record was not found.'), 404

with app.app_context():
    db.create_all()
    # Bootstrap the first admin only when the database has no users. Change these credentials immediately.
    if User.query.count() == 0:
        admin = User(full_name=os.environ.get('INITIAL_ADMIN_NAME', 'Benjor System Administrator'), username=os.environ.get('INITIAL_ADMIN_USERNAME', 'admin'), email=os.environ.get('INITIAL_ADMIN_EMAIL') or None, role='admin', department='IT')
        admin.set_password(os.environ.get('INITIAL_ADMIN_PASSWORD', 'ChangeMe123!'))
        db.session.add(admin); db.session.commit()

if __name__ == '__main__':
    app.run(host='172.17.0.12', port=int(os.environ.get('PORT', '5000')), debug=os.environ.get('FLASK_DEBUG') == '1')
