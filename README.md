# Run

```sh
uv run dndyo
```

# Manual TUI

Start the API server first in another terminal:

```sh
uv run dndyo
```

Then run the TUI (it streams `/ai` responses using SSE):

```sh
uv run dndyo-tui
```

# Test

```sh
uv run pytest
```
