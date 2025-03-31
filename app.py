import os
import subprocess
import json
from datetime import datetime
from enum import Enum
from flask import Flask, request, render_template, stream_template
from flask_wtf import FlaskForm
from wtforms import URLField, StringField, SelectField
from wtforms.validators import URL, DataRequired, AnyOf

app = Flask(__name__)
app.config.from_prefixed_env(prefix='YDP')
app.config['OUTPUTS'] = app.config['OUTPUTS'].split(os.pathsep)

class Format(Enum):
    VIDEO_AUDIO = "Video+Audio"
   # VIDEO_ONLY  = "Video Only" - not needed tbh
    AUDIO_ONLY  = "Audio Only"

    @property
    def ytdlp(self):
        match self:
            # pls add the other two
            case self.VIDEO_AUDIO:
                return 'bv*[vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b' 
                # force codec to h264 m4a/mp4
            case self.AUDIO_ONLY:
                return '-x'
            case _:
                raise ValueError("invalid format")

class DownloadForm(FlaskForm):
    url = URLField('url', validators=[DataRequired(), URL()])
    slug = StringField('slug', validators=[DataRequired()])
    format = SelectField('format', choices=[(v.name, v.value) for v in Format],
        validators=[DataRequired(), AnyOf([v.name for v in Format])])
    directory = SelectField('directory', validators=[DataRequired()])

    def args(self):
        return ['-f', Format[self.format.data].ytdlp, "-o", f"{self.slug.data}.%(ext)s", self.url.data]

@app.get('/')
def index():
    form = DownloadForm(request.args)
    form.directory.choices = app.config['OUTPUTS']
    if request.args:
        if form.validate():
            out = subprocess.run(['yt-dlp', '-J'] + form.args(), capture_output=True, encoding='UTF-8')
            out.check_returncode()
            data = json.loads(out.stdout)
            return render_template('preview.html', form=form, data=data,
                timestamp=datetime.fromtimestamp(data['timestamp']))
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
    def output():
        with subprocess.Popen(['yt-dlp'] + form.args(), cwd=form.directory.data,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='UTF-8') as ytdlp:
            for line in ytdlp.stdout:
                yield line
    return stream_template('download.html', output=output())
