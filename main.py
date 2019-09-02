import sys
import asyncio

import msgpack
import websockets
from asyncqt import QEventLoop, asyncSlot, asyncClose
from PySide2.QtWidgets import QApplication, QWidget, QLineEdit, QTextEdit, QPushButton, QVBoxLayout


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.default_uri = "ws://192.168.0.15"
        self.setLayout(QVBoxLayout())
        self.editUrl = QLineEdit(self.default_uri, self)
        self.layout().addWidget(self.editUrl)
        self.log_view = QTextEdit('', self)
        self.layout().addWidget(self.log_view)
        self.btn_connect = QPushButton('Connect', self)
        self.btn_connect.clicked.connect(self.on_btn_connect_clicked)
        self.layout().addWidget(self.btn_connect)
        self.btn_on = QPushButton('LED On', self)
        self.btn_on.clicked.connect(self.on_btn_on_clicked)
        self.layout().addWidget(self.btn_on)
        self.btn_off = QPushButton('LED Off', self)
        self.btn_off.clicked.connect(self.on_btn_off_clicked)
        self.layout().addWidget(self.btn_off)
        self.disconnect_event = asyncio.Event()
        self.connected = False
        self.send_queue = asyncio.Queue()

    @asyncClose
    async def closeEvent(self, event):
        self.disconnect_event.set()
        await asyncio.sleep(1)
        self.log("Shutting Down")

    def log(self, msg):
        print(msg)
        self.log_view.append(msg)

    @asyncSlot()
    async def on_btn_on_clicked(self):
        await self.send_queue.put({"LED": True})

    @asyncSlot()
    async def on_btn_off_clicked(self):
        await self.send_queue.put({"LED": False})

    @asyncSlot()
    async def on_btn_connect_clicked(self):
        if self.connected:
            self.disconnect_event.set()
        else:
            self.connected = True
            self.send_queue = asyncio.Queue()
            self.disconnect_event.clear()
            async with websockets.connect(self.editUrl.text()) as websocket:
                self.log("Connected")
                self.btn_connect.setText("Disconnect")
                done, pending = await asyncio.wait([asyncio.ensure_future(self.repeat_send(websocket)),
                                                    asyncio.ensure_future(self.repeat_recv(websocket)),
                                                    self.disconnect_event.wait()],
                                                   return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
            self.log("Disconnected")
            self.btn_connect.setText("Connect")
            self.connected = False

    async def repeat_send(self, websocket):
        try:
            while True:
                msg = await self.send_queue.get()
                self.log(f"Sending: {msg}")
                await websocket.send(msgpack.packb(msg))
        except (websockets.ConnectionClosedError, OSError, ConnectionResetError) as e:
            self.log(f"Connection lost with error: {e}")

    async def repeat_recv(self, websocket):
        count = 0
        try:
            async for received in websocket:
                count += 1
                if isinstance(received, bytes):
                    msg = f"Received {count}: {msgpack.unpackb(received, raw=False)}"
                else:
                    msg = f"Received {count}: {received}"
                self.log(msg)
        except (websockets.ConnectionClosedError, OSError, ConnectionResetError) as e:
            self.log(f"Connection lost with error: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    mainWindow = MainWindow()
    mainWindow.show()

    with loop:
        sys.exit(loop.run_forever())
