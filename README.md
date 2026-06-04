<h1 align="center">🥤 Slurp</h1>
<p align="center"><b>A web media ingest utility, built with broadcast environments in mind.</b></p>

## What is Slurp?

_Slurp_ is your media organization's gateway for fetching web audio and video, and getting it into your existing
production ingest workflows.

At its core, it simply gets the media from a given URL, then outputs it into a folder along with a chosen filename.
The power is that you can then automate into your existing workflows, such
as [Telestream Vantage](https://www.telestream.com/vantage/), to produce a seamless experience for your team.

Thanks to its queue-based architecture, _Slurp_ can scale from small, infrequently-used deployments, to enormous scale
with multiple downloads simultaneously being executed.

_Slurp_ is built with international broadcast and MCR teams in mind - all times are in UTC, and there's a rapidly
growing REST API that you can use for integration into your own systems to query state, enqueue new jobs, and more.

## Deployment

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

#### Scaling

> [!NOTE]
> You probably don't need to worry about scaling Slurp - one worker can handle a decent amount of workload.

If you want to scale _Slurp_ to handle more load, you can run as many instances of the web server and worker process as
you'd like.

What you likely want to do is increase the number of celery workers so you can process more videos simultaneously.

**Do not horizontally scale the _Celery Beat_ container.** Your solution **must** ensure that only one _Beat_ instance
is running at a time.

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
celery -A slurp.make_celery:celery worker -Q celery,fetch
```

You might want to run separate celery and fetch workers so you don't end up with a blocked queue (which can stop new
tasks from being created over the REST API).
To do that, just run two Celery worker instances: one with `-Q celery` and one with `-Q fetch`.

### Notes on Developing Slurp

The app stores times in `UTC` - remember to convert to local timezones where required (or don't, I'm not your mom)

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

## Sponsors

In the interest of transparency, _Slurp_ is made possible thanks to funding from CBS News.

<img src="docs/static/img/CBS_News_logo_(2020).svg" width="256"></img>

## License

Slurp is licensed under the terms of the [European Union Public License v1.2](LICENSE.md). This means that use for
commercial purposes is permitted, but please read the license (and take legal advice!) for more information.