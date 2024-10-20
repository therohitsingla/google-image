import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, flash, redirect, url_for
from werkzeug.utils import secure_filename
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import zipfile
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Set up logging
logging.basicConfig(level=logging.DEBUG)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

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
    
    download_folder = os.path.join(app.config['UPLOAD_FOLDER'], query)
    if not os.path.exists(download_folder):
        os.makedirs(download_folder)
    
    downloaded_images = []
    for i, img_tag in enumerate(image_tags):
        img_url = img_tag.get("src")
        try:
            img_data = requests.get(img_url).content
            filename = f"{query}_{i+1}.jpg"
            filepath = os.path.join(download_folder, filename)
            with open(filepath, "wb") as img_file:
                img_file.write(img_data)
            downloaded_images.append(filepath)
            app.logger.info(f"Downloaded image: {filepath}")
        except Exception as e:
            app.logger.error(f"Could not download image {i+1}: {e}")
    
    app.logger.info(f"Downloaded {len(downloaded_images)} images")
    return downloaded_images

def create_zip(images, query):
    app.logger.info(f"Creating zip file for query: {query}")
    zip_filename = f"{query}_images.zip"
    zip_filepath = os.path.join(app.config['UPLOAD_FOLDER'], zip_filename)
    try:
        with zipfile.ZipFile(zip_filepath, 'w') as zipf:
            for image in images:
                zipf.write(image, os.path.basename(image))
        app.logger.info(f"Zip file created: {zip_filepath}")
        return zip_filepath
    except Exception as e:
        app.logger.error(f"Error creating zip file: {e}")
        return None

def send_email(email, zip_file):
    app.logger.info(f"Sending email to: {email}")
    sender_email = "tikkipikkipikki@gmail.com"
    sender_password = "ylnf eggx vxnk yzrg"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = "Your downloaded images"

    body = "Please find attached the images you requested."
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with open(zip_file, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename*=UTF-8''{os.path.basename(zip_file)}",
        )
        msg.attach(part)
    except Exception as e:
        app.logger.error(f"Error attaching zip file: {e}")
        return False

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
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

        app.logger.info(f"Processing request - Query: {search_query}, Limit: {image_limit}, Email: {email}")

        images = download_images(search_query, image_limit)
        if not images:
            flash('Failed to download images. Please try again.', 'error')
            return redirect(url_for('index'))

        zip_file = create_zip(images, search_query)
        if not zip_file:
            flash('Failed to create zip file. Please try again.', 'error')
            return redirect(url_for('index'))

        if send_email(email, zip_file):
            flash('Images have been sent to your email!', 'success')
        else:
            flash('Failed to send email. Please try again.', 'error')

        # Clean up
        for image in images:
            try:
                os.remove(image)
                app.logger.info(f"Removed image: {image}")
            except Exception as e:
                app.logger.error(f"Error removing image {image}: {e}")

        try:
            os.remove(zip_file)
            app.logger.info(f"Removed zip file: {zip_file}")
        except Exception as e:
            app.logger.error(f"Error removing zip file {zip_file}: {e}")

        return redirect(url_for('index'))

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)