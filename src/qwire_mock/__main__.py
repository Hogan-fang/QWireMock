"""Entry point: python -m qwire_mock runs callback (8000) and order (9000) services."""

import argparse
import logging
import threading

import uvicorn

from qwire_mock import __version__

CALLBACK_PORT = 8000
ORDER_PORT = 9000


def main() -> None:
    log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    log_datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(
        level=logging.INFO,
        format=log_fmt,
        datefmt=log_datefmt,
    )
    file_handler = logging.FileHandler("callback.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_fmt, datefmt=log_datefmt))
    logging.getLogger().addHandler(file_handler)

    order_file_handler = logging.FileHandler("order.log", encoding="utf-8")
    order_file_handler.setLevel(logging.INFO)
    order_file_handler.setFormatter(logging.Formatter(log_fmt, datefmt=log_datefmt))
    logging.getLogger("qwire_mock.order_service").addHandler(order_file_handler)

    parser = argparse.ArgumentParser(description="QWire Mock - Callback & Order API")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument(
        "--service",
        choices=("callback", "order", "all"),
        default="all",
        help="Run callback (8000), order (9000), or both (default)",
    )
    args = parser.parse_args()

    if args.service == "all":
        from qwire_mock.callback import app as callback_app
        from qwire_mock.order_service import app as order_app

        def run_callback() -> None:
            uvicorn.run(callback_app, host=args.host, port=CALLBACK_PORT)

        def run_order() -> None:
            uvicorn.run(order_app, host=args.host, port=ORDER_PORT)

        t1 = threading.Thread(target=run_callback, daemon=True)
        t2 = threading.Thread(target=run_order, daemon=True)
        t1.start()
        t2.start()
        logging.info("Callback server http://%s:%s", args.host, CALLBACK_PORT)
        logging.info("Order server http://%s:%s", args.host, ORDER_PORT)
        t1.join()
        t2.join()
    elif args.service == "callback":
        from qwire_mock.callback import app

        uvicorn.run(app, host=args.host, port=CALLBACK_PORT)
    else:
        from qwire_mock.order_service import app

        uvicorn.run(app, host=args.host, port=ORDER_PORT)


if __name__ == "__main__":
    main()
