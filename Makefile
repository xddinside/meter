.PHONY: install uninstall clean test run aur-update aur-push

PREFIX ?= $(HOME)/.local
BINDIR = $(PREFIX)/bin
SHAREDIR = $(PREFIX)/share
APPDIR = $(SHAREDIR)/applications
SYSTEMD_USER_DIR = $(HOME)/.config/systemd/user
VERSION = $(shell grep '^pkgver=' PKGBUILD | cut -d= -f2)

install:
	pip install -e .
	install -Dm644 systemd/meter.service $(SYSTEMD_USER_DIR)/meter.service
	@echo "Installed meter."
	@echo ""
	@echo "To start now and enable on boot:"
	@echo "  systemctl --user daemon-reload"
	@echo "  systemctl --user enable --now meter"

uninstall:
	-systemctl --user stop meter 2>/dev/null || true
	-systemctl --user disable meter 2>/dev/null || true
	pip uninstall -y meter-tray 2>/dev/null || true
	rm -f $(SYSTEMD_USER_DIR)/meter.service
	rm -f $(APPDIR)/meter.desktop
	rm -f $(HOME)/.config/autostart/meter.desktop
	-systemctl --user daemon-reload 2>/dev/null || true
	@echo "Uninstalled meter."

autostart:
	install -Dm644 systemd/meter.service $(SYSTEMD_USER_DIR)/meter.service
	-systemctl --user daemon-reload
	-systemctl --user enable --now meter
	@echo "Autostart enabled via systemd user service."

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/

test:
	python -m meter --no-tray --refresh

run:
	python -m meter

# AUR targets
aur-init:
	git clone ssh://aur@aur.archlinux.org/meter-tray.git aur

aur-update:
	@makepkg --printsrcinfo > .SRCINFO
	@echo "Updated .SRCINFO for version $(VERSION)"

aur-push: aur-update
	@if [ ! -d "aur" ]; then \
		echo "AUR repo not found. Run 'make aur-init' first."; \
		exit 1; \
	fi
	cp PKGBUILD .SRCINFO aur/
	cd aur && git add -A && git commit -m "Update to $(VERSION)" && git push origin master
	@echo "Pushed $(VERSION) to AUR"
