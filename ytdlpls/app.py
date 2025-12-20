import os
import queue
import threading
from datetime import datetime
from enum import Enum

from flask import Flask, request, render_template, stream_template
from flask_wtf import FlaskForm
import tomllib
from wtforms import URLField, StringField, SelectField
from wtforms.validators import URL, DataRequired, AnyOf

from yt_dlp import YoutubeDL

app = Flask(__name__)
# app.config.from_prefixed_env(prefix='YDP')
app.config.from_file(os.path.join(os.getcwd(), "config.toml"), load=tomllib.load, text=False)
app.config['OUTPUTS'] = app.config.get('OUTPUTS', '').split(os.pathsep)

class Format(Enum):
    VIDEO_AUDIO = "Video+Audio"
   # VIDEO_ONLY  = "Video Only" - not needed tbh
    AUDIO_ONLY  = "Audio Only"

    @property
    def ytdl_config(self):
        match self:
            case self.VIDEO_AUDIO:
                return {
                    'format': 'bestvideo*+bestaudio/best',
                }
                # force codec to h264 m4a/mp4
                # fails if this format isn't available, fix later
                # return ['-f', 'bv*[vcodec^=avc]+ba[ext=m4a]/b[ext=mp4]/b']
            case self.AUDIO_ONLY:
                return {
                    'format': 'm4a/bestaudio/best',
                    'postprocessors': [{  # Extract audio using ffmpeg
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'm4a',
                    }]
                }
            case _:
                raise ValueError("invalid format")

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
            with YoutubeDL() as ydl:
                info = ydl.extract_info(form.url.data, download=False)

                # sanitize_info required to make serializable
                data = ydl.sanitize_info(info)
                return render_template('preview.html', form=form, data=data,
                    timestamp=datetime.fromtimestamp(data.get('timestamp', None)))
        for field in form:
            if field.errors:
                field.render_kw = dict(aria_invalid = 'true', aria_describedby = f'{field.id}-errors')
    return render_template('index.html', form=form)

class YtQueueLogger:
    """ YtQueueLogger provides a yt-dlp compatible logging interface that emits exclusively to a queue."""
    def __init__(self, q: queue.Queue):
        self.q = q
    def debug(self, msg):
        # As recommended by library documentation
        if msg.startswith('[debug] '):
            self.q.put(("debug", msg))
        else:
            self.info(msg)

    def info(self, msg):
        self.q.put(("info", msg))

    def warning(self, msg):
        self.q.put(("warn", msg))

    def error(self, msg):
        self.q.put(("error", msg))

@app.post('/download')
def download():
    form = DownloadForm()
    form.directory.choices = app.config['OUTPUTS']
    if not form.validate_on_submit():
        return form.errors

    q = queue.Queue()

    def yt_download():
        """
        Commence a download from Youtube.
        """
        opts = {
            'logger': YtQueueLogger(q),
            'no_warnings': True,
            'paths': {
                'home': form.directory.data,
                'temp': f"{form.directory.data}/temp",
            },
            # Note: This will break if you were to pass in multiple target URLs
            'outtmpl': f'{form.slug.data}.%(ext)s',
        } | Format[form.format.data].ytdl_config
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([form.url.data])
        except Exception as e:
            q.put(("error", f"download exception: {e}"))
        finally:
            # signals end of stream
            q.put(None)

    # We need to run the download on a thread so we can continue to execute our client response
    thread = threading.Thread(target=yt_download, daemon=True)
    thread.start()

    def output():
        while True:
            item = q.get()
            if item is None:
                break
            typ, payload = item
            line_fmt = ""
            match typ:
                case "info":
                    line_fmt = "color: blue"
                case "warn":
                    line_fmt = "color: orange"
                case "error":
                    line_fmt = "color: red"
            yield f"<span style='{line_fmt}'>{typ}</span>: {payload}"
        yield "☑️ Download complete\n"

    return stream_template('download.html', output=output())

def serve():
    app.run(host='0.0.0.0', port=8000, debug=False)
