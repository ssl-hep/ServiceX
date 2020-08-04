from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email


class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(0, 120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    institution = StringField('Institution', validators=[DataRequired()])
    experiment = SelectField('Experiment', validators=[DataRequired()],
                             choices=[("ATLAS", "ATLAS"), ("CMS", "CMS")],
                             default="ATLAS")
    submit = SubmitField('Save Profile')
