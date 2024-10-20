from flask import Flask, render_template, request, jsonify
import os
import io
from PIL import Image
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import zipfile

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

UPLOAD_FOLDER = 'downloads'
ALLOWED_EXTENSIONS = {'zip'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # Set up logging
# logging.basicConfig(level=logging.DEBUG)
# handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
# handler.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# app.logger.addHandler(handler)


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
        try:
            img_data = requests.get(img_url).content
            img_io = io.BytesIO(img_data)  # Store the image in memory instead of disk
            downloaded_images.append(img_io)
            app.logger.info(f"Downloaded image {i+1}")
        except Exception as e:
            app.logger.error(f"Could not download image {i+1}: {e}")
    
    app.logger.info(f"Downloaded {len(downloaded_images)} images")
    return downloaded_images

def create_zip(images, query):
    app.logger.info(f"Creating zip file for query: {query}")
    zip_io = io.BytesIO()  # Create a BytesIO object to store the zip data
    try:
        with zipfile.ZipFile(zip_io, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for i, img_io in enumerate(images):
                filename = f"{query}_{i+1}.jpg"
                zipf.writestr(filename, img_io.getvalue())
        zip_io.seek(0)  # Reset pointer to the start of the BytesIO object
        app.logger.info("Zip file created in memory")
        return zip_io
    except Exception as e:
        app.logger.error(f"Error creating zip file: {e}")
        return None

def send_email(email, zip_io, query):
    app.logger.info(f"Sending email to: {email}")
    sender_email = os.environ.get('SENDER_EMAIL')
    sender_password = os.environ.get('SENDER_PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = email
    msg['Subject'] = f"Your downloaded images for {query}"

    body = "Please find attached the images you requested."
    msg.attach(MIMEText(body, 'plain'))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(zip_io.getvalue())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f"attachment; filename={query}_images.zip",
    )
    msg.attach(part)

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

        images = download_images(search_query, image_limit)
        if not images:
            return jsonify({'error': 'Failed to download images. Please try again.'})

        zip_data = create_zip(images)
        if not zip_data:
            return jsonify({'error': 'Failed to create zip file. Please try again.'})

        if send_email(email, zip_data, search_query):
            return jsonify({'success': 'Images have been sent to your email!'})
        else:
            return jsonify({'error': 'Failed to send email. Please try again.'})

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
