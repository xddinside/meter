.PHONY: install uninstall clean test run autostart aur-update aur-push

PREFIX ?= $(HOME)/.local
BINDIR = $(PREFIX)/bin
SHAREDIR = $(PREFIX)/share
APPDIR = $(SHAREDIR)/applications
AUTOSTARTDIR = $(HOME)/.config/autostart
VERSION = $(shell grep '^pkgver=' PKGBUILD | cut -d= -f2)

install:
	pip install -e .
	install -Dm644 autostart/meter.desktop $(APPDIR)/meter.desktop
	@echo "Installed. Run 'meter' to start."

uninstall:
	pip uninstall -y meter-tray 2>/dev/null || true
	rm -f $(APPDIR)/meter.desktop
	rm -f $(AUTOSTARTDIR)/meter.desktop
	@echo "Uninstalled."

autostart:
	install -Dm644 autostart/meter.desktop $(AUTOSTARTDIR)/meter.desktop
	@echo "Autostart enabled."

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
