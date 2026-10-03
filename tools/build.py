#!/usr/bin/env python3
"""Build the static site: src/ -> repository root.

    pip install -r requirements.txt
    python tools/build.py

Generated (safe to overwrite, do not edit by hand): index.html, en/, zh/, sitemap.xml
Edit instead: src/data/*.yml, src/content/**, src/templates/*
"""
import datetime
import hashlib
import re
import shutil
import sys
from pathlib import Path
from html import escape
from urllib.parse import quote

import markdown
import yaml

try:
    from PIL import Image
except ImportError:  # image sizes are then omitted; the build warns
    Image = None
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
LANGS = ('en', 'zh')
PLATFORMS = (  # order = button order
    ('spotify', 'Spotify'),
    ('apple', 'Apple Music'),
    ('bandcamp', 'Bandcamp'),
    ('youtube', 'YouTube'),
    ('soundcloud', 'SoundCloud'),
)
MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
warnings = []


def load_yaml(name):
    return yaml.safe_load((SRC / 'data' / name).read_text(encoding='utf-8'))


def split_front_matter(text):
    text = text.replace('\r\n', '\n')
    m = re.match(r'^---\n(.*?)\n?---\n?(.*)$', text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def render_md(text):
    return markdown.markdown(text, extensions=['extra', 'sane_lists']) if text.strip() else ''


def fmt_date(d, lang):
    return f'{d.month}/{d.day}' if lang == 'zh' else f'{MONTHS[d.month - 1]} {d.day}'


# ---------------------------------------------------------------------------
# Blog bodies: Markdown plus a few shortcodes (one per line):
#   ::youtube[VIDEO_ID or URL]{caption}
#   ::spotify[open.spotify.com URL]{caption}
#   ::soundcloud[soundcloud.com URL]{caption}
#   ::bandcamp[track=ID | album=ID | EmbeddedPlayer URL]{caption}
#   ::audio[/assets/blog/clip.mp3]{caption}
# Third-party players are click-to-load; images get width/height, lazy loading and captions.
# ---------------------------------------------------------------------------
SHORTCODE_RE = re.compile(r'^::(\w+)\[(.+?)\](?:\{(.*?)\})?[ \t]*$', re.M)
IMG_RE = re.compile(r'<img\b([^>]*?)\s*/?>')


def _attr(attrs, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', attrs)
    return m.group(1) if m else None


def _embed_html(kind, arg, caption, lang, i18n):
    """Return the HTML for one shortcode, or None if the argument could not be understood."""
    arg = arg.strip()
    t = i18n[lang]
    cap = f'<p class="embed-caption">{escape(caption)}</p>' if caption else ''
    if kind == 'audio':
        local = ROOT / arg.lstrip('/')
        if arg.startswith('/') and not local.exists():
            warnings.append(f'blog audio not found: {arg}')
        label = f'<figcaption>{escape(caption)}</figcaption>' if caption else ''
        return (f'<figure class="audio"><audio controls preload="none" src="{escape(arg, quote=True)}"></audio>'
                f'{label}</figure>')

    if kind == 'youtube':
        m = re.search(r'(?:[?&]v=|youtu\.be/|/embed/|/shorts/)([\w-]{11})', arg) or re.fullmatch(r'()([\w-]{11})', arg)
        vid = m.group(m.lastindex) if m else None
        if not vid:
            return None
        src, label, css = f'https://www.youtube-nocookie.com/embed/{vid}?autoplay=1&rel=0', 'YouTube', 'video'
    elif kind == 'spotify':
        m = re.search(r'open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist|episode|show)/(\w+)', arg)
        if not m:
            return None
        src = f'https://open.spotify.com/embed/{m.group(1)}/{m.group(2)}?utm_source=generator&theme=0'
        label, css = 'Spotify', 'spotify' if m.group(1) in ('track', 'episode') else 'spotify-tall'
    elif kind == 'soundcloud':
        if 'soundcloud.com/' not in arg:
            return None
        src = ('https://w.soundcloud.com/player/?url=' + quote(arg, safe='')
               + '&color=%23ff5500&auto_play=true&hide_related=true&show_comments=false'
                 '&show_user=true&show_reposts=false&show_teaser=false')
        label, css = 'SoundCloud', 'soundcloud-tall' if '/sets/' in arg else 'soundcloud'
    elif kind == 'bandcamp':
        if arg.startswith('http'):
            src = arg
        elif re.fullmatch(r'(track|album)=\d+', arg):
            src = (f'https://bandcamp.com/EmbeddedPlayer/{arg}/size=large/bgcol=0d0d11/linkcol=e63946/'
                   'tracklist=false/artwork=small/transparent=true/')
        else:
            return None
        label, css = 'Bandcamp', 'bandcamp'
    else:
        return None
    title = escape(caption or label, quote=True)
    return (f'<div class="embed"><div class="embed-slot">'
            f'<button type="button" class="player-load" data-src="{escape(src, quote=True)}" data-kind="{css}" '
            f'data-title="{title}" data-umami-event="play-{kind}"><span class="play-icon" aria-hidden="true">▶</span>'
            f'<span>{escape(t["play_preview"] % label)}</span></button></div>{cap}</div>')


def _figure(img_attrs):
    """<img ...> -> lazy-loaded <img> with intrinsic size (avoids layout shift), wrapped in <figure> with caption."""
    attrs = img_attrs
    title = _attr(attrs, 'title')
    src = _attr(attrs, 'src') or ''
    attrs = re.sub(r'\s*\btitle="[^"]*"', '', attrs)
    extra = ' loading="lazy" decoding="async"'
    local = ROOT / src.lstrip('/')
    if src.startswith('/') and local.is_file():
        if Image is None:
            warnings.append('Pillow is not installed: blog images get no width/height (pip install -r requirements.txt)')
        else:
            with Image.open(local) as im:
                extra += f' width="{im.width}" height="{im.height}"'
    elif src.startswith('/'):
        warnings.append(f'blog image not found: {src}')
    cap = f'<figcaption>{title}</figcaption>' if title else ''
    return f'<figure><img{attrs}{extra}>{cap}</figure>'


def render_post(text, lang, i18n):
    """Markdown (+ shortcodes) -> HTML for a blog post."""
    embeds = []

    def stash(m):
        html = _embed_html(m.group(1).lower(), m.group(2), (m.group(3) or '').strip(), lang, i18n)
        if html is None:
            warnings.append(f'blog: could not understand shortcode: {m.group(0).strip()}')
            return ''
        embeds.append(html)
        return f'\n\n@@EMBED{len(embeds) - 1}@@\n\n'

    text = SHORTCODE_RE.sub(stash, text.replace('\r\n', '\n'))
    html = markdown.markdown(text, extensions=['extra', 'sane_lists']) if text.strip() else ''
    for i, e in enumerate(embeds):
        html = html.replace(f'<p>@@EMBED{i}@@</p>', e)
    # two or more images in one paragraph -> gallery; a lone image -> figure
    html = re.sub(r'<p>\s*((?:<img\b[^>]*>\s*){2,})</p>',
                  lambda m: '<div class="gallery">' + ''.join(_figure(i.group(1)) for i in IMG_RE.finditer(m.group(1))) + '</div>',
                  html)
    html = re.sub(r'<p>\s*<img\b([^>]*?)\s*/?>\s*</p>', lambda m: _figure(m.group(1)), html)
    return html



def pick_embed(r):
    """Preview player source, by priority: YouTube -> Spotify -> SoundCloud (only exact track URLs)."""
    links = r.get('links') or {}
    yt = links.get('youtube')
    if isinstance(yt, str):
        m = re.search(r'(?:[?&]v=|youtu\.be/|/embed/)([\w-]{11})', yt)
        if m:
            return {'provider': 'youtube', 'label': 'YouTube', 'kind': 'video',
                    'src': f'https://www.youtube-nocookie.com/embed/{m.group(1)}?autoplay=1&rel=0'}
    sp = links.get('spotify')
    if isinstance(sp, str):
        m = re.search(r'/track/(\w+)', sp)
        if m:
            return {'provider': 'spotify', 'label': 'Spotify', 'kind': 'spotify',
                    'src': f'https://open.spotify.com/embed/track/{m.group(1)}?utm_source=generator&theme=0'}
    sc = links.get('soundcloud')
    if isinstance(sc, str):
        return {'provider': 'soundcloud', 'label': 'SoundCloud', 'kind': 'soundcloud',
                'src': 'https://w.soundcloud.com/player/?url=' + quote(sc, safe='')
                       + '&color=%23ff5500&auto_play=true&hide_related=true&show_comments=false'
                         '&show_user=true&show_reposts=false&show_teaser=false'}
    return None


def prepare_release(r, site, i18n):
    """Normalise one release entry: buttons, chips, status text."""
    buttons = []
    soon_texts = []
    for key, label in PLATFORMS:
        v = (r.get('links') or {}).get(key)
        if v is None or v is False:
            continue
        b = {'key': key, 'label': label}
        if isinstance(v, dict):
            d = v.get('soon')
            b['soon'] = True
            b['soon_text'] = {}
            for lang in LANGS:
                if isinstance(d, datetime.date):
                    b['soon_text'][lang] = f'{fmt_date(d, lang)}' + (' 上架' if lang == 'zh' else '')
                else:
                    b['soon_text'][lang] = i18n[lang]['coming_soon']
            if isinstance(d, datetime.date):
                soon_texts.append((d, label))
                if d <= datetime.date.today():
                    warnings.append(f"{r['slug']}: {label} date {d} has passed - add the real URL in releases.yml")
        elif v is True:
            b['url'] = site['artist_links'][key]
            b['fallback'] = True
            warnings.append(f"{r['slug']}: {label} link falls back to the artist page - add the track URL")
        else:
            b['url'] = v
        buttons.append(b)
    r['buttons'] = buttons
    r['soundcloud_url'] = next(
        (b['url'] for b in buttons if b['key'] == 'soundcloud' and b.get('url') and not b.get('fallback')), None)
    r['embed'] = pick_embed(r)

    # genre may be a list or a comma separated string ("Digicore, Lo-fi, Electronic")
    genres = r.get('genre') or []
    if isinstance(genres, str):
        genres = re.split(r'[,，、]', genres)
    r['genres'] = [g.strip() for g in genres if str(g).strip()]

    chips = {lang: [] for lang in LANGS}
    for lang in LANGS:
        chips[lang].extend(r['genres'])
        if r.get('bpm'):
            chips[lang].append(f"{r['bpm']} BPM")
        if r.get('key'):
            chips[lang].append(f"{i18n[lang]['key']} {r['key']}")
        if r.get('duration'):
            chips[lang].append(str(r['duration']))
        if r.get('instrumental'):
            chips[lang].append(i18n[lang]['instrumental'])
    r['chips'] = chips

    dated_text = None
    if soon_texts:
        d, label = sorted(soon_texts)[0]
        several = len({x[0] for x in soon_texts}) == 1 and len(soon_texts) > 1  # same day on several stores
        dated_text = {
            lang: (f'{fmt_date(d, lang)} 上架' if lang == 'zh' else f'Out {fmt_date(d, lang)}') if several
            else f'{label} · {fmt_date(d, lang)}' + (' 上架' if lang == 'zh' else '')
            for lang in LANGS}

    if r.get('upcoming'):
        # teaser page; once a release date is known it replaces "In production"
        r['status'] = 'upcoming'
        r['status_text'] = dated_text or {lang: i18n[lang]['in_production'] for lang in LANGS}
    elif dated_text:
        r['status'] = 'soon'
        r['status_text'] = dated_text
    else:
        r['status'] = 'out'
        r['status_text'] = {lang: i18n[lang]['out_now'] for lang in LANGS}
    return r


def write_small_logo():
    """Small-size logo for the sub pages' top bar: same outlines as the home page, thin stroke, padded viewBox."""
    frag = (SRC / 'templates' / '_logo_paths.html').read_text(encoding='utf-8')
    paths = ''.join(re.findall(r'<path\b[^>]*/>', frag, re.S))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-8 -8 919.90356 183.13313">'
           '<style>path{fill:#06050a;stroke:#e63946;stroke-width:1.2px;stroke-linejoin:round;stroke-linecap:round;'
           'vector-effect:non-scaling-stroke}</style>' + paths + '</svg>\n')
    out = ROOT / 'assets' / 'logo-small.svg'
    out.write_text(svg, encoding='utf-8', newline='\n')


def asset_version(name):
    """Short content hash, appended to CSS urls so browsers never keep a stale stylesheet after a deploy."""
    data = (ROOT / name).read_bytes().replace(b'\r\n', b'\n')  # same hash on Windows (CRLF) and CI (LF)
    return hashlib.md5(data).hexdigest()[:8]


def main():
    site = load_yaml('site.yml')
    write_small_logo()
    site['css_v'] = {'style': asset_version('style.css'), 'pages': asset_version('pages.css'),
                     'logo': asset_version('assets/logo-small.svg')}
    i18n = load_yaml('i18n.yml')
    releases = [prepare_release(r, site, i18n) for r in load_yaml('releases.yml') if not r.get('hidden')]
    releases.sort(key=lambda r: r['order'])

    # ---- posts: src/content/posts/YYYY-MM-DD-slug.<lang>.md ----
    posts = {lang: [] for lang in LANGS}
    for f in sorted((SRC / 'content' / 'posts').glob('*.md')):
        m = re.match(r'^(\d{4}-\d{2}-\d{2})-(.+)\.(en|zh)$', f.stem)
        if not m:
            warnings.append(f'skipped post with unexpected name: {f.name}')
            continue
        date, slug, lang = datetime.date.fromisoformat(m.group(1)), m.group(2), m.group(3)
        fm, body = split_front_matter(f.read_text(encoding='utf-8'))
        posts[lang].append({
            'title': fm.get('title', slug), 'summary': fm.get('summary', ''), 'date': date,
            'slug': slug, 'lang': lang, 'ref': fm.get('ref', slug), 'cover': fm.get('cover'),
            'body': render_post(body, lang, i18n), 'path': f'/{lang}/blog/{slug}/',
        })
    for lang in LANGS:
        posts[lang].sort(key=lambda p: p['date'], reverse=True)
    has_blog = any(posts.values())

    env = Environment(loader=FileSystemLoader(SRC / 'templates'), autoescape=select_autoescape(['html']))
    written = []  # public paths, for the sitemap

    def write(rel, text):
        out = ROOT / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding='utf-8', newline='\n')

    # clean generated directories
    for lang in LANGS:
        shutil.rmtree(ROOT / lang, ignore_errors=True)

    def page_ctx(lang, **kw):
        other = 'zh' if lang == 'en' else 'en'
        ctx = dict(site=site, lang=lang, t=i18n[lang], has_blog=has_blog, jsonld=None, accent=None,
                   bg_image=None, og_square=False, og_type='website', section=None, alternates=[],
                   alt_page=None, og_image='/assets/og-image.jpg')
        ctx.update(kw)
        if kw.get('alt_path'):
            ctx['alt_page'] = {'lang': other, 'path': kw['alt_path'], 'name': i18n[other]['lang_name']}
        return ctx

    def alternates_for(paths):
        alts = [{'hreflang': {'en': 'en', 'zh': 'zh-Hant'}[l], 'path': p} for l, p in paths.items()]
        if 'en' in paths:
            alts.append({'hreflang': 'x-default', 'path': paths['en']})
        return alts

    # ---- release pages ----
    released = sorted([r for r in releases if not r.get('upcoming')], key=lambda r: r['order'], reverse=True)
    upcoming = sorted([r for r in releases if r.get('upcoming')], key=lambda r: r['order'], reverse=True)
    for idx, r in enumerate(releases):
        prev_r = releases[idx - 1] if idx > 0 else None
        next_r = releases[idx + 1] if idx + 1 < len(releases) else None
        paths = {l: f"/{l}/releases/{r['slug']}/" for l in LANGS}
        for lang in LANGS:
            md_file = SRC / 'content' / 'releases' / f"{r['slug']}.{lang}.md"
            fm, body = split_front_matter(md_file.read_text(encoding='utf-8')) if md_file.exists() else ({}, '')
            title = r['title']
            desc = fm.get('description') or (
                f"{title} - {site['artist']}. " + (r['status_text'][lang] + '.'))
            jsonld = {
                '@context': 'https://schema.org', '@type': 'MusicRecording', 'name': title,
                'url': site['site_url'] + paths[lang], 'image': f"{site['site_url']}/assets/covers/{r['slug']}-og.jpg",
                'byArtist': {'@type': 'MusicGroup', 'name': site['artist'], 'url': site['site_url'] + '/'},
            }
            if r['genres']:
                jsonld['genre'] = r['genres'] if len(r['genres']) > 1 else r['genres'][0]
            publisher = r.get('publisher') or site.get('publisher')
            if publisher:
                jsonld['publisher'] = {'@type': 'Organization', 'name': publisher}
            ctx = page_ctx(
                lang, r=r, body=render_md(body), prev=prev_r, next=next_r, section='releases',
                page_title=f"{title} | AEGISULF", description=desc, path=paths[lang],
                alt_path=paths['zh' if lang == 'en' else 'en'], alternates=alternates_for(paths),
                share_url=site['site_url'] + paths['en'],
                og_image=f"/assets/covers/{r['slug']}-og.jpg", og_square=True, accent=r['accent'],
                bg_image=f"/assets/covers/{r['slug']}-512.webp", jsonld=jsonld, og_type='music.song')
            write(paths[lang].strip('/') + '/index.html', env.get_template('release.html').render(ctx))
            written.append(paths[lang])

    # ---- releases index ----
    paths = {l: f'/{l}/releases/' for l in LANGS}
    for lang in LANGS:
        ctx = page_ctx(lang, released=released, upcoming=upcoming, section='releases',
                       page_title=f"{i18n[lang]['releases']} | AEGISULF", description=i18n[lang]['site_desc'],
                       path=paths[lang], alt_path=paths['zh' if lang == 'en' else 'en'], alternates=alternates_for(paths))
        write(paths[lang].strip('/') + '/index.html', env.get_template('releases_index.html').render(ctx))
        written.append(paths[lang])

    # ---- blog (only generated when posts exist) ----
    if has_blog:
        paths = {l: f'/{l}/blog/' for l in LANGS if posts[l]}
        for lang in LANGS:
            if not posts[lang]:
                continue
            alt = paths.get('zh' if lang == 'en' else 'en')
            ctx = page_ctx(lang, posts=posts[lang], section='blog', page_title=f"{i18n[lang]['blog']} | AEGISULF",
                           description=i18n[lang]['site_desc'], path=paths[lang], alt_path=alt,
                           alternates=alternates_for(paths))
            write(paths[lang].strip('/') + '/index.html', env.get_template('blog_index.html').render(ctx))
            written.append(paths[lang])
            for p in posts[lang]:
                translations = {l: q['path'] for l in LANGS for q in posts[l] if q['ref'] == p['ref']}
                other = 'zh' if lang == 'en' else 'en'
                ctx = page_ctx(lang, post=p, body=p['body'], section='blog', page_title=f"{p['title']} | AEGISULF",
                               description=p['summary'] or i18n[lang]['site_desc'], path=p['path'],
                               alt_path=translations.get(other), alternates=alternates_for(translations),
                               share_url=site['site_url'] + translations.get('en', p['path']),
                               og_type='article', og_image=p['cover'] or '/assets/og-image.jpg')
                write(p['path'].strip('/') + '/index.html', env.get_template('post.html').render(ctx))
                written.append(p['path'])
            entries = ''.join(
                f"<entry><title>{_x(p['title'])}</title><link href=\"{site['site_url']}{p['path']}\"/>"
                f"<id>{site['site_url']}{p['path']}</id><updated>{p['date']}T00:00:00Z</updated>"
                f"<summary>{_x(p['summary'])}</summary></entry>" for p in posts[lang])
            write(f'{lang}/feed.xml',
                  '<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
                  f"<title>AEGISULF - {i18n[lang]['blog']}</title><id>{site['site_url']}/{lang}/blog/</id>"
                  f"<link rel=\"self\" href=\"{site['site_url']}/{lang}/feed.xml\"/>"
                  f"<updated>{posts[lang][0]['date']}T00:00:00Z</updated>{entries}</feed>")

    # ---- hub ----
    featured = next((r for r in releases if r.get('featured')), None) or (released[0] if released else None)
    jsonld = {
        '@context': 'https://schema.org', '@type': 'MusicGroup', 'name': site['artist'],
        'url': site['site_url'] + '/', 'image': site['site_url'] + '/assets/og-image.jpg',
        'description': 'Aegisulf, crafting electronic music.',
        'sameAs': [site['artist_links'][k] for k in ('spotify', 'apple', 'bandcamp', 'youtube', 'soundcloud', 'x')],
    }
    hub = env.get_template('hub.html').render(site=site, featured=featured, has_blog=has_blog, jsonld=jsonld,
                                                  en=i18n['en'], zh=i18n['zh'])
    write('index.html', hub)
    written.insert(0, '/')

    # ---- sitemap ----
    today = datetime.date.today().isoformat()
    urls = ''.join(f"  <url>\n    <loc>{site['site_url']}{p}</loc>\n    <lastmod>{today}</lastmod>\n  </url>\n" for p in written)
    write('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                         + urls + '</urlset>\n')

    print(f'built {len(written)} pages')
    for w in warnings:
        print('WARNING:', w)


def _x(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


if __name__ == '__main__':
    sys.exit(main())
