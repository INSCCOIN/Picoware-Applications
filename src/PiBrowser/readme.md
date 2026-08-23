# PiBrowse

Text-only browser for PicoCalc / Picoware.

```
/sd/picoware/apps/pibrowse.py
```

Connect Wi-Fi in the system app first, then launch PiBrowse.

## Screen

```
https://info.cern.ch/                 <     site bar (top)
--------------------------------------
article text (15 rows)
                                      ▌    2px scrollbar
--------------------------------------
12/80   4 links                          status
12.3 kb   Up/Dn scroll   F10 links       status
```

`<` means a Back snapshot is stored. Rate is shown as `#.#` KB/s.

## Controls

### Anywhere

| Key | Action |
|---|---|
| Enter | Open the highlighted item |
| Up / Down | Move highlight or scroll the page |
| F6 | Address bar |
| F7 | Search (FrogFind) |
| Back | One step back |

### Home

| Key | Action |
|---|---|
| Enter | Address / Search / 1990s directory / Quit |
| Back or Left | Exit PiBrowse |

### Directory

| Key | Action |
|---|---|
| Enter | Load that site |
| Back or Left | Home |

### Page

| Key | Action |
|---|---|
| Up / Down | Scroll text |
| Enter, Right, or F10 | Links on this page |
| Left or Back | Instant Back (no download) |
| F6 | Edit URL |
| F7 | Search |
| F8 | Reload from the network |
| F9 | Home |

### Links list

| Key | Action |
|---|---|
| Enter | Follow the link |
| Back or Left | Return to the page |

### Address / search keyboard

| Key | Action |
|---|---|
| Enter | Go |
| Back | Cancel |

### Downloading

| Key | Action |
|---|---|
| Back | Cancel the fetch |

## On-disk cache

Root of the SD card:

```
/pibrowse/page.html    last download
/pibrowse/page.txt     extracted text
/pibrowse/page.lnk     links
/pibrowse/page.meta    title + url
/pibrowse/b0.txt … b5  Back snapshots
```

Up to 6 snapshots. Opening a new URL writes the current page into the next `b#` slot. Back reads that slot.

## Limits

- **No images, CSS files, or JavaScript.** Only the HTML (or plain text) is downloaded.
- **No cookies, logins, or POST forms.**
- HTML cap **32 KB**. Extracted text cap **8 KB / 160 lines**. At most **24 links**.
- Inline `<style>` is only used to hide `display:none` / `visibility:hidden` nodes. There is no layout engine.
- Many modern sites are empty or broken without JS. Search goes through FrogFind; a failed fetch retries HTTP, then FrogFind reader.
- PicoCalc TLS can fail on some hosts. Gzip is refused (`Accept-Encoding: identity`).
- Body font is Picoware `FONT_SMALL`. No TTF, bold, or arbitrary sizes.
- Scroll uses an in-RAM line list. Do not expect a full desktop browser.

## Built-in directory

CERN 1991, Textfiles, FrogFind, Wiby, 68k News, NPR text, CNN Lite, Simple Wikipedia, Jargon File, Floodgap Gopher, RFC 791, wttr.in, example.com.
