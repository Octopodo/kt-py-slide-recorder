import logging

from ui.app import App


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(name)s  %(levelname)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
