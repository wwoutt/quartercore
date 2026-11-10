# Starts quartercore-core: python3 -m quartercore.core [--port 27013] [--openlinkhub URL] [--standalone]
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later

import argparse
import signal
import sys
import threading

from . import hs80, inputs, k100, psu, xeneon
from .server import Core, serve
from .store import Store

DEFAULT_PORT = 27013


def main(argv=None):
    parser = argparse.ArgumentParser(prog="quartercore-core",
                                     description="Drives devices itself and passes the rest on to OpenLinkHub")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--openlinkhub", default="http://127.0.0.1:27003")
    parser.add_argument("--standalone", action="store_true",
                        help="take over every supported device, also when OpenLinkHub isn't running")
    args = parser.parse_args(argv)

    store = Store()

    def log(text):
        print(text, flush=True)

    core = Core(args.openlinkhub, lambda: psu.discover(store) + xeneon.discover(store) + hs80.discover(store) + k100.discover(store), args.standalone, log)
    server = serve(core, args.port)

    def shutdown(*_):
        log("stopping")
        core.stop()
        inputs.close_shared()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    threading.Thread(target=core.run, daemon=True).start()
    log("quartercore-core on http://127.0.0.1:%d, passing the rest on to %s" % (args.port, args.openlinkhub))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
