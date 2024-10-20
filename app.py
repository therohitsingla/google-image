from flask import Flask, render_template, request, jsonify
import os
import io
import requests
import zipfile
from PIL import Image
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv  # Add this line

load_dotenv()  # Add this line

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def download_images(query, limit):
    app.logger.info(f"Downloading images for query: {query}, limit: {limit}")
    
    search_url = f"https://www.google.com/search?q={query}&tbm=isch"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
    }
    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        app.logger.error(f"Failed to retrieve images. Status code: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    image_tags = soup.find_all("img", limit=limit)

    downloaded_images = []
    
    for i, img_tag in enumerate(image_tags):
        img_url = img_tag.get("src")
        
        # Check if URL is valid and starts with 'http' or 'https'
        if not img_url or not img_url.startswith("http"):
            app.logger.error(f"Invalid URL for image {i+1}: {img_url}")
            continue
        
        try:
            # Sometimes the image is a thumbnail; we need to find the full resolution version.
            # Search for the larger image (if possible)
            larger_img_url = img_tag.get("data-iurl") or img_url  # Use 'data-iurl' if available

            # Try downloading the larger image
            img_data = requests.get(larger_img_url).content
            if len(img_data) < 100000:  # If the image size is very small, continue
                app.logger.warning(f"Image {i+1} is too small. Skipping.")
                continue

            downloaded_images.append((f"{query}_{i+1}.jpg", img_data))  # Store filename and data
            app.logger.info(f"Downloaded image {i+1} (size: {len(img_data)} bytes)")
        except Exception as e:
            app.logger.error(f"Could not download image {i+1}: {e}")

    app.logger.info(f"Downloaded {len(downloaded_images)} images")
    return downloaded_images


def create_zip(images, query):
    app.logger.info(f"Creating zip for query: {query}")
    
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for filename, img_data in images:
            zip_file.writestr(filename, img_data)  # Write image data directly to zip

    zip_buffer.seek(0)
    
    app.logger.info(f"Zip file created for query: {query}, size: {len(zip_buffer.getvalue())} bytes")
    return zip_buffer.getvalue()

def send_email(email, zip_data, query):
    app.logger.info(f"Sending email to: {email}")
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')

    if not sender_email or not sender_password:
        app.logger.error("Sender email or password not set in environment variables.")
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = f"Your downloaded images for {query}"

    body = "Please find attached the images you requested."
    msg.attach(MIMEText(body, 'plain'))

    # Check if zip_data is None or empty
    if zip_data is None or len(zip_data) == 0:
        app.logger.error("No zip data to attach to email.")
        return False

    try:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(zip_data)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={query}_images.zip",
        )
        msg.attach(part)

        # Log the message content type
        app.logger.info(f"Email message content type: {msg.get_content_type()}")
        
        # Send the email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        app.logger.info("Email sent successfully")
        return True
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        return False

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        search_query = request.form['search_query']
        image_limit = int(request.form['image_limit'])
        email = request.form['email']

        images = download_images(search_query, image_limit)
        if not images:
            return jsonify({'error': 'Failed to download images. Please try again.'})

        zip_data = create_zip(images, search_query)  # Create zip data

        # Log the zip data length
        app.logger.info(f"Zip data length: {len(zip_data) if zip_data else 'None'}")
        
        if zip_data is None or len(zip_data) == 0:
            return jsonify({'error': 'Failed to create zip file. Please try again.'})

        if send_email(email, zip_data, search_query):
            return jsonify({'success': 'Images have been sent to your email!'})
        else:
            return jsonify({'error': 'Failed to send email. Please try again.'})

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
