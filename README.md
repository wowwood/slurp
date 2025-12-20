ytdlpls
=======

Development
-----------

### Install dependencies:

- [Python 3](https://www.python.org/)
- [Javascript runtime](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [Poetry](https://python-poetry.org/docs/cli/#script-project)
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

Simply supply an overridden `config.toml` file.