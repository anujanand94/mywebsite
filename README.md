# Anuj Anand — Portfolio (Live / Vercel)

Pure static HTML/CSS/JS. No build step. Deploys to Vercel in under 2 minutes.

---

## Quick Deploy Checklist

- [ ] Step 1 — Push this folder to GitHub
- [ ] Step 2 — Connect repo to Vercel
- [ ] Step 3 — Upload hero video to Cloudflare R2
- [ ] Step 4 — Replace `HERO_VIDEO_URL` in `index.html`
- [ ] Step 5 — Add CV PDF
- [ ] Step 6 — Connect custom domain

---

## Step 1 — Push to GitHub

```bash
cd live_website
git init
git add .
git commit -m "Initial portfolio deploy"
```

Create a new **private** repo on GitHub (github.com → New repository), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/portfolio-live.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Connect to Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repo (`portfolio-live`)
3. Framework Preset: **Other**
4. Root Directory: leave as `/` (already pointing at `live_website/`)
5. Build & Output Settings: leave everything blank (no build step)
6. Click **Deploy**

Your site is live at `https://portfolio-live-xxx.vercel.app`.

---

## Step 3 — Upload Hero Video to Cloudflare R2

The hero video (`hero.mp4`) is excluded from git (too large). Host it on a CDN.

### Using Cloudflare R2 (free tier — recommended)

1. Sign up at [cloudflare.com](https://cloudflare.com) (free)
2. Sidebar → **R2** → **Create Bucket** (name it e.g. `portfolio-assets`)
3. Upload `hero.mp4` to the bucket
4. Go to bucket **Settings** → **Public Access** → enable **R2.dev subdomain**
5. Copy the public URL — it looks like:
   ```
   https://pub-abc123def456.r2.dev/hero.mp4
   ```

### Confirm byte-range serving works (optional sanity check)
```bash
curl -I -H "Range: bytes=0-1023" https://pub-abc123def456.r2.dev/hero.mp4
# Should return: HTTP/2 206
```

---

## Step 4 — Replace HERO_VIDEO_URL in index.html

Open `index.html` and find:

```html
<source src="HERO_VIDEO_URL" type="video/mp4">
```

Replace `HERO_VIDEO_URL` with your actual R2 URL:

```html
<source src="https://pub-abc123def456.r2.dev/hero.mp4" type="video/mp4">
```

Commit and push — Vercel auto-deploys on every push to `main`.

```bash
git add index.html
git commit -m "Set hero video URL"
git push
```

---

## Step 5 — Add Your CV PDF

Drop `cv.pdf` into `static/`. It is gitignored by default (contains personal info).

**Options:**

**Option A — Include in git** (simpler, fine for a public CV):
```bash
# Remove cv.pdf from .gitignore first, then:
git add static/cv.pdf
git commit -m "Add CV"
git push
```

**Option B — Upload directly in Vercel dashboard** (keeps it out of git):
Vercel → Project → **Files** tab → upload `static/cv.pdf`

---

## Step 6 — Connect a Custom Domain

1. Vercel → Project → **Settings** → **Domains**
2. Add your domain (e.g. `anujanand.com`)
3. Vercel shows you DNS records to add — go to your domain registrar and add them:
   - If using Cloudflare DNS: add a **CNAME** record pointing to `cname.vercel-dns.com`
   - Or use Vercel Nameservers (easiest — Vercel manages everything)
4. SSL is provisioned automatically within ~60 seconds

---

## Keeping Content Updated

All content is plain HTML — no CMS, no build step. Edit `index.html` directly.

Search for `TODO` comments throughout the file to find every section that needs updating:

| What to update | Where |
|:---|:---|
| Hero video URL | `<source src="HERO_VIDEO_URL">` |
| Hero stats (returns, hit rate) | `.hero-stats` div |
| Eyebrow / tagline | `.hero-eyebrow`, `.hero-tagline` |
| About bio paragraphs | `#about .about-bio` |
| Credential cards | `#about .credentials` |
| Experience bullets | `#experience .timeline` |
| Project cards | `#projects .projects-grid` |
| G&M articles list | `#projects .gm-articles` |
| Education entries | `#education .edu-grid` |
| Certifications | `#skills .cert-list` |
| Contact subtext + availability | `#contact .contact-sub` |
| Email address | `mailto:` link in contact |
| LinkedIn URL | `href` in contact |
| Footer year / city | `<footer>` |

After any edit:
```bash
git add index.html
git commit -m "Update [what you changed]"
git push
```
Vercel deploys in ~15 seconds.

---

## File Structure

```
live_website/
├── index.html          ← Full portfolio (edit this for content changes)
├── static/
│   ├── css/
│   │   └── style.css   ← All styles (dark luxury design system)
│   ├── js/
│   │   └── main.js     ← Video scrub, cursor, scroll animations
│   ├── hero.mp4        ← NOT in git — host on R2 (see Step 3)
│   └── cv.pdf          ← NOT in git by default (see Step 5)
├── vercel.json         ← Static routing + cache headers
├── .gitignore
├── .env.example        ← Template for environment variables
└── README.md           ← This file
```

---

## Troubleshooting

| Problem | Fix |
|:---|:---|
| Hero video doesn't play / scrub | Check R2 URL in `index.html`; open DevTools → Network → filter `hero.mp4` → status must be **206** |
| Hero text never appears | Confirm the video URL is accessible (no 403/404); the `loadedmetadata` event depends on the video loading |
| CV download 404 | Add `cv.pdf` to `static/` and commit (or upload via Vercel Files tab) |
| Custom domain not working | Check DNS propagation (can take up to 48 hrs); verify CNAME record points to `cname.vercel-dns.com` |
| Old content still showing after push | Vercel caches aggressively — do a hard refresh (Cmd+Shift+R) or wait ~30s for CDN invalidation |
