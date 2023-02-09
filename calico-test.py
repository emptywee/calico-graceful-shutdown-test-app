import select
import signal
import socket
import time
from datetime import datetime
from queue import Queue
import logging
import threading

SLEEP_TIME = 20.0
response = """HTTP/1.1 200 OK
Server: my-socket-server/0.0.1
Date: %DATE%
Last-Modified: %DATE%
Content-Type: text/plain; charset=utf8
Content-Length: 9

HEALTH OK"""

response_in_flight = """HTTP/1.1 200 OK
Server: my-socket-server/0.0.1
Date: %DATE%
Last-Modified: %DATE%
Content-Type: text/plain; charset=utf8
Content-Length: 9

IN-FLIGHT"""

abort = False
shutting_down = False
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

# add ch to logger
LOGGER.addHandler(ch)


def set_abort():
    global abort
    abort = True
    LOGGER.debug(f"Set abort to true: {abort}")


def signal_handler(_signal, _frame):
    global shutting_down
    if not shutting_down:
        LOGGER.debug(f"Sleeping a bit ({SLEEP_TIME} seconds) before setting abort -> True")
        timer = threading.Timer(SLEEP_TIME, set_abort)
        timer.start()
        shutting_down = True
    else:
        LOGGER.debug(f"We're already shutting down, please, be patient...")


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def make_response(data: bytes):
    dt = datetime.now()
    # Mon, 19 Dec 2022 18:10:57 GMT
    dt_str = dt.strftime("%a, %-d %b %Y %H:%M:%S GMT")
    if data and isinstance(data, bytes) and "inflight" in data.decode():
        return response_in_flight.replace('%DATE%', dt_str)
    return response.replace('%DATE%', dt_str)


def server_program():
    host = '0.0.0.0'
    port = 8080

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(0)
    server.bind((host, port))
    server.listen(5)
    inputs = [server]
    outputs = []
    message_queues = {}
    LOGGER.info(f"Listening on {(host, port)}")
    while inputs and not abort:
        readable, writable, exceptional = select.select(inputs, outputs, inputs, 2)
        for s in readable:
            if s is server:
                connection, client_address = s.accept()
                connection.setblocking(0)
                inputs.append(connection)
                LOGGER.debug(f"Accepted connection: {connection}")
                message_queues[connection] = Queue()
            else:
                data = s.recv(1024)
                if data:
                    LOGGER.debug(f"Received data from a client: {data}")
                    message_queues[s].put(make_response(data).encode())
                    if s not in outputs:
                        outputs.append(s)
                else:
                    if s in outputs:
                        outputs.remove(s)
                    inputs.remove(s)
                    s.close()
                    del message_queues[s]

        for s in writable:
            try:
                if message_queues[s] and message_queues[s].empty():
                    outputs.remove(s)
                else:
                    next_msg = message_queues[s].get_nowait()
                    if isinstance(next_msg, bytes) and "IN-FLIGHT" in next_msg.decode():
                        LOGGER.debug("Simulating in-flight request: sleeping 10 seconds "
                                     "before sending response...")
                        time.sleep(10)
                    s.send(next_msg)
            except KeyError:
                try:
                    outputs.remove(s)
                except Exception:
                    pass

        for s in exceptional:
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()
            del message_queues[s]
    LOGGER.info("Gracefully shutting down. Closing sockets...")
    server.close()
    LOGGER.info("Done.")


if __name__ == '__main__':
    server_program()
