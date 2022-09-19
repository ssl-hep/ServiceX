from typing import Optional

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, Email

from servicex.models import UserModel


class ProfileForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(0, 120)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    institution = StringField('Institution', validators=[DataRequired()])
    experiment = SelectField('Experiment', validators=[DataRequired()],
                             choices=[("ATLAS", "ATLAS"), ("CMS", "CMS")],
                             default="ATLAS")
    submit = SubmitField('Save Profile')

    def __init__(self, user: Optional[UserModel] = None):
        super().__init__()
        if user:
            self.name.data = user.name
            self.email.data = user.email
            self.institution.data = user.institution
            self.experiment.data = user.experiment
