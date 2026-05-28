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
    UV_NO_DEV=1 \
    PATH="${PATH}:/app/.venv/bin" \
    USER="python"

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /bin/uv

COPY --chown=python:python pyproject.toml uv.lock ./
COPY --chown=python:python . .

RUN uv sync --no-dev --locked

CMD ["bash"]

###############################################################################

FROM python:3.14.2-slim-trixie

WORKDIR /app

ARG APP_UID=1000
ARG APP_GID=1000

# Get main project dependencies, then add the get-iplayer repository and download
# FIXME This is supremely sucky (get-iplayer has a stupidly long list of dependencies) and should be replaced with a manual build stage
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl libpq-dev gpg nodejs \
  && echo 'deb https://download.opensuse.org/repositories/home:/m-grant-prg/Debian_13/ /' | tee /etc/apt/sources.list.d/home:m-grant-prg.list \
  && curl -fsSL https://download.opensuse.org/repositories/home:m-grant-prg/Debian_13/Release.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/home_m-grant-prg.gpg > /dev/null \
  && apt-get update && apt-get install -y --no-install-recommends get-iplayer \
  && rm -rf /var/lib/apt/lists/* /usr/share/doc /usr/share/man \
  && apt-get clean \
  && groupadd -g "${APP_GID}" python \
  && useradd --create-home --no-log-init -u "${APP_UID}" -g "${APP_GID}" python \
  && mkdir /data \
  && chown python:python -R /app /data

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
    PATH="${PATH}:/app/.venv/bin" \
    USER="python" \
    SLURP_FETCHER_YTDLP_JS_RUNTIMES="{'node': {'path': '/usr/bin/node'}}"

COPY --chown=python:python --from=app-build /app/.venv /app/.venv
COPY --chown=python:python . .

# Static file compilation step - not presently used.
#RUN if [ "${FLASK_DEBUG}" != "true" ]; then \
#  ln -s /public /app/public && SECRET_KEY=dummy flask digest compile && rm -rf /app/public; fi

ENTRYPOINT ["/app/deploy/cri/bin/entrypoint"]

EXPOSE 8000

CMD ["/app/deploy/cri/bin/start-web"]