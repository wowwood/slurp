ytdlpls
=======

Development
-----------

### Install dependencies:

- [Python 3](https://www.python.org/)
- [Javascript runtime](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [Poetry](https://python-poetry.org/docs/cli/#script-project)

For the YT-DLP fetcher:
- ffmpeg

> [!TIP]
> If you have [Nix](https://nixos.org/) installed, you can simply run `nix-shell` in the project directory, to get a shell with all dependencies available.

> [!TIP]
> If you have [Nix](https://nixos.org/) *and* [direnv](https://direnv.net/) installed, you can simply run `direnv allow` to automatically make all dependencies available in your shell whenever you change into this directory.

### Install Python dependencies:

```bash
$ poetry install --no-root
```

### Run the development server:

> [!CAUTION]
> Do not expose the development server in production!

```bash
$ poetry run flask run --debug --host=0.0.0.0
```
_The host flag exposes it on the local interface, not just on the machine itself_

### Configuration

Copy the `config.template.toml` file to `config.toml` and edit as you wish.

Note: you must have at least one fetcher enabled, or you'll get an error on startup.

### Available Fetchers

The currently available fetchers are as follows:

#### YT-DLP
The YT-DLP fetcher reliably grabs media directly from Youtube (and Youtube alone) to your target. 
It does not require any extra setup.

#### Cobalt
The _Cobalt_ fetcher uses a [Cobalt API](https://github.com/imputnet/cobalt) instance to request a media stream from a 
wide variety of sources, then grabs that and saves it to the target.

_Cobalt_ is significantly more flexible thanks to its extensive supported sources list, but requires some setup.

##### Getting a Backing Cobalt API Server

You can either use any _Cobalt_ API server which you have API access too (likely with an API key!), or you can spin one
up alongside your _slurp_ instance.

To run a _Cobalt_ instance, please see the [Cobalt Documentation](https://github.com/imputnet/cobalt/blob/main/docs/run-an-instance.md).

Note that it's easiest to run _Cobalt_ in a Docker or Podman container, then bind it to a localhost-only address (using a flag like `-p 127.0.0.1:9000:9000/tcp`).

Once you've done this, configure _Slurp_ to dial this _Cobalt_ instance:

```toml
FETCHER_COBALT_ENABLED = true
FETCHER_COBALT_URL = "http://127.0.0.1:9000/"
```

>[!WARNING]
> If you're running Cobalt locally, **please make sure it is correctly isolated from the internet!** 
> You don't want external parties thrashing your download server. 
> For an extra layer of security, consider using API keys as well.