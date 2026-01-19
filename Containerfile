FROM python:3.14.2-slim-trixie AS app-build

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential curl libpq-dev \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${APP_GID}" python \
  && useradd --create-home --no-log-init -u "${APP_UID}" -g "${APP_GID}" python \
  && chown python:python -R /app

USER python

ENV PYTHONUNBUFFERED="true" \
    PYTHONPATH="." \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/tmp/poetry_cache' \
    POETRY_VERSION=2.2.1 \
    PATH="${PATH}:/home/python/.local/bin" \
    USER="python"

RUN curl -sSL https://install.python-poetry.org | python3 -

COPY --chown=python:python pyproject.toml poetry.toml poetry.lock ./
COPY --chown=python:python bin/ ./bin

RUN chmod 0755 bin/* && bin/install-deps

CMD ["bash"]

###############################################################################

FROM python:3.14.2-slim-trixie

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000

# Get main project dependencies, then add the get-iplayer repository and download
# FIXME This is supremely sucky (get-iplayer has a stupidly long list of dependencies) and should be replaced with a manual build stage
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl libpq-dev gpg \
  && echo 'deb http://download.opensuse.org/repositories/home:/m-grant-prg/Debian_13/ /' | tee /etc/apt/sources.list.d/home:m-grant-prg.list \
  && curl -fsSL https://download.opensuse.org/repositories/home:m-grant-prg/Debian_13/Release.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/home_m-grant-prg.gpg > /dev/null \
  && apt-get update && apt-get install -y --no-install-recommends get-iplayer \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${APP_GID}" python \
  && useradd --create-home --no-log-init -u "${APP_UID}" -g "${APP_GID}" python \
  && chown python:python -R /app

USER python

ARG FLASK_DEBUG="false"
ENV FLASK_DEBUG="${FLASK_DEBUG}" \
    FLASK_APP="slurp" \
    FLASK_SKIP_DOTENV="true" \
    PYTHONUNBUFFERED="true" \
    PYTHONPATH="." \
    PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PATH="${PATH}:/home/python/.local/bin" \
    USER="python"

COPY --chown=python:python --from=app-build /home/python/.local /home/python/.local
COPY --chown=python:python . .

# Static file compilation step - not presently used.
#RUN if [ "${FLASK_DEBUG}" != "true" ]; then \
#  ln -s /public /app/public && SECRET_KEY=dummy flask digest compile && rm -rf /app/public; fi

ENTRYPOINT ["/app/deploy/cri/bin/entrypoint-web"]

EXPOSE 8000

CMD ["gunicorn", "-c", "python:config.gunicorn", "slurp:create_app()"]