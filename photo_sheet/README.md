# Passport Photo Sheet

Crops a photo to the size a form or passport office asks for, entirely in your browser. The photo
never leaves your computer or phone: nothing is uploaded, and no website ever sees the picture.

Two things come out of it:

- **One JPEG** (the usual photo file type, name ending .jpg) at the exact pixel size and under the
  file-size limit an online form states (for example "600 x 600 px, max 200 KB").
- **A print sheet**: a 4 x 6 inch picture (1200 x 1800 px at 300 dpi) holding six copies of the
  photo with thin cut lines, to order as an ordinary 4 x 6 print at a store kiosk.

## The easy way

Open `photo_sheet/photo_sheet.html` from the Start here page (`index.html`) or double-click the
file. It opens in your browser (Chrome, Edge, Safari, Firefox). No install, no internet needed.

1. Press the big **Try it with a drawn face** button (this page's version of the "Try it with
   example data" button). It loads a drawn test face (an oval, not a person), picks the US 2 x 2
   inch size and makes the finished picture straight away (shown under **Save one picture**, lower
   down the page), so you can see what the page does.
2. Press **Choose photo** and pick your own picture from your camera roll or a folder. Pick the
   size the form asks for from the list under **2. Size** (the page calls a ready-made size a
   preset), then drag the picture into place and pinch or scroll to zoom. For the US size, fit the
   head between the two ovals and the eyes in the shaded band.
3. Press **Save one picture** (type the pixel size and the KB limit the form states first) or
   **Make print sheet**. The result is shown on the page as a picture: press and hold (phone) or
   right-click (PC) the picture and choose Save. A copy may also land in your Downloads folder. If
   no download appears (phone downloads blocked, or the online copy), press and hold the picture on
   the page and choose Save.

### Using it step by step

1. **Choose photo** and pick a picture from your camera or gallery. Phone photos that are stored
   sideways are turned upright automatically. (To try the page without a real photo, press
   **Try it with a drawn face**, which loads the drawn test face.)
2. Pick a **preset**: US 2x2 in, 35x45 mm, a square form photo, or Custom (type width and height in
   mm or px, and the dpi). The page shows the size in mm and in pixels.
3. **Drag** the picture to position it; **pinch** or use the **mouse wheel** (or the + and - buttons)
   to zoom. For the US preset, fit the head between the two ovals and the eyes in the shaded band.
   Brightness can be nudged; a grayscale box exists for forms that accept black and white.
4. Either:
   - **Save one picture**: type the pixel size and the KB limit the form states, press the button. The page
     tells you the final size, for example "Made 600 x 600 px, 143 KB at JPEG quality 0.80 (1.00 is
     best; the page lowers it only until the file fits under your KB limit), under the 200 KB cap."
     If the typed
     size is a different shape from the preset (say 600 x 600 for the 35 x 45 mm preset), the page
     trims the long side equally and says how many pixels went; to see exactly what will be saved,
     pick Custom, choose px and type that size.
   - **Make print sheet**: pick 6 per sheet (passport sizes) or 2 per sheet (bigger sizes), press
     the button, and send the PNG (a picture file type that loses nothing) to a kiosk as a plain
     4 x 6 print. Cut along the lines.
5. Go through the **Before you submit** checklist on the page.

Saved files land in your browser's download folder. On iPhone the file may open in a new tab
instead: tap **Share**, then **Save Image**.

### Opening it on a phone

- **Android (Chrome):** use the online link you were given, or copy the file to the phone and open
  it from the Files app, or share it to yourself by email and tap it.
- **iPhone:** the easiest route is the online link you were given, opened in Safari. The Files app only previews a page: the buttons, sound and moving parts do nothing there. If you have the file on the phone, try Share > **Open in Safari**; if that is not offered, use the online link. Or use the page on a computer and send the saved JPEG to the phone (AirDrop, email,
  or a shared folder).

## What the numbers mean

- **mm and px.** Offices state sizes in millimetres or inches; online forms state pixels (px, the
  dots a screen picture is made of). The link between them is the dpi (dots per inch):
  `pixels = mm x dpi / 25.4`. At the usual 300 dpi, 2 x 2 in = 50.8 x 50.8 mm = 600 x 600 px, and
  35 x 45 mm = 413 x 531 px (rounded to whole pixels).
- **Head guide (US preset).** The two ovals are 25 mm and 35 mm tall (1 in to 1 3/8 in), which is
  about 49% to 69% of the 50.8 mm photo height; the shaded band marks eye height 28.6 to 34.9 mm
  (1 1/8 to 1 3/8 in) from the bottom edge, and the dashed line is the middle of that band. The
  ovals are centred on that line and drawn 0.72 as wide as they are tall, a rough face shape, so
  judge by height. Other presets have no official rule in the page because it differs by country: they
  draw a border, a centre line and one faint dashed oval (head about 70-80% of the photo height) labelled
  "rough aid; the issuing body decides". Centre the face and leave space above the head.
- **Max KB and quality.** Forms cap the upload size (KB = kilobyte; 1 KB = 1024 bytes). A JPEG gets
  smaller as its quality setting drops, so the page saves at quality 0.92 and, if the file is over
  the cap, tries again at 0.88, 0.84, and so on down to 0.32 (sixteen steps), stopping at the first
  size that fits. It reports the quality used. If even 0.32 is too big, it says so; then type a
  smaller pixel size.
- **Print sheet.** 4 x 6 in at 300 dpi is 1200 x 1800 px. 2x2 in copies (600 px) fit exactly two
  across and three down. 35 x 45 mm copies (413 x 531 px) fit the same 2 x 3 grid with a margin
  around it. The sheet is a PNG so nothing is lost before printing; cut lines are 1 px grey.
- **Brightness** is a plain multiplier on every pixel (120% = each colour value times 1.2). It is the
  only edit the page makes besides cropping and optional grayscale.

## Before you submit

Plain, light, even background. Neutral expression, eyes open, mouth closed. Head size inside the
guide with the whole head and top of the shoulders visible. No glasses glare (many offices now
want no glasses at all). No hat unless worn for religious reasons. Recent, in colour unless the
form says otherwise. No filters.

The guides help; the issuing body decides. Read the rules of the office or form you are sending
the photo to.

## Limits

- No background removal, no face detection, no red-eye fix. It crops, brightens and resizes only.
- Guides are general guidance, not the rules of any specific office; nothing here is a compliance
  check or a guarantee that a photo will be accepted.
- Output quality is browser-dependent: each browser has its own JPEG encoder, so the same quality
  setting gives slightly different file sizes in Chrome, Safari and Firefox, and the "quality" number
  is only meaningful within one browser. Pixel sizes are exact everywhere.
- Formats are whatever your browser can open. JPEG and PNG work everywhere; HEIC photos from an
  iPhone open in Safari and may not open in Chrome on Windows (export as JPEG first).
- Very large photos (over about 20 megapixels) may be slow on an old phone.
- A small original is enlarged, not refused: if the part inside the crop box has fewer pixels than
  the size you typed, the saved JPEG will look soft and the page says so. Forms often reject blurry
  photos, so start from the biggest original you have.
- The print sheet assumes the kiosk prints a 4 x 6 at true size. Some kiosks trim a little from
  the edges ("full bleed"); the grid is centred so the cut lines near the edge survive, but check
  one print before ordering many.
- Tested by hand in a browser (and with an automated headless browser when built). The pytest checks
  cover only the preset maths, the sheet grid, the embedded data and the page text; EXIF rotation
  (the "which way up" note a phone stores in a photo) and JPEG compression happen inside the browser
  and are not tested by pytest.
- Only the name of the preset you last picked is remembered (in the browser's local storage).

## Where the rules/figures come from

- 2 x 2 in photo, head height 1 to 1 3/8 in (25 to 35 mm), eyes 1 1/8 to 1 3/8 in from the bottom:
  the US Department of State's published photo-composition guidance, as repeated by many photo
  services. Verify with the issuing body.
- 35 x 45 mm: a common international passport/visa size. Head-size rules differ by country, so the
  page draws only a faint rough-aid oval (head about 70-80% of the height). Verify with the issuing body.
- 300 dpi and the 4 x 6 in sheet: common print-lab conventions, not a rule.
- 25.4 mm = 1 inch (exact).

All figures are labelled "verify with the issuing body" in `photo_sheet/presets.json`, which is the
one place the numbers live. Rules change; check the current requirements of the office or form.

## Advanced: the command-line version

Optional helper commands (Python 3.11 or newer, nothing to install; not needed to use the page).
On Windows type `python` or `py` where these say `python3`. Open a terminal (the text window where you type commands: on Windows search the Start menu for Command Prompt or PowerShell; on a Mac open Terminal) in the project folder (the one that contains
`photo_sheet`) and run them from there.

- `python3 -m photo_sheet presets` prints the preset table and how many copies fit on a sheet.
- `python3 -m photo_sheet testface samples/photo_sheet_test_face.png` writes the synthetic test
  picture (a drawn oval) used by the checks.
- `python3 -m photo_sheet embed` copies `photo_sheet/presets.json` into the page. Edit the JSON
  (the bracketed text format that file is written in) to add a preset (name, width_mm, height_mm, dpi, optional head and eye figures, source), run this,
  and the page picks it up. The pixel sizes are recomputed for you. An empty list, a repeated name,
  a missing source line, a missing or non-positive size, or only one of the two head (or eye)
  figures, is refused with a message naming the preset and the field.

To run the checks: `pip install pytest` once, then `python3 -m pytest tests/test_photo_sheet.py -q`.
