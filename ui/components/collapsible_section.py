import customtkinter as ctk


class CollapsibleSection(ctk.CTkFrame):
    """Clickable header that shows/hides a content_frame below it."""

    def __init__(self, parent, title: str, expanded: bool = True, **kw) -> None:
        super().__init__(parent, corner_radius=8, **kw)
        self._expanded = expanded
        self._title = title
        self._header = ctk.CTkButton(
            self,
            text=self._label(),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("gray82", "gray28"),
            command=self._toggle,
        )
        self._header.pack(fill="x", padx=2, pady=(4, 0))
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        if expanded:
            self.content_frame.pack(fill="x", padx=4, pady=(0, 6))

    def _label(self) -> str:
        arrow = "\u25bc" if self._expanded else "\u25b6"
        return f"{arrow}  {self._title}"

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._header.configure(text=self._label())
        if self._expanded:
            self.content_frame.pack(fill="x", padx=4, pady=(0, 6))
        else:
            self.content_frame.pack_forget()
