import os

from flask import Flask, request, render_template, stream_template
from flask_wtf import FlaskForm
import tomllib

from wtforms import URLField, StringField, SelectField
from wtforms.validators import URL, DataRequired, AnyOf

from slurp.fetchers.types import Format
from slurp.fetchers import determine_fetcher
from slurp.helpers import format_duration

app = Flask(__name__)
# app.config.from_prefixed_env(prefix='YDP')
app.config.from_file(os.path.join(os.getcwd(), "config.toml"), load=tomllib.load, text=False)
app.config['OUTPUTS'] = app.config.get('OUTPUTS', '').split(os.pathsep)

app.jinja_env.filters['duration'] = format_duration


class DownloadForm(FlaskForm):
    url = URLField('url', validators=[DataRequired(), URL()])
    slug = StringField('slug', validators=[DataRequired()])
    format = SelectField('format', choices=[(v.name, v.value) for v in Format],
                         validators=[DataRequired(), AnyOf([v.name for v in Format])])
    directory = SelectField('directory', validators=[DataRequired()])

@app.get('/')
def index():
    form = DownloadForm(request.args)
    form.directory.choices = app.config['OUTPUTS']
    if request.args:
        if form.validate():
            try:
                fetcher = determine_fetcher(form.url.data)
            except ValueError as e:
                return str(e), 400
            data = fetcher.get_metadata(form.url.data)
            return render_template('preview.html', form=form, metadata=data, fetcher=fetcher.name)

        for field in form:
            if field.errors:
                field.render_kw = dict(aria_invalid = 'true', aria_describedby = f'{field.id}-errors')
    return render_template('index.html', form=form)

@app.post('/download')
def download():
    form = DownloadForm()
    form.directory.choices = app.config['OUTPUTS']
    if not form.validate_on_submit():
        return form.errors

    return stream_template('download.html', output=get_media(form.url.data, Format[form.format.data], form.directory.data, form.slug.data))

def serve():
    app.run(host='0.0.0.0', port=8000, debug=False)
