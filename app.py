import os
import boto3
from flask import Flask, request, render_template, redirect, url_for
from werkzeug.utils import secure_filename
from pprint import pformat
import base64

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

# Ensure the uploads directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Initialize AWS services using boto3
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')
dynamodb = boto3.resource('dynamodb')

# S3 bucket name

bucket_name = 'speechrekog'
# DynamoDB table name
table_name = 'iSHIP'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def upload_image_to_s3(file_path, bucket_name, object_name):
    try:
        s3.upload_file(file_path, bucket_name, object_name)
        print(f"Image {object_name} uploaded successfully.")
    except Exception as e:
        print(f"Error uploading image: {e}")

def compare_faces(source_image, target_image):
    try:
        response = rekognition.compare_faces(
            SourceImage={'S3Object': {'Bucket': bucket_name, 'Name': source_image}},
            TargetImage={'S3Object': {'Bucket': bucket_name, 'Name': target_image}}
        )
        for faceMatch in response['FaceMatches']:
            if faceMatch['Similarity'] > 90:  # You can adjust the similarity threshold
                return True
        return False
    except Exception as e:
        print(f"Error comparing faces: {e}")
        return False

def query_dynamodb(roll_number):
    table = dynamodb.Table(table_name)
    try:
        response = table.get_item(Key={'Roll Number': roll_number})
        if 'Item' in response:
            return response['Item']
        else:
            print("No matching record found in DynamoDB.")
            return None
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        return None

def find_matching_student(file_path):
    input_image_name = os.path.basename(file_path)
    upload_image_to_s3(file_path, bucket_name, input_image_name)

    # List all objects in the S3 bucket
    response = s3.list_objects_v2(Bucket=bucket_name)
    if 'Contents' in response:
        for obj in response['Contents']:
            student_image = obj['Key']
            if compare_faces(input_image_name, student_image):
                roll_number = os.path.splitext(student_image)[0]
                print(f"Match found: {roll_number}")

                # Query DynamoDB for the roll number
                record = query_dynamodb(roll_number)
                if record:
                    return roll_number, record
    return None, None

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        image_data = request.form['image_data']
        if image_data:
            # Decode the image data
            header, encoded = image_data.split(",", 1)
            data = base64.b64decode(encoded)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'captured_image.png')
            
            with open(file_path, 'wb') as f:
                f.write(data)

            roll_number, record = find_matching_student(file_path)
            if record:
                return render_template('result.html', roll_number=roll_number, record=pformat(record))
            else:
                return render_template('result.html', roll_number=None, record=None)
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    image_data = request.form['image_data']
    if image_data:
        # Decode the image data
        header, encoded = image_data.split(",", 1)
        data = base64.b64decode(encoded)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'captured_image.png')
        
        with open(file_path, 'wb') as f:
            f.write(data)

        roll_number, record = find_matching_student(file_path)
        if record:
            return render_template('result.html', roll_number=roll_number, record=pformat(record))
        else:
            return render_template('result.html', roll_number=None, record=None)
    return redirect(url_for('upload_file'))

if __name__ == "__main__":
    app.run(debug=True)
