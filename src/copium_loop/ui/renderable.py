from rich.style import Style
from rich.text import Text


class TailRenderable:
    """A custom Rich renderable that handles height-constrained rendering (clipping from the top)."""

    def __init__(self, buffer: list[str], status: str):
        self.buffer = buffer
        self.status = status

    def __rich_console__(self, console, options):
        # Use provided height/width or console defaults
        height = (
            options.max_height if options.max_height is not None else console.height
        )
        width = options.max_width if options.max_width is not None else console.width

        rendered_lines = []

        # Iterate backwards through the buffer to find the lines that fit from the bottom
        for i, line in enumerate(reversed(self.buffer)):
            # distance_from_end: 0 is newest
            distance_from_end = i

            if distance_from_end == 0:
                style = Style(color="#FFFFFF", bold=True)
                prefix = "> "
            elif distance_from_end < 5:
                # Very recent lines: Neon Green
                style = Style(color="#00FF41")
                prefix = "  "
            elif distance_from_end < 10:
                # Recent lines: Dark Green
                style = Style(color="#008F11")
                prefix = "  "
            else:
                # Older: Fade to Grey/Black
                style = Style(color="#333333")
                prefix = "  "

            text = Text(f"{prefix}{line}", style=style)
            # Wrap the text to the available width
            # This returns a list of Text objects, one for each console line
            lines = text.wrap(console, width)

            # Since we are going backwards, we want to add these lines to the START
            # of our rendered_lines list. The wrapped lines for THIS buffer line
            # should stay in their original relative order.
            for wrapped_line in reversed(lines):
                rendered_lines.insert(0, wrapped_line)
                if len(rendered_lines) >= height:
                    break

            if len(rendered_lines) >= height:
                break

        yield from rendered_lines
