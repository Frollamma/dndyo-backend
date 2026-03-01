# Run

Run the server

```sh
uv run dndyo
```

# Features

- Generates images automatically based on game descripiton
- Uses mistral


# TUI

If you want, you can run our TUI as client.

Start the API server first in a terminal:

```sh
uv run dndyo
```

Then run the TUI in another terminal

```sh
uv run dndyo-tui
```

Use `/help` and you will see a list of commands. Example:

```sh
you> Dev: hi
ai> How can I assit you in the game?
you> Dev: create an enemy named HellFlexer and make it flex
```

# Test

```sh
uv run pytest
```
