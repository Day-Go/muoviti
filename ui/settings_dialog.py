"""Settings dialog."""

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

import config


class SettingsDialog(QDialog):
    """Application settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(config.GENAI_API_KEY)
        self.api_key_edit.setPlaceholderText("Enter Google API Key")
        form.addRow("API Key:", self.api_key_edit)

        # Pixel snapper palette
        self.palette_spin = QSpinBox()
        self.palette_spin.setRange(2, 256)
        self.palette_spin.setValue(config.PIXEL_SNAPPER_PALETTE)
        form.addRow("Pixel Snapper Palette:", self.palette_spin)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_and_accept(self):
        """Save settings and close."""
        # Update config (runtime only - not persisted)
        config.GENAI_API_KEY = self.api_key_edit.text()
        config.PIXEL_SNAPPER_PALETTE = self.palette_spin.value()
        self.accept()
