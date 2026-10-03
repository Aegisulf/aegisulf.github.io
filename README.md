# aegisulf.github.io

Official hub for **Aegisulf** (electronic music): <https://aegisulf.github.io/>

A small static site. Pages are generated from `src/` by `tools/build.py`, and the generated files are committed so GitHub Pages can serve them as-is.

## Layout

| Path | What it is |
|---|---|
| `src/data/releases.yml` | Releases shown on the site (links, status, accent colour, `hidden`, `featured`, ...) |
| `src/data/site.yml` | Site-wide settings: artist links, art credit, analytics id |
| `src/data/i18n.yml` | UI strings for the English / Traditional Chinese pages |
| `src/content/releases/<slug>.<en\|zh>.md` | Per-release story text (empty file = no story section) |
| `src/content/posts/YYYY-MM-DD-<slug>.<en\|zh>.md` | Blog posts (see below) |
| `src/templates/` | Jinja2 templates (`hub.html` is the home page) |
| `style.css` | Home page styles |
| `pages.css` | Styles for release / blog pages |
| `assets/` | Images (`assets/covers/<slug>*.webp` are the optimised covers) |
| `index.html`, `en/`, `zh/`, `sitemap.xml` | **Generated** - do not edit by hand |

## Build

```bash
pip install -r requirements.txt
python tools/build.py
```

The build prints warnings, for example when a platform date has passed but no URL was added yet.

When `src/`, `tools/` or `requirements.txt` change on `main`, the *Build site* GitHub Action runs the same build and commits the result, so editing a Markdown file on GitHub is enough.

## Common tasks

**New release** - add an entry to `src/data/releases.yml`, put the cover at `assets/covers/<slug>.webp` (1024px), `<slug>-512.webp`, `<slug>-128.webp` and `<slug>-og.jpg`, then create `src/content/releases/<slug>.en.md` and `.zh.md`.

**A platform goes live** - replace `{soon: 2026-10-16}` with the track URL in `releases.yml`.

**Hide a release** - add `hidden: true`.

**Blog post** - create `src/content/posts/2026-11-01-my-post.zh.md` (and optionally `.en.md`):

```markdown
---
title: Post title
summary: One sentence for the list and link previews.
ref: my-post        # same ref in both languages links the translations
---

Markdown body...
```

The Blog link appears on the home page automatically once a post exists.

**Images, video and music in posts** - plain Markdown for text and images, plus one-line shortcodes. Third-party players only load after a click.

```markdown
![Alt text](/assets/blog/photo.webp "Caption shown under the image")   <- single image with caption

![First](/assets/blog/a.webp)                                          <- 2+ images in a row
![Second](/assets/blog/b.webp)                                            become a gallery

::youtube[VIDEO_ID or URL]{optional caption}
::spotify[https://open.spotify.com/track/...]{optional caption}        <- track, album, playlist, episode
::soundcloud[https://soundcloud.com/aegisulf/track-name]{optional caption}
::bandcamp[track=1234567890]{optional caption}                          <- or album=ID, or a full EmbeddedPlayer URL
::audio[/assets/blog/clip.mp3]{optional caption}                        <- a file hosted in this repo
```

Put images and audio under `assets/blog/` (use WebP images and short MP3 clips; host full tracks and long videos on YouTube / SoundCloud instead). The Bandcamp ID is in the page's `bc-page-properties` meta tag, or in the embed code from Bandcamp's *Share / Embed* dialog.

**Preview** - `python -m http.server 8000`, then open <http://localhost:8000/>.

## Notes

- Language follows the visitor from any entry page: a Chinese-preferring browser is sent to the `/zh/` version of whatever page it opened, an explicit choice (language link / toggle, stored in `localStorage`) always wins, and English or unknown browsers and crawlers are never redirected, so both versions stay indexable. Share buttons always share the `/en/` URL, which Chinese browsers are redirected away from automatically.
- Analytics: [Umami Cloud](https://umami.is/), cookie-free, only on the production domain, honours Do Not Track.
- Wolf illustration by [@Korl413115](https://x.com/Korl413115).
