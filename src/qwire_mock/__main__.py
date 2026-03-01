import argparse
import logging
import threading

import uvicorn

from qwire_mock import __version__
from qwire_mock.config import load_config


def main() -> None:
    config = load_config()
    server_config = config["server"]
    callback_port = int(server_config["callback_port"])
    order_port = int(server_config["order_port"])
    logging.basicConfig(level=logging.INFO, format=config["logging"]["format"])

    parser = argparse.ArgumentParser(description="QWire Mock v2 - Callback & Order API")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--host", default=server_config["host"], help="Bind host")
    parser.add_argument(
        "--service",
        choices=("callback", "order", "all"),
        default="all",
        help=f"Run callback ({callback_port}), order ({order_port}), or both",
    )
    args = parser.parse_args()

    if args.service == "all":
        from qwire_mock.callback_service import app as callback_app
        from qwire_mock.order_service import app as order_app

        def run_callback() -> None:
            uvicorn.run(callback_app, host=args.host, port=callback_port)

        def run_order() -> None:
            uvicorn.run(order_app, host=args.host, port=order_port)

        callback_thread = threading.Thread(target=run_callback, daemon=True)
        order_thread = threading.Thread(target=run_order, daemon=True)
        callback_thread.start()
        order_thread.start()
        logging.info("v2 callback server: http://%s:%s", args.host, callback_port)
        logging.info("v2 order server: http://%s:%s", args.host, order_port)
        callback_thread.join()
        order_thread.join()
    elif args.service == "callback":
        from qwire_mock.callback_service import app

        uvicorn.run(app, host=args.host, port=callback_port)
    else:
        from qwire_mock.order_service import app

        uvicorn.run(app, host=args.host, port=order_port)


if __name__ == "__main__":
    main()
