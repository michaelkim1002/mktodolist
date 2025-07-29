from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateField, PasswordField, TimeField
from wtforms.validators import DataRequired, URL, Email, Length, EqualTo, Optional
from wtforms.widgets import TextArea
from flask_ckeditor import CKEditorField

# WTForm for creating a blog post
class CreateTaskForm(FlaskForm):
    task = StringField("Task", validators=[DataRequired(message="Please enter a task.")], render_kw={"class": "form-control"})
    additional_info = StringField('Additional Information', widget=TextArea())
    due_date = DateField('Due Date', format='%Y-%m-%d', validators=[DataRequired(message="Please enter a valid date.")])
    due_time = TimeField("Due Time",format='%H:%M',validators=[Optional()],render_kw={"type": "time", "class": "form-control"}
    )
    submit = SubmitField("Add")


class RegisterForm(FlaskForm):
    username = StringField("Username",validators=[DataRequired(), Length(min=3, max=30)])
    email = StringField("Email", validators=[DataRequired(), Email(message="Please enter a valid email address.")])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), Length(min=6), EqualTo('password', message='Passwords must match.')])
    submit = SubmitField("Sign Up")

class NewPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(message="Please enter your email address.")])
    verification_code = StringField("Verification Code", validators=[DataRequired("Please enter the verification code")])
    new_password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField("Confirm Password", validators=[DataRequired(), Length(min=6), EqualTo('new_password', message='Passwords must match.')])
    submit = SubmitField("Reset Password")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(message="Please enter a valid email address.")])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign In")

class ContactForm(FlaskForm):
    subject = StringField("Subject", validators=[DataRequired(message="Please enter a subject for email")])
    message = StringField('message', validators=[DataRequired(message="Please enter a message for email")], widget=TextArea())
    submit = SubmitField("Send Email")




