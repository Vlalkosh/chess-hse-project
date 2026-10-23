"""Themes are color dictionaries independent of the chess rules."""


THEMES = {
    "Classic": {
        "bg": "#f3eee7", "card": "#fffaf3", "text": "#302b26", "muted": "#786e62",
        "accent": "#756148", "accent_text": "#ffffff", "accent_hover": "#5c4935",
        "button": "#e8dfd2", "button_hover": "#ddd0bf", "border": "#8b6946",
        "light": "#f2dfbd", "dark": "#aa7b50", "selected": "#edc26c",
        "last": "#c9bb7a", "check": "#da8c78", "dot": "#4b5938",
        "white_piece": "#fff9e7", "black_piece": "#28221f", "pieces": "chessnut",
    },
    "Night": {
        "bg": "#161c26", "card": "#202936", "text": "#e6edf6", "muted": "#a1b0c1",
        "accent": "#6fb8a4", "accent_text": "#0b2720", "accent_hover": "#91ccba",
        "button": "#303d4e", "button_hover": "#3a4b61", "border": "#61788c",
        "light": "#8795a2", "dark": "#3e5364", "selected": "#b5a47c",
        "last": "#5d8a87", "check": "#b56e75", "dot": "#e2c77c",
        "white_piece": "#fff9e7", "black_piece": "#17202e", "pieces": "chessnut",
    },
    "Halloween": {
        "bg": "#17121f", "card": "#271e30", "text": "#f6e9dc", "muted": "#c1a9c9",
        "accent": "#ed994c", "accent_text": "#241321", "accent_hover": "#ffb369",
        "button": "#493044", "button_hover": "#62404e", "border": "#795567",
        "light": "#bd957e", "dark": "#655570", "selected": "#e6ac58",
        "last": "#9f8650", "check": "#bc627d", "dot": "#ffcc7d",
        "white_piece": "#fff3dc", "black_piece": "#392526", "pieces": "skulls",
    },
}

DEFAULT_THEME = "Classic"


def recolor_widgets(widget, old_theme, new_theme):
    """Replace old theme colors in a widget and recursively in its children.

    Only change supported color options that match an old theme value.
    The caller configures ttk styles separately.
    """
    replacements = {}
    for key, old_color in old_theme.items():
        if old_color.startswith("#"):
            replacements[old_color] = new_theme[key]
    options = widget.keys()
    for option in ("background", "foreground", "selectbackground", "selectforeground",
                   "activebackground", "activeforeground", "highlightbackground"):
        if option in options:
            old_color = str(widget.cget(option))
            if old_color in replacements:
                widget.configure(**{option: replacements[old_color]})
    for child in widget.winfo_children():
        recolor_widgets(child, old_theme, new_theme)
