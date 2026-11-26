
import requests
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import queue
import os
import sys


API_URL = "https://api.mangaupdates.com/v1"

session = requests.Session()
headers = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

updates = queue.Queue()


# ================= API =================

def get_releases(page):
    response = session.get(
        f"{API_URL}/releases/days",
        headers=headers,
        params={"page": page, "include_metadata": "true"},
        timeout=20
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
        response = session.get(
            f"{API_URL}/series/{series_id}",
            headers=headers,
            timeout=20
        )
        response.raise_for_status()
        data = response.json()

        title = data.get("title")
        link = data.get("url")
        completed = data.get("completed")
        series_type = data.get("type")
        status = data.get("status")

        if series_type in {"Manhwa", "Manhua", "Doujinshi", "Novel"}:
            return None

        if not completed or "Oneshot" in str(status):
            return None

        image_data = data.get("image", {}).get("url", {})
        image = image_data.get("original") or image_data.get("thumb")

        if not image:
            return None

        return {
            "name": title,
            "link": link,
            "image": image,
            "date": series["date"]
        }

    except Exception as e:
        print(f"Error fetching series {series_id}: {e}")
        return None


# ================= IMAGES =================

def resize_image(img, max_height=218, max_width=160):
    width, height = img.size

    if height > max_height:
        new_height = max_height
        new_width = int(width * new_height / height)
        img = img.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

    width, height = img.size

    if width > max_width:
        new_width = max_width
        new_height = int(height * new_width / width)
        img = img.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )

    return img


def make_blank_image(size=(150, 218), text="No Image"):
    img = Image.new('RGB', size, color=(200, 200, 200))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)

    position = (
        (size[0] - (bbox[2] - bbox[0])) // 2,
        (size[1] - (bbox[3] - bbox[1])) // 2
    )

    draw.text(position, text, fill=(50, 50, 50), font=font)

    return img


def download_image(series):
    try:
        response = session.get(series["image"], timeout=20)
        response.raise_for_status()

        img = Image.open(
            BytesIO(response.content)
        ).convert('RGB')

    except Exception as e:
        print(f"Failed to load {series['name']}: {e}")
        img = make_blank_image()

    return resize_image(img), series["name"]


def prep_images(info):
    images = []
    titles = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        for i, result in enumerate(executor.map(download_image, info)):
            img, title = result

            images.append(img)
            titles.append(title)

            updates.put((
                "progress",
                70 + (i + 1) / len(info) * 25,
                f"Downloading covers: {i + 1}/{len(info)}"
            ))

    return images, titles


# ================= CHART =================

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


def create_chart(images, titles, first_date, last_date):
    if not images:
        raise Exception("No images to create a chart.")

    images_per_row = 10

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

    title_position = (
        (chart_width - (bbox[2] - bbox[0])) // 2,
        10
    )

    draw.text(
        title_position,
        title_text,
        font=title_font,
        fill=(0, 0, 0)
    )

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

    folder = os.path.dirname(
        sys.executable if getattr(sys, "frozen", False) else __file__
    )

    path = os.path.join(folder, "chart.png")

    chart.save(path)

    return path


# ================= GENERATOR =================

def generate_chart(start_page, end_page):
    ended_series = {}
    date_elements = []

    # Get ended series

    for page_num in range(start_page, end_page + 1):
        updates.put((
            "progress",
            (page_num - start_page + 1) / (end_page - start_page + 1) * 20,
            f"Fetching release page {page_num}..."
        ))

        data = get_releases(page_num)

        if not data.get("results"):
            break

        for item in data["results"]:
            date = item.get("record", {}).get("release_date")

            if date and date not in date_elements:
                date_elements.append(date)

        for series in get_series_ids(data):
            if series["id"] not in ended_series:
                ended_series[series["id"]] = series

    ids = list(ended_series.values())

    if not ids:
        raise Exception("No ended series found in these pages.")

    # Get series information

    results = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        for i, result in enumerate(executor.map(get_info, ids)):
            results.append(result)

            updates.put((
                "progress",
                20 + (i + 1) / len(ids) * 50,
                f"Checking series: {i + 1}/{len(ids)}"
            ))

    ended_series = [
        series for series in results if series is not None
    ]

    if not ended_series:
        raise Exception("No matching series found.")

    # Download covers

    images, titles = prep_images(ended_series)

    # Create chart

    first_date = date_elements[0] if date_elements else "Unknown"
    last_date = date_elements[-1] if date_elements else "Unknown"

    path = create_chart(
        images,
        titles,
        first_date,
        last_date
    )

    updates.put(("done", path))


# ================= GUI =================

def start_generation():
    try:
        start_page = int(start_entry.get())
        end_page = int(end_entry.get())

        if start_page < 1 or end_page < start_page:
            raise ValueError

    except ValueError:
        messagebox.showerror(
            "Invalid pages",
            "Enter valid page numbers. The end page must be greater than or equal to the start page."
        )
        return

    generate_button.config(state="disabled")
    progress["value"] = 0

    status.config(text="Starting...")

    thread = threading.Thread(
        target=run_generator,
        args=(start_page, end_page),
        daemon=True
    )
    thread.start()


def run_generator(start_page, end_page):
    try:
        generate_chart(start_page, end_page)

    except Exception as e:
        updates.put(("error", str(e)))


def check_updates():
    try:
        while True:
            item = updates.get_nowait()

            if item[0] == "progress":
                progress["value"] = item[1]
                status.config(text=item[2])

            elif item[0] == "done":
                path = item[1]

                progress["value"] = 100
                status.config(text="Done! Opening chart...")

                generate_button.config(state="normal")

                if sys.platform == "win32":
                    os.startfile(path)

                elif sys.platform == "darwin":
                    import subprocess
                    subprocess.Popen(["open", path])

                else:
                    import subprocess
                    subprocess.Popen(["xdg-open", path])

            elif item[0] == "error":
                progress["value"] = 0
                status.config(text="Something went wrong.")
                generate_button.config(state="normal")

                messagebox.showerror("Error", item[1])

    except queue.Empty:
        pass

    root.after(100, check_updates)


# ================= WINDOW =================

root = tk.Tk()

root.title("MU Chart Generator")
root.geometry("420x280")
root.resizable(False, False)

root.configure(bg="#f0f0f0")

tk.Label(
    root,
    text="Enter release pages:",
    font=("Arial", 11, "bold"),
    bg="#f0f0f0"
).pack(pady=(20, 12))


# Page inputs

input_frame = tk.Frame(root, bg="#f0f0f0")
input_frame.pack()

tk.Label(
    input_frame,
    text="From:",
    bg="#f0f0f0"
).grid(row=0, column=0, padx=5)

start_entry = tk.Entry(
    input_frame,
    width=10,
    justify="center"
)
start_entry.grid(row=0, column=1, padx=5)
start_entry.insert(0, "1")

tk.Label(
    input_frame,
    text="To:",
    bg="#f0f0f0"
).grid(row=0, column=2, padx=5)

end_entry = tk.Entry(
    input_frame,
    width=10,
    justify="center"
)
end_entry.grid(row=0, column=3, padx=5)
end_entry.insert(0, "15")


# Progress bar

progress = ttk.Progressbar(
    root,
    length=340,
    mode="determinate",
    maximum=100
)
progress.pack(pady=(25, 15))


# Generate button

generate_button = tk.Button(
    root,
    text="Generate Chart",
    font=("Arial", 10),
    command=start_generation,
    width=16
)
generate_button.pack(pady=5)


# Status

status = tk.Label(
    root,
    text="Ready",
    bg="#f0f0f0",
    font=("Arial", 10)
)
status.pack(pady=15)


root.after(100, check_updates)

root.mainloop()
