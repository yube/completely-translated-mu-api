import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import threading

BEGIN_PAG = 1
END_PAG = 15
if END_PAG is None:
    END_PAG = BEGIN_PAG + 5

session = requests.Session()
headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

API_URL = "https://api.mangaupdates.com/v1"

print_lock = threading.Lock()


def get_releases(page):
    url = f"{API_URL}/releases/days"
    response = session.get(
        url,
        headers=headers,
        params={"page": page, "include_metadata": "true"}
    )
    response.raise_for_status()
    return response.json()


def get_series_ids(data):
    ids = []

    for item in data.get("results", []):
        record = item.get("record", {})
        series = item.get("metadata", {}).get("series", {})

        volume = str(record.get("volume") or "")
        chapter = str(record.get("chapter") or "")

        if "(end)" in f"{volume} {chapter}".lower():
            series_id = series.get("series_id")

            if series_id:
                ids.append({
                    "id": series_id,
                    "date": record.get("release_date")
                })

    return ids


def get_info(series):
    series_id = series["id"]

    try:
        url = f"{API_URL}/series/{series_id}"
        response = session.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        title = data.get("title")
        link = data.get("url")
        image = data.get("image", {}).get("url", {}).get("original")
        completed = data.get("completed")
        series_type = data.get("type")
        status = data.get("status")

        if series_type in {"Manhwa", "Manhua", "Doujinshi", "Novel"}:
            return None

        if not completed or "Oneshot" in str(status):
            return None

        if not image:
            return None

        with print_lock:
            print(f"{title}: {link}")

        return {
            "name": title,
            "link": link,
            "image": image,
            "date": series["date"]
        }

    except Exception as e:
        print(f"Error fetching series {series_id}: {e}")
        return None


def resize_image(img, max_height=218, max_width=160):
    width, height = img.size

    if height > max_height:
        new_height = max_height
        aspect_ratio = width / height
        new_width = int(new_height * aspect_ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    width, height = img.size

    if width > max_width:
        new_width = max_width
        aspect_ratio = height / width
        new_height = int(new_width * aspect_ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    return img


def make_blank_image(size=(150, 218), text="No Image"):
    img = Image.new('RGB', size, color=(200, 200, 200))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    position = (
        (size[0] - text_width) // 2,
        (size[1] - text_height) // 2
    )

    draw.text(position, text, fill=(50, 50, 50), font=font)
    return img


def download_image(series):
    try:
        response = session.get(series["image"], timeout=10)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert('RGB')
    except Exception as e:
        print(f"Failed to load image for {series['name']}: {e}")
        img = make_blank_image()

    img = resize_image(img)
    return img, series["name"]


def prep_images(info):
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(tqdm(
            executor.map(download_image, info),
            total=len(info),
            desc="Downloading images"
        ))

    images, titles = zip(*results)
    return list(images), list(titles)


def break_text(text, max_length=18):
    if len(text) <= max_length:
        return [text]

    lines = []
    current_line = ""

    for word in text.split(" "):
        if len(current_line) + len(word) + 1 > max_length:
            lines.append(current_line)
            current_line = ""

        current_line += word + " "

    lines.append(current_line)
    return lines


def truncate_text(text, max_length=50):
    return text[:45] + "..." if len(text) > max_length else text


def create_chart(images, titles, first_date, last_date, images_per_row=10):
    images = [img for img in images if img is not None]

    if len(images) == 0:
        print("No images to create a chart.")
        return

    img_width = max(img.size[0] for img in images)
    img_height = max(img.size[1] for img in images)

    text_height = 53
    title_height = 60
    new_img_height = img_height + text_height

    num_rows = (len(images) - 1) // images_per_row + 1
    chart_width = img_width * min(images_per_row, len(images))
    chart_height = new_img_height * num_rows + title_height

    chart = Image.new(
        mode="RGB",
        size=(chart_width, chart_height),
        color=(255, 255, 255)
    )

    draw = ImageDraw.Draw(chart)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        title_font = ImageFont.truetype("arial.ttf", 24)
    except IOError:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    title_text = f"Series completed from {last_date} to {first_date}"

    bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = bbox[2] - bbox[0]
    title_position = ((chart_width - title_width) // 2, 10)

    draw.text(title_position, title_text, font=title_font, fill=(0, 0, 0))

    for i, (img, title) in enumerate(zip(images, titles)):
        row = i // images_per_row
        col = i % images_per_row

        x_offset = col * img_width
        y_offset = row * new_img_height + title_height

        chart.paste(img, (x_offset, y_offset))

        lines = break_text(truncate_text(title))
        bbox = font.getbbox("A")
        line_height = bbox[3] - bbox[1]
        line_spacing = line_height + 2

        for j, line in enumerate(lines):
            text_y = y_offset + img_height + j * line_spacing
            draw.text(
                (x_offset, text_y),
                line.strip(),
                font=font,
                fill=(0, 0, 0)
            )

    chart.save("chart.png")
    print("Chart saved as chart.png")


# Get ended series

ended_series = {}
date_elements = []

for page_num in range(BEGIN_PAG, END_PAG + 1):
    print(f"Fetching page {page_num}...")

    try:
        data = get_releases(page_num)
    except Exception as e:
        print(f"Error fetching page {page_num}: {e}")
        continue

    if not data.get("results"):
        break

    for item in data["results"]:
        date = item.get("record", {}).get("release_date")

        if date and date not in date_elements:
            date_elements.append(date)

    ids = get_series_ids(data)

    for series in ids:
        if series["id"] not in ended_series:
            ended_series[series["id"]] = series


ids = list(ended_series.values())

print(f"Found {len(ids)} unique ended series.")

# Get series information

with ThreadPoolExecutor(max_workers=8) as executor:
    results = list(tqdm(
        executor.map(get_info, ids),
        total=len(ids),
        desc="Processing series"
    ))

ended_series = [series for series in results if series is not None]

print(f"Matching series: {len(ended_series)}")

# Download covers and create chart

if ended_series:
    images, titles = prep_images(ended_series)

    first_date = date_elements[0] if date_elements else "Unknown"
    last_date = date_elements[-1] if date_elements else "Unknown"

    create_chart(images, titles, first_date, last_date)
else:
    print("No matching series found.")
