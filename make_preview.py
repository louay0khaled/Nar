from pathlib import Path
import math
import os
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

W, H, FPS = 1920, 1080, 24
OUTPUT = "Nar-Preview.mp4"
DARK = (5, 10, 22)
PURPLE = (166, 147, 255)
WHITE = (246, 245, 255)
MUTED = (190, 191, 211)

files = sorted(Path(".").glob("Screenshot_*.jpg"))
if len(files) < 16:
    raise SystemExit(f"Expected 16 uploaded screenshots; found {len(files)}")

def font_path(bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    raise SystemExit("Arabic font not found. Install fonts-noto-core.")

_FONT_CACHE = {}
def get_font(size, bold=False):
    key = (size, bold)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(font_path(bold), size)
    return _FONT_CACHE[key]

def text_width(draw, text, font):
    try:
        return draw.textlength(text, font=font, direction="rtl", language="ar")
    except Exception:
        return draw.textlength(text, font=font)

def wrap_rtl(text, font, max_width):
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if current and text_width(probe, trial, font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]

def draw_rtl(draw, text, xy, font, fill, max_width, line_gap=14, max_lines=4):
    x, y = xy
    lines = wrap_rtl(text, font, max_width)[:max_lines]
    for line in lines:
        try:
            draw.text((x, y), line, font=font, fill=fill, anchor="ra", direction="rtl", language="ar")
        except Exception:
            draw.text((x, y), line, font=font, fill=fill, anchor="ra")
        y += font.size + line_gap
    return y, len(lines)

def make_background(im):
    bg = ImageOps.fit(im.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(34))
    tint = Image.new("RGB", (W, H), DARK)
    bg = Image.blend(bg, tint, 0.88).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-500, 240, 1120, 1680), fill=(75, 65, 170, 75))
    gd.ellipse((950, -600, 2300, 500), fill=(27, 100, 153, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(145))
    bg = Image.alpha_composite(bg, glow)
    overlay = Image.new("RGBA", (W, H), (2, 5, 14, 48))
    return Image.alpha_composite(bg, overlay).convert("RGB")

_BACKGROUND_CACHE = {}
def background_for(im):
    key = id(im)
    if key not in _BACKGROUND_CACHE:
        _BACKGROUND_CACHE[key] = make_background(im)
    return _BACKGROUND_CACHE[key]

def rounded_image(im, size, radius):
    im = ImageOps.fit(im.convert("RGB"), size, method=Image.Resampling.LANCZOS)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return im, mask

def paste_card(canvas, source, p):
    # Subtle Ken Burns zoom while keeping the full phone screenshot legible.
    zoom = 0.985 + 0.025 * p
    target_h = int(820 * zoom)
    target_w = int(source.width * target_h / source.height)
    x = 1640 - target_w // 2
    y = 535 - target_h // 2 + int(5 * math.sin(p * math.pi))
    screen, mask = rounded_image(source, (target_w, target_h), 26)
    margin = 36
    sh = Image.new("RGBA", (target_w + margin * 2, target_h + margin * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.rounded_rectangle((margin - 3, margin - 3, margin + target_w + 3, margin + target_h + 3),
                         radius=37, fill=(0, 0, 0, 190))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    canvas = canvas.convert("RGB")
    canvas.paste(sh, (x - margin, y - margin), sh)
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x - 7, y - 7, x + target_w + 7, y + target_h + 7),
                        radius=34, fill=(13, 18, 34), outline=(151, 132, 255), width=3)
    canvas.paste(screen, (x, y), mask)
    return canvas

def build_slide(source, title, subtitle, note, step_label, progress, p, kind="step"):
    bg = background_for(source)
    canvas = paste_card(bg.copy(), source, p).convert("RGBA")
    d = ImageDraw.Draw(canvas)

    # Restrained technical framing and a premium navy/lavender palette.
    d.rounded_rectangle((82, 72, 365, 126), radius=25,
                        fill=(16, 23, 42, 238), outline=(141, 126, 244, 190), width=2)
    d.text((105, 87), "NAR  /  VIDEO LAB", font=get_font(20, True), fill=(208, 202, 255, 255))
    d.line((100, 164, 1330, 164), fill=(112, 102, 164, 140), width=2)
    d.ellipse((99, 158, 111, 170), fill=(*PURPLE, 255))

    if kind == "intro":
        d.rounded_rectangle((100, 245, 395, 294), radius=18, fill=(126, 104, 232, 50),
                            outline=(165, 147, 255, 170), width=2)
        d.text((125, 255), "ANDROID INSTALL GUIDE", font=get_font(18, True), fill=(215, 207, 255, 255))
    elif kind == "outro":
        d.rounded_rectangle((100, 245, 410, 294), radius=18, fill=(126, 104, 232, 50),
                            outline=(165, 147, 255, 170), width=2)
        d.text((125, 255), "PREVIEW  /  01", font=get_font(18, True), fill=(215, 207, 255, 255))
    else:
        d.rounded_rectangle((100, 245, 315, 294), radius=18, fill=(126, 104, 232, 50),
                            outline=(165, 147, 255, 170), width=2)
        d.text((124, 255), step_label, font=get_font(18, True), fill=(215, 207, 255, 255))

    title_font = get_font(68 if kind != "intro" else 74, True)
    next_y, title_lines = draw_rtl(d, title, (1320, 350), title_font, WHITE, 1160, 15, 3)
    d.rounded_rectangle((100, next_y + 12, 235, next_y + 19), radius=3, fill=(*PURPLE, 255))
    sub_y = next_y + 58
    sub_y, _ = draw_rtl(d, subtitle, (1320, sub_y), get_font(33, False), (218, 219, 235, 255), 1120, 12, 3)
    note_y = sub_y + 30
    draw_rtl(d, note, (1320, note_y), get_font(25, False), (174, 177, 200, 255), 1100, 10, 2)

    # Progress track and editorial footer.
    d.rounded_rectangle((100, 924, 1325, 932), radius=4, fill=(57, 61, 83, 230))
    fill_w = max(8, int(1225 * progress))
    d.rounded_rectangle((100, 924, 100 + fill_w, 932), radius=4, fill=(*PURPLE, 255))
    d.text((100, 955), "COMMAND & CONQUER  •  GENERALS ZERO HOUR", font=get_font(18, True), fill=(177, 179, 201, 255))
    d.text((1325, 955), "16:9  /  1080p  /  SILENT TEST", font=get_font(17, True), fill=(148, 150, 175, 255), anchor="ra")

    return canvas.convert("RGB")

# The uploaded screenshots are already time-stamped, so sorting preserves their capture order.
steps = [
    (0, "افهم الملفات المطلوبة", "توضح اللقطة إصدار التطبيق والأرشيف المستخدم في الشرح.", "استخدم ملفات تملك حق استخدامها، ولا تعِد نشر ملفات اللعبة دون إذن."),
    (1, "نزّل الأرشيف بالكامل", "تحقّق من اكتمال التنزيل وسلامة الملف قبل بدء الاستخراج.", "حجم الأرشيف كبير؛ اترك مساحة كافية على الهاتف."),
    (2, "جهّز مدير الملفات", "يمكنك استخدام ZArchiver أو مدير الملفات المتوفر على جهازك.", "احتفظ بالملفات في مسار يسهل الوصول إليه."),
    (3, "تحقّق من محتويات المجلد", "تأكد من وجود الأرشيف والمجلدات المطلوبة قبل فتح التطبيق.", "لا تحذف الملفات الأصلية حتى تتأكد من نجاح التجربة."),
    (4, "استخرج الملفات", "من قائمة الأرشيف اختر «استخراج هنا» أو حدد مجلدًا واضحًا.", "انتظر حتى تنتهي عملية الاستخراج."),
    (5, "افتح تطبيق GeneralsZH", "اختر Zero Hour من الشاشة الرئيسية للتطبيق.", "تختلف أسماء الخيارات حسب إصدار التطبيق."),
    (6, "حدّد مجلد اللعبة", "انتقل إلى مجلد اللعبة المستخرج ثم اختر «استخدام هذا المجلد».", "لا تختر مجلدًا فارغًا أو مجلدًا أعلى من مجلد اللعبة."),
    (7, "ضبط الرسوميات", "عدّل معدل المحاكاة وخيار الرسومات بناءً على استقرار جهازك.", "إذا واجهت بطئًا، جرّب إعدادات أخف."),
    (9, "اضبط حجم الواجهة", "اجعل حجم النص والواجهة مناسبًا لشاشة هاتفك.", "يمكنك الرجوع إلى الإعدادات وتغييرها لاحقًا."),
    (10, "اختر لغة النصوص", "حدد العربية إذا كانت حزمة اللغة المطلوبة متوفرة لديك.", "لغة واجهة التطبيق ليست بالضرورة لغة نصوص اللعبة."),
    (11, "راجع حجم القائمة", "طبّق حجم القائمة والواجهة ثم ارجع إلى الشاشة الرئيسية.", "احتفظ بإعدادات مريحة للقراءة والتحكم."),
    (12, "خيارات اللعب عبر الإنترنت", "هذه الإعدادات إضافية، وليست ضرورية للعب الفردي.", "لا تفعّل خيارات الشبكة إلا عند الحاجة."),
    (13, "حساب اللعب الجماعي", "تظهر هنا تعليمات الحساب وتسجيل الدخول إلى الخدمة.", "اتبع تعليمات الخدمة الرسمية عند استخدام اللعب الجماعي."),
    (14, "بيانات اللعب الجماعي", "قد تتطلب المباريات الشبكية حزمة بيانات إضافية من مصدر المشروع.", "هذه الخطوة اختيارية إذا كان هدفك اللعب المحلي فقط."),
    (15, "تحقّق من حالة الجاهزية", "راجع الحالة المعروضة داخل التطبيق قبل تجربة اللعب.", "الصور الحالية لا تتضمن تسجيلًا فعليًا من داخل المباراة."),
]

loaded = {}
for idx, path in enumerate(files):
    loaded[idx] = Image.open(path).convert("RGB")

scenes = []
hero = loaded[5]
scenes.append(("intro", hero, "جنرالز زيرو آور على أندرويد", "دليل التثبيت خطوة بخطوة", "معاينة مونتاج تجريبية من الصور المرفوعة — بدون تعليق صوتي.", "INTRO", 0.0, 2.8))
for n, (img_idx, title, subtitle, note) in enumerate(steps, start=1):
    scenes.append(("step", loaded[img_idx], title, subtitle, note, f"STEP {n:02d}", n / (len(steps) + 1), 2.15))
scenes.append(("outro", loaded[15], "هذه معاينة أولى", "لإكمال النسخة النهائية، أرسل تعليقك الصوتي ولقطة لعب فعلية.", "سأضيف إيقاعًا أدق وانتقالات متزامنة مع الصوت عندما تتوفر المواد.", "OUTRO", 1.0, 3.0))

def main():
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{W}x{H}",
        "-framerate", str(FPS), "-i", "-", "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUTPUT,
    ]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    total_frames = sum(round(scene[-1] * FPS) for scene in scenes)
    current_frame = 0
    try:
        for scene_no, (kind, src, title, subtitle, note, label, progress, duration) in enumerate(scenes):
            frame_count = round(duration * FPS)
            for frame_no in range(frame_count):
                p = frame_no / max(1, frame_count - 1)
                frame = build_slide(src, title, subtitle, note, label,
                                    min(1.0, max(0.0, progress)), p, kind)
                # Fade at each cut; gentle motion comes from the portrait-card zoom.
                fade = min(1.0, p / 0.12, (1.0 - p) / 0.12)
                fade = max(0.0, fade)
                if fade < 0.999:
                    black = Image.new("RGB", (W, H), (0, 0, 0))
                    frame = Image.blend(black, frame, fade)
                proc.stdin.write(frame.tobytes())
                current_frame += 1
            print(f"Rendered scene {scene_no + 1}/{len(scenes)}", flush=True)
        proc.stdin.close()
    except Exception:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        raise
    code = proc.wait()
    if code != 0:
        raise SystemExit(f"ffmpeg exited with status {code}")
    print(f"Created {OUTPUT} ({Path(OUTPUT).stat().st_size:,} bytes; {total_frames / FPS:.1f} seconds)")

if __name__ == "__main__":
    main()
