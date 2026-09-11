"""
Desktop client, mirroring the Android app's guided-capture flow.
Network calls, audio, and the Windows Hello prompt all run on a
background QThread - never the UI thread - via the small Worker
helper below.

Design intent matches android-client: plain Qt widgets, no custom
styling framework. This client typically runs on the same machine as
the server (see docs/ARCHITECTURE.md), so it also has the "generate
a pairing code for a new phone" action that the phone app itself
deliberately doesn't have.
"""
import sys
import uuid
from pathlib import Path
from tempfile import gettempdir

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)

import api_client
from audio_capture import AudioRecorder
from canonical_json import canonical_json

APP_DATA_DIR = Path(gettempdir()) / "voice_ledger_pc"

GUIDED_FIELDS = [
    ("counterparty_name", "Say the name"),
    ("place", "Say the place"),
    ("transaction_date", "Say the date"),
    ("amount_paid", "Say how much was paid"),
    ("amount_due", "Say how much is left to pay"),
    ("due_date", "Say by when it should be paid"),
]


class Worker(QThread):
    """Runs `fn(*args)` off the UI thread and reports back via signals."""
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self._fn = fn
        self._args = args

    def run(self):
        try:
            result = self._fn(*self._args)
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e))
        else:
            self.succeeded.emit(result)


class AppState:
    def __init__(self):
        self.server_base_url = "http://localhost:8420/"
        self.device_id: str | None = None
        self.entry: dict[str, dict] = {}  # field -> parsed result

    def build_payload(self) -> dict:
        def val(field, key):
            return self.entry.get(field, {}).get(key)

        return {
            "id": str(uuid.uuid4()),
            "counterparty_name": val("counterparty_name", "text") or "",
            "place": val("place", "text"),
            "amount_paid": val("amount_paid", "amount"),
            "amount_paid_currency": val("amount_paid", "currency"),
            "amount_due": val("amount_due", "amount"),
            "amount_due_currency": val("amount_due", "currency"),
            "transaction_date": val("transaction_date", "date"),
            "due_date": val("due_date", "date"),
            "raw_transcript": " | ".join(
                self.entry.get(f, {}).get("raw_transcript", "") for f, _ in GUIDED_FIELDS
            ),
        }


class SettingsPage(QWidget):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Server address"))
        self.url_field = QLineEdit(state.server_base_url)
        layout.addWidget(self.url_field)
        self.url_field.textChanged.connect(self._on_url_changed)

        layout.addWidget(QLabel("Pair a new phone"))
        self.gen_code_btn = QPushButton("Generate pairing code")
        self.gen_code_btn.clicked.connect(self._generate_code)
        layout.addWidget(self.gen_code_btn)
        self.code_label = QLabel("")
        self.code_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.code_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.code_label)

        layout.addWidget(QLabel("Pair this PC"))
        self.pair_pc_btn = QPushButton("Set up this computer")
        self.pair_pc_btn.clicked.connect(self._pair_this_pc)
        layout.addWidget(self.pair_pc_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _on_url_changed(self, text: str):
        self.state.server_base_url = text

    def _generate_code(self):
        self._run(api_client.pair_start, self.state.server_base_url, on_ok=self._show_code)

    def _show_code(self, result: dict):
        self.code_label.setText(result["pairing_code"])
        self.status_label.setText(f"Valid for {result['expires_in'] // 60} minutes. Type this into the phone app.")

    def _pair_this_pc(self):
        # Self-pairing: generate a code and immediately complete pairing
        # with it, since this is the same trusted process that just
        # generated it. See docs/ARCHITECTURE.md for why the phone app
        # doesn't get this shortcut.
        def do_pair():
            import biometric_windows

            start = api_client.pair_start(self.state.server_base_url)
            pub_pem = biometric_windows.get_public_key_pem()
            return api_client.pair_complete(
                self.state.server_base_url, start["pairing_code"], "Office PC", pub_pem
            )

        self._run(do_pair, on_ok=self._on_paired)

    def _on_paired(self, result: dict):
        self.state.device_id = result["device_id"]
        self.status_label.setText("This PC is paired.")

    def _run(self, fn, *args, on_ok):
        self._worker = Worker(fn, *args)
        self._worker.succeeded.connect(on_ok)
        self._worker.failed.connect(lambda msg: self.status_label.setText(f"Error: {msg}"))
        self._worker.start()


class CapturePage(QWidget):
    all_fields_done = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.field_index = 0
        self.recorder = AudioRecorder(APP_DATA_DIR)
        self.is_recording = False

        layout = QVBoxLayout(self)
        self.progress = QProgressBar()
        self.progress.setMaximum(len(GUIDED_FIELDS))
        layout.addWidget(self.progress)

        self.prompt_label = QLabel("")
        self.prompt_label.setStyleSheet("font-size: 20px;")
        self.prompt_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.prompt_label)

        self.heard_label = QLabel("")
        self.heard_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.heard_label)

        self.record_btn = QPushButton("Record")
        self.record_btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_btn)

        self.skip_btn = QPushButton("Skip this field")
        self.skip_btn.clicked.connect(self._skip)
        layout.addWidget(self.skip_btn)

        layout.addStretch()
        self._refresh()

    def reset(self):
        self.field_index = 0
        self.state.entry = {}
        self._refresh()

    def _refresh(self):
        if self.field_index >= len(GUIDED_FIELDS):
            self.all_fields_done.emit()
            return
        field, prompt = GUIDED_FIELDS[self.field_index]
        self.progress.setValue(self.field_index)
        self.prompt_label.setText(prompt)
        self.heard_label.setText("")

    def _skip(self):
        self.field_index += 1
        self._refresh()

    def _toggle_recording(self):
        if not self.is_recording:
            self.recorder.start()
            self.is_recording = True
            self.record_btn.setText("Stop")
        else:
            self.is_recording = False
            self.record_btn.setText("Record")
            wav_path = self.recorder.stop()
            field, _ = GUIDED_FIELDS[self.field_index]
            self._worker = Worker(self._process_field, field, wav_path)
            self._worker.succeeded.connect(self._on_field_done)
            self._worker.failed.connect(lambda msg: self.heard_label.setText(f"Error: {msg}"))
            self._worker.start()

    def _process_field(self, field: str, wav_path: Path) -> dict:
        transcript = api_client.speech_to_text(self.state.server_base_url, wav_path)
        return api_client.guided_field(self.state.server_base_url, field, transcript)

    def _on_field_done(self, parsed: dict):
        field, _ = GUIDED_FIELDS[self.field_index]
        self.state.entry[field] = parsed
        summary = parsed.get("text") or parsed.get("date") or parsed.get("amount")
        self.heard_label.setText(f"Heard: {summary}")
        self.field_index += 1
        self._refresh()


class ConfirmPage(QWidget):
    submitted = Signal()

    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Review before signing"))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.confirm_btn = QPushButton("Confirm with Windows Hello")
        self.confirm_btn.clicked.connect(self._confirm)
        layout.addWidget(self.confirm_btn)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def refresh(self):
        self.list_widget.clear()
        for field, prompt in GUIDED_FIELDS:
            parsed = self.state.entry.get(field, {})
            value = parsed.get("text") or parsed.get("date")
            if value is None and "amount" in parsed:
                value = f"{parsed.get('amount')} {parsed.get('currency', '')}"
            self.list_widget.addItem(QListWidgetItem(f"{prompt.replace('Say ', '')}: {value or '-'}"))

    def _confirm(self):
        if not self.state.device_id:
            self.status_label.setText("Pair this PC first (Settings tab).")
            return

        def do_sign_and_submit():
            import biometric_windows

            payload = self.state.build_payload()
            payload_json = canonical_json(payload)
            signature = biometric_windows.sign_with_windows_hello(payload_json)
            return api_client.submit_transaction(
                self.state.server_base_url, self.state.device_id, payload_json, signature
            )

        self.status_label.setText("Waiting for Windows Hello...")
        self._worker = Worker(do_sign_and_submit)
        self._worker.succeeded.connect(self._on_submitted)
        self._worker.failed.connect(lambda msg: self.status_label.setText(f"Error: {msg}"))
        self._worker.start()

    def _on_submitted(self, _result: dict):
        self.status_label.setText("Saved.")
        self.submitted.emit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Voice Ledger")
        self.resize(480, 640)

        state = AppState()
        self.settings_page = SettingsPage(state)
        self.capture_page = CapturePage(state)
        self.confirm_page = ConfirmPage(state)

        tabs = QTabWidget()
        tabs.addTab(self.capture_page, "Record")
        tabs.addTab(self.confirm_page, "Review")
        tabs.addTab(self.settings_page, "Settings")
        self.setCentralWidget(tabs)
        self._tabs = tabs

        self.capture_page.all_fields_done.connect(self._go_to_confirm)
        self.confirm_page.submitted.connect(self._back_to_capture)

    def _go_to_confirm(self):
        self.confirm_page.refresh()
        self._tabs.setCurrentWidget(self.confirm_page)

    def _back_to_capture(self):
        self.capture_page.reset()
        self._tabs.setCurrentWidget(self.capture_page)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
