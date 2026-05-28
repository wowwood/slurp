🥤 Slurp
===

## Deployment

___

### CRI / Docker

Ready-to-use CRI builds are available in the Packages area of this repository.

You will need to make sure you have _at least_ the following running:

* Redis (with persistence!)
    * Persistence is not mandatory, but you'll lose all history every time you restart the instance.
* Web server (the default)
* Celery worker (cmd: `/app/deploy/cri/bin/start-celeryworker`)
* Celery Beat (cmd: `/app/deploy/cri/bin/start-celerybeat`)

An example docker-compose manifest is available in `/app/deploy/cri` - tweak to your requirements.

To call the individual container functions yourself, do something like the following:
`[podman|docker] run -d --restart=always -v config.toml:/app/config.toml --name slurp wowwood/slurp`

### Directly (systemd / Gunicorn)

> [!WARNING]
> This is not a supported configuration.
> You still need a Redis instance somewhere for the job queue.

First, ensure that you have downloaded _slurp_ to a directory on your system (e.g `/usr/local/slurp`).

Next, make sure all dependencies are available (see "Development" below), and that uv has configured a venv at
`.venv`.
Also ensure that a valid configuration file is available at `config.toml` (see [Configuration](#Configuration)).

Copy the service file located at [deploy/systemd/slurp.service](deploy/systemd/slurp.service) to your
`/etc/systemd/system` directory.

Modify it to fit your requirements, do `systemctl daemon-reload`, then you should be able to issue
`systemctl start slurp` to get going.

You can either expose this instance directly, or reverse-proxy it with something like _Træfik_ or _Caddy_.

## Development

___

### Install dependencies:

- [Python 3](https://www.python.org/)
- [Javascript runtime](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

For the YT-DLP fetcher:

- ffmpeg
- (optionally) a [compatible JavaScript runtime](https://github.com/yt-dlp/yt-dlp/wiki/EJS)

> [!TIP]
> If you have [Nix](https://nixos.org/) installed, you can simply run `nix-shell` in the project directory, to get a
> shell with all dependencies available.

> [!TIP]
> If you have [Nix](https://nixos.org/) *and* [direnv](https://direnv.net/) installed, you can simply run `direnv allow`
> to automatically make all dependencies available in your shell whenever you change into this directory.

### Install Python dependencies:

```bash
$ uv sync --locked --all-extras
```

### Run the development server:

> [!CAUTION]
> Do not expose the development server in production!

```bash
$ uv run flask --app slurp run --debug --host=0.0.0.0
```

_The host flag exposes it on the local interface, not just on the machine itself_

#### Run the Celery Worker

You'll also need the job runner. To run that:

```bash
celery -A slurp.make_celery:celery worker
```

# Configuration

___

Copy the `config.template.toml` file to `config.toml` and edit as you wish.

Note: you must have at least one fetcher enabled, or you'll get an error on startup.

### Available Fetchers

The currently available fetchers are as follows:

#### YT-DLP

The YT-DLP fetcher reliably grabs media directly from YouTube (and YouTube alone) to your target.
It does not _require_ any extra setup, but you'll receive a warning if a JavaScript runtime isn't available.

The compatible runtimes are listed here: https://github.com/yt-dlp/yt-dlp/wiki/EJS

If `deno` is available on the system path, it should be detected automatically. Otherwise, set the
`FETCHER_YTDLP_JS_RUNTIMES` flag with the path to the runtime binary, like
so:

```toml
FETCHER_YTDLP_JS_RUNTIMES = '{"node": {"path": "/usr/bin/node"}}'
```

##### get_iplayer

The _get\_iplayer_ fetcher grabs media in up to HD quality using an installed copy
of [get_iplayer](https://github.com/get-iplayer/get_iplayer/tree/master).
It's up to you to ensure `get_iplayer` is available on your system to be called by _Slurp_.

> [!IMPORTANT]
> This is quite a rudimentary fetcher, and may be replaced / removed at a later date.

#### Cobalt

The _Cobalt_ fetcher uses a [Cobalt API](https://github.com/imputnet/cobalt) instance to request a media stream from a
wide variety of sources, then grabs that and saves it to the target.

_Cobalt_ is significantly more flexible thanks to its extensive supported sources list, but requires some setup.

##### Getting a Backing Cobalt API Server

You can either use any _Cobalt_ API server which you have API access too (likely with an API key!), or you can spin one
up alongside your _slurp_ instance.

To run a _Cobalt_ instance, please see
the [Cobalt Documentation](https://github.com/imputnet/cobalt/blob/main/docs/run-an-instance.md).

Note that it's easiest to run _Cobalt_ in a Docker or Podman container, then bind it to a localhost-only address (using
a flag like `-p 127.0.0.1:9000:9000/tcp`).

Once you've done this, configure _Slurp_ to dial this _Cobalt_ instance:

```toml
FETCHER_COBALT_ENABLED = true
FETCHER_COBALT_URL = "http://127.0.0.1:9000/"
```

> [!WARNING]
> If you're running Cobalt locally, **please make sure it is correctly isolated from the internet!**
> You don't want external parties thrashing your download server.

For extra security, it is strongly recommended to configure _Cobalt_ to require an API key - see
the [Cobalt Documentation](https://github.com/imputnet/cobalt/blob/main/docs/protect-an-instance.md#configure-api-keys)
for details.

You will likely want the key for _Slurp_ to look something like this in _Cobalt_'s `keys.json`:

```json
{
  "random-uuidv4-goes-here": {
    "limit": "unlimited",
    "ips": [
      "127.0.0.0/8"
    ],
    "userAgents": [
      "*slurp*"
    ]
  }
}
```

Then simply configure _Slurp_ to use the API key for authentication:

```toml
FETCHER_COBALT_KEY = "random-uuidv4-goes-here"
```